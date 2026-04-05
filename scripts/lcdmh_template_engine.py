# -*- coding: utf-8 -*-
"""Moteur de templates LCDMH.

Ce module est le point d'entrée unique pour :
- charger un template HTML depuis le disque (dossier configurable) ;
- résoudre les placeholders {{variable}} dans le HTML ;
- gérer un registre de templates (principal, journal, PDF, etc.) ;
- fournir des helpers HTML réutilisables (timeline, cards, FAQ, etc.).

Convention placeholders :
    {{variable_name}}            → remplacement simple (escape HTML auto)
    {{raw:variable_name}}        → remplacement sans escape (HTML brut)
    {{if:variable_name}}...{{endif:variable_name}}  → bloc conditionnel
    {{each:items}}...{{endeach:items}}              → boucle sur liste de dicts

Architecture :
    page_generateur_roadbook.py  ──→  lcdmh_template_engine.py  ──→  templates/*.html
    page_journal.py              ──→  lcdmh_template_engine.py  ──→  templates/*.html
    toute_autre_page.py          ──→  lcdmh_template_engine.py  ──→  templates/*.html
"""
from __future__ import annotations

import re
import json
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

MODULE_DIR = Path(__file__).resolve().parent

# Dossier par défaut contenant les templates HTML
DEFAULT_TEMPLATES_DIR = MODULE_DIR / "templates"

# Registre statique : nom logique → nom de fichier dans le dossier templates
TEMPLATE_REGISTRY: Dict[str, str] = {
    "main_roadtrip":   "template_roadtrip_principal.html",
    "journal":         "template_journal.html",
    "pdf_printable":   "template_pdf_printable.html",
}

# Fichiers de fallback (anciens noms) cherchés si le nom principal est absent
FALLBACK_FILENAMES: Dict[str, List[str]] = {
    "main_roadtrip": [
        "template_roadtrip_principal.html",
        "Road Trip Moto Écosse & Irlande 2026 _ 10 000 km Solo _ LCDMH.html",
        "ecosse-irlande.html",
    ],
    "journal": [
        "template_journal.html",
    ],
}


# ═══════════════════════════════════════════════════════════════════
#  CHARGEMENT DES TEMPLATES
# ═══════════════════════════════════════════════════════════════════

def get_templates_dir(*extra_dirs: Union[str, Path]) -> Path:
    """Renvoie le dossier templates. Accepte des dossiers supplémentaires
    à tester en priorité (ex. le dossier projet de l'utilisateur)."""
    for d in extra_dirs:
        p = Path(d).expanduser().resolve()
        if (p / "templates").is_dir():
            return p / "templates"
        # Le dossier lui-même contient peut-être directement les templates
        if p.is_dir() and any(p.glob("template_*.html")):
            return p
    return DEFAULT_TEMPLATES_DIR


def list_available_templates(templates_dir: Optional[Path] = None) -> Dict[str, Path]:
    """Liste tous les templates disponibles dans le dossier."""
    d = templates_dir or DEFAULT_TEMPLATES_DIR
    if not d.is_dir():
        return {}
    return {p.stem: p for p in sorted(d.glob("*.html"))}


