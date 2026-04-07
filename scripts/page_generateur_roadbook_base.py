# -*- coding: utf-8 -*-
"""
page_generateur_roadbook.py

Module Streamlit pour LCDMH.

Objectif :
- lire un export CSV Kurviger ligne à ligne ;
- considérer ⚐ comme le départ initial ;
- considérer Ⓥ comme une fin d'étape et une nuit sur place ;
- considérer Ⓢ comme un point de passage interne à la journée ;
- considérer ⚑ comme la fin du road trip si présent ;
- ignorer totalement les instructions de navigation (tournez à gauche, rond-point, etc.) ;
- construire les journées à partir de la logique métier ⚐ / Ⓥ / ⚑ ;
- générer un index HTML + une fiche HTML détaillée par jour.

La logique de calcul ne repose PAS sur des distances haversine approximatives.
Elle utilise directement les colonnes natives du CSV Kurviger :
- Distance totale
- Durée totale
ce qui garantit un kilométrage journalier fidèle à l'export.
"""

from __future__ import annotations

import csv
import html
import io
import os
import sys
import re
import zipfile
import tempfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    import streamlit as st
except Exception:  # pragma: no cover
    class _StreamlitFallback:
        def __getattr__(self, name):
            raise RuntimeError("Streamlit est requis pour utiliser page_generateur_roadbook().")
    st = _StreamlitFallback()

# ═══ Import du module d'enrichissement des questions *xxx ? ═══
try:
    import lcdmh_enrichissement_questions as questions_module
    QUESTIONS_MODULE_AVAILABLE = True
except ImportError:
    # Fallback : tenter de charger depuis le même dossier
    import importlib.util
    _questions_path = Path(__file__).resolve().parent / "lcdmh_enrichissement_questions.py"
    if _questions_path.exists():
        _spec = importlib.util.spec_from_file_location("lcdmh_enrichissement_questions", _questions_path)
        questions_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(questions_module)
        QUESTIONS_MODULE_AVAILABLE = True
    else:
        questions_module = None
        QUESTIONS_MODULE_AVAILABLE = False

# ═══ Import du module d'enrichissement web automatique ═══
try:
    import lcdmh_web_enrichment as web_enrichment
    WEB_ENRICHMENT_AVAILABLE = True
except ImportError:
    # Fallback : tenter de charger depuis le même dossier
    _web_enrich_path = Path(__file__).resolve().parent / "lcdmh_web_enrichment.py"
    if _web_enrich_path.exists():
        _spec2 = importlib.util.spec_from_file_location("lcdmh_web_enrichment", _web_enrich_path)
        web_enrichment = importlib.util.module_from_spec(_spec2)
        _spec2.loader.exec_module(web_enrichment)
        WEB_ENRICHMENT_AVAILABLE = True
    else:
        web_enrichment = None
        WEB_ENRICHMENT_AVAILABLE = False

# ═══ Import du Location Engine (fusion GPS .kurviger + reverse geocoding) ═══
try:
    import lcdmh_location_engine as location_engine
    LOCATION_ENGINE_AVAILABLE = True
except ImportError:
    _loc_engine_path = Path(__file__).resolve().parent / "lcdmh_location_engine.py"
    if _loc_engine_path.exists():
        _spec3 = importlib.util.spec_from_file_location("lcdmh_location_engine", _loc_engine_path)
        location_engine = importlib.util.module_from_spec(_spec3)
        _spec3.loader.exec_module(location_engine)
        LOCATION_ENGINE_AVAILABLE = True
    else:
        location_engine = None
        LOCATION_ENGINE_AVAILABLE = False

# ============================================================
# CONFIG
# ============================================================

UPLOAD_PHOTO_FILE = "https://lcdmh.com/LCDMH_Publication_v4_pin-yz.html"
DEFAULT_CONSO = 6.5
DEFAULT_UK_PRICE = 1.565
DEFAULT_IE_PRICE = 1.73

INFO_SYMBOLS = {"⚐", "Ⓥ", "Ⓢ"}
STAGE_SYMBOLS = {"⚐", "Ⓥ"}

BADGES = {
    "depart": ("Départ", "#22c55e"),
    "arrivee": ("Arrivée", "#3b82f6"),
    "etape": ("Étape", "#ea580c"),
    "passage": ("Passage", "#64748b"),
    "drone": ("Spot drone", "#8b5cf6"),
    "ferry": ("Ferry", "#0891b2"),
    "train": ("Train", "#2563eb"),
    "photo": ("Spot photo", "#0f766e"),
    "danger": ("Alerte", "#dc2626"),
    "logement": ("Nuit", "#f59e0b"),
    "base": ("Base / pause", "#7c3aed"),
}

# ============================================================
# OUTILS GÉNÉRAUX
# ============================================================


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def parse_int(value: Any) -> int:
    try:
        return int(str(value).strip().replace(" ", ""))
    except Exception:
        return 0


def format_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h{m:02d}"


_COORD_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)°\s*([+-]?\d+(?:\.\d+)?)°")


def extract_coords(text: str) -> Tuple[Optional[float], Optional[float]]:
    m = _COORD_RE.search(text or "")
    if not m:
        return None, None
    try:
        return float(m.group(1)), float(m.group(2))
    except Exception:
        return None, None


_DAY_RE = re.compile(r"\bJ\s*(\d{1,2})(?:\s*[-/]\s*(\d{1,2}))?\b", re.I)
_DATE_RANGE_RE = re.compile(r"\b(\d{1,2})-(\d{1,2})(?:/(\d{2}))?\b")
# Accepte : "Départ 4 mai 2026", "Départ le 4 mai 2026", "Départ du 4 mai 2026"
_START_DATE_RE = re.compile(r"\bDépart\s+(?:le\s+|du\s+)?(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\b", re.I)
_START_DATE_SLASH_RE = re.compile(r"\bDépart\s+(?:le\s+|du\s+)?(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", re.I)
_GENERIC_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_NIGHTS_RE = re.compile(r"(?<![A-Z0-9])N\s*(\d+)\b", re.I)

_MONTHS_FR = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}


@dataclass
class DayInfo:
    days: List[int] = field(default_factory=list)
    raw: Optional[str] = None


@dataclass
class DateInfo:
    arrival_day: Optional[int] = None
    departure_day: Optional[int] = None
    departure_month: Optional[str] = None
    raw: Optional[str] = None


@dataclass
class CsvPoint:
    row_num: int
    symbol: str
    description: str
    distance_m: int
    total_m: int
    duration_s: int
    total_s: int
    day_info: DayInfo
    date_info: DateInfo
    lat: Optional[float] = None
    lon: Optional[float] = None

    @property
    def is_stage(self) -> bool:
        return self.symbol == "Ⓥ"

    @property
    def is_start(self) -> bool:
        return self.symbol == "⚐"

    @property
    def is_info(self) -> bool:
        return self.symbol in INFO_SYMBOLS


# ============================================================
# PARSING JOUR / DATES / LIBELLÉS
# ============================================================


def parse_day_info(text: str) -> DayInfo:
    text = str(text or "")
    m = _DAY_RE.search(text)
    if not m:
        return DayInfo([], None)

    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else None
    if end is None:
        return DayInfo([start], m.group(0))
    if end >= start:
        return DayInfo(list(range(start, end + 1)), m.group(0))
    return DayInfo([start, end], m.group(0))



def _normalize_month_token(token: str) -> str:
    token = norm(token).lower()
    token = (
        token.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ä", "a")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ô", "o")
        .replace("ö", "o")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ü", "u")
        .replace("ç", "c")
    )
    return token