def load_template(
    name: str,
    templates_dir: Optional[Path] = None,
    extra_dirs: Optional[List[Union[str, Path]]] = None,
    trace: Optional[List[str]] = None,
) -> str:
    """Charge un template par son nom logique (clé du registre) ou par nom de fichier.

    Si trace est fourni (liste), y ajoute les messages de diagnostic.

    Raises FileNotFoundError si rien n'est trouvé.
    """
    if trace is None:
        trace = []

    search_dirs: List[Path] = []
    if extra_dirs:
        for d in extra_dirs:
            p = Path(d).expanduser().resolve()
            if p.is_dir():
                search_dirs.append(p)
                tp = p / "templates"
                if tp.is_dir():
                    search_dirs.append(tp)
    if templates_dir and templates_dir.is_dir():
        search_dirs.append(templates_dir)
    search_dirs.append(DEFAULT_TEMPLATES_DIR)
    search_dirs.append(MODULE_DIR)

    trace.append(f"[TEMPLATE] Recherche de '{name}'")
    trace.append(f"[TEMPLATE] Dossiers de recherche : {[str(d) for d in search_dirs]}")

    # Construire la liste de noms de fichiers à chercher
    filenames: List[str] = []
    if name in TEMPLATE_REGISTRY:
        filenames.append(TEMPLATE_REGISTRY[name])
        filenames.extend(FALLBACK_FILENAMES.get(name, []))
    else:
        filenames.append(name)
        if not name.endswith(".html"):
            filenames.append(f"{name}.html")
            filenames.append(f"template_{name}.html")

    # Déduplique en gardant l'ordre
    seen = set()
    unique_filenames = []
    for fn in filenames:
        if fn not in seen:
            seen.add(fn)
            unique_filenames.append(fn)

    trace.append(f"[TEMPLATE] Fichiers cherchés : {unique_filenames}")

    # Variable pour stocker le chemin du template trouvé (utilisé par _copy_template_css)
    _last_template_path: Optional[Path] = None

    # Recherche
    for d in search_dirs:
        for fn in unique_filenames:
            path = d / fn
            exists = path.exists() and path.is_file()
            trace.append(f"[TEMPLATE]   {path} → {'TROUVÉ ✅' if exists else 'absent'}")
            if exists:
                content = path.read_text(encoding="utf-8", errors="ignore")
                trace.append(f"[TEMPLATE] ✅ Chargé : {path} ({len(content)} caractères)")
                # Stocker le chemin pour que le CSS puisse être cherché à côté
                load_template._last_found_path = path
                load_template._last_found_dir = d
                trace.append(f"[TEMPLATE] ✅ Chargé : {path} ({len(content)} caractères)")
                # Vérifier que c'est bien un template avec placeholders
                placeholder_count = content.count("{{")
                trace.append(f"[TEMPLATE]   Placeholders trouvés : {placeholder_count}")
                if placeholder_count == 0:
                    trace.append(f"[TEMPLATE] ⚠️  ATTENTION : le fichier ne contient aucun placeholder {{{{ }}}} — c'est peut-être le mauvais fichier")
                # Vérifier la référence CSS
                if "roadbook.css" in content:
                    trace.append(f"[TEMPLATE]   Référence CSS : roadbook.css ✅")
                elif "roadbook-fusion.css" in content:
                    trace.append(f"[TEMPLATE]   Référence CSS : roadbook-fusion.css")
                elif "<style>" in content:
                    trace.append(f"[TEMPLATE]   CSS inline détecté (pas de fichier externe)")
                else:
                    trace.append(f"[TEMPLATE] ⚠️  Aucune référence CSS trouvée dans le template")
                return content

    tried = [f"{d}/{fn}" for d in search_dirs for fn in unique_filenames]
    trace.append(f"[TEMPLATE] ❌ AUCUN TEMPLATE TROUVÉ")
    trace.append(f"[TEMPLATE]   Chemins testés : {tried[:20]}")
    raise FileNotFoundError(
        f"Template '{name}' introuvable.\n"
        f"Fichiers cherchés :\n" + "\n".join(f"  - {t}" for t in tried[:20])
    )


def template_exists(name: str, templates_dir: Optional[Path] = None) -> bool:
    """Vérifie si un template existe sans lever d'exception."""
    try:
        load_template(name, templates_dir=templates_dir)
        return True
    except FileNotFoundError:
        return False


# ═══════════════════════════════════════════════════════════════════
#  MOTEUR DE RÉSOLUTION DES PLACEHOLDERS
# ═══════════════════════════════════════════════════════════════════

_RE_PLACEHOLDER = re.compile(r"\{\{(raw:)?([a-zA-Z_][a-zA-Z0-9_.:]*)\}\}")
_RE_IF_BLOCK = re.compile(
    r"\{\{if:([a-zA-Z_][a-zA-Z0-9_.]*)\}\}(.*?)\{\{endif:\1\}\}",
    re.DOTALL,
)
_RE_EACH_BLOCK = re.compile(
    r"\{\{each:([a-zA-Z_][a-zA-Z0-9_.]*)\}\}(.*?)\{\{endeach:\1\}\}",
    re.DOTALL,
)


def _resolve_key(data: Dict[str, Any], key: str) -> Any:
    """Résout une clé imbriquée comme 'hero.src' dans un dict."""
    parts = key.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _is_truthy(value: Any) -> bool:
    """Teste si une valeur est considérée comme vraie pour les blocs conditionnels."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, dict)):
        return bool(value)
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip()
    return bool(s) and s.lower() not in ("0", "false", "non", "none", "null", "—", "")


def render(html: str, data: Dict[str, Any]) -> str:
    """Résout tous les placeholders dans le HTML avec les données fournies.

    Étapes :
    1. Blocs {{each:items}}...{{endeach:items}}
    2. Blocs {{if:var}}...{{endif:var}}
    3. Placeholders simples {{var}} et {{raw:var}}
    """
    # 1. Boucles each
    def _replace_each(match: re.Match) -> str:
        key = match.group(1)
        body = match.group(2)
        items = _resolve_key(data, key)
        if not isinstance(items, list):
            return ""
        parts = []
        for idx, item in enumerate(items):
            # Créer un sous-contexte avec les clés de l'item + index
            sub_data = {**data}
            if isinstance(item, dict):
                for k, v in item.items():
                    sub_data[f"{key}.{k}"] = v
                    sub_data[k] = v  # accès direct aussi
            sub_data[f"{key}._index"] = idx
            sub_data[f"{key}._num"] = idx + 1
            sub_data["_index"] = idx
            sub_data["_num"] = idx + 1
            parts.append(render(body, sub_data))
        return "".join(parts)

    html = _RE_EACH_BLOCK.sub(_replace_each, html)

    # 2. Blocs conditionnels
    def _replace_if(match: re.Match) -> str:
        key = match.group(1)
        body = match.group(2)
        value = _resolve_key(data, key)
        if _is_truthy(value):
            return render(body, data)
        return ""

    html = _RE_IF_BLOCK.sub(_replace_if, html)

    # 3. Placeholders simples
    def _replace_placeholder(match: re.Match) -> str:
        is_raw = bool(match.group(1))
        key = match.group(2)
        # Pour {{raw:xxx}}, chercher d'abord la clé "raw:xxx" dans le dict,
        # sinon chercher "xxx" et l'insérer sans escape
        if is_raw:
            value = _resolve_key(data, f"raw:{key}")
            if value is None:
                value = _resolve_key(data, key)
        else:
            value = _resolve_key(data, key)
        if value is None:
            return ""
        text = str(value)
        return text if is_raw else html_escape(text)

    html = _RE_PLACEHOLDER.sub(_replace_placeholder, html)

    return html


# ═══════════════════════════════════════════════════════════════════
#  HELPERS HTML RÉUTILISABLES
# ═══════════════════════════════════════════════════════════════════

def timeline_item_html(
    index: int,
    date_label: str = "",
    title: str = "",
    subtitle: str = "",
    region: str = "",
    km_label: str = "",
    highlight: str = "",
    dot_class: str = "orange",
    description_immersive: str = "",
    moment_fort: str = "",
    stay_type: str = "",
) -> str:
    """Génère un élément de timeline enrichi avec description immersive."""
    km_tag = f'<span class="tl-tag orange">{html_escape(km_label)}</span>' if km_label else ""
    # Description immersive remplace le highlight géologique si disponible
    if description_immersive:
        highlight_html = f'<p class="tl-highlight">{html_escape(description_immersive)}</p>'
    elif highlight:
        highlight_html = f'<p class="tl-highlight">🏔️ {html_escape(highlight)}</p>'
    else:
        highlight_html = ""
    # Moment fort
    moment_html = f'<p class="tl-moment">✨ {html_escape(moment_fort)}</p>' if moment_fort else ""
    # Région
    region_html = f'<span class="tl-tag">🌍 {html_escape(region)}</span>' if region else ""
    # Type hébergement
    stay_icons = {"Bivouac": "⛺", "Camping": "🏕️", "Hotel": "🏨", "B&B": "🛏️"}
    stay_html = f'<span class="tl-tag">{stay_icons.get(stay_type, "")} {html_escape(stay_type)}</span>' if stay_type else ""
    return f"""
<div class="tl-item">
  <div class="tl-dot {html_escape(dot_class)}">J{index}</div>
  <div class="tl-content">
    <div class="tl-ep">{html_escape(date_label)}</div>
    <h3>{html_escape(title)}</h3>
    <p>{html_escape(subtitle)}</p>
    {highlight_html}
    {moment_html}
    {region_html}
    {stay_html}
    {km_tag}
  </div>
</div>
"""


def timeline_html(days: List[Dict[str, Any]], limit: int = 30) -> str:
    """Génère la timeline complète à partir des données de jours."""
    items = []
    for idx, day in enumerate((days or [])[:limit], 1):
        # Utiliser le titre nettoyé si disponible
        if day.get("clean_start_stage") or day.get("clean_end_stage"):
            start = day.get("clean_start_stage", "")
            end = day.get("clean_end_stage", "")
            if start and end and start != end:
                title = f"{start} → {end}"
            else:
                title = start or end or _day_title(day, idx)
        else:
            title = _day_title(day, idx)
        sub = _day_subtitle(day, idx)
        region = _day_region(day)
        highlight = _day_highlight(day)
        date_label = _day_date(day, idx)
        km = day.get("distance_km") or day.get("km_total")
        try:
            km_label = f"≈ {float(km):.0f} km" if km else ""
        except (ValueError, TypeError):
            km_label = ""
        # Nouvelles clés immersives
        description_immersive = day.get("description_immersive", "")
        moment_fort = day.get("moment_fort", "")
        stay_type = day.get("stay_type", "")
        items.append(timeline_item_html(
            index=idx,
            date_label=date_label,
            title=title,
            subtitle=sub,
            region=region,
            km_label=km_label,
            highlight=highlight,
            description_immersive=description_immersive,
            moment_fort=moment_fort,
            stay_type=stay_type,
        ))
    return "".join(items)


def short_card_html(
    index: int,
    title: str = "",
    text: str = "",
    thumb: str = "",
    url: str = "#",
    label: str = "",
) -> str:
    """Génère une carte vidéo short (design de référence avec img)."""
    thumb_html = f'<img alt="{html_escape(title)}" src="{html_escape(thumb)}"/>' if thumb else ""
    return f"""