def _extract_date_from_text(text: str) -> Optional[date]:
    text = str(text or "")

    m = _START_DATE_RE.search(text)
    if m:
        day_num = int(m.group(1))
        month_name = _normalize_month_token(m.group(2))
        year_num = int(m.group(3))
        month_num = _MONTHS_FR.get(month_name)
        if month_num:
            try:
                return date(year_num, month_num, day_num)
            except ValueError:
                return None

    m = _START_DATE_SLASH_RE.search(text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None

    m = _GENERIC_DATE_RE.search(text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None

    return None


def parse_date_info(text: str) -> DateInfo:
    dt = _extract_date_from_text(text)
    if dt:
        return DateInfo(
            arrival_day=dt.day,
            departure_day=dt.day,
            departure_month=f"{dt.month:02d}",
            raw=dt.strftime("%d/%m/%Y"),
        )

    text = str(text or "")
    m = _DATE_RANGE_RE.search(text)
    if not m:
        return DateInfo()

    return DateInfo(
        arrival_day=int(m.group(1)),
        departure_day=int(m.group(2)),
        departure_month=m.group(3),
        raw=m.group(0),
    )


def cleanup_text(text: str) -> str:
    text = norm(text)
    text = text.replace('"', "")
    # ── Nettoyage métadonnées Kurviger (ne pas toucher au CSV) ──
    # Retirer prix_indicatif, alternatives_proches et variantes
    text = re.sub(r"\bprix[_ ]indicatif\b[^|]*", "", text, flags=re.I)
    text = re.sub(r"\balternatives?[_ ]proches?\b[^|]*", "", text, flags=re.I)
    # ── Convertir les marqueurs *question en texte lisible ──
    # Au lieu de supprimer, on transforme *point_de_vue → "Point de vue",
    # *panorama → "Panorama", etc. pour garder le sens dans la page questions
    _question_labels = {
        r"\*point_de_vue": "Point de vue",
        r"\*panorama": "Panorama",
        r"\*Highlands?\s*infos?": "Highlands infos",
        r"\*Bivouac\??\s*": "Bivouac ? ",
        r"\*Spot\s+Bivouac": "Spot Bivouac",
        r"\*couchage\s+option\s*\??": "Couchage option ?",
        r"\*autres_campings": "Autres campings",
        r"\*prix_camping": "Prix camping",
        r"\*prix_B&B": "Prix B&B",
        r"\*ferry_info": "Ferry info",
        r"\*shuttle\s*info": "Shuttle info",
        r"\*train\s+horaire": "Train horaire",
        r"\*intere[st]\s*\??": "Intérêt ?",
        r"\*visite\s*\??": "Visite ?",
        r"\*drone": "Drone",
        r"\*photo": "Photo",
    }
    for pattern, label in _question_labels.items():
        text = re.sub(pattern, label, text, flags=re.I)
    # Nettoyer les * restants non reconnus (garder le texte après)
    text = re.sub(r"\*\s*(\w)", r"\1", text)
    # Retirer les segments pipes Kurviger : | N2 | camping | bord de mer | …
    # On garde la partie avant le premier pipe si elle est significative
    if "|" in text:
        parts = [p.strip() for p in text.split("|")]
        # Filtrer les segments qui ressemblent à des métadonnées Kurviger
        _kurviger_meta_re = re.compile(
            r"^(N\d+|camping|bord de mer|sauvage|parking|gratuit|payant|"
            r"prix[_ ]indicatif|alternatives?[_ ]proches?|bivouac|"
            r"\d+[.,]?\d*\s*[€£]|montagne|forêt|lac|plage|village)$",
            re.I,
        )
        cleaned_parts = [p for p in parts if p and not _kurviger_meta_re.match(p)]
        text = " - ".join(cleaned_parts) if cleaned_parts else parts[0] if parts else text
    # ── Fin nettoyage Kurviger ──
    text = _START_DATE_RE.sub("", text)
    text = _START_DATE_SLASH_RE.sub("", text)
    text = _GENERIC_DATE_RE.sub("", text)
    text = re.sub(r"\bJ\s*\d{1,2}(?:\s*[-/]\s*\d{1,2})?\b", "", text, flags=re.I)
    text = _COORD_RE.sub("", text)
    text = re.sub(r"\s*[-–—]\s*", " - ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_,;|")

    fixes = {
        "s13hared": "shared",
        "Déport d'Edinbourg": "Départ d'Édimbourg",
        "Deport d'Edinbourg": "Départ d'Édimbourg",
    }
    for wrong, right in fixes.items():
        text = text.replace(wrong, right)

    return text or "Point du parcours"


def split_title_note(text: str) -> Tuple[str, str]:
    clean = cleanup_text(text)
    if not clean:
        return "Point du parcours", ""

    parts = [p.strip(" -_,;") for p in re.split(r"\s*\|\s*", clean) if p.strip(" -_,;")]
    title = ""
    note_parts: List[str] = []

    if len(parts) > 1:
        title = parts[0]
        note_parts = parts[1:]
    else:
        hy_parts = [p.strip() for p in re.split(r"\s+-\s+", clean) if p.strip()]
        generic_prefix_re = re.compile(r"^(Couchage|Hébergement|Hebergement|A réserver|A reserver|Prévoir|Prevoir)\b", re.I)
        if len(hy_parts) == 2 and generic_prefix_re.match(hy_parts[0]):
            title = hy_parts[1]
        elif len(hy_parts) >= 3:
            title = " - ".join(hy_parts[:2])
            note_parts = hy_parts[2:]
        else:
            title = clean

    title = re.sub(r"\bN\s*\d+\b", "", title, flags=re.I)
    title = re.sub(r"^(Couchage|Hébergement|Hebergement|A réserver|A reserver|Prévoir|Prevoir)\s+", "", title, flags=re.I)
    title = norm(title).strip(" -_,;|")

    cleaned_notes = []
    for p in note_parts:
        if re.fullmatch(r"N\s*\d+", p, flags=re.I):
            continue
        p = norm(p).strip(" -_,;|")
        if p:
            cleaned_notes.append(p)

    note = " · ".join(cleaned_notes)
    return title or clean, note

def point_label(point: CsvPoint) -> str:
    title, _ = split_title_note(point.description)
    return title



def point_note(point: CsvPoint) -> str:
    _, note = split_title_note(point.description)
    return note



def complete_display_date(point: CsvPoint, current_month: str) -> str:
    info = point.date_info
    month = info.departure_month or current_month or "05"
    if info.departure_month:
        current_month = info.departure_month
    if info.departure_day is None:
        return ""
    return f"{int(info.departure_day):02d}/{month}"


# ============================================================
# ENRICHISSEMENT HISTOIRE / GÉOLOGIE / RÉGION
# ============================================================

_RUNTIME_HELPERS: Optional[Dict[str, Any]] = None

_REGION_RULES = [
    (["fortrose", "cromarty", "nigg"], "Black Isle"),
    (["dunnet", "thurso", "john o' groats"], "Caithness"),
    (["durness", "sango", "smoo"], "Sutherland Nord-Ouest"),
    (["stonehaven", "dunnottar"], "Aberdeenshire côtier"),
    (["blair castle", "pitlochry", "atholl"], "Perthshire / Atholl"),
    (["assynt", "clachtoll", "stoer", "knockan"], "Assynt"),
    (["skye", "sligachan", "storr", "neist"], "Île de Skye"),
    (["glenfinnan"], "Lochaber"),
    (["glencoe"], "Highlands de l’Ouest"),
    (["donegal"], "Donegal"),
    (["achill"], "Mayo / Achill"),
    (["renvyle", "connemara"], "Connemara"),
    (["galway"], "Comté de Galway"),
    (["burren", "poulnabrone"], "Burren"),
    (["loop head"], "Clare Ouest"),
    (["fishguard"], "Pembrokeshire"),
    (["stonehenge"], "Wiltshire"),
]

_GEOLOGY_RULES = [
    (["dunnottar", "stonehaven"], "Falaises de grès sur côte battue par la mer du Nord."),
    (["dunnet", "caithness", "john o' groats"], "Plateaux et falaises de grès exposés au vent."),
    (["durness", "sango"], "Falaises atlantiques et relief littoral très exposé du Nord-Ouest."),
    (["smoo", "grotte marine", "cascade intérieure"], "Grottes marines et relief côtier entaillé, typiques d’un littoral très battu."),
    (["fortrose", "cromarty", "black isle"], "Relief côtier doux autour du Moray Firth, routes secondaires et terres anciennes."),
    (["blair castle", "atholl", "pitlochry"], "Vallée intérieure des Highlands, relief glaciaire et versants boisés."),
    (["burren", "poulnabrone"], "Karst calcaire, dalles fissurées et relief tabulaire."),
    (["loop head"], "Falaises atlantiques et grès littoraux."),
    (["skye", "sligachan", "storr", "neist"], "Massif volcanique et relief très découpé."),
    (["glenfinnan", "glencoe", "gap of dunloe"], "Vallée glaciaire encaissée, relief de montagne et versants rocheux."),
]

_HISTORY_RULES = [
    (["blair castle"], "Blair Castle est lié aux ducs d’Atholl et à l’histoire des Highlands centraux."),
    (["dunnottar", "stonehaven"], "Dunnottar Castle occupe un promontoire fortifié spectaculaire et compte parmi les grands sites historiques de la côte est écossaise."),
    (["fortrose"], "Fortrose garde l’héritage d’un ancien bourg religieux du Black Isle."),
    (["cromarty", "nigg", "ferry"], "La traversée Cromarty–Nigg sert de liaison locale sur le Cromarty Firth."),
    (["dunnet head"], "Dunnet Head est un repère emblématique de l’extrême nord de la Grande-Bretagne."),
    (["sango", "durness"], "Durness et Sango sont des haltes majeures de la côte nord-ouest écossaise, tournées vers l’Atlantique."),
    (["smoo", "grotte marine"], "Les grandes grottes marines du nord-ouest écossais sont depuis longtemps des étapes marquantes pour les voyageurs."),
    (["stonehenge"], "Stonehenge est un monument néolithique majeur. Sa fonction exacte reste débattue."),
    (["poulnabrone"], "Poulnabrone est une tombe mégalithique du Néolithique, emblématique du Burren."),
    (["dunrobin"], "Dunrobin est lié aux ducs de Sutherland et reste un grand repère historique du Nord."),
    (["eilean donan"], "Eilean Donan est l’un des châteaux les plus photographiés d’Écosse."),
    (["glenfinnan"], "Glenfinnan est lié au soulèvement jacobite de 1745."),
    (["donegal"], "Donegal garde l’empreinte des seigneuries gaéliques. Le château en est un symbole."),
    (["galway"], "Galway fut un grand port de l’Ouest irlandais. Son centre reste très vivant."),
    (["fishguard"], "Fishguard est un vieux port gallois et un point charnière vers l’Irlande."),
]

_GENERIC_LABEL_RE = re.compile(r"^(étape\s*\d+|point du parcours|pause|arrêt)$", re.I)


def _get_runtime_helpers() -> Dict[str, Any]:
    global _RUNTIME_HELPERS
    if _RUNTIME_HELPERS is not None:
        return _RUNTIME_HELPERS

    helper_names = [
        "recherche_wikipedia_cascade",
        "obtenir_geologie",
        "obtenir_meteo_historique",
        "appeler_gemini",
        "extraire_sections_multiligne",
        "charger_cle_api",
    ]
    helpers: Dict[str, Any] = {}
    for mod_name, mod in list(sys.modules.items()):
        if mod_name not in {"__main__", "app"} and not mod_name.endswith(".app"):
            continue
        for name in helper_names:
            if not helpers.get(name):
                helpers[name] = getattr(mod, name, None)

    _RUNTIME_HELPERS = helpers
    return helpers


def _resolve_helper(name: str, fallback: Any = None) -> Any:
    return _get_runtime_helpers().get(name) or fallback


def _resolve_gemini_key() -> str:
    helper = _get_runtime_helpers().get("charger_cle_api")
    if callable(helper):
        try:
            return helper() or ""
        except Exception:
            return ""
    return ""


def _first_sentence(text: str, max_len: int = 220) -> str:
    txt = norm(text)
    if not txt:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", txt)
    candidate = parts[0].strip() if parts else txt
    if len(candidate) <= max_len:
        return candidate
    cut = txt[:max_len].rfind(" ")
    return txt[: cut if cut > 80 else max_len].rstrip(" ,;:") + "…"


def _normalize_heading_text(s: str) -> str:
    s = norm(s)
    s = re.sub(r"^[#\-*\s]+", "", s)
    return s


def _extraire_sections_multiligne_local(brief: str) -> Dict[str, str]:
    out = {
        "histoire": "",
        "anecdote": "",
        "geologie": "",
        "specialite": "",
        "a_ne_pas_rater": "",
        "conseil_route": "",
        "meteo": "",
    }
    brief = str(brief or "").replace("\r\n", "\n").replace("\r", "\n")
    if not brief.strip():
        return out
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in brief.split("\n") if l.strip()]

    def detect_key(line: str) -> Optional[str]:
        u = line.upper()
        if ("HISTOIRE" in u) or ("🏛️" in line):
            return "histoire"
        if ("ANECDOTE" in u) or ("ANÉCDOTE" in u) or ("🎭" in line) or ("LÉGENDE" in u) or ("LEGENDE" in u):
            return "anecdote"
        if ("GÉOLOGIE" in u) or ("GEOLOGIE" in u) or ("PAYSAGE" in u) or ("⛰️" in line) or ("🧭" in line):
            return "geologie"
        if ("SPÉCIALIT" in u) or ("SPECIALIT" in u) or ("🍽️" in line):
            return "specialite"
        if ("À NE PAS RATER" in u) or ("A NE PAS RATER" in u) or ("INCONTOURNABLE" in u) or ("📍" in line):
            return "a_ne_pas_rater"
        if ("CONSEIL" in u) or ("ROUTE" in u) or ("🏍️" in line) or ("⚠️" in line):
            return "conseil_route"
        if ("MÉTÉO" in u) or ("METEO" in u) or ("🌤" in line):
            return "meteo"
        return None

    current = None
    for line in lines:
        key = detect_key(line)
        if key:
            current = key
            clean = re.sub(r"^[^—:]+[—:]\s*", "", _normalize_heading_text(line))
            if clean and clean != line:
                out[key] = clean.strip()
            continue
        if current:
            out[current] = (out[current] + " " + line).strip()
    return out


def _infer_practical_text(kind: str, label: str, raw_text: str) -> str:
    text = f"{label} {raw_text}".lower()
    if kind == "ferry" or "ferry" in text:
        return "Vérifie l’horaire du jour et présente-toi en avance à l’embarquement."
    if kind == "train" or "viaduc" in text or "train" in text:
        return "Anticipe l’horaire de passage et garde une marge pour te placer."
    if kind == "drone" or "drone" in text:
        return "Contrôle le vent, les restrictions locales et la zone de décollage avant de sortir le drone."
    if "camping" in text or "campsite" in text or "hotel" in text or "hôtel" in text or "guest house" in text or "b&b" in text:
        return "Pense au check-in et au ravitaillement avant la fermeture."
    if "bivouac" in text:
        return "Repère le terrain en avance et garde une solution de repli."
    if "castle" in text or "château" in text or "dolmen" in text:
        return "Vise tôt ou tard pour la lumière et un site plus calme."
    return "Fais un point carburant, météo et lumière avant de repartir."


def _clean_place_query(text: str) -> str:
    text = cleanup_text(text)
    text = re.sub(r"\b\d{1,2}\s*h\s*/\s*\d{1,2}\s*h\b", "", text, flags=re.I)
    text = re.sub(r"\bfr[eé]quence\b.*", "", text, flags=re.I)
    text = re.sub(r"\bvisite gratuite\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -·,;")
    return text


def _candidate_queries(point: CsvPoint) -> List[str]:
    label = point_label(point)
    note = point_note(point)
    desc = cleanup_text(point.description)
    country = infer_country(point)
    candidates: List[str] = []

    def add(q: str) -> None:
        q = _clean_place_query(q)
        if not q:
            return
        if q.lower() not in [c.lower() for c in candidates]:
            candidates.append(q)

    if label and not _GENERIC_LABEL_RE.match(label):
        add(label)
    if label and note and not _GENERIC_LABEL_RE.match(label):
        add(f"{label} {note}")
    if note and len(note) > 6:
        add(note)

    text = f"{label} {note} {desc}".lower()
    if "ferry" in text and "cromarty" in text and "nigg" in text:
        add("Cromarty Nigg ferry")
    if "dunnottar" in text:
        add("Dunnottar Castle Stonehaven")
    if "sango" in text:
        add("Sango Sands Durness")
    if "dunnet" in text:
        add("Dunnet Head")
    if "blair castle" in text:
        add("Blair Castle Pitlochry")
    if country:
        add(f"{label} {country}")
    return candidates[:5]


def _country_to_countrycodes(country_hint: str) -> str:
    hint = norm(country_hint).lower()
    if "irland" in hint and "nord" not in hint:
        return "ie"
    return "gb,ie"


def _forward_geocode_local(query: str, country_hint: str = "") -> Tuple[Optional[float], Optional[float]]:
    if not requests or not query:
        return None, None
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 0,
                "accept-language": "fr",
                "countrycodes": _country_to_countrycodes(country_hint),
            },
            headers={"User-Agent": "lcdmh-roadbook/1.0"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json() or []
        if not data:
            return None, None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None, None


def _infer_region_from_text(text: str, country: str) -> str:
    t = norm(text).lower()
    for keys, value in _REGION_RULES:
        if any(k in t for k in keys):
            return value
    if "irlande" in norm(country).lower():
        return "Irlande"
    return ""


def _infer_geology_from_text(text: str, country: str, region: str) -> str:
    t = norm(text).lower()
    for keys, value in _GEOLOGY_RULES:
        if any(k in t for k in keys):
            return value
    if "assynt" in norm(region).lower():
        return "Socle ancien avec reliefs isolés sur tourbières."
    if "irlande" in norm(country).lower():
        return "Relief atlantique mixte, plateaux, vallées humides et côte battue."
    return "Relief routier varié, typé secondaire / mixte."


def _infer_history_from_text(text: str) -> str:
    t = norm(text).lower()
    for keys, value in _HISTORY_RULES:
        if any(k in t for k in keys):
            return value
    return ""


def _build_item_links(item: Dict[str, Any]) -> str:
    links: List[Tuple[str, str]] = []
    lat = item.get("lat")
    lon = item.get("lon")
    label = item.get("label") or "Point du parcours"
    raw = item.get("raw") or ""
    note = item.get("note") or ""

    if lat is not None and lon is not None:
        links.append(("Maps", f"https://www.google.com/maps?q={lat},{lon}"))
    else:
        links.append(("Maps", f"https://www.google.com/search?q={quote_plus(label)}"))
    links.append(("Recherche", f"https://www.google.com/search?q={quote_plus((label + ' ' + note).strip() or raw)}"))

    lower = f"{label} {note} {raw}".lower()
    if "ferry" in lower:
        links.append(("Horaires ferry", f"https://www.google.com/search?q={quote_plus(label + ' ferry horaires officiel')}"))
    if "train" in lower or "viaduc" in lower:
        links.append(("Horaires train", f"https://www.google.com/search?q={quote_plus(label + ' train horaires officiel')}"))

    for title, url in (item.get("wiki_links") or [])[:2]:
        links.append((title or "Wikipedia", url))

    parts = []
    seen = set()
    for label_txt, url in links:
        if not url or url in seen:
            continue
        seen.add(url)
        parts.append(f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(label_txt)}</a>')
    return " · ".join(parts)


def _date_iso_from_day_display(day_display: str, trip_year: int) -> Optional[str]:
    m = re.match(r"^(\d{2})/(\d{2})$", str(day_display or "").strip())
    if not m:
        return None
    day = int(m.group(1))
    month = int(m.group(2))
    return f"{trip_year:04d}-{month:02d}-{day:02d}"


def _format_meteo_short(meteo: Optional[Dict[str, Any]]) -> str:
    if not meteo:
        return ""
    parts = []
    if meteo.get("temp_min") is not None and meteo.get("temp_max") is not None:
        parts.append(f"{meteo['temp_min']:.0f}°C → {meteo['temp_max']:.0f}°C")
    if meteo.get("precipitation") is not None:
        parts.append(f"pluie {meteo['precipitation']:.1f} mm")
    if meteo.get("vent_max") is not None:
        parts.append(f"vent {meteo['vent_max']:.0f} km/h")
    return " · ".join(parts)


def enrich_timeline_item(
    item: Dict[str, Any],
    day_date: str,
    trip_year: int,
    use_online: bool,
    use_gemini: bool,
    gemini_key: str,
    cache: Dict[Tuple[Any, ...], Dict[str, Any]],
) -> None:
    point: Optional[CsvPoint] = item.get("point_obj")
    if point is None:
        return

    cache_key = (point.row_num, day_date, bool(use_online), bool(use_gemini and gemini_key))
    if cache_key in cache:
        item.update(cache[cache_key])
        item["links_html"] = _build_item_links(item)
        return

    text_all = " ".join([item.get("label") or "", item.get("note") or "", item.get("raw") or ""]).strip()
    country = item.get("country") or infer_country(point)
    lat = item.get("lat")
    lon = item.get("lon")
    region = _infer_region_from_text(text_all, country)
    wiki_links: List[Tuple[str, str]] = []
    wiki_data: Dict[str, Dict[str, str]] = {}

    if (lat is None or lon is None) and use_online:
        for query in _candidate_queries(point):
            lat_try, lon_try = _forward_geocode_local(query, country)
            if lat_try is not None and lon_try is not None:
                lat, lon = lat_try, lon_try
                break

    recherche_wikipedia_cascade = _resolve_helper("recherche_wikipedia_cascade", None)
    if use_online and callable(recherche_wikipedia_cascade):
        try:
            ville = item.get("label") or "Point du parcours"
            wiki_data = recherche_wikipedia_cascade(ville, region, country) or {}
        except Exception:
            wiki_data = {}
    for _, w in (wiki_data or {}).items():
        if isinstance(w, dict) and w.get("url"):
            wiki_links.append((w.get("title") or "Wikipedia", w["url"]))

    obtenir_geologie = _resolve_helper("obtenir_geologie", None)
    type_sol = desc_geo = None
    if callable(obtenir_geologie):
        try:
            type_sol, desc_geo = obtenir_geologie(item.get("label") or "", region, country)
        except Exception:
            type_sol = desc_geo = None

    meteo = None
    obtenir_meteo_historique = _resolve_helper("obtenir_meteo_historique", None)
    if use_online and callable(obtenir_meteo_historique) and lat is not None and lon is not None:
        try:
            date_iso = _date_iso_from_day_display(day_date, trip_year)
            if date_iso:
                meteo = obtenir_meteo_historique(lat, lon, date_iso)
        except Exception:
            meteo = None

    gemini_text = ""
    appeler_gemini = _resolve_helper("appeler_gemini", None)
    extraire_sections = _resolve_helper("extraire_sections_multiligne", _extraire_sections_multiligne_local)
    if use_gemini and gemini_key and callable(appeler_gemini):
        try:
            gemini_text, _ = appeler_gemini(
                gemini_key,
                item.get("label") or "",
                region,
                country,
                None,
                type_sol,
                wiki_data,
                meteo,
            )
        except Exception:
            gemini_text = ""

    sections = extraire_sections(gemini_text) if gemini_text and callable(extraire_sections) else _extraire_sections_multiligne_local(gemini_text or "")

    # ═══ PARSING DES QUESTIONS *xxx ? (V2 — avec GPS + location) ═══
    # Supporte les questions multiples séparées par | dans une même ligne CSV
    parsed_questions_list = []
    if QUESTIONS_MODULE_AVAILABLE and questions_module:
        raw_text = item.get("raw") or item.get("label") or ""
        # Détecter toute question *xxx ? dans le texte
        import re as _re_q
        _q_matches = _re_q.findall(r"\*[^?]+\?", raw_text)
        
        # Extraire le sujet contextuel (partie avant le premier * ou premier |)
        _context_subject = ""
        if "|" in raw_text:
            _parts = [p.strip() for p in raw_text.split("|")]
            for _p in _parts:
                if _p and not _p.strip().startswith("*") and not _re_q.match(r"^\s*N\d+\s*$", _p):
                    # Nettoyer le sujet : retirer prix, dates, etc.
                    _ctx = _re_q.sub(r"\s*-\s*\d+\s*[€£CHF]+.*$", "", _p).strip(" -|")
                    _ctx = _re_q.sub(r"\s*\d+\s*[€£CHF]+.*$", "", _ctx).strip(" -|")
                    if len(_ctx) > 2:
                        _context_subject = _ctx
                        break
        
        for _q_match in _q_matches:
            try:
                parsed_question = questions_module.parse_question(
                    _q_match.strip(), lat=lat, lon=lon,
                )
                if parsed_question:
                    # Si la question n'a pas de sujet propre, utiliser le contexte
                    if not parsed_question.subject or parsed_question.subject == _q_match.strip():
                        if _context_subject:
                            parsed_question.subject = _context_subject
                    
                    pq_data = {
                        "raw": parsed_question.raw_text,
                        "type": parsed_question.question_type.name if parsed_question.question_type else "UNKNOWN",
                        "subject": parsed_question.subject,
                        "actions": [a.name for a in parsed_question.actions] if parsed_question.actions else [],
                        "known_price": parsed_question.known_price,
                        "is_resolved": False,
                    }
                    
                    # ═══ ENRICHISSEMENT WEB V2 — avec reverse geocoding ═══
                    if WEB_ENRICHMENT_AVAILABLE and web_enrichment and use_online:
                        try:
                            resolved_location = None
                            if LOCATION_ENGINE_AVAILABLE and location_engine and lat is not None and lon is not None:
                                try:
                                    resolved_location = location_engine.reverse_geocode(lat, lon)
                                except Exception:
                                    pass

                            enrichment_result = web_enrichment.enrich_question(
                                parsed_question,
                                location=resolved_location,
                            )
                            if enrichment_result and enrichment_result.main_info:
                                pq_data["is_resolved"] = True
                                pq_data["enrichment"] = {
                                    "main_info": enrichment_result.main_info,
                                    "price_range": enrichment_result.price_range,
                                    "tips": enrichment_result.tips[:5] if enrichment_result.tips else [],
                                    "warnings": enrichment_result.warnings[:3] if enrichment_result.warnings else [],
                                    "links": [(t, u) for t, u in enrichment_result.links[:6]] if enrichment_result.links else [],
                                    "source": enrichment_result.source,
                                    "quality_score": enrichment_result.quality_score,
                                }
                            elif enrichment_result and enrichment_result.tips:
                                pq_data["enrichment"] = {
                                    "main_info": "",
                                    "price_range": "",
                                    "tips": enrichment_result.tips[:5],
                                    "warnings": [],
                                    "links": [(t, u) for t, u in enrichment_result.links[:6]] if enrichment_result.links else [],
                                    "source": enrichment_result.source,
                                    "quality_score": 0,
                                }
                        except Exception as e:
                            print(f"[ENRICHMENT] Erreur pour {parsed_question.subject}: {e}")
                    
                    parsed_questions_list.append(pq_data)
            except Exception:
                pass
    
    # Stocker la première question dans parsed_question (compatibilité)
    # ET toutes les questions dans parsed_questions (nouveau)
    if parsed_questions_list:
        item["parsed_question"] = parsed_questions_list[0]
        item["parsed_questions"] = parsed_questions_list

    item.update({
        "lat": lat,
        "lon": lon,
        "country": country,
        "region": region,
        "geology": sections.get("geologie") or (f"{type_sol} — {desc_geo}" if type_sol and desc_geo else "") or (type_sol or "") or _infer_geology_from_text(text_all, country, region),
        "history": sections.get("histoire") or _first_sentence((wiki_data.get("ville") or {}).get("extract", "")) or _first_sentence((wiki_data.get("region") or {}).get("extract", "")) or _infer_history_from_text(text_all),
        "anecdote": sections.get("anecdote") or "",
        "speciality": sections.get("specialite") or _first_sentence((wiki_data.get("gastronomie") or {}).get("extract", ""), 170),
        "must_see": sections.get("a_ne_pas_rater") or "",
        "advice": sections.get("conseil_route") or _infer_practical_text(item.get("kind") or "passage", item.get("label") or "", item.get("raw") or ""),
        "meteo": sections.get("meteo") or _format_meteo_short(meteo),
        "wiki_links": wiki_links,
    })
    item["links_html"] = _build_item_links(item)
    cache[cache_key] = {
        "lat": item["lat"],
        "lon": item["lon"],
        "country": item["country"],
        "region": item["region"],
        "geology": item["geology"],
        "history": item["history"],
        "anecdote": item["anecdote"],
        "speciality": item["speciality"],
        "must_see": item["must_see"],
        "advice": item["advice"],
        "meteo": item["meteo"],
        "wiki_links": item["wiki_links"],
        "links_html": item["links_html"],
    }


def enrich_days_data(
    days_data: List[Dict[str, Any]],
    trip_year: int,
    use_online: bool,
    use_gemini: bool,
    gemini_key: str,
) -> None:
    cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for day in days_data:
        for item in day.get("timeline", []):
            enrich_timeline_item(
                item=item,
                day_date=day.get("day_date") or "",
                trip_year=int(trip_year),
                use_online=bool(use_online),
                use_gemini=bool(use_gemini),
                gemini_key=gemini_key or "",
                cache=cache,
            )


# ============================================================
# LECTURE CSV
# ============================================================
# ============================================================
# LECTURE CSV
# ============================================================


def _clean_csv_header_name(name: Any) -> str:
    text = norm(name)
    text = text.lstrip("﻿").strip().strip('"').strip("'")
    text = re.sub(r"\s+", " ", text)
    return text


_CANONICAL_CSV_KEYS = {
    "symbole": "Symbole",
    "description": "Description",
    "distance": "Distance",
    "distance totale": "Distance totale",
    "durée": "Durée",
    "duree": "Durée",
    "durée totale": "Durée totale",
    "duree totale": "Durée totale",
}


def _canonicalize_csv_row(row: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in row.items():
        cleaned_key = _clean_csv_header_name(key)
        canonical = _CANONICAL_CSV_KEYS.get(cleaned_key.lower(), cleaned_key)
        cleaned[canonical] = value
    return cleaned


def _repair_kurviger_csv_text(text: str) -> str:
    if not text:
        return text
    lines = text.splitlines()
    if not lines:
        return text
    first = lines[0].lstrip("﻿")
    if first.startswith('Symbole","Description"'):
        lines[0] = '"' + first
    elif first.startswith('Symbole;"Description"'):
        lines[0] = '"' + first
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def load_csv(path: str) -> List[CsvPoint]:
    raw_text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    raw_text = _repair_kurviger_csv_text(raw_text)

    points: List[CsvPoint] = []
    reader = csv.DictReader(io.StringIO(raw_text))
    if reader.fieldnames:
        reader.fieldnames = [_CANONICAL_CSV_KEYS.get(_clean_csv_header_name(name).lower(), _clean_csv_header_name(name)) for name in reader.fieldnames]

    for idx, row in enumerate(reader, start=2):
        fixed_row = _canonicalize_csv_row(row)
        symbol = norm(fixed_row.get("Symbole"))
        desc = norm(fixed_row.get("Description"))
        lat, lon = extract_coords(desc)
        points.append(
            CsvPoint(
                row_num=idx,
                symbol=symbol,
                description=desc,
                distance_m=parse_int(fixed_row.get("Distance")),
                total_m=parse_int(fixed_row.get("Distance totale")),
                duration_s=parse_int(fixed_row.get("Durée")),
                total_s=parse_int(fixed_row.get("Durée totale")),
                day_info=parse_day_info(desc),
                date_info=parse_date_info(desc),
                lat=lat,
                lon=lon,
            )
        )
    return points


# ============================================================
# DÉCOUPAGE DES JOURNÉES
# ============================================================


def is_daily_anchor(point: CsvPoint) -> bool:
    return point.symbol in STAGE_SYMBOLS and bool(point.day_info.days)



def build_day_anchor_map(points: List[CsvPoint]) -> Tuple[Dict[int, CsvPoint], List[str]]:
    anchors: Dict[int, CsvPoint] = {}
    warnings: List[str] = []

    for p in points:
        if not is_daily_anchor(p):
            continue
        for d in p.day_info.days:
            if d not in anchors:
                anchors[d] = p
            else:
                warnings.append(
                    f"[doublon J{d:02d}] ancre conservée ligne {anchors[d].row_num}, doublon ignoré ligne {p.row_num} : {p.description}"
                )

    if anchors:
        all_days = sorted(anchors)
        for expected in range(all_days[0], all_days[-1] + 1):
            if expected not in anchors:
                warnings.append(f"[jour manquant] aucun point de départ explicite trouvé pour J{expected:02d}.")

    return anchors, warnings



def is_interesting_inside_day(point: CsvPoint) -> bool:
    return point.symbol == "Ⓢ"



def classify_point(point: CsvPoint, is_start: bool, is_end: bool) -> str:
    if is_start:
        return "depart"
    if is_end:
        return "arrivee"

    text = (point.description or "").lower()
    if point.symbol == "Ⓥ":
        return "etape"
    # Ferry : exiger *ferry_info ou "ferry" suivi de mots-clés transport
    # (évite le faux positif "Ferry Pools" = Fairy Pools)
    if "*ferry_info" in text or "shuttle" in text:
        return "ferry"
    if "ferry" in text and any(k in text for k in ["horaire", "info", "check-in", "réserv", "reserv", "billet", "traversée", "travers"]):
        return "ferry"
    if "train" in text or "viaduc" in text:
        return "train"
    if "drone" in text:
        return "drone"
    if "photo" in text:
        return "photo"
    if any(k in text for k in ["danger", "vent", "étroite", "etroite", "gravillon", "glissant"]):
        return "danger"
    if any(k in text for k in ["camping", "campsite", "hotel", "hôtel", "guest house", "b&b", "bivouac", "wigwam", "flat"]):
        return "logement"
    return "passage"



def border_color(kind: str) -> str:
    color = BADGES.get(kind, ("Info", "#cbd5e1"))[1]
    return color



def badge_html(kind: str) -> str:
    label, color = BADGES.get(kind, ("Info", "#64748b"))
    return (
        f'<span style="display:inline-block;padding:4px 10px;border-radius:999px;'
        f'font-size:12px;font-weight:bold;background:{color};color:white;">{esc(label)}</span>'
    )



def infer_country(point: CsvPoint) -> str:
    text = (point.description or "").lower()
    lat, lon = point.lat, point.lon

    # Mots-clés par pays
    _COUNTRY_KEYWORDS = {
        "Irlande": ["donegal", "achill", "galway", "connemara", "burren", "rosslare", "irlande", "ireland", "cork", "dublin", "kerry", "clare"],
        "Royaume-Uni": ["belfast", "causeway", "antrim", "giant's causeway", "malin head", "fishguard", "stonehenge", "écosse", "scotland", "angleterre", "england", "wales", "edinburgh", "glasgow", "inverness", "skye"],
        "Slovénie": ["slovenia", "slovénie", "slovenie", "ljubljana", "bled", "triglav", "piran", "koper", "postojna", "bovec", "maribor", "ptuj", "soca", "soča", "vrsic", "vršič"],
        "Italie": ["italia", "italie", "italy", "roma", "milano", "venezia", "firenze", "napoli", "dolomiti", "stelvio", "toscana", "sicilia", "sardegna"],
        "Autriche": ["austria", "autriche", "österreich", "wien", "salzburg", "innsbruck", "tirol", "tyrol", "grossglockner", "kärnten"],
        "France": ["france", "paris", "lyon", "marseille", "bretagne", "normandie", "alsace", "provence", "alpes", "corse", "verdon"],
        "Suisse": ["suisse", "switzerland", "schweiz", "bern", "zürich", "genève", "geneva", "lugano", "graubünden", "valais"],
        "Allemagne": ["germany", "allemagne", "deutschland", "berlin", "münchen", "munich", "hamburg", "schwarzwald", "bayern"],
        "Espagne": ["spain", "espagne", "españa", "madrid", "barcelona", "sevilla", "andalucia", "mallorca"],
        "Portugal": ["portugal", "lisboa", "porto", "algarve", "faro"],
        "Norvège": ["norway", "norvège", "norvege", "norge", "oslo", "bergen", "tromsø", "lofoten", "nordkapp"],
        "Croatie": ["croatia", "croatie", "hrvatska", "dubrovnik", "split", "zagreb", "plitvice"],
        "Grèce": ["greece", "grèce", "grece", "athènes", "athens", "santorini", "crete", "thessaloniki"],
        "Roumanie": ["romania", "roumanie", "românia", "bucharest", "transylvania", "brasov", "transfagarasan"],
    }

    for country, keywords in _COUNTRY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return country

    # Détection par GPS
    _COUNTRY_BBOX = {
        "Irlande": (51.3, -10.9, 55.6, -5.2),
        "Royaume-Uni": (49.8, -8.8, 59.0, 2.5),
        "France": (41.3, -5.2, 51.1, 9.6),
        "Slovénie": (45.4, 13.3, 46.9, 16.6),
        "Italie": (36.6, 6.6, 47.1, 18.5),
        "Autriche": (46.3, 9.5, 49.0, 17.2),
        "Suisse": (45.8, 5.9, 47.8, 10.5),
        "Allemagne": (47.2, 5.9, 55.1, 15.0),
        "Espagne": (36.0, -9.3, 43.8, 3.3),
        "Portugal": (36.9, -9.5, 42.2, -6.2),
        "Norvège": (57.9, 4.5, 71.2, 31.1),
        "Croatie": (42.4, 13.5, 46.6, 19.4),
        "Grèce": (34.8, 19.3, 41.8, 29.6),
        "Roumanie": (43.6, 20.3, 48.3, 29.7),
    }

    if lat is not None and lon is not None:
        for country, (lat_min, lon_min, lat_max, lon_max) in _COUNTRY_BBOX.items():
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return country

    return "Europe"



def infer_fuel_price(segment_points: List[CsvPoint], uk_price: float, ie_price: float, fuel_prices_by_country: dict = None) -> float:
    """Détermine le prix carburant moyen pondéré par pays sur un segment.
    
    Si fuel_prices_by_country est fourni (ex: {"France": 1.85, "Slovénie": 1.55}),
    calcule la moyenne pondérée par le nombre de points dans chaque pays.
    Sinon, fallback uk_price / ie_price.
    """
    if not segment_points:
        return ie_price
    
    # Compter les points par pays
    country_counts = {}
    for p in segment_points:
        country = infer_country(p)
        country_counts[country] = country_counts.get(country, 0) + 1
    
    # Si on a des prix par pays, calculer la moyenne pondérée
    if fuel_prices_by_country and country_counts:
        total_points = sum(country_counts.values())
        weighted_price = 0.0
        for country, count in country_counts.items():
            price = fuel_prices_by_country.get(country, ie_price)
            weighted_price += price * (count / total_points)
        return round(weighted_price, 3)
    
    # Fallback : UK vs reste
    uk_countries = {"Royaume-Uni"}
    uk_votes = sum(v for k, v in country_counts.items() if k in uk_countries)
    other_votes = sum(v for k, v in country_counts.items() if k not in uk_countries)
    return uk_price if uk_votes > other_votes else ie_price



def point_maps_link(point: CsvPoint) -> str:
    if point.lat is not None and point.lon is not None:
        return f"https://www.google.com/maps?q={point.lat},{point.lon}"
    q = quote_plus(point_label(point))
    return f"https://www.google.com/search?q={q}"



def build_useful_links(point: CsvPoint) -> List[Tuple[str, str]]:
    links: List[Tuple[str, str]] = []
    links.append(("Maps", point_maps_link(point)))

    text = point.description or ""
    label = point_label(point)
    q = quote_plus(label or text)
    links.append(("Recherche", f"https://www.google.com/search?q={q}"))

    lower = text.lower()
    if "ferry" in lower:
        qf = quote_plus(f"{label} ferry horaires officiel")
        links.append(("Horaires ferry", f"https://www.google.com/search?q={qf}"))
    if "train" in lower or "viaduc" in lower:
        qt = quote_plus(f"{label} train horaires officiel")
        links.append(("Horaires train", f"https://www.google.com/search?q={qt}"))
    if "shuttle" in lower or ("calais" in lower and "douvres" in lower):
        qs = quote_plus(f"{label} shuttle officiel")
        links.append(("Site shuttle", f"https://www.google.com/search?q={qs}"))

    # dédoublonnage simple
    dedup: List[Tuple[str, str]] = []
    seen = set()
    for item in links:
        if item[1] in seen:
            continue
        dedup.append(item)
        seen.add(item[1])
    return dedup



def format_links_html(point: CsvPoint) -> str:
    links = build_useful_links(point)
    if not links:
        return ""
    parts = []
    for label, url in links:
        parts.append(f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>')
    return " · ".join(parts)



def build_segment_timeline(start: CsvPoint, end: CsvPoint, segment_points: List[CsvPoint]) -> List[Dict[str, Any]]:
    info_points: List[CsvPoint] = []
    seen_rows = set()

    ordered = [start]
    for p in segment_points:
        if p.row_num == start.row_num:
            continue
        if p.row_num == end.row_num:
            continue
        if is_interesting_inside_day(p):
            ordered.append(p)
    if end.row_num != start.row_num:
        ordered.append(end)

    for p in ordered:
        if p.row_num in seen_rows:
            continue
        info_points.append(p)
        seen_rows.add(p.row_num)

    timeline: List[Dict[str, Any]] = []
    base_m = start.total_m
    base_s = start.total_s

    for idx, p in enumerate(info_points):
        is_start = idx == 0
        is_end = idx == len(info_points) - 1 and end.row_num != start.row_num
        kind = classify_point(p, is_start=is_start, is_end=is_end)
        km = max(0, round((p.total_m - base_m) / 1000.0))
        sec = max(0, p.total_s - base_s)

        timeline.append({
            "row_num": p.row_num,
            "symbol": p.symbol,
            "kind": kind,
            "label": point_label(p),
            "note": point_note(p),
            "raw": p.description,
            "km": km,
            "time": format_seconds(sec),
            "lat": p.lat,
            "lon": p.lon,
            "country": infer_country(p),
            "region": "",
            "geology": "",
            "history": "",
            "anecdote": "",
            "speciality": "",
            "must_see": "",
            "advice": _infer_practical_text(kind, point_label(p), p.description),
            "meteo": "",
            "wiki_links": [],
            "point_obj": p,
            "links_html": format_links_html(p),
        })

    if len(timeline) == 1:
        timeline[0]["kind"] = "base"

    return timeline



TRIP_BUSINESS_SYMBOLS = {"⚐", "Ⓢ", "Ⓥ", "⚑"}
DAY_END_SYMBOLS = {"Ⓥ", "⚑"}


def _parse_nights_count(text: str, default: int = 1) -> int:
    m = _NIGHTS_RE.search(str(text or ""))
    if not m:
        return max(0, int(default))
    try:
        return max(0, int(m.group(1)))
    except Exception:
        return max(0, int(default))


def _format_display_date(day_date: Optional[date]) -> str:
    if not day_date:
        return ""
    return day_date.strftime("%d/%m/%Y")


def _extract_trip_start_date(points: List[CsvPoint]) -> Tuple[Optional[date], List[str]]:
    warnings: List[str] = []
    starts = [p for p in points if p.symbol == "⚐"]
    if not starts:
        return None, ["Aucun point ⚐ trouvé dans le CSV."]
    if len(starts) > 1:
        warnings.append(f"[multi-départs] {len(starts)} points ⚐ trouvés ; seul le premier sera utilisé (ligne {starts[0].row_num}).")

    start_point = starts[0]
    start_date = _extract_date_from_text(start_point.description)
    if start_date is None:
        warnings.append(
            f"[date départ] date réelle introuvable sur le point ⚐ ligne {start_point.row_num}. "
            "Le découpage reste calculé correctement, mais les dates affichées resteront vides."
        )
    return start_date, warnings


def _build_business_segments(points: List[CsvPoint]) -> Tuple[List[Tuple[CsvPoint, CsvPoint, List[CsvPoint]]], List[str]]:
    warnings: List[str] = []
    relevant = [p for p in points if p.symbol in TRIP_BUSINESS_SYMBOLS]
    if not relevant:
        return [], ["Aucun point métier (⚐ Ⓢ Ⓥ ⚑) trouvé dans le CSV."]

    starts = [p for p in relevant if p.symbol == "⚐"]
    if not starts:
        return [], ["Aucun point ⚐ trouvé dans le CSV."]
    if len(starts) > 1:
        warnings.append(f"[multi-départs] {len(starts)} points ⚐ trouvés ; seul le premier sera utilisé.")

    current_start = starts[0]
    segments: List[Tuple[CsvPoint, CsvPoint, List[CsvPoint]]] = []

    while current_start is not None:
        next_end = None
        for p in relevant:
            if p.row_num <= current_start.row_num:
                continue
            if p.symbol in DAY_END_SYMBOLS:
                next_end = p
                break

        if next_end is None:
            warnings.append(
                f"[fin manquante] aucun point Ⓥ ou ⚑ trouvé après le point de départ ligne {current_start.row_num}."
            )
            break

        segment_points = [p for p in points if current_start.row_num <= p.row_num <= next_end.row_num]
        segments.append((current_start, next_end, segment_points))

        if next_end.symbol == "⚑":
            break
        current_start = next_end

    if not segments:
        warnings.append("Aucune journée exploitable n'a pu être construite depuis ⚐ / Ⓥ / ⚑.")

    return segments, warnings


def build_days(points: List[CsvPoint], conso_l_100: float, uk_price: float, ie_price: float, fuel_prices_by_country: dict = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []

    start_date, start_warnings = _extract_trip_start_date(points)
    warnings.extend(start_warnings)

    segments, segment_warnings = _build_business_segments(points)
    warnings.extend(segment_warnings)

    if not segments:
        return [], warnings

    days_data: List[Dict[str, Any]] = []
    current_date = start_date

    for idx, (start, end, segment_points) in enumerate(segments, start=1):
        timeline = build_segment_timeline(start, end, segment_points)

        raw_km = end.total_m - start.total_m
        raw_sec = end.total_s - start.total_s

        if raw_km < 0:
            warnings.append(
                f"[distance négative] J{idx:02d} a une distance totale incohérente "
                f"(ligne départ {start.row_num} -> ligne arrivée {end.row_num})."
            )
        if raw_sec < 0:
            warnings.append(
                f"[durée négative] J{idx:02d} a une durée totale incohérente "
                f"(ligne départ {start.row_num} -> ligne arrivée {end.row_num})."
            )

        km_total = max(0, round(raw_km / 1000.0))
        sec_total = max(0, raw_sec)

        if end.row_num != start.row_num and km_total == 0:
            warnings.append(
                f"[km nul] J{idx:02d} couvre plusieurs lignes ({start.row_num}->{end.row_num}) "
                "mais le calcul aboutit à 0 km."
            )

        fuel_price = infer_fuel_price(segment_points, uk_price=uk_price, ie_price=ie_price, fuel_prices_by_country=fuel_prices_by_country)
        fuel_cost = round((km_total / 100.0) * conso_l_100 * fuel_price, 2)

        nights_after_end = _parse_nights_count(end.description, default=1 if end.symbol == "Ⓥ" else 0)

        days_data.append({
            "day_num": idx,
            "day_date": _format_display_date(current_date),
            "start_stage": start,
            "end_stage": end,
            "timeline": timeline,
            "km_total": km_total,
            "route_time": format_seconds(sec_total),
            "fuel_price_eur": fuel_price,
            "fuel_cost_eur": fuel_cost,
            "conso_l_100": conso_l_100,
            "segment_points_count": len(segment_points),
            "is_pause_day": start.row_num == end.row_num,
            "nights_after_end": nights_after_end,
            "start_symbol": start.symbol,
            "end_symbol": end.symbol,
        })

        if current_date is not None and end.symbol == "Ⓥ":
            current_date = current_date + timedelta(days=max(1, nights_after_end))
        elif current_date is not None and end.symbol == "⚑":
            current_date = None

    return days_data, warnings


# ============================================================
# HTML
# ============================================================


def comment_widget_script(day_num: int) -> str:
    key = f"roadbook_comment_J{day_num:02d}"
    return f"""
<script>
(function() {{
    const storageKey = "{key}";
    const textarea = document.getElementById("commentaire-jour");
    const status = document.getElementById("commentaire-status");
    const btnSave = document.getElementById("btn-save-comment");
    const btnClear = document.getElementById("btn-clear-comment");
    const btnMic = document.getElementById("btn-mic-comment");

    function setStatus(msg) {{
        if (status) status.textContent = msg;
    }}

    function loadComment() {{
        const saved = localStorage.getItem(storageKey);
        if (saved && textarea) {{
            textarea.value = saved;
            setStatus("Commentaire rechargé depuis cet appareil.");
        }}
    }}

    function saveComment() {{
        if (!textarea) return;
        localStorage.setItem(storageKey, textarea.value || "");
        setStatus("Commentaire enregistré sur cet appareil.");
    }}

    function clearComment() {{
        if (!textarea) return;
        textarea.value = "";
        localStorage.removeItem(storageKey);
        setStatus("Commentaire effacé sur cet appareil.");
    }}

    if (btnSave) btnSave.addEventListener("click", saveComment);
    if (btnClear) btnClear.addEventListener("click", clearComment);

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {{
        if (btnMic) {{
            btnMic.disabled = true;
            btnMic.title = "Reconnaissance vocale non supportée par ce navigateur";
        }}
        setStatus("Micro non supporté par ce navigateur.");
    }} else {{
        const recognition = new SpeechRecognition();
        recognition.lang = "fr-FR";
        recognition.interimResults = false;
        recognition.continuous = false;

        if (btnMic) {{
            btnMic.addEventListener("click", function() {{
                setStatus("Écoute en cours...");
                recognition.start();
            }});
        }}

        recognition.onresult = function(event) {{
            const text = event.results[0][0].transcript;
            if (textarea) {{
                if (textarea.value && !textarea.value.endsWith(" ")) {{
                    textarea.value += " ";
                }}
                textarea.value += text;
            }}
            saveComment();
            setStatus("Texte dicté et enregistré.");
        }};

        recognition.onerror = function() {{
            setStatus("Erreur micro ou dictée interrompue.");
        }};

        recognition.onend = function() {{
            if ((textarea && textarea.value) || localStorage.getItem(storageKey)) {{
                setStatus("Prêt.");
            }}
        }};
    }}

    loadComment();
}})();
</script>
"""



def base_css() -> str:
    return """
<style>
body {
    margin:0;
    background:#e5e7eb;
    font-family:Arial, Helvetica, sans-serif;
    color:#0f172a;
    font-size:17px;
}
.wrapper {
    max-width:1360px;
    margin:24px auto;
    background:#ffffff;
    border-radius:24px;
    overflow:hidden;
    box-shadow:0 10px 35px rgba(0,0,0,.08);
}
.header {
    background:#172554;
    color:white;
    padding:26px 30px;
    border-bottom:4px solid #f97316;
}
.top-header-actions, .top-actions {
    display:flex;
    gap:12px;
    margin-top:14px;
    flex-wrap:wrap;
}
.top-btn {
    display:inline-block;
    background:#24324f;
    color:#fff;
    text-decoration:none;
    padding:10px 16px;
    border-radius:999px;
    font-weight:bold;
    font-size:14px;
}
.top-metrics {
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:16px;
    padding:24px 28px 12px 28px;
}
.metric {
    background:#f8fafc;
    border:1px solid #cbd5e1;
    border-radius:14px;
    padding:16px;
    text-align:center;
}
.metric .big {
    font-size:20px;
    font-weight:bold;
    color:#ea580c;
}
.info-box {
    margin:8px 28px 16px 28px;
    background:#f8fafc;
    border:1px solid #cbd5e1;
    border-left:4px solid #f97316;
    border-radius:14px;
    padding:18px;
}
.legend {
    margin:0 0 10px 0;
    padding:14px 28px;
    border-top:1px solid #cbd5e1;
    border-bottom:1px solid #cbd5e1;
    background:#fff;
}
.content {
    padding:18px 28px 8px 28px;
}
.comment-box {
    margin:0 28px 24px 28px;
    background:#f8fafc;
    border:1px solid #cbd5e1;
    border-radius:16px;
    padding:18px;
}
.comment-box textarea {
    width:100%;
    min-height:140px;
    border:1px solid #cbd5e1;
    border-radius:12px;
    padding:12px;
    font-family:Arial, Helvetica, sans-serif;
    font-size:17px;
    resize:vertical;
    box-sizing:border-box;
}
.comment-actions {
    display:flex;
    gap:12px;
    flex-wrap:wrap;
    margin-top:12px;
}
.comment-btn {
    border:none;
    background:#172554;
    color:#fff;
    padding:10px 16px;
    border-radius:999px;
    cursor:pointer;
    font-weight:bold;
}
.comment-btn.secondary { background:#64748b; }
.comment-btn.mic { background:#ea580c; }
.footer-nav {
    display:flex;
    justify-content:space-between;
    padding:0 28px 24px 28px;
    gap:12px;
}
small.meta {
    color:#64748b;
    display:block;
    margin-top:6px;
}
.status {
    margin-top:10px;
    color:#64748b;
    font-size:14px;
}
.grid {
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(360px,1fr));
    gap:16px;
    padding:24px 28px 28px 28px;
}
@media (max-width:900px) {
    .top-metrics { grid-template-columns:repeat(2,1fr); }
}
</style>
"""



def photo_upload_href(from_day_page: bool = False) -> str:
    target = norm(UPLOAD_PHOTO_FILE) or "https://lcdmh.com/LCDMH_Publication_v4_pin-yz.html"
    if re.match(r"^[a-z]+://", target, flags=re.I):
        return target
    return f"../{target}" if from_day_page else target

def generate_day_html(day_data: Dict[str, Any], prev_day: Optional[int], next_day: Optional[int]) -> str:
    tl = day_data["timeline"]
    day = day_data["day_num"]
    day_date = day_data["day_date"] or "Date à vérifier"
    km_total = day_data["km_total"]
    route_time = day_data["route_time"]
    fuel = day_data["fuel_cost_eur"]

    depart = point_label(day_data["start_stage"])
    arrivee = point_label(day_data["end_stage"]) if not day_data["is_pause_day"] else depart
    start_raw = norm(day_data["start_stage"].description)
    end_raw = norm(day_data["end_stage"].description)

    highlight_lines = []
    for item in tl:
        if item["kind"] in {"drone", "ferry", "train", "photo", "danger"}:
            highlight_lines.append(
                f"<li><strong>{esc(item['label'])}</strong> — {esc(item['kind'].replace('_', ' '))}</li>"
            )
    if not highlight_lines and day_data["is_pause_day"]:
        highlight_lines.append("<li><strong>Journée base</strong> — aucune nouvelle étape journalière détectée avant le lendemain.</li>")

    rows = []
    for item in tl:
        note_html = f'<p style="margin:8px 0 8px;color:#334155;">{esc(item["note"] or item["raw"])}</p>' if (item["note"] or item["raw"]) else ""
        coords_html = ""
        if item["lat"] is not None and item["lon"] is not None:
            coords_html = f'{item["lat"]:.6f}, {item["lon"]:.6f} · '

        extra_lines = []
        if item.get("region"):
            extra_lines.append(f'<p style="margin:10px 0 6px;color:#334155;"><strong>Région :</strong> {esc(item["region"])}</p>')
        if item.get("geology"):
            extra_lines.append(f'<p style="margin:0 0 6px;color:#334155;"><strong>Géologie :</strong> {esc(item["geology"])}</p>')
        if item.get("history"):
            extra_lines.append(f'<p style="margin:0 0 6px;color:#334155;"><strong>Histoire :</strong> {esc(item["history"])}</p>')
        if item.get("anecdote"):
            extra_lines.append(f'<p style="margin:0 0 6px;color:#334155;"><strong>Anecdote :</strong> {esc(item["anecdote"])}</p>')
        if item.get("speciality"):
            extra_lines.append(f'<p style="margin:0 0 6px;color:#334155;"><strong>Spécialité :</strong> {esc(item["speciality"])}</p>')
        if item.get("must_see"):
            extra_lines.append(f'<p style="margin:0 0 6px;color:#334155;"><strong>À ne pas rater :</strong> {esc(item["must_see"])}</p>')
        if item.get("meteo"):
            extra_lines.append(f'<p style="margin:0 0 6px;color:#334155;"><strong>Météo repère :</strong> {esc(item["meteo"])}</p>')
        if item.get("advice"):
            extra_lines.append(f'<p style="margin:0 0 8px;color:#334155;"><strong>Conseil :</strong> {esc(item["advice"])}</p>')

        # ═══ AFFICHAGE INLINE DES ENRICHISSEMENTS *xxx ? (MODULE DÉPLIABLE) ═══
        pq = item.get("parsed_question")
        if pq:
            enrichment = pq.get("enrichment", {})
            is_resolved = pq.get("is_resolved", False)
            q_type = pq.get("type", "UNKNOWN")
            q_subject = pq.get("subject", "")
            
            # Icône selon le type
            q_icons = {
                "VISITE": "🏛️", "BIVOUAC": "⛺", "CAMPING": "🏕️", "HOTEL": "🏨",
                "FERRY": "⛴️", "SHUTTLE": "🚂", "DRONE": "🎥", "PRIX": "💰",
                "INFO": "ℹ️", "VIEWPOINT": "👁️", "INTERET": "📍", "COUCHAGE": "🛏️"
            }
            q_icon = q_icons.get(q_type, "❓")
            
            # Construire le contenu enrichi (sera dans le module dépliable)
            has_enrichment_content = False
            enrichment_content = ""
            
            if is_resolved and enrichment.get("main_info"):
                has_enrichment_content = True
                # Contenu pour question résolue
                enrichment_content += f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px;"><span style="font-size:18px;">{q_icon}</span><strong style="color:#166534;">✅ {esc(enrichment.get("main_info", ""))}</strong></div>'
                if enrichment.get("price_range"):
                    enrichment_content += f'<div style="color:#15803d;font-weight:bold;font-size:1.1rem;margin-top:6px;">💰 {esc(enrichment["price_range"])}</div>'
                if enrichment.get("tips"):
                    tips_txt = " · ".join(enrichment["tips"][:3])
                    enrichment_content += f'<div style="font-size:13px;color:#334155;margin-top:6px;">{esc(tips_txt)}</div>'
                if enrichment.get("warnings"):
                    for w in enrichment["warnings"][:2]:
                        enrichment_content += f'<div style="color:#dc2626;font-size:13px;margin-top:4px;">⚠️ {esc(w)}</div>'
                if enrichment.get("links"):
                    links_html = " ".join([f'<a href="{u}" target="_blank" style="display:inline-block;padding:4px 10px;background:#dcfce7;color:#166534;border-radius:6px;font-size:12px;text-decoration:none;margin-right:6px;">{esc(t)}</a>' for t, u in enrichment["links"][:3]])
                    enrichment_content += f'<div style="margin-top:8px;">{links_html}</div>'
                if enrichment.get("source"):
                    enrichment_content += f'<div style="font-size:10px;color:#999;margin-top:8px;">📍 Source: {esc(enrichment["source"])}</div>'
                
                # Module dépliable VERT (résolu)
                summary_text = f"✅ Infos enrichies : {esc(enrichment.get('main_info', q_subject)[:50])}"
                enrich_html = f'''
                <details style="margin:10px 0;background:#f0fdf4;border:1px solid #86efac;border-left:4px solid #22c55e;border-radius:8px;overflow:hidden;">
                    <summary style="padding:12px;cursor:pointer;font-weight:bold;color:#166534;list-style:none;display:flex;align-items:center;gap:8px;">
                        <span style="transition:transform 0.2s;">▶</span> {summary_text}
                    </summary>
                    <div style="padding:0 12px 12px 12px;border-top:1px solid #86efac;">
                        {enrichment_content}
                    </div>
                </details>'''
                extra_lines.append(enrich_html)
                
            elif enrichment.get("tips") or enrichment.get("links"):
                has_enrichment_content = True
                # Contenu pour question non résolue
                enrichment_content += f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px;"><span style="font-size:18px;">{q_icon}</span><strong style="color:#c2410c;">⏳ À rechercher : {esc(q_subject)}</strong></div>'
                if enrichment.get("tips"):
                    tips_txt = " · ".join(enrichment["tips"][:3])
                    enrichment_content += f'<div style="font-size:13px;color:#555;margin-top:6px;">{esc(tips_txt)}</div>'
                if enrichment.get("links"):
                    links_html = " ".join([f'<a href="{u}" target="_blank" style="display:inline-block;padding:4px 10px;background:#fef3c7;color:#92400e;border-radius:6px;font-size:12px;text-decoration:none;margin-right:6px;">{esc(t)}</a>' for t, u in enrichment["links"][:3]])
                    enrichment_content += f'<div style="margin-top:8px;">{links_html}</div>'
                
                # Module dépliable ORANGE (à rechercher)
                summary_text = f"⏳ À rechercher : {esc(q_subject[:40])}"
                enrich_html = f'''
                <details style="margin:10px 0;background:#fff8f0;border:1px solid #fdba74;border-left:4px solid #f97316;border-radius:8px;overflow:hidden;">
                    <summary style="padding:12px;cursor:pointer;font-weight:bold;color:#c2410c;list-style:none;display:flex;align-items:center;gap:8px;">
                        <span style="transition:transform 0.2s;">▶</span> {summary_text}
                    </summary>
                    <div style="padding:0 12px 12px 12px;border-top:1px solid #fdba74;">
                        {enrichment_content}
                    </div>
                </details>'''
                extra_lines.append(enrich_html)

        rows.append(f"""
        <div style="
            background:#f8fafc;
            border:1px solid #cbd5e1;
            border-left:6px solid {border_color(item['kind'])};
            border-radius:14px;
            padding:18px;
            margin-bottom:14px;
            display:grid;
            grid-template-columns:120px 1fr;
            gap:16px;">
            <div>
                <div style="font-size:20px;font-weight:bold;color:#ea580c;">{item['km']} km</div>
                <div style="font-size:13px;color:#64748b;">{esc(item['time'])}</div>
                <div style="font-size:12px;color:#94a3b8;">ligne CSV #{item['row_num']}</div>
            </div>
            <div>
                <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                    <h3 style="margin:0;color:#0f172a;">{esc(item['label'])}</h3>
                    {badge_html(item['kind'])}
                </div>
                {note_html}
                {''.join(extra_lines)}
                <div style="font-size:12px;color:#94a3b8;">
                    {coords_html}{esc(item['country'])}
                </div>
                <div style="font-size:13px;color:#334155;margin-top:8px;">
                    {item['links_html']}
                </div>
            </div>
        </div>
        """)

    prev_link = f'<a href="jour-{prev_day:02d}.html" style="color:#ea580c;text-decoration:none;">← Jour précédent</a>' if prev_day else "<span></span>"
    next_link = f'<a href="jour-{next_day:02d}.html" style="color:#ea580c;text-decoration:none;">Jour suivant →</a>' if next_day else "<span></span>"

    highlights_block = ""
    if highlight_lines:
        highlights_block = f"""
        <div class="info-box">
            <h2 style="margin:0 0 10px 0;">⭐ Points forts du jour</h2>
            <ul style="margin:0;padding-left:20px;color:#334155;">
                {''.join(highlight_lines)}
            </ul>
        </div>
        """

    # ═══ SECTION QUESTIONS À RÉSOUDRE *xxx ? ═══
    questions_block = ""
    questions_resolved_list = []
    questions_pending_list = []
    
    for item in tl:
        pq = item.get("parsed_question")
        if not pq:
            continue
            
        q_type = pq.get("type", "UNKNOWN")
        q_subject = pq.get("subject", "")
        q_raw = pq.get("raw", item.get("raw", ""))
        q_actions = pq.get("actions", [])
        q_price = pq.get("known_price")
        enrichment = pq.get("enrichment", {})
        is_resolved = pq.get("is_resolved", False)
        
        # Icône selon le type
        icons = {
            "VISITE": "🏛️", "BIVOUAC": "⛺", "CAMPING": "🏕️", "HOTEL": "🏨",
            "FERRY": "⛴️", "SHUTTLE": "🚂", "DRONE": "🎥", "PRIX": "💰",
            "INFO": "ℹ️", "VIEWPOINT": "👁️", "INTERET": "📍", "COUCHAGE": "🛏️"
        }
        icon = icons.get(q_type, "❓")
        
        # Prix connu ou enrichi
        price_info = ""
        if enrichment.get("price_range"):
            price_info = f" <span style='color:#22c55e;font-weight:bold;'>{esc(enrichment['price_range'])}</span>"
        elif q_price:
            price_info = f" <span style='color:#22c55e;font-weight:bold;'>{q_price}€</span>"
        
        actions_badges = " ".join([f"<span style='background:#e0e7ff;color:#4338ca;padding:2px 8px;border-radius:4px;font-size:11px;'>{a}</span>" for a in q_actions])
        
        # Infos enrichies
        enrichment_html = ""
        if enrichment:
            parts = []
            if enrichment.get("main_info"):
                parts.append(f"<div style='font-weight:bold;color:#166534;margin-top:6px;'>✅ {esc(enrichment['main_info'])}</div>")
            if enrichment.get("tips"):
                tips_str = " · ".join(enrichment["tips"][:3])
                parts.append(f"<div style='font-size:12px;color:#555;margin-top:4px;'>{esc(tips_str)}</div>")
            if enrichment.get("warnings"):
                for w in enrichment["warnings"]:
                    parts.append(f"<div style='color:#dc2626;font-size:12px;margin-top:4px;'>⚠️ {esc(w)}</div>")
            if enrichment.get("links"):
                links_html = " ".join([f"<a href='{u}' target='_blank' style='font-size:11px;color:#4338ca;margin-right:8px;'>{esc(t)}</a>" for t, u in enrichment["links"][:3]])
                parts.append(f"<div style='margin-top:6px;'>{links_html}</div>")
            if enrichment.get("source"):
                parts.append(f"<div style='font-size:10px;color:#999;margin-top:4px;'>Source: {esc(enrichment['source'])}</div>")
            enrichment_html = "".join(parts)
        
        # Style différent selon résolu ou non
        if is_resolved:
            q_bg_color = "#f0fdf4"
            q_border_color = "#22c55e"
            status_badge = "<span style='background:#dcfce7;color:#166534;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:bold;'>RÉSOLU</span>"
        else:
            q_bg_color = "#fff8f0"
            q_border_color = "#f97316"
            status_badge = "<span style='background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:bold;'>À RECHERCHER</span>"
        
        question_card = f"""
            <li style="margin-bottom:12px;padding:12px;background:{q_bg_color};border-left:4px solid {q_border_color};border-radius:0 8px 8px 0;">
                <div style="display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap;">
                    <span style="font-size:20px;">{icon}</span>
                    <div style="flex:1;">
                        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                            <strong style="color:#1a1a1a;">{esc(q_subject or q_raw)}</strong>
                            {price_info}
                            {status_badge}
                        </div>
                        <div style="margin-top:4px;">{actions_badges}</div>
                        {enrichment_html}
                    </div>
                </div>
            </li>
        """
        
        if is_resolved:
            questions_resolved_list.append(question_card)
        else:
            questions_pending_list.append(question_card)
    
    # Construire le bloc complet
    all_questions = questions_resolved_list + questions_pending_list
    if all_questions:
        resolved_count = len(questions_resolved_list)
        pending_count = len(questions_pending_list)
        stats_line = f"<p style='font-size:12px;color:#666;margin-bottom:10px;'>✅ {resolved_count} résolu(s) · ⏳ {pending_count} en attente</p>"
        
        questions_block = f"""
        <div class="info-box" style="background:#fafafa;border:1px solid #e5e5e5;">
            <h2 style="margin:0 0 10px 0;color:#1a2b56;">❓ Questions du jour <a href="../questions.html" style="font-size:14px;color:#f97316;margin-left:10px;">Voir toutes →</a></h2>
            {stats_line}
            <ul style="margin:0;padding:0;list-style:none;">
                {''.join(all_questions)}
            </ul>
        </div>
        """
    

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>J{day:02d} · {esc(day_date)}</title>
{base_css()}
<link rel="stylesheet" href="../css/roadbook-jour-override.css">
</head>
<body>
<div class="wrapper">
    <div class="header">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;">
            <h1 style="margin:0;">J{day:02d} · {esc(day_date)}</h1>
            <div style="background:#f59e0b;color:white;padding:10px 18px;border-radius:999px;font-weight:bold;">
                {km_total} km
            </div>
        </div>
        <div class="top-header-actions">
            <a class="top-btn" href="../index.html">🗺️ Index</a>
            <a class="top-btn" href="../questions.html">❓ Questions</a>
            <a class="top-btn" href="{photo_upload_href(from_day_page=True)}">📤 Upload photos</a>
        </div>
    </div>

    <div class="top-metrics">
        <div class="metric"><div class="big">{km_total}</div>Kilomètres</div>
        <div class="metric"><div class="big">{esc(route_time)}</div>Temps route</div>
        <div class="metric"><div class="big">{fuel:.2f} €</div>Carburant estimé</div>
        <div class="metric"><div class="big">{day_data['conso_l_100']}</div>/100 km</div>
    </div>

    <div class="info-box">
        <div><strong>🏁 Départ du matin :</strong> {esc(depart)}</div>
        <div><strong>🏁 Arrivée du soir :</strong> {esc(arrivee)}</div>
        <small class="meta"><strong>Étape départ :</strong> {esc(start_raw)}</small>
        <small class="meta"><strong>Étape arrivée :</strong> {esc(end_raw)}</small>
        <small class="meta"><strong>Prix carburant appliqué :</strong> {day_data['fuel_price_eur']:.3f} €/L</small>
        <small class="meta"><strong>Points utiles retenus :</strong> {len(tl)} (instructions de navigation ignorées)</small>
    </div>

    <div class="legend">
        {' '.join(badge_html(k) for k in ["depart", "etape", "passage", "drone", "ferry", "train", "photo", "danger", "arrivee", "base"])}
    </div>

    {questions_block}

    {highlights_block}

    <div class="content">
        {''.join(rows)}
    </div>

    <div class="comment-box">
        <h2 style="margin-top:0;">🗣️ Commentaire du jour J{day:02d}</h2>
        <textarea id="commentaire-jour" placeholder="Tu peux écrire ou dicter ton commentaire ici..."></textarea>
        <div class="comment-actions">
            <button id="btn-mic-comment" class="comment-btn mic">🎤 Micro</button>
            <button id="btn-save-comment" class="comment-btn">💾 Enregistrer</button>
            <button id="btn-clear-comment" class="comment-btn secondary">🗑️ Effacer</button>
        </div>
        <div id="commentaire-status" class="status">Prêt.</div>
    </div>

    <div class="footer-nav">
        {prev_link}
        <a href="../index.html" style="color:#172554;text-decoration:none;">🗺️ Master planning</a>
        {next_link}
    </div>
</div>
{comment_widget_script(day)}
</body>
</html>
"""



def generate_master_html(days_data: List[Dict[str, Any]], trip_title: str, source_name: str) -> str:
    cards = []
    for d in days_data:
        start_title = point_label(d["start_stage"])
        end_title = point_label(d["end_stage"]) if not d["is_pause_day"] else start_title
        href = f"jours/jour-{d['day_num']:02d}.html"
        subtitle = f"{start_title} → {end_title}" if not d["is_pause_day"] else f"Base / pause autour de {start_title}"
        cards.append(f"""
        <a href="{href}" style="
            display:block;
            text-decoration:none;
            color:#0f172a;
            background:#fff;
            border:1px solid #cbd5e1;
            border-radius:16px;
            padding:18px;">
            <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;">
                <strong style="font-size:20px;color:#172554;">J{d['day_num']:02d} · {esc(d['day_date'] or 'à vérifier')}</strong>
                <span style="background:#f59e0b;color:white;padding:6px 12px;border-radius:999px;font-weight:bold;">
                    {d['km_total']} km
                </span>
            </div>
            <h2 style="margin:12px 0 8px 0;">{esc(subtitle)}</h2>
            <p style="margin:0;color:#475569;">{esc(d['route_time'])} · {len(d['timeline'])} points utiles retenus</p>
        </a>
        """)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(trip_title)}</title>
{base_css()}
</head>
<body>
<div class="wrapper">
    <div class="header">
        <h1 style="margin:0;">🗺️ {esc(trip_title)}</h1>
        <div class="meta">LCDMH · Road trip en préparation — itinéraire prévisionnel susceptible d'évoluer</div>
        <div class="top-actions">
            <a class="top-btn" href="questions.html">❓ Questions à résoudre</a>
            <a class="top-btn" href="{photo_upload_href(from_day_page=False)}">📤 Upload photos</a>
        </div>
    </div>
    <div class="grid">
        {''.join(cards)}
    </div>
</div>
</body>
</html>
"""


# ============================================================
# PDF
# ============================================================

PDF_ACCENT = colors.HexColor("#f97316")
PDF_NAVY = colors.HexColor("#172554")
PDF_SLATE = colors.HexColor("#475569")
PDF_BG = colors.HexColor("#f8fafc")
PDF_BORDER = colors.HexColor("#cbd5e1")
PDF_TEXT = colors.HexColor("#0f172a")


def _pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="LCDMH-Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=PDF_NAVY,
        spaceAfter=8,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="LCDMH-Subtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=PDF_SLATE,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="LCDMH-H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=PDF_NAVY,
        spaceBefore=8,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="LCDMH-H3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=PDF_TEXT,
        spaceBefore=4,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="LCDMH-Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.4,
        leading=13,
        textColor=PDF_TEXT,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="LCDMH-Small",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.5,
        textColor=PDF_SLATE,
    ))
    styles.add(ParagraphStyle(
        name="LCDMH-CenterSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.5,
        textColor=PDF_SLATE,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="LCDMH-Metric",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=20,
        textColor=PDF_ACCENT,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="LCDMH-DayTitle",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.white,
    ))
    return styles


def _pdf_escape(text: Any) -> str:
    return html.escape(str(text or "")).replace("\n", "<br/>")



def _pdf_meta_box(value: str, label: str, styles) -> Table:
    box = Table([[Paragraph(_pdf_escape(value), styles["LCDMH-Metric"])], [Paragraph(_pdf_escape(label), styles["LCDMH-CenterSmall"])]], colWidths=[42*mm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), PDF_BG),
        ("BOX", (0,0), (-1,-1), 0.8, PDF_BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ]))
    return box


def _pdf_info_table(rows: List[Tuple[str, str]], styles) -> Table:
    data = []
    for label, value in rows:
        data.append([Paragraph(f"<b>{_pdf_escape(label)}</b>", styles["LCDMH-Body"]), Paragraph(_pdf_escape(value), styles["LCDMH-Body"])])
    t = Table(data, colWidths=[42*mm, 128*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), PDF_BG),
        ("BOX", (0,0), (-1,-1), 0.8, PDF_BORDER),
        ("INNERGRID", (0,0), (-1,-1), 0.5, PDF_BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 9),
        ("RIGHTPADDING", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t


def _pdf_summary_table(days_data: List[Dict[str, Any]], styles) -> Table:
    data = [[
        Paragraph("<b>Jour</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Date</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Km</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Départ</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Arrivée</b>", styles["LCDMH-Body"]),
    ]]
    for d in days_data:
        start_title = point_label(d["start_stage"])
        end_title = point_label(d["end_stage"]) if not d["is_pause_day"] else start_title
        data.append([
            Paragraph(f"J{d['day_num']:02d}", styles["LCDMH-Body"]),
            Paragraph(_pdf_escape(d["day_date"] or "-"), styles["LCDMH-Body"]),
            Paragraph(str(d["km_total"]), styles["LCDMH-Body"]),
            Paragraph(_pdf_escape(start_title), styles["LCDMH-Small"]),
            Paragraph(_pdf_escape(end_title), styles["LCDMH-Small"]),
        ])
    table = Table(data, colWidths=[18*mm, 24*mm, 18*mm, 58*mm, 58*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PDF_NAVY),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("BACKGROUND", (0,1), (-1,-1), colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, PDF_BG]),
        ("BOX", (0,0), (-1,-1), 0.8, PDF_BORDER),
        ("INNERGRID", (0,0), (-1,-1), 0.4, PDF_BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (2,-1), "CENTER"),
    ]))
    return table