<article class="short-card">
    <div class="short-thumb">{thumb_html}</div>
    <div class="short-body">
        <span class="short-badge">{html_escape(label)}</span>
        <h3>{html_escape(title)}</h3>
        <p>{html_escape(text)}</p>
        <a class="btn btn-dark" href="{html_escape(url)}" target="_blank" rel="noopener">Voir le short</a>
    </div>
</article>
"""


def short_cards_html(cards: List[Dict[str, Any]], limit: int = 3) -> str:
    """Génère la grille de shorts."""
    items = []
    for idx, card in enumerate((cards or [])[:limit], 1):
        items.append(short_card_html(
            index=idx,
            title=_safe(card.get("title"), f"Vidéo {idx}"),
            text=_truncate(_safe(card.get("text") or card.get("date_label") or ""), 120),
            thumb=_safe(card.get("thumb"), ""),
            url=_safe(card.get("url"), "#"),
            label=_safe(card.get("date_label"), f"Short {idx}"),
        ))
    return "".join(items)


def journal_card_html(
    index: int,
    title: str = "",
    text: str = "",
    thumb: str = "",
    url: str = "#",
    date_label: str = "",
) -> str:
    """Génère une carte horizontale pour le journal de bord.
    Layout : vignette à gauche (280px) + texte à droite."""
    thumb_html = f'<img alt="{html_escape(title)}" src="{html_escape(thumb)}"/>' if thumb else ""
    text_html = f'<p>{html_escape(text)}</p>' if text else ""
    return f"""
<article class="journal-card">
    <div class="journal-thumb">
        <span class="journal-badge">{html_escape(date_label)}</span>
        {thumb_html}
    </div>
    <div class="journal-body">
        <h2>{html_escape(title)}</h2>
        {text_html}
        <a class="btn-sm" href="{html_escape(url)}" target="_blank" rel="noopener">Voir la vidéo</a>
    </div>
</article>
"""


def journal_cards_html(entries: List[Dict[str, Any]]) -> str:
    """Génère toutes les cartes du journal."""
    if not entries:
        return (
            '<article class="journal-empty">'
            '<h2>Le journal arrive bientôt</h2>'
            '<p>Les shorts et notes publiés pendant le voyage apparaîtront ici automatiquement.</p>'
            '</article>'
        )
    items = []
    for idx, entry in enumerate(entries, 1):
        items.append(journal_card_html(
            index=idx,
            title=_safe(entry.get("title"), f"Entrée {idx}"),
            text=_truncate(_safe(entry.get("text") or entry.get("date_label") or ""), 220),
            thumb=_safe(entry.get("thumb"), ""),
            url=_safe(entry.get("url"), "#"),
            date_label=_safe(entry.get("date_label"), f"Entrée {idx}"),
        ))
    return "".join(items)


def metrics_html(metrics: List[Dict[str, str]]) -> str:
    """Génère les métriques hero (cartes semi-transparentes du design de référence).
    Chaque item = {label: str, value: str}."""
    return "".join(
        f'<div class="metric"><div class="label">{html_escape(m.get("label", ""))}</div>'
        f'<div class="value">{html_escape(m.get("value", "—"))}</div></div>'
        for m in (metrics or [])
    )


def kpi_html(value: str, label: str) -> str:
    """Génère un bloc KPI hero."""
    return f'<div class="kpi"><strong>{html_escape(value)}</strong><span>{html_escape(label)}</span></div>'


def kpis_html(kpis: List[Dict[str, str]]) -> str:
    """Génère la ligne de KPIs. Chaque item = {value: str, label: str}."""
    return "".join(kpi_html(k.get("value", "—"), k.get("label", "")) for k in (kpis or []))


def faq_html(items: List[Dict[str, str]]) -> str:
    """Génère le bloc FAQ. Chaque item = {question: str, answer: str}."""
    parts = []
    for item in (items or []):
        q = html_escape(item.get("question", ""))
        a = html_escape(item.get("answer", ""))
        parts.append(f"""