def _pdf_accommodations_table(days_data: List[Dict[str, Any]], styles) -> Table:
    """
    Génère un tableau récapitulatif des hébergements avec coordonnées GPS.
    
    Colonnes : Jour | Hébergement | Type | Prix | GPS
    """
    data = [[
        Paragraph("<b>Jour</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Hébergement</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Type</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Prix</b>", styles["LCDMH-Body"]),
        Paragraph("<b>GPS</b>", styles["LCDMH-Body"]),
    ]]
    
    for d in days_data:
        if d.get("is_pause_day"):
            continue  # Pas d'hébergement les jours de pause
        
        end_stage = d.get("end_stage")
        if not end_stage:
            continue
        
        # Extraire le nom de l'hébergement
        hebergement_name = point_label(end_stage)
        if not hebergement_name or hebergement_name == "-":
            continue
        
        # Détecter le type d'hébergement - chercher dans nom + description
        search_text = ((end_stage.description or "") + " " + (hebergement_name or "")).lower()
        if "bivouac" in search_text or "sauvage" in search_text:
            type_nuit = "🏕️ Bivouac"
        elif "camping" in search_text or "camp " in search_text or "kamp" in search_text:
            type_nuit = "⛺ Camping"
        elif "hotel" in search_text or "hôtel" in search_text or "ibis" in search_text:
            type_nuit = "🏨 Hôtel"
        elif "b&b" in search_text or "guesthouse" in search_text or "guest house" in search_text or "room and breakfast" in search_text or "gasthof" in search_text:
            type_nuit = "🛏️ B&B"
        elif "hostel" in search_text or "auberge" in search_text:
            type_nuit = "🛏️ Auberge"
        else:
            type_nuit = "🏠 Autre"
        
        # Extraire le prix depuis la description
        prix_str = "-"
        price_match = re.search(r"(\d+)\s*[€£]|[€£]\s*(\d+)|(\d+)\s*(?:EUR|GBP|CHF)", desc_lower, re.I)
        if price_match:
            prix = price_match.group(1) or price_match.group(2) or price_match.group(3)
            # Détecter la devise
            if "£" in search_text or "gbp" in desc_lower.lower():
                prix_str = f"{prix} £"
            elif "chf" in search_text:
                prix_str = f"{prix} CHF"
            else:
                prix_str = f"{prix} €"
        
        # Coordonnées GPS
        lat = getattr(end_stage, "lat", None) or d.get("end_stage_lat")
        lon = getattr(end_stage, "lon", None) or d.get("end_stage_lon")
        
        # Chercher dans la timeline si pas trouvé
        if (lat is None or lon is None) and d.get("timeline"):
            for item in reversed(d["timeline"]):
                if item.get("lat") is not None and item.get("lon") is not None:
                    lat, lon = item["lat"], item["lon"]
                    break
        
        if lat is not None and lon is not None:
            gps_str = f"{lat:.4f}, {lon:.4f}"
        else:
            gps_str = "-"
        
        data.append([
            Paragraph(f"J{d['day_num']:02d}", styles["LCDMH-Body"]),
            Paragraph(_pdf_escape(hebergement_name[:45] + ("..." if len(hebergement_name) > 45 else "")), styles["LCDMH-Small"]),
            Paragraph(type_nuit, styles["LCDMH-Small"]),
            Paragraph(prix_str, styles["LCDMH-Body"]),
            Paragraph(gps_str, styles["LCDMH-Small"]),
        ])
    
    if len(data) == 1:
        # Pas d'hébergements trouvés
        data.append([
            Paragraph("-", styles["LCDMH-Body"]),
            Paragraph("Aucun hébergement détecté", styles["LCDMH-Small"]),
            Paragraph("-", styles["LCDMH-Small"]),
            Paragraph("-", styles["LCDMH-Body"]),
            Paragraph("-", styles["LCDMH-Small"]),
        ])
    
    table = Table(data, colWidths=[18*mm, 62*mm, 28*mm, 22*mm, 46*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PDF_NAVY),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("BACKGROUND", (0,1), (-1,-1), colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, PDF_BG]),
        ("BOX", (0,0), (-1,-1), 0.8, PDF_BORDER),
        ("INNERGRID", (0,0), (-1,-1), 0.4, PDF_BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (0,-1), "CENTER"),
        ("ALIGN", (3,0), (3,-1), "CENTER"),
    ]))
    return table