<details class="faq-item">
  <summary class="faq-q">{q}</summary>
  <div class="faq-a">{a}</div>
</details>
""")
    return "".join(parts)


def resource_box_html(
    title: str,
    kurviger_href: str = "",
    pdf_href: str = "",
    html_href: str = "",
    qr_src: str = "",
    description: str = "",
    journey_text: str = "",
) -> str:
    """Génère le bloc Ressources + Immersion dans le conteneur .blocs-wrapper.
    
    Utilise les classes de roadbook-blocs.css v3 :
    .res-card, .res-grid, .res-left, .res-btns, .qr-box, .imm-inner
    """
    desc = html_escape(description or "Retrouve ici les ressources utiles du voyage : trace Kurviger, roadbook PDF, version HTML modifiable et accès rapide au journal de bord.")
    
    # Bloc Immersion (intégré dans la carte Ressources)
    imm_html = ""
    if journey_text and journey_text.strip():
        paragraphs = [p.strip() for p in journey_text.strip().split("\n") if p.strip()]
        imm_paragraphs = "".join(f"<p>{html_escape(p)}</p>" for p in paragraphs)
        imm_html = f"""
  <div class="imm-inner">
    <h3>Immersion du voyage</h3>
    <div class="imm-text">{imm_paragraphs}</div>
  </div>"""
    
    return f"""
<div class="res-card">
  <div class="bloc-kicker">Ressources du voyage</div>
  <div class="res-grid">
    <div class="res-left">
      <h3>{html_escape(title or "Préparer et télécharger")}</h3>
      <p>{desc}</p>
      <div class="res-btns">
        <a href="{html_escape(kurviger_href)}" class="btn btn-orange" download>Télécharger la trace Kurviger</a>
        <a href="{html_escape(pdf_href)}" class="btn btn-dark" download>Roadbook PDF</a>
        <a href="{html_escape(html_href)}" class="btn btn-outline" target="_blank" rel="noopener">Roadbook HTML</a>
      </div>
      <p class="res-note">L'itinéraire réel pourra évoluer selon la météo, les imprévus et le terrain.</p>
    </div>
    <div class="qr-box">
      <h4>Scan rapide</h4>
      <img class="qr-img" src="{html_escape(qr_src)}" alt="QR code ressources {html_escape(title)}" loading="lazy">
      <div class="qr-caption">Téléchargement direct</div>
    </div>
  </div>{imm_html}