def _pdf_timeline_table(day_data: Dict[str, Any], styles) -> Table:
    data = [[
        Paragraph("<b>Km</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Temps</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Type</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Point utile</b>", styles["LCDMH-Body"]),
        Paragraph("<b>Note / liens</b>", styles["LCDMH-Body"]),
    ]]
    for item in day_data.get("timeline", []):
        label, _color = BADGES.get(item["kind"], (item["kind"], "#64748b"))
        note_parts = []
        if item.get("note"):
            note_parts.append(item["note"])
        if item.get("advice"):
            note_parts.append(f"Conseil : {item['advice']}")
        if item.get("history"):
            note_parts.append(f"Repère : {item['history']}")
        if item.get("links_html"):
            note_parts.append(re.sub(r"<[^>]+>", " ", item["links_html"]))
        note_txt = "<br/>".join(_pdf_escape(p) for p in note_parts[:3]) or "-"
        data.append([
            Paragraph(str(item.get("km", 0)), styles["LCDMH-Body"]),
            Paragraph(_pdf_escape(item.get("time", "")), styles["LCDMH-Small"]),
            Paragraph(_pdf_escape(label), styles["LCDMH-Small"]),
            Paragraph(_pdf_escape(item.get("label") or "Point du parcours"), styles["LCDMH-Body"]),
            Paragraph(note_txt, styles["LCDMH-Small"]),
        ])
    table = Table(data, colWidths=[14*mm, 20*mm, 24*mm, 58*mm, 66*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e2e8f0")),
        ("TEXTCOLOR", (0,0), (-1,0), PDF_TEXT),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, PDF_BG]),
        ("BOX", (0,0), (-1,-1), 0.7, PDF_BORDER),
        ("INNERGRID", (0,0), (-1,-1), 0.35, PDF_BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (2,-1), "CENTER"),
    ]))
    return table