</div>
"""


# ═══════════════════════════════════════════════════════════════════
#  HELPERS DE DONNÉES (extraction depuis days_data)
# ═══════════════════════════════════════════════════════════════════

def _safe(value: Any, fallback: str = "") -> str:
    return str(value or fallback).strip()


def _truncate(text: str, limit: int = 180) -> str:
    raw = " ".join(str(text or "").split())
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 1)].rstrip() + "…"


def _extract_label(obj: Any) -> str:
    """Extrait un label lisible depuis un objet CsvPoint ou un dict ou une string.

    Gère :
    - CsvPoint (a .description) → nettoyage des préfixes et métadonnées Kurviger
    - dict avec clés 'label', 'name', 'title', 'description'
    - string directe
    """
    if obj is None:
        return ""
    # String directe
    if isinstance(obj, str):
        return obj.strip()
    # Objet CsvPoint (a .description)
    if hasattr(obj, "description"):
        desc = str(getattr(obj, "description", "")).strip()
        if not desc:
            return ""
        import re as _re
        # Retirer "Départ DD mois YYYY JN - "
        desc = _re.sub(r"^Départ\s+\d+\s+\w+\s+\d{4}\s+J\d+\s*[-–]\s*", "", desc, flags=_re.IGNORECASE)
        # Retirer préfixes génériques
        desc = _re.sub(r"^(Couchage|Hébergement|Hebergement)\s+", "", desc, flags=_re.IGNORECASE)
        # Couper au premier | (métadonnées Kurviger : N2, camping, bord de mer, etc.)
        if "|" in desc:
            desc = desc.split("|")[0]
        # Retirer les métadonnées entre parenthèses en fin
        desc = _re.sub(r"\s*\(prix_indicatif[^)]*\)\s*$", "", desc, flags=_re.IGNORECASE)
        # Retirer les codes route isolés en fin (N2, A9, M6, B9005, etc.)
        desc = _re.sub(r"\s+[NABM]\d{1,5}\s*$", "", desc)
        # Retirer les préfixes *xxx (ex: *shuttle_info, *point_de_vue, *Bivouac?)
        desc = _re.sub(r"^\*\w+\s*[-–]?\s*", "", desc)
        return desc.strip(" -–_,;|")
    # Dict
    if isinstance(obj, dict):
        for key in ("label", "name", "title", "description"):
            val = obj.get(key)
            if val and str(val).strip():
                return str(val).strip()
    return str(obj).strip()
    # Dict
    if isinstance(obj, dict):
        for key in ("label", "name", "title", "description"):
            val = obj.get(key)
            if val and str(val).strip():
                return str(val).strip()
    return str(obj).strip()


def _day_title(day: Dict[str, Any], index: int) -> str:
    # 1. Clé titre explicite
    for key in ("title", "label", "name", "stage_title", "heading", "day_title"):
        value = _safe(day.get(key))
        if value:
            return value
    # 2. Objets CsvPoint (sortie directe de build_days)
    start_obj = day.get("start_stage")
    end_obj = day.get("end_stage")
    if start_obj is not None or end_obj is not None:
        start = _extract_label(start_obj)
        end = _extract_label(end_obj)
        if start and end and start != end:
            return f"{start} → {end}"
        return start or end or f"Étape {index}"
    # 3. Clés string classiques (variantes possibles)
    start = _safe(
        day.get("start_name") or day.get("start_city") or day.get("depart_name")
        or day.get("depart") or day.get("start") or day.get("from")
        or day.get("departure") or day.get("ville_depart")
    )
    end = _safe(
        day.get("end_name") or day.get("arrival_name") or day.get("finish_name")
        or day.get("nuit_name") or day.get("nuit") or day.get("arrivee")
        or day.get("end") or day.get("to") or day.get("arrival")
        or day.get("ville_arrivee") or day.get("sleep") or day.get("night")
    )
    if start and end:
        return f"{start} → {end}"
    return start or end or f"Étape {index}"


def _day_subtitle(day: Dict[str, Any], index: int) -> str:
    pieces: List[str] = []
    # 1. Distance — build_days retourne km_total (int en km)
    for key in ("distance_text", "distance_label", "distance_display"):
        value = _safe(day.get(key))
        if value:
            pieces.append(value)
            break
    if not pieces:
        km = day.get("km_total") or day.get("distance_km") or day.get("km") or day.get("distance")
        if km is not None:
            try:
                v = float(km)
                if v > 10000:  # probablement en mètres
                    v = v / 1000.0
                if v > 0:
                    pieces.append(f"{v:.0f} km")
            except (ValueError, TypeError):
                pass
    # 2. Durée — build_days retourne route_time (string "11h24")
    duree = _safe(day.get("route_time") or day.get("duree") or day.get("duration") or day.get("duree_text"))
    if duree:
        try:
            secs = int(float(duree))
            if secs > 3600:
                pieces.append(f"{secs // 3600}h{(secs % 3600) // 60:02d}")
            elif secs > 60:
                pieces.append(f"{secs // 60} min")
        except (ValueError, TypeError):
            # C'est déjà une string formatée comme "11h24"
            pieces.append(duree)
    # 3. Note complémentaire
    end_obj = day.get("end_stage")
    if end_obj is not None:
        note = _extract_label(end_obj)
        # Éviter de répéter si c'est déjà dans le titre
        if note and note not in " ".join(pieces):
            pieces.append(note)
    else:
        note = _safe(
            day.get("night_name") or day.get("sleep_name") or day.get("summary")
            or day.get("nuit") or day.get("arrivee")
        )
        if note and note not in " ".join(pieces):
            pieces.append(note)
    if not pieces:
        pieces.append(f"J{index}")
    return " • ".join(pieces[:2])


def _day_date(day: Dict[str, Any], index: int) -> str:
    for key in ("date_label", "date_display", "date", "day_date", "display_date",
                "date_depart", "date_start", "jour_label"):
        value = _safe(day.get(key))
        if value:
            return value
    jour = day.get("jour") or day.get("day_num") or day.get("day_number")
    if jour:
        return f"Jour {jour}"
    return f"Jour {index}"


def _day_region(day: Dict[str, Any]) -> str:
    """Extrait les régions/pays traversés pour l'affichage timeline."""
    # 1. Clés explicites de régions
    for key in ("regions_label", "regions", "area_label", "areas", "country_label", "countries", "places_label", "places_text"):
        value = day.get(key)
        if isinstance(value, list):
            clean = [str(v).strip() for v in value if str(v).strip()]
            if clean:
                return " • ".join(clean[:3])
        else:
            text = _safe(value)
            if text:
                return _truncate(text, 90)
    
    # 2. Extraire depuis la timeline enrichie
    timeline = day.get("timeline") or []
    regions_set = set()
    for item in timeline:
        region = _safe(item.get("region"))
        country = _safe(item.get("country"))
        if region and region not in regions_set:
            regions_set.add(region)
        if country and country not in regions_set:
            regions_set.add(country)
    if regions_set:
        return " • ".join(list(regions_set)[:3])
    
    # 3. Fallback summary
    summary = _safe(day.get("summary"))
    if summary:
        return _truncate(summary, 90)
    
    return ""