def _pdf_highlights(day_data: Dict[str, Any], styles) -> Optional[Table]:
    items = []
    for item in day_data.get("timeline", []):
        if item["kind"] in {"drone", "ferry", "train", "photo", "danger"}:
            items.append(f"<b>{_pdf_escape(item['label'])}</b> - {_pdf_escape(BADGES.get(item['kind'], ('Info',''))[0])}")
    if not items:
        return None
    p = Paragraph("<br/>".join(f"• {x}" for x in items[:6]), styles["LCDMH-Body"])
    t = Table([[p]], colWidths=[170*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#fff7ed")),
        ("BOX", (0,0), (-1,-1), 0.8, PDF_ACCENT),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 9),
    ]))
    return t


def _pdf_page_deco(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(PDF_NAVY)
    canvas.rect(0, h - 16*mm, w, 16*mm, fill=1, stroke=0)
    canvas.setStrokeColor(PDF_ACCENT)
    canvas.setLineWidth(2)
    canvas.line(doc.leftMargin, h - 18*mm, w - doc.rightMargin, h - 18*mm)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(doc.leftMargin, h - 10*mm, "LCDMH - Roadbook")
    canvas.setFillColor(PDF_SLATE)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - doc.rightMargin, 9*mm, f"Page {doc.page}")
    canvas.restoreState()