def _day_highlight(day: Dict[str, Any]) -> str:
    """Extrait le point fort / highlight du jour pour l'affichage timeline.
    
    Cherche dans les données enrichies : géologie, must_see, conseil_route, etc.
    """
    # 1. Clés explicites de highlight
    for key in ("highlight", "point_fort", "focus", "must_see_summary"):
        value = _safe(day.get(key))
        if value:
            return _truncate(value, 100)
    
    # 2. Extraire depuis la timeline enrichie (premier point remarquable)
    timeline = day.get("timeline") or []
    for item in timeline:
        # Géologie
        geology = _safe(item.get("geology"))
        if geology and len(geology) > 20:
            return _truncate(geology, 100)
        # Must see
        must_see = _safe(item.get("must_see"))
        if must_see and len(must_see) > 20:
            return _truncate(must_see, 100)
        # Conseil route
        advice = _safe(item.get("advice"))
        if advice and len(advice) > 20:
            return _truncate(advice, 100)
    
    # 3. Chercher dans les clés directes du jour
    for key in ("geology", "geologie", "must_see", "a_ne_pas_rater", "advice", "conseil_route"):
        value = _safe(day.get(key))
        if value and len(value) > 20:
            return _truncate(value, 100)
    
    return ""


def sum_distance_km(days: List[Dict[str, Any]]) -> float:
    total = 0.0
    for day in days or []:
        value = day.get("km_total") or day.get("distance_km") or day.get("km") or day.get("distance")
        try:
            v = float(value or 0)
            if v > 10000:  # probablement en mètres
                v = v / 1000.0
            total += v
        except (ValueError, TypeError):
            pass
    return total


def route_hint(days: List[Dict[str, Any]]) -> str:
    if not days:
        return ""
    first = days[0] or {}
    last = days[-1] or {}
    # Priorité : objets CsvPoint de build_days
    start = _extract_label(first.get("start_stage"))
    end = _extract_label(last.get("end_stage"))
    # Fallback clés string
    if not start:
        start = _safe(
            first.get("start_name") or first.get("start_city") or first.get("depart_name")
            or first.get("depart") or first.get("start")
        )
    if not end:
        end = _safe(
            last.get("end_name") or last.get("arrival_name") or last.get("finish_name")
            or last.get("nuit_name") or last.get("nuit") or last.get("arrivee")
        )
    if start and end:
        return f"{start} → {end}"
    return start or end


def format_km(km: float) -> str:
    """Formate un nombre de km en texte lisible (ex: '10 234 km')."""
    if not km:
        return "Prévisionnel"
    return f"{int(round(km)):,} km".replace(",", " ")