def generate_pdf_report(days_data: List[Dict[str, Any]], warnings: List[str], trip_title: str, source_name: str, output_path: str) -> str:
    styles = _pdf_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=18*mm,
        rightMargin=18*mm,
        topMargin=26*mm,
        bottomMargin=22*mm,
        title=trip_title,
        author="Yves Vella — LCDMH",
    )

    total_km = sum(int(d.get("km_total", 0)) for d in days_data)
    total_days = len(days_data)
    total_budget = sum(float(d.get("fuel_cost_eur", 0.0)) for d in days_data)
    first_date = days_data[0].get("day_date", "-") if days_data else "-"
    last_date = days_data[-1].get("day_date", "-") if days_data else "-"

    story = []
    story.append(Paragraph(_pdf_escape(trip_title), styles["LCDMH-Title"]))
    story.append(Paragraph(f"Roadbook prévisionnel - source : {_pdf_escape(source_name)}", styles["LCDMH-Subtitle"]))
    story.append(Spacer(1, 5*mm))

    metrics = Table([[
        _pdf_meta_box(str(total_days), "Jours calculés", styles),
        _pdf_meta_box(str(total_km), "Kilomètres estimés", styles),
        _pdf_meta_box(f"{total_budget:.0f} €", "Budget carburant", styles),
        _pdf_meta_box(f"{first_date} -> {last_date}", "Période", styles),
    ]], colWidths=[43*mm, 43*mm, 43*mm, 43*mm])
    metrics.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story.append(metrics)
    story.append(Spacer(1, 7*mm))

    intro = (
        "Ce PDF reprend le roadbook LCDMH dans une version plus lisible pour le repérage, l'impression et la préparation du voyage. "
        "Les journées sont listées avec leur kilométrage, leur départ, leur arrivée et les points utiles retenus. "
        "Les indications de navigation pures sont exclues du document."
    )
    story.append(Paragraph(intro, styles["LCDMH-Body"]))
    story.append(Spacer(1, 4*mm))

    lecture_rows = [
        ("Premier jour", f"J{days_data[0]['day_num']:02d} - {days_data[0]['day_date']} - {point_label(days_data[0]['start_stage'])}" if days_data else "-"),
        ("Dernier jour", f"J{days_data[-1]['day_num']:02d} - {days_data[-1]['day_date']} - {point_label(days_data[-1]['end_stage'])}" if days_data else "-"),
        ("Jour le plus long", "-"),
        ("Alerte calcul", warnings[0] if warnings else "Aucune alerte bloquante"),
    ]
    if days_data:
        longest = max(days_data, key=lambda d: int(d.get("km_total", 0)))
        lecture_rows[2] = ("Jour le plus long", f"J{longest['day_num']:02d} - {longest['km_total']} km - {point_label(longest['start_stage'])} -> {point_label(longest['end_stage']) if not longest['is_pause_day'] else point_label(longest['start_stage'])}")
    story.append(KeepTogether([
        Paragraph("Lecture rapide", styles["LCDMH-H2"]),
        _pdf_info_table(lecture_rows, styles),
        Spacer(1, 6*mm),
    ]))

    if warnings:
        warn_text = "<br/>".join(f"• {_pdf_escape(w)}" for w in warnings[:8])
        warn_box = Table([[Paragraph(warn_text, styles["LCDMH-Small"])]], colWidths=[170*mm])
        warn_box.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#fef2f2")),
            ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#fecaca")),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING", (0,0), (-1,-1), 9),
        ]))
        story.append(Paragraph("Points de vigilance", styles["LCDMH-H2"]))
        story.append(warn_box)

    story.append(PageBreak())
    story.append(Paragraph("Vue d'ensemble jour par jour", styles["LCDMH-H2"]))
    story.append(Paragraph("Tableau synthétique pour repérer rapidement les journées, les dates et les étapes principales.", styles["LCDMH-Subtitle"]))
    story.append(Spacer(1, 2*mm))
    story.append(_pdf_summary_table(days_data, styles))

    # ═══ RÉCAPITULATIF DES HÉBERGEMENTS AVEC GPS ═══
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("📍 Récapitulatif des hébergements", styles["LCDMH-H2"]))
    story.append(Paragraph("Liste des nuits avec type, prix indicatif et coordonnées GPS pour navigation.", styles["LCDMH-Subtitle"]))
    story.append(Spacer(1, 2*mm))
    story.append(_pdf_accommodations_table(days_data, styles))

    for day in days_data:
        story.append(PageBreak())
        title = Table([[Paragraph(f"J{day['day_num']:02d} - {_pdf_escape(day.get('day_date') or 'Date à vérifier')}", styles["LCDMH-DayTitle"]), Paragraph(f"{day.get('km_total', 0)} km", styles["LCDMH-DayTitle"]) ]], colWidths=[138*mm, 32*mm])
        title.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), PDF_NAVY),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING", (0,0), (-1,-1), 9),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN", (1,0), (1,0), "RIGHT"),
        ]))
        story.append(title)
        story.append(Spacer(1, 4*mm))

        start_title = point_label(day["start_stage"])
        end_title = point_label(day["end_stage"]) if not day["is_pause_day"] else start_title
        info_rows = [
            ("Départ du matin", start_title),
            ("Arrivée du soir", end_title),
            ("Temps route", day.get("route_time", "-")),
            ("Carburant estimé", f"{day.get('fuel_cost_eur', 0.0):.2f} €  |  {day.get('fuel_price_eur', 0.0):.3f} €/L"),
        ]
        # Bloc info du jour insécable (ne sera pas coupé entre 2 pages)
        story.append(KeepTogether([
            _pdf_info_table(info_rows, styles),
            Spacer(1, 4*mm),
        ]))

        hi = _pdf_highlights(day, styles)
        if hi is not None:
            story.append(KeepTogether([
                Paragraph("Points forts du jour", styles["LCDMH-H3"]),
                hi,
                Spacer(1, 4*mm),
            ]))

        story.append(Paragraph("Feuille de route détaillée", styles["LCDMH-H3"]))
        story.append(_pdf_timeline_table(day, styles))

    doc.build(story, onFirstPage=_pdf_page_deco, onLaterPages=_pdf_page_deco)
    return output_path