def build_template_data(
    trip_title: str,
    trip_year: int,
    days_data: List[Dict[str, Any]],
    slug: str = "",
    hero_src: str = "",
    qr_src: str = "",
    kurviger_href: str = "",
    pdf_href: str = "",
    html_href: str = "",
    journal_href: str = "",
    journey_text: str = "",
    main_shorts: Optional[List[Dict[str, Any]]] = None,
    journal_entries: Optional[List[Dict[str, Any]]] = None,
    traveler_name: str = "Yves – LCDMH",
    vehicle_label: str = "Honda NT1100",
    kpis: Optional[List[Dict[str, str]]] = None,
    faq_items: Optional[List[Dict[str, str]]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construit le dictionnaire de données complet pour le moteur de templates.

    Toutes les valeurs dynamiques passent par ici — RIEN n'est écrit en dur
    dans le template ni dans le moteur de rendu.
    """
    total_days = len(days_data)
    total_km = sum_distance_km(days_data)
    total_km_label = format_km(total_km)
    route = route_hint(days_data)
    shorts = (main_shorts or [])[:3]
    entries = journal_entries or []

    # KPIs par défaut calculés depuis les données
    if kpis is None:
        kpis = [
            {"value": total_km_label.replace(" km", ""), "label": "km prévus"},
            {"value": str(total_days) if total_days else "—", "label": "jours de road trip"},
            {"value": "Journal", "label": "suivi terrain"},
        ]

    # FAQ par défaut
    if faq_items is None:
        faq_items = [
            {"question": "Quand la série d'épisodes longs sera-t-elle publiée ?",
             "answer": "Les shorts et le journal vivent pendant le voyage. Les épisodes longs arriveront après le retour, au rythme du montage."},
            {"question": "Que contient la page journal ?",
             "answer": "Le journal regroupe les shorts, les notes terrain et les mises à jour du road trip au fil du voyage."},
            {"question": "Les ressources du voyage sont-elles définitives ?",
             "answer": "Non. La trace, le roadbook et les étapes peuvent évoluer selon la météo, les imprévus et le terrain."},
        ]

    # Calcul du budget carburant depuis days_data
    total_fuel_cost = sum(float(d.get("fuel_cost_eur", 0) or 0) for d in days_data)
    total_fuel_liters = round(total_km / 100.0 * 6.5, 1) if total_km else 0  # estimation
    total_nights = sum(int(d.get("nights_after_end", 1) or 1) for d in days_data)

    # Métriques hero (design de référence)
    default_metrics = [
        {"label": "Départ prévu", "value": str(trip_year)},
        {"label": "Objectif voyage", "value": f"{total_days} jours" if total_days else "—"},
        {"label": "Distance", "value": total_km_label},
        {"label": "Journal", "value": "Suivi quotidien"},
    ]

    data = {
        # Identité
        "slug": slug,
        "title": trip_title,
        "page_title": trip_title,
        "trip_year": str(trip_year),
        "traveler_name": traveler_name,
        "vehicle_label": vehicle_label,

        # Métriques
        "total_days": str(total_days),
        "total_days_label": f"{total_days} jours" if total_days else "Prévisionnel",
        "total_km": str(int(round(total_km))) if total_km else "",
        "total_km_label": total_km_label,
        "route_hint": route,

        # Textes
        "journey_text": journey_text,
        "hero_subtitle": route or journey_text[:200] if journey_text else "Préparation du voyage en cours.",

        # URLs / ressources
        "hero_src": hero_src,
        "qr_src": qr_src,
        "kurviger_href": kurviger_href,
        "pdf_href": pdf_href,
        "html_href": html_href,
        "journal_href": journal_href,
        "canonical_url": f"https://lcdmh.com/roadtrips/{slug}.html",
        "og_image": f"https://lcdmh.com{hero_src}" if hero_src else "",

        # Blocs HTML pré-rendus (injectés via {{raw:...}})
        "raw:timeline_html": timeline_html(days_data),
        "raw:metrics_html": metrics_html(default_metrics),
        "raw:short_cards_html": short_cards_html(shorts),
        "raw:journal_cards_html": journal_cards_html(entries),
        "raw:kpis_html": kpis_html(kpis),
        "raw:faq_html": faq_html(faq_items),
        "raw:resource_box_html": resource_box_html(
            title=trip_title,
            kurviger_href=kurviger_href,
            pdf_href=pdf_href,
            html_href=html_href,
            qr_src=qr_src,
        ),

        # Données brutes (pour les boucles {{each:...}} si le template les utilise)
        "days_data": days_data,
        "shorts": shorts,
        "journal_entries": entries,
        "kpis": kpis,
        "faq_items": faq_items,

        # Flags conditionnels
        "has_shorts": bool(shorts),
        "has_journal": bool(entries),
        "has_journey_text": bool(journey_text and journey_text.strip()),
        "has_route": bool(route),
    }

    # Ajouter les données supplémentaires
    if extra:
        data.update(extra)

    return data


# ═══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE PRINCIPAL : render_page
# ═══════════════════════════════════════════════════════════════════

def render_page(
    template_name: str,
    data: Dict[str, Any],
    templates_dir: Optional[Path] = None,
    extra_dirs: Optional[List[Union[str, Path]]] = None,
    trace: Optional[List[str]] = None,
) -> str:
    """Charge un template et le rend avec les données fournies.

    Si trace est fourni, y ajoute les messages de diagnostic pas à pas.
    """
    if trace is None:
        trace = []
    trace.append(f"[RENDER] render_page('{template_name}') appelé")
    trace.append(f"[RENDER]   extra_dirs = {extra_dirs}")
    trace.append(f"[RENDER]   templates_dir = {templates_dir}")
    html = load_template(template_name, templates_dir=templates_dir, extra_dirs=extra_dirs, trace=trace)
    trace.append(f"[RENDER] Résolution des placeholders...")
    result = render(html, data)
    # Vérifier les placeholders non résolus
    import re as _re
    remaining = _re.findall(r'\{\{(?!if:|endif:|each:|endeach:)[^}]+\}\}', result)
    if remaining:
        trace.append(f"[RENDER] ⚠️  Placeholders non résolus : {remaining[:10]}")
    else:
        trace.append(f"[RENDER] ✅ Tous les placeholders résolus")
    trace.append(f"[RENDER] HTML final : {len(result)} caractères")
    return result