# ============================================================
# ÉCRITURE / ZIP
# ============================================================


def write_outputs(days_data: List[Dict[str, Any]], warnings: List[str], trip_title: str, source_name: str, output_dir: str) -> Dict[str, str]:
    out_dir = Path(output_dir)
    jours_dir = out_dir / "jours"
    out_dir.mkdir(parents=True, exist_ok=True)
    jours_dir.mkdir(parents=True, exist_ok=True)

    index_path = out_dir / "index.html"
    warnings_path = out_dir / "warnings.txt"

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(generate_master_html(days_data, trip_title=trip_title, source_name=source_name))

    day_numbers = [d["day_num"] for d in days_data]
    for i, d in enumerate(days_data):
        prev_day = day_numbers[i - 1] if i > 0 else None
        next_day = day_numbers[i + 1] if i < len(day_numbers) - 1 else None
        day_path = jours_dir / f"jour-{d['day_num']:02d}.html"
        with open(day_path, "w", encoding="utf-8") as f:
            f.write(generate_day_html(d, prev_day=prev_day, next_day=next_day))

    with open(warnings_path, "w", encoding="utf-8") as f:
        if warnings:
            f.write("\n".join(warnings))
        else:
            f.write("Aucune alerte.\n")

    # ═══ GÉNÉRATION DE LA PAGE RÉCAPITULATIVE DES QUESTIONS ═══
    questions_path = out_dir / "questions.html"
    if WEB_ENRICHMENT_AVAILABLE and web_enrichment:
        # Collecter toutes les questions (y compris multiples par item)
        all_enrichment_results = []
        for d in days_data:
            for item in d.get("timeline", []):
                # V2 : itérer sur parsed_questions (liste) si disponible
                pq_list = item.get("parsed_questions", [])
                if not pq_list:
                    # Fallback : ancienne clé unique parsed_question
                    pq_single = item.get("parsed_question")
                    if pq_single:
                        pq_list = [pq_single]
                
                for pq in pq_list:
                    if pq and QUESTIONS_MODULE_AVAILABLE and questions_module:
                        # Recréer l'objet ParsedQuestion
                        parsed_q = questions_module.ParsedQuestion(
                            raw_text=pq.get("raw", ""),
                            question_type=getattr(questions_module.QuestionType, pq.get("type", "UNKNOWN"), questions_module.QuestionType.UNKNOWN),
                            actions=[getattr(questions_module.ActionType, a, questions_module.ActionType.INFO) for a in pq.get("actions", [])],
                            subject=pq.get("subject", ""),
                            known_price=pq.get("known_price"),
                            day_num=d.get("day_num"),
                            date_str=d.get("day_date", ""),
                        )
                        
                        # Créer l'EnrichmentResult
                        enrichment = pq.get("enrichment", {})
                        result = web_enrichment.EnrichmentResult(
                            question=parsed_q,
                            main_info=enrichment.get("main_info", ""),
                            price_range=enrichment.get("price_range", ""),
                            tips=enrichment.get("tips", []),
                            warnings=enrichment.get("warnings", []),
                            links=[(t, u) for t, u in enrichment.get("links", [])],
                            source=enrichment.get("source", ""),
                            quality_score=enrichment.get("quality_score", 0),
                        )
                        all_enrichment_results.append(result)
        
        if all_enrichment_results:
            questions_html = web_enrichment.generate_questions_summary_html(
                results=all_enrichment_results,
                trip_title=trip_title,
            )
            with open(questions_path, "w", encoding="utf-8") as f:
                f.write(questions_html)

    return {
        "index": str(index_path),
        "jours": str(jours_dir),
        "warnings": str(warnings_path),
        "questions": str(questions_path),
        "pdf": str(out_dir / "roadbook_previsionnel.pdf"),
    }



def build_zip_bytes(output_dir: str) -> bytes:
    mem = io.BytesIO()
    root = Path(output_dir)
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(root)))
    return mem.getvalue()


# ============================================================
# PAGE STREAMLIT
# ============================================================


def page_generateur_roadbook() -> None:
    global UPLOAD_PHOTO_FILE
    st.title("🛣️ Générateur Roadbook")
    st.caption("Transforme un export CSV Kurviger en index HTML + fiches jour détaillées, avec un découpage métier basé sur ⚐ / Ⓥ / ⚑ et des points utiles Ⓢ.")

    with st.expander("Règle de calcul retenue", expanded=True):
        st.markdown(
            """
- `⚐` = **début réel du road trip**.
- `Ⓥ` = **fin d'étape / nuit sur place** ; ce même point devient le départ du lendemain.
- `Ⓢ` = **point de passage interne à la journée** ; il ne découpe jamais une nouvelle journée.
- `⚑` = **fin du road trip** si présent.
- Le moteur **ignore les libellés Jx comme source de vérité** ; ils restent seulement des repères visuels.
- Les kilomètres et durées sont calculés à partir des colonnes natives **Distance totale** et **Durée totale** du CSV Kurviger.
- `N2`, `N3`, etc. sur un point `Ⓥ` décalent automatiquement la date de départ de la journée suivante.
            """
        )

    csv_file = st.file_uploader("CSV Kurviger", type=["csv"])

    # ═══ V2 : Upload optionnel du fichier .kurviger pour fusion GPS ═══
    kurviger_file = None
    if LOCATION_ENGINE_AVAILABLE:
        kurviger_file = st.file_uploader(
            "Fichier .kurviger (optionnel — enrichit les GPS des questions)",
            type=["kurviger"],
            help="Le fichier .kurviger contient les coordonnées GPS exactes de chaque waypoint. "
                 "Sans lui, les questions *xxx? sans GPS dans le CSV ne seront pas localisées.",
        )

    runtime_key = _resolve_gemini_key()

    col1, col2 = st.columns(2)
    with col1:
        trip_title = st.text_input("Titre du road trip", value="Écosse & Irlande 2026")
        output_dir = st.text_input("Dossier de sortie", value=r"F:\RoadBook HTML\roadbook-2026")
        upload_photo_file = st.text_input("Lien ou fichier upload photo", value=UPLOAD_PHOTO_FILE)
        trip_year = st.number_input("Année du road trip", min_value=2020, max_value=2100, value=2026, step=1)
    with col2:
        conso = st.number_input("Consommation (L/100)", min_value=1.0, max_value=20.0, value=float(DEFAULT_CONSO), step=0.1)
        uk_price = st.number_input("Prix carburant UK (€ / L)", min_value=0.5, max_value=5.0, value=float(DEFAULT_UK_PRICE), step=0.001, format="%.3f")
        ie_price = st.number_input("Prix carburant Irlande (€ / L)", min_value=0.5, max_value=5.0, value=float(DEFAULT_IE_PRICE), step=0.001, format="%.3f")
        enable_online = st.checkbox("Enrichir les points via GPS / web / Wikipédia", value=True)
        use_gemini = st.checkbox(
            "Utiliser Gemini pour les blocs histoire / géologie / conseils",
            value=bool(runtime_key),
            disabled=not bool(runtime_key),
        )
        if runtime_key:
            st.caption("Clé Gemini détectée dans app.py.")
        else:
            st.caption("Aucune clé Gemini détectée depuis app.py : enrichissement IA désactivé.")

    UPLOAD_PHOTO_FILE = upload_photo_file.strip() or "UploadPhoto_v3.html"

    if not st.button("🚀 Générer le roadbook", type="primary", use_container_width=True):
        return

    if not csv_file:
        st.error("Ajoute d'abord le CSV Kurviger.")
        return

    if not output_dir.strip():
        st.error("Le dossier de sortie est obligatoire.")
        return

    try:
        raw_tmp_csv = st.session_state.get("_tmp_roadbook_csv")
        if raw_tmp_csv and str(raw_tmp_csv).strip() not in {"", "."}:
            temp_csv = Path(str(raw_tmp_csv)).expanduser()
            temp_csv.parent.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = Path(tempfile.mkdtemp(prefix="roadbook_csv_"))
            temp_csv = temp_dir / "roadtrip_import.csv"
        temp_csv.write_bytes(csv_file.getvalue())

        points = load_csv(str(temp_csv))

        # ═══ V2 : Fusion GPS depuis le fichier .kurviger ═══
        if kurviger_file and LOCATION_ENGINE_AVAILABLE and location_engine:
            try:
                temp_kurv = temp_csv.parent / "route.kurviger"
                temp_kurv.write_bytes(kurviger_file.getvalue())
                kurv_waypoints = location_engine.parse_kurviger_file(str(temp_kurv))

                # Préparer les données CSV pour le matching
                csv_for_match = [
                    {"row_num": p.row_num, "description": p.description,
                     "lat": p.lat, "lon": p.lon}
                    for p in points if p.symbol in {"⚐", "Ⓥ", "Ⓢ", "⚑"}
                ]
                matches = location_engine.match_kurviger_to_csv(kurv_waypoints, csv_for_match)

                # Injecter les GPS manquants dans les CsvPoint
                gps_injected = 0
                for p in points:
                    if p.row_num in matches:
                        wp = matches[p.row_num]
                        if p.lat is None or p.lon is None:
                            p.lat = wp.lat
                            p.lon = wp.lon
                            gps_injected += 1
                        elif abs((p.lat or 0) - wp.lat) > 0.01 or abs((p.lon or 0) - wp.lon) > 0.01:
                            # Le .kurviger a de meilleures coordonnées
                            p.lat = wp.lat
                            p.lon = wp.lon
                            gps_injected += 1

                st.success(f"📍 Fichier .kurviger : {len(kurv_waypoints)} waypoints, "
                           f"{len(matches)} matchés, {gps_injected} GPS injectés")
            except Exception as e:
                st.warning(f"⚠️ Fusion .kurviger échouée (le CSV reste utilisable) : {e}")

        days_data, warnings = build_days(points, conso_l_100=conso, uk_price=uk_price, ie_price=ie_price)

        if days_data:
            enrich_days_data(
                days_data=days_data,
                trip_year=int(trip_year),
                use_online=bool(enable_online),
                use_gemini=bool(use_gemini and runtime_key),
                gemini_key=runtime_key,
            )
            # V2 : sauvegarder le cache de reverse geocoding
            if LOCATION_ENGINE_AVAILABLE and location_engine:
                try:
                    location_engine.get_cache().save()
                except Exception:
                    pass

        if not days_data:
            st.error("Aucune journée exploitable n'a pu être générée.")
            if warnings:
                st.code("\n".join(warnings[:50]), language="text")
            return

        paths = write_outputs(
            days_data=days_data,
            warnings=warnings,
            trip_title=trip_title,
            source_name=csv_file.name,
            output_dir=output_dir,
        )
        generate_pdf_report(
            days_data=days_data,
            warnings=warnings,
            trip_title=trip_title,
            source_name=csv_file.name,
            output_path=paths["pdf"],
        )
        zip_bytes = build_zip_bytes(output_dir)

        st.success(f"✅ Roadbook généré : {len(days_data)} journées HTML + PDF.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Jours générés", len(days_data))
        c2.metric("Premier jour", f"J{days_data[0]['day_num']:02d}")
        c3.metric("Dernier jour", f"J{days_data[-1]['day_num']:02d}")

        st.markdown("**Fichiers écrits**")
        st.code("\n".join([paths["index"], paths["jours"], paths["pdf"], paths["warnings"]]), language="text")

        pdf_bytes = Path(paths["pdf"]).read_bytes()

        st.download_button(
            "📦 Télécharger le roadbook HTML (.zip)",
            data=zip_bytes,
            file_name="roadbook_html.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.download_button(
            "📄 Télécharger le PDF synthétique",
            data=pdf_bytes,
            file_name="roadbook_previsionnel.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        with st.expander("Aperçu du résumé journalier", expanded=True):
            for d in days_data:
                st.markdown(
                    f"**J{d['day_num']:02d} · {d['day_date'] or 'à vérifier'}** — "
                    f"{d['km_total']} km — {point_label(d['start_stage'])} → {point_label(d['end_stage']) if not d['is_pause_day'] else point_label(d['start_stage'])}"
                )

        with st.expander("Alertes et incohérences détectées", expanded=bool(warnings)):
            if warnings:
                st.code("\n".join(warnings), language="text")
            else:
                st.success("Aucune alerte détectée.")

    except Exception as exc:
        st.error(f"Erreur pendant la génération : {exc}")


if __name__ == "__main__":
    page_generateur_roadbook()

