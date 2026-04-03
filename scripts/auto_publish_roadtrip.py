# -*- coding: utf-8 -*-
"""Surcouche roadbook LCDMH — v2 avec moteur de templates.

Changements par rapport à l'ancienne version :
- TOUT le rendu HTML passe par lcdmh_template_engine (placeholders {{...}})
- Plus aucun HTML écrit en dur dans ce fichier
- Plus de BeautifulSoup pour manipuler les templates
- Les templates sont dans le dossier templates/ et sont modifiables librement
- Toutes les pages (principale, journal, PDF) s'appuient sur le même moteur

Architecture :
    page_generateur_roadbook.py
        ├── lcdmh_template_engine.py    (moteur de templates)
        ├── templates/
        │   ├── template_roadtrip_principal.html
        │   ├── template_journal.html
        │   └── template_pdf_printable.html
        ├── page_generateur_roadbook_base.py  (moteur métier CSV/enrichissement)
        └── ai_studio_code.py                (PDF HTML→PDF)
"""
from __future__ import annotations

try:
    from publish_site_to_github import verify_publish_tree, publish_site_to_github
    GITHUB_PUBLISH_AVAILABLE = True
    GITHUB_PUBLISH_IMPORT_ERROR = ""
except Exception as _github_import_exc:  # pragma: no cover
    verify_publish_tree = None  # type: ignore[assignment]
    publish_site_to_github = None  # type: ignore[assignment]
    GITHUB_PUBLISH_AVAILABLE = False
    GITHUB_PUBLISH_IMPORT_ERROR = str(_github_import_exc)

import importlib.util
import io
import csv
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ═══ Import du moteur de templates ═══
try:
    import lcdmh_template_engine as tpl
except ImportError:
    # Si le module n'est pas dans sys.path, on le charge depuis le même dossier
    _tpl_path = Path(__file__).resolve().parent / "lcdmh_template_engine.py"
    if _tpl_path.exists():
        _spec = importlib.util.spec_from_file_location("lcdmh_template_engine", _tpl_path)
        tpl = importlib.util.module_from_spec(_spec)
        sys.modules["lcdmh_template_engine"] = tpl
        _spec.loader.exec_module(tpl)
    else:
        raise ImportError(
            f"lcdmh_template_engine.py introuvable dans {_tpl_path.parent}. "
            "Placez-le à côté de page_generateur_roadbook.py."
        )

try:
    import streamlit as st
except Exception:  # pragma: no cover
    class _StreamlitFallback:
        def __getattr__(self, name):
            raise RuntimeError("Streamlit est requis pour utiliser page_generateur_roadbook().")
    st = _StreamlitFallback()

MODULE_DIR = Path(__file__).resolve().parent
BASE_PATH = MODULE_DIR / "page_generateur_roadbook_base.py"
AI_CANDIDATES = [
    MODULE_DIR / "ai_studio_code.py",
    MODULE_DIR / "ai_studio_code_v2.py",
    MODULE_DIR / "ai_studio_code_nouveau.py",
    MODULE_DIR / "ai_studio_code_v3.py",
]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RB_BASE = _load_module(BASE_PATH, "page_generateur_roadbook_base_runtime")

_TEMPLATE_PATH = next((p for p in AI_CANDIDATES if p.exists()), None)
if _TEMPLATE_PATH is None:
    raise FileNotFoundError(
        f"Aucun template AI studio trouvé dans {MODULE_DIR}. "
        "Noms acceptés : ai_studio_code.py, ai_studio_code_v2.py, ai_studio_code_nouveau.py, ai_studio_code_v3.py"
    )
AI = _load_module(_TEMPLATE_PATH, "ai_studio_code_runtime")

DEFAULT_WORK_ROOT = MODULE_DIR / "_site_test"
DEFAULT_PUBLISH_ROOT = Path(r"F:\LCDMH")
DEFAULT_GITHUB_REPO = Path(r"F:\LCDMH_GitHub_Audit")


# ═══════════════════════════════════════════════════════════════════
#  UTILITAIRES GÉNÉRAUX (inchangés)
# ═══════════════════════════════════════════════════════════════════

def _slug(text: str) -> str:
    s = AI.slugify(text)
    # Nettoyer le prefixe "roadtrips" si present (bug doublon Dashboard)
    if s.startswith("roadtrips"):
        s = s[len("roadtrips"):].lstrip("-")
    return s


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _copy_if_needed(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return dst
    shutil.copy2(src, dst)
    return dst


def _copy_tree(src: Path, dst: Path) -> List[Path]:
    copied: List[Path] = []
    if src.is_dir():
        for file_path in src.rglob("*"):
            if not file_path.is_file():
                continue
            target = dst / file_path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, target)
            copied.append(target)
        return copied
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.append(dst)
    return copied


# ═══════════════════════════════════════════════════════════════════
#  PUBLICATION (inchangé)
# ═══════════════════════════════════════════════════════════════════

def _publish_plan(work_root: Path, slug: str) -> List[Dict[str, Path]]:
    plan: List[Dict[str, Path]] = []
    candidates = [
        (work_root / "roadtrips" / f"{slug}.html", Path("roadtrips") / f"{slug}.html", "page principale"),
        (work_root / "roadtrips" / f"{slug}-journal.html", Path("roadtrips") / f"{slug}-journal.html", "journal"),
        (work_root / "roadtrips" / "css", Path("roadtrips") / "css", "css template"),
        (work_root / "images" / "roadtrips" / slug, Path("images") / "roadtrips" / slug, "images"),
        (work_root / "kurviger", Path("kurviger"), "traces kurviger"),
        (work_root / "roadbooks" / f"{slug}-roadbook.pdf", Path("roadbooks") / f"{slug}-roadbook.pdf", "pdf"),
        (work_root / "roadbooks-html" / slug, Path("roadbooks-html") / slug, "roadbook html"),
        (work_root / "data" / "roadtrips" / slug, Path("data") / "roadtrips" / slug, "données"),
    ]
    for src, rel_dst, label in candidates:
        if src.exists():
            plan.append({"src": src, "rel_dst": rel_dst, "label": label})
    return plan


def _update_navigation_menu(nav_path: Path, trip_title: str, slug: str) -> Dict[str, str]:
    href = f"roadtrips/{slug}.html"
    legacy_href = f"{slug}.html"
    if not nav_path.exists():
        return {"ok": False, "message": f"nav.html introuvable : {nav_path}"}
    raw = nav_path.read_text(encoding="utf-8")
    new_raw = raw.replace(f'href="{legacy_href}"', f'href="{href}"')
    if href in new_raw:
        if new_raw != raw:
            backup = nav_path.with_suffix(nav_path.suffix + ".bak")
            shutil.copy2(nav_path, backup)
            nav_path.write_text(new_raw, encoding="utf-8")
            return {"ok": True, "message": f"Menu corrigé dans {nav_path}"}
        return {"ok": True, "message": "Lien déjà présent dans le menu."}
    item = f'    <li class="lcdmh-auto-roadtrip"><a href="{href}">{escape(trip_title)}</a></li>\n'
    backup = nav_path.with_suffix(nav_path.suffix + ".bak")
    shutil.copy2(nav_path, backup)
    start_marker = "<!-- LCDMH_AUTO_ROADTRIPS_START -->"
    end_marker = "<!-- LCDMH_AUTO_ROADTRIPS_END -->"
    if start_marker in new_raw and end_marker in new_raw:
        start = new_raw.index(start_marker) + len(start_marker)
        end = new_raw.index(end_marker)
        block = new_raw[start:end]
        if href not in block:
            block = block.rstrip() + "\n" + item
        new_raw = new_raw[:start] + "\n" + block.strip("\n") + "\n" + new_raw[end:]
    else:
        insert_at = new_raw.lower().rfind("</ul>")
        if insert_at != -1:
            new_raw = new_raw[:insert_at] + item + new_raw[insert_at:]
        else:
            insert_at = new_raw.lower().rfind("</nav>")
            if insert_at != -1:
                new_raw = new_raw[:insert_at] + "<ul>\n" + item + "</ul>\n" + new_raw[insert_at:]
            else:
                new_raw = new_raw + "\n<ul>\n" + item + "</ul>\n"
    nav_path.write_text(new_raw, encoding="utf-8")
    return {"ok": True, "message": f"Menu mis à jour dans {nav_path}"}


def publish_generated_roadtrip(
    work_root: str | Path,
    publish_root: str | Path,
    slug: str,
    trip_title: str,
    update_navigation: bool = False,
) -> Dict[str, Any]:
    work_root = Path(work_root).expanduser().resolve()
    publish_root = Path(publish_root).expanduser().resolve()
    result: Dict[str, Any] = {"ok": False, "copied": [], "warnings": [], "publish_trace": []}
    trace = result["publish_trace"]
    trace.append(f"[PUBLISH] work_root = {work_root}")
    trace.append(f"[PUBLISH] publish_root = {publish_root}")
    trace.append(f"[PUBLISH] slug = {slug}")
    trace.append(f"[PUBLISH] work_root existe : {work_root.exists()}")
    trace.append(f"[PUBLISH] publish_root existe : {publish_root.exists()}")
    if not work_root.exists():
        result["message"] = f"Dossier de travail introuvable : {work_root}"
        return result
    plan = _publish_plan(work_root, slug)
    trace.append(f"[PUBLISH] Plan de publication : {len(plan)} entrée(s)")
    if not plan:
        result["message"] = "Aucun fichier publiable trouvé dans le dossier de travail."
        trace.append(f"[PUBLISH] ❌ Aucun fichier trouvé — vérifier les chemins dans _publish_plan")
        # Lister ce qui existe pour debug
        for d in ["roadtrips", "images", "kurviger", "roadbooks", "roadbooks-html", "data"]:
            p = work_root / d
            trace.append(f"[PUBLISH]   {p} → {'existe' if p.exists() else 'ABSENT'}")
        return result
    copied_paths: List[str] = []
    for item in plan:
        src = item["src"]
        dst = publish_root / item["rel_dst"]
        trace.append(f"[PUBLISH]   {item.get('label','?')}: {src} → {dst}")
        trace.append(f"[PUBLISH]     src existe : {src.exists()}")
        copied = _copy_tree(src, dst)
        trace.append(f"[PUBLISH]     fichiers copiés : {len(copied)}")
        copied_paths.extend(str(p.resolve()) for p in copied)
    nav_result = None
    if update_navigation:
        nav_result = _update_navigation_menu(publish_root / "nav.html", trip_title=trip_title, slug=slug)
        if not nav_result.get("ok"):
            result["warnings"].append(nav_result.get("message", "Échec mise à jour menu."))
    result["ok"] = True
    result["copied"] = copied_paths
    result["message"] = f"Publication terminée vers {publish_root} ({len(copied_paths)} fichier(s))"
    trace.append(f"[PUBLISH] ✅ Total : {len(copied_paths)} fichier(s) copiés")
    if nav_result and nav_result.get("ok"):
        result["nav_message"] = nav_result.get("message", "")
    return result


# ═══════════════════════════════════════════════════════════════════
#  DÉTECTION DES FICHIERS PROJET (inchangé)
# ═══════════════════════════════════════════════════════════════════

def _detect_default_publish_root() -> Path:
    return DEFAULT_PUBLISH_ROOT if DEFAULT_PUBLISH_ROOT.exists() else DEFAULT_WORK_ROOT.parent


def _detect_default_work_root() -> Path:
    return DEFAULT_WORK_ROOT


def _detect_project_files(project_dir: Path) -> Dict[str, Optional[Path]]:
    found: Dict[str, Optional[Path]] = {
        "hero": None, "qr": None, "kurviger": None,
        "csv": None, "pdf": None, "html_index": None,
    }
    files = [p for p in project_dir.rglob("*") if p.is_file()]

    def pick(candidates, keywords=None, exts=None, exclude_keywords=None):
        matches = []
        for p in candidates:
            name = p.name.lower()
            suffix = p.suffix.lower()
            if exts and suffix not in exts:
                continue
            if exclude_keywords and any(k in name for k in exclude_keywords):
                continue
            score = 0
            if keywords:
                for k in keywords:
                    if k in name:
                        score += 10
            if suffix in {".jpg", ".jpeg", ".webp"}:
                score += 3
            if suffix == ".png":
                score += 1
            matches.append((score, p))
        if not matches:
            return None
        matches.sort(key=lambda x: (-x[0], x[1].name.lower()))
        return matches[0][1]

    images = [p for p in files if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    pngs = [p for p in images if p.suffix.lower() == ".png"]

    found["qr"] = (
        pick(pngs, keywords=["qr", "qrcode"])
        or pick(pngs)
        or pick(images, keywords=["qr", "qrcode"])
    )
    found["hero"] = (
        pick(images, keywords=["hero", "bandeau", "cover", "header", "banner"], exts={".jpg", ".jpeg", ".webp"}, exclude_keywords=["qr", "qrcode"])
        or pick([p for p in images if p.suffix.lower() in {".jpg", ".jpeg", ".webp"}], exclude_keywords=["qr", "qrcode"])
        or pick(images, exclude_keywords=["qr", "qrcode"])
    )
    found["kurviger"] = pick(files, keywords=["kurviger", "trace", "route"], exts={".kurviger"})
    found["csv"] = pick(files, keywords=["kurviger", "trace", "route", "roadbook"], exts={".csv"})
    found["pdf"] = pick(files, keywords=["roadbook", "guide", "pdf"], exts={".pdf"})
    htmls = [p for p in files if p.suffix.lower() == ".html" and p.name.lower() == "index.html"]
    found["html_index"] = htmls[0] if htmls else None
    return found


def _validate_resources(detected: Dict[str, Optional[Path]]) -> List[str]:
    errors: List[str] = []
    if not detected.get("csv"):
        errors.append("Aucun CSV Kurviger détecté dans le dossier projet.")
    if not detected.get("kurviger"):
        errors.append("Aucune trace .kurviger détectée dans le dossier projet.")
    if not detected.get("hero"):
        errors.append("Aucune image bandeau (JPG/JPEG/WEBP) détectée dans le dossier projet.")
    if not detected.get("qr"):
        errors.append("Aucun QR code PNG détecté dans le dossier projet.")
    return errors


def _precheck_csv(points: List[Any]) -> List[str]:
    business = [p for p in points if getattr(p, "symbol", "") in {"⚐", "Ⓢ", "Ⓥ", "⚑"}]
    if not business:
        return ["Aucun point métier (⚐ Ⓢ Ⓥ ⚑) trouvé dans le CSV."]
    starts = [p for p in business if getattr(p, "symbol", "") == "⚐"]
    if not starts:
        return ["Aucun point ⚐ trouvé dans le CSV."]
    start = starts[0]
    next_end = next((p for p in business if p.row_num > start.row_num and getattr(p, "symbol", "") in {"Ⓥ", "⚑"}), None)
    if next_end is None:
        return [f"Aucun point Ⓥ ou ⚑ trouvé après le point de départ ligne {start.row_num}."]
    return []


def _public_warning_filter(warnings: List[str]) -> List[str]:
    blocked_prefixes = ("[fin manquante]", "[multi-départs]", "[date départ]")
    return [w for w in warnings if not any(w.startswith(prefix) for prefix in blocked_prefixes)]


# ═══════════════════════════════════════════════════════════════════
#  YOUTUBE HELPERS (inchangés — copie exacte de l'original)
# ═══════════════════════════════════════════════════════════════════

def _extract_youtube_id(url_or_id: str) -> str:
    text = (url_or_id or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
        r"(?:live/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return text


def _youtube_watch_url(url_or_id: str) -> str:
    text = (url_or_id or "").strip()
    if not text:
        return ""
    video_id = _extract_youtube_id(text)
    if video_id and len(video_id) == 11:
        return f"https://www.youtube.com/watch?v={video_id}"
    return text


def _youtube_thumb(url_or_id: str) -> str:
    video_id = _extract_youtube_id(url_or_id)
    if not video_id:
        return ""
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def _fetch_youtube_title(url_or_id: str, timeout: int = 10) -> str:
    video_id = _extract_youtube_id(url_or_id)
    if not video_id or len(video_id) != 11:
        return ""
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    # Essai 1 : oembed YouTube officiel
    for attempt in range(2):
        endpoint = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({"url": canonical_url, "format": "json"})
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0 (compatible; LCDMH/1.0)"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            title = str((payload.get("title") if isinstance(payload, dict) else "") or "").strip()
            if title:
                return title
        except Exception:
            if attempt == 0:
                import time; time.sleep(1)
                continue
            break
    # Essai 2 : noembed.com comme fallback
    try:
        noembed_url = "https://noembed.com/embed?" + urllib.parse.urlencode({"url": canonical_url})
        req = urllib.request.Request(noembed_url, headers={"User-Agent": "Mozilla/5.0 (compatible; LCDMH/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        title = str((payload.get("title") if isinstance(payload, dict) else "") or "").strip()
        if title:
            return title
    except Exception:
        pass
    return ""


def _api_fetch_video_meta(video_id: str) -> Dict[str, str]:
    """Récupère titre + description d'une vidéo via l'API YouTube Data v3.
    
    Utilise le même service que le panneau playlists (_get_youtube_api_service).
    Retourne {"title": "...", "description": "...", "author_name": "...", "published_at": "..."} ou dict vide.
    """
    if not video_id or len(video_id) != 11:
        return {}
    try:
        service = _get_youtube_api_service()
        resp = service.videos().list(
            part="snippet",
            id=video_id,
            maxResults=1,
        ).execute()
        items = resp.get("items") or []
        if not items:
            return {}
        snippet = items[0].get("snippet", {})
        title = str(snippet.get("title", "")).strip()
        description = str(snippet.get("description", "")).strip()
        author = str(snippet.get("channelTitle", "")).strip()
        published = str(snippet.get("publishedAt", "")).strip()[:10]
        if title:
            return {
                "title": title,
                "description": description,
                "author_name": author,
                "published_at": published,
            }
    except Exception:
        pass
    return {}


def _fetch_youtube_meta(url_or_id: str, timeout: int = 10) -> Dict[str, str]:
    """Récupère titre, description et auteur d'une vidéo YouTube.
    
    Cascade de sources :
    1. API YouTube Data v3 (titre + description complète + date)
    2. oembed YouTube (titre + auteur seulement)
    3. noembed.com (titre + auteur seulement)
    
    Retourne {"title": "...", "description": "...", "author_name": "...", "published_at": "..."} ou dict vide.
    """
    video_id = _extract_youtube_id(url_or_id)
    if not video_id or len(video_id) != 11:
        return {}

    # ═══ Essai 1 : API YouTube Data v3 (donne titre + description complète) ═══
    api_meta = _api_fetch_video_meta(video_id)
    if api_meta.get("title"):
        return api_meta

    # ═══ Essai 2 : oembed YouTube (titre + auteur, pas de description) ═══
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    for attempt in range(2):
        endpoint = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({"url": canonical_url, "format": "json"})
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0 (compatible; LCDMH/1.0)"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if isinstance(payload, dict) and payload.get("title"):
                return {
                    "title": str(payload.get("title", "")).strip(),
                    "description": "",
                    "author_name": str(payload.get("author_name", "")).strip(),
                    "published_at": "",
                }
        except Exception:
            if attempt == 0:
                import time; time.sleep(1)
                continue
            break

    # ═══ Essai 3 : noembed.com fallback ═══
    try:
        noembed_url = "https://noembed.com/embed?" + urllib.parse.urlencode({"url": canonical_url})
        req = urllib.request.Request(noembed_url, headers={"User-Agent": "Mozilla/5.0 (compatible; LCDMH/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        if isinstance(payload, dict) and payload.get("title"):
            return {
                "title": str(payload.get("title", "")).strip(),
                "description": "",
                "author_name": str(payload.get("author_name", "")).strip(),
                "published_at": "",
            }
    except Exception:
        pass
    return {}


_MOIS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _format_date_fr(date_str: str) -> str:
    """Formate une date ISO (2025-05-16) en français (16 mai 2025).
    Retourne la chaîne originale si le parsing échoue."""
    text = (date_str or "").strip()[:10]
    if not text:
        return ""
    try:
        parts = text.split("-")
        if len(parts) == 3:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            if 1 <= month <= 12:
                return f"{day} {_MOIS_FR[month]} {year}"
    except (ValueError, IndexError):
        pass
    return text


def _extract_place_from_title(title: str) -> str:
    """Extrait un nom de lieu court depuis un titre YouTube.
    
    Exemples :
      "Enfin la journée se termine ! Campement installé à Lidesnes" → "Lidesnes"
      "Aalborg Danemark : je trinque à votre santé en moto !" → "Aalborg"
      "16 mai 2025 : Le jour J de mon road trip de 11 000 km vers le Cap Nord !" → "Cap Nord"
      "Road Trip Cap Nord #11 Honda NT1100" → "Cap Nord"
    """
    text = (title or "").strip()
    if not text:
        return ""
    
    # Stratégie 1 : "... à LIEU" ou "... vers LIEU" (dernière occurrence)
    for prep in [" à ", " vers ", " direction ", " arrivée à ", " installé à "]:
        idx = text.lower().rfind(prep.lower())
        if idx >= 0:
            after = text[idx + len(prep):].strip()
            # Prendre les mots qui commencent par une majuscule + ce qui suit
            words = after.split()
            place_words = []
            for w in words:
                # Nettoyer la ponctuation de fin
                clean = w.rstrip("!?.,;:-#")
                if not clean:
                    break
                # Accepter les mots capitalisés ou courts connecteurs (de, du, le, la)
                if clean[0].isupper() or clean.lower() in {"de", "du", "le", "la", "les", "des", "l'", "d'", "en"}:
                    place_words.append(clean)
                else:
                    break
            if place_words:
                return " ".join(place_words)
    
    # Stratégie 2 : Premier mot capitalisé avant ":" ou "-" (souvent le lieu)
    for sep in [":", " -", " –"]:
        if sep in text:
            before = text.split(sep)[0].strip()
            # Ignorer les dates en début
            if re.match(r"^\d{1,2}\s+\w+\s+\d{4}$", before):
                continue
            # Prendre les mots capitalisés
            words = before.split()
            place_words = [w.rstrip("!?.,;") for w in words 
                          if w[0:1].isupper() and not w.rstrip("!?.,;").isdigit()
                          and w.lower() not in {"enfin", "road", "trip", "moto", "honda", "le", "la", "mon", "je"}]
            if place_words and len(place_words) <= 3:
                return " ".join(place_words)
    
    return ""


def _parse_video_lines(raw: str, try_fetch_title: bool = False) -> List[Dict[str, str]]:
    videos: List[Dict[str, str]] = []
    fetch_failures: List[str] = []
    for idx, line in enumerate((raw or "").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        url = parts[0] if len(parts) > 0 else ""
        manual_title = parts[1] if len(parts) > 1 else ""
        text_value = parts[2] if len(parts) > 2 else ""
        date_value = parts[3] if len(parts) > 3 else ""
        auto_title = ""
        auto_description = ""
        auto_author = ""
        auto_date = ""
        if try_fetch_title:
            meta = _fetch_youtube_meta(url)
            auto_title = meta.get("title", "")
            auto_description = meta.get("description", "")
            auto_author = meta.get("author_name", "")
            auto_date = meta.get("published_at", "")
            if not auto_title and not manual_title:
                fetch_failures.append(f"⚠️ Impossible de récupérer le titre YouTube pour : {url}")
        title = manual_title or auto_title or f"Vidéo {idx}"
        # Description : priorité au texte saisi, sinon description API (tronquée), sinon auteur
        if not text_value:
            if auto_description:
                # Prendre la première ligne significative de la description (avant les liens/hashtags)
                desc_lines = [l.strip() for l in auto_description.splitlines() if l.strip()]
                clean_desc = ""
                for dl in desc_lines:
                    # Ignorer les lignes qui commencent par des liens, hashtags ou emojis de section
                    if dl.startswith(("http", "#", "🎬", "📍", "👉", "🔔", "📱", "💬", "🎵", "📸")):
                        continue
                    clean_desc = dl
                    break
                text_value = clean_desc or auto_author
            elif auto_author:
                text_value = auto_author
        # Date : priorité à la date saisie, sinon date API formatée en français
        # + lieu extrait du titre pour le badge
        effective_title = title if title != f"Vidéo {idx}" else ""
        place = _extract_place_from_title(effective_title)
        if date_value:
            date_formatted = _format_date_fr(date_value) or date_value
        elif auto_date:
            date_formatted = _format_date_fr(auto_date) or auto_date
        else:
            date_formatted = ""
        # Construire le badge : "16 mai 2025 · Lidesnes" ou juste la date ou juste le lieu
        if date_formatted and place:
            date_label = f"{date_formatted} · {place}"
        elif date_formatted:
            date_label = date_formatted
        elif place:
            date_label = place
        else:
            date_label = f"Vidéo {idx}"
        videos.append({
            "url": _youtube_watch_url(url),
            "title": title,
            "text": text_value,
            "date_label": date_label,
            "thumb": _youtube_thumb(url),
            "youtube_id": _extract_youtube_id(url),
            "title_auto": auto_title,
            "description_auto": auto_description,
            "fetch_failures": "; ".join(fetch_failures) if fetch_failures else "",
        })
    return videos


# ═══════════════════════════════════════════════════════════════════
#  YOUTUBE PLAYLIST HELPERS (inchangés — inclure seulement les fonctions
#  utilisées par _render_youtube_playlist_panel)
# ═══════════════════════════════════════════════════════════════════

def _coalesce_str(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        s = str(value).strip()
        if s:
            return s
    return ""


def _bool_from_any(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "oui", "short", "shorts"}:
        return True
    if s in {"0", "false", "no", "non", "long", "video"}:
        return False
    return None


def _date_label_from_value(value: Any) -> str:
    s = _coalesce_str(value)
    return s[:10] if len(s) >= 10 else s


def _extract_playlist_id(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        parsed = urllib.parse.urlparse(text)
        if parsed.scheme and parsed.netloc:
            qs = urllib.parse.parse_qs(parsed.query)
            playlist_id = (qs.get("list") or [""])[0].strip()
            if playlist_id:
                return playlist_id
    except Exception:
        pass
    return text if re.fullmatch(r"[A-Za-z0-9_-]{10,}", text) else ""


def _iso8601_duration_seconds(value: str) -> int:
    text = (value or "").strip().upper()
    if not text or not text.startswith("P"):
        return 0
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        text,
    )
    if not match:
        return 0
    return (int(match.group("days") or 0) * 86400 +
            int(match.group("hours") or 0) * 3600 +
            int(match.group("minutes") or 0) * 60 +
            int(match.group("seconds") or 0))


def _thumbnail_from_snippet(snippet: Dict[str, Any]) -> str:
    thumbs = snippet.get("thumbnails") or {}
    for key in ["maxres", "standard", "high", "medium", "default"]:
        url = _coalesce_str((thumbs.get(key) or {}).get("url"))
        if url:
            return url
    return ""


def _video_entry_from_mapping(item: Dict[str, Any], playlist_name: str = "") -> Optional[Dict[str, Any]]:
    url = _coalesce_str(item.get("url"), item.get("video_url"), item.get("link"), item.get("watch_url"))
    video_id = _coalesce_str(item.get("video_id"), item.get("id"))
    if not url and video_id:
        url = _youtube_watch_url(video_id)
    if not url:
        return None
    is_short = _bool_from_any(item.get("is_short"))
    if is_short is None:
        duration_s = _iso8601_duration_seconds(_coalesce_str(item.get("duration"), item.get("video_duration")))
        is_short = (duration_s <= 70) if duration_s > 0 else ("/shorts/" in url)
    title = _coalesce_str(item.get("title"), item.get("video_title")) or _fetch_youtube_title(url) or "Vidéo YouTube"
    description = _coalesce_str(item.get("description"), item.get("summary"), item.get("text"), item.get("video_description"))
    playlist = _coalesce_str(playlist_name, item.get("playlist"), item.get("playlist_name"), item.get("playlist_title"), item.get("collection")) or "Sans playlist"
    published = _date_label_from_value(item.get("published_at") or item.get("date") or item.get("published") or item.get("upload_date") or item.get("video_published_at"))
    thumb = _coalesce_str(item.get("thumbnail"), item.get("thumb"), item.get("thumbnail_url")) or _youtube_thumb(url)
    return {
        "playlist": playlist,
        "url": _youtube_watch_url(url),
        "title": title,
        "text": description,
        "date_label": published or playlist,
        "thumb": thumb,
        "is_short": bool(is_short),
    }


def _load_playlists_from_json(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    playlists: Dict[str, List[Dict[str, Any]]] = {}

    def add_item(playlist_name: str, mapping: Dict[str, Any]) -> None:
        entry = _video_entry_from_mapping(mapping, playlist_name=playlist_name)
        if entry:
            playlists.setdefault(entry["playlist"], []).append(entry)

    if isinstance(raw, dict):
        if isinstance(raw.get("playlists"), list):
            for playlist_obj in raw["playlists"]:
                if not isinstance(playlist_obj, dict):
                    continue
                pname = _coalesce_str(playlist_obj.get("title"), playlist_obj.get("name")) or "Sans playlist"
                videos = playlist_obj.get("videos") or playlist_obj.get("items") or []
                if isinstance(videos, list):
                    for item in videos:
                        if isinstance(item, dict):
                            add_item(pname, item)
        elif isinstance(raw.get("playlists"), dict):
            for pname, items in raw["playlists"].items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            add_item(str(pname), item)
        elif isinstance(raw.get("videos"), list):
            for item in raw["videos"]:
                if isinstance(item, dict):
                    add_item("", item)
        else:
            for key, value in raw.items():
                if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
                    for item in value:
                        add_item(str(key), item)
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                add_item("", item)
    return playlists


def _load_playlists_from_csv(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    playlists: Dict[str, List[Dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not isinstance(row, dict):
                continue
            entry = _video_entry_from_mapping(row)
            if entry:
                playlists.setdefault(entry["playlist"], []).append(entry)
    return playlists


def _load_playlists(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    return _load_playlists_from_csv(path) if path.suffix.lower() == ".csv" else _load_playlists_from_json(path)


def _entry_to_line(entry: Dict[str, Any]) -> str:
    return "|".join([
        _coalesce_str(entry.get("url")),
        _coalesce_str(entry.get("title")),
        _coalesce_str(entry.get("text")),
        _coalesce_str(entry.get("date_label")),
    ])


def _playlist_source_candidates(project_dir: Path, publish_root: Path, repo_path: Path) -> List[Path]:
    candidates: List[Path] = []
    patterns = ["videos.json", "data/videos.json", "playlists.json", "youtube_playlists.json", "playlists.csv", "youtube_playlists.csv"]
    for base in [project_dir, publish_root, repo_path]:
        try:
            root = Path(base)
        except Exception:
            continue
        for rel in patterns:
            path = root / rel
            if path.exists() and path not in candidates:
                candidates.append(path)
    return candidates


def _get_youtube_api_service() -> Any:
    errors: List[str] = []
    try:
        import page_gestion_playlists as _pgp
        if hasattr(_pgp, "_get_service"):
            return _pgp._get_service()
    except Exception as exc:
        errors.append(f"gestion playlists: {exc}")
    try:
        import page_publication_youtube as _ppy
        if hasattr(_ppy, "_get_service"):
            return _ppy._get_service()
    except Exception as exc:
        errors.append(f"publication YouTube: {exc}")
    raise RuntimeError(f"Impossible d'ouvrir l'API YouTube : {' | '.join(errors) if errors else 'aucune passerelle'}")


def _api_list_playlists() -> List[Dict[str, Any]]:
    try:
        import page_publication_youtube as _ppy
        if hasattr(_ppy, "_charger_playlists"):
            items = _ppy._charger_playlists()
            return [{"id": str(item.get("id", "")), "title": str(item.get("title", "")).strip(), "itemCount": int(item.get("itemCount", 0) or 0)} for item in items if str(item.get("id", "")).strip() and str(item.get("title", "")).strip()]
    except Exception:
        pass
    try:
        import page_gestion_playlists as _pgp
        if hasattr(_pgp, "_charger_donnees_chaine"):
            df_playlists, _ = _pgp._charger_donnees_chaine()
            if hasattr(df_playlists, "to_dict"):
                rows = df_playlists.to_dict(orient="records")
                return [{"id": str(row.get("playlist_id", "")).strip(), "title": str(row.get("playlist_title", "")).strip(), "itemCount": int(row.get("item_count", 0) or 0)} for row in rows if str(row.get("playlist_id", "")).strip() and str(row.get("playlist_title", "")).strip()]
    except Exception:
        pass
    return []


def _api_fetch_playlist_title(playlist_id: str) -> str:
    service = _get_youtube_api_service()
    resp = service.playlists().list(part="snippet", id=playlist_id, maxResults=1).execute()
    items = resp.get("items", []) or []
    if not items:
        return playlist_id
    return _coalesce_str(items[0].get("snippet", {}).get("title")) or playlist_id


def _api_fetch_playlist_videos(playlist_id: str, playlist_title: str = "") -> List[Dict[str, Any]]:
    service = _get_youtube_api_service()
    if not playlist_title:
        playlist_title = _api_fetch_playlist_title(playlist_id)
    items: List[Dict[str, Any]] = []
    token = None
    while True:
        resp_items = service.playlistItems().list(part="snippet,contentDetails", playlistId=playlist_id, maxResults=50, pageToken=token).execute()
        items.extend(resp_items.get("items", []) or [])
        token = resp_items.get("nextPageToken")
        if not token:
            break
    video_ids = [_coalesce_str(item.get("contentDetails", {}).get("videoId")) for item in items]
    video_ids = [v for v in video_ids if v]
    item_map = {_coalesce_str(item.get("contentDetails", {}).get("videoId")): item for item in items}
    videos_meta: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        if not chunk:
            continue
        resp_v = service.videos().list(part="snippet,contentDetails,status", id=",".join(chunk), maxResults=50).execute()
        for v in resp_v.get("items", []) or []:
            videos_meta[str(v.get("id", ""))] = v
    out: List[Dict[str, Any]] = []
    for vid in video_ids:
        item = item_map.get(vid, {})
        meta = videos_meta.get(vid, {})
        snippet = meta.get("snippet", {})
        content = meta.get("contentDetails", {})
        position = int(item.get("snippet", {}).get("position", 0) or 0)
        duration_s = _iso8601_duration_seconds(_coalesce_str(content.get("duration")))
        out.append({
            "playlist": playlist_title,
            "url": _youtube_watch_url(vid),
            "title": _coalesce_str(snippet.get("title"), item.get("snippet", {}).get("title")) or f"Vidéo {position + 1}",
            "text": _coalesce_str(snippet.get("description")),
            "date_label": _date_label_from_value(_coalesce_str(snippet.get("publishedAt"))),
            "thumb": _thumbnail_from_snippet(snippet) or _youtube_thumb(vid),
            "is_short": duration_s > 0 and duration_s <= 70,
            "position": position,
        })
    out.sort(key=lambda entry: int(entry.get("position", 0)))
    return out


def _playlist_trigger_dir(project_dir: str | Path) -> Path:
    return Path(project_dir).expanduser() / "build" / "_playlist_triggers"


# ═══════════════════════════════════════════════════════════════════
#  INJECTION VIDÉO DIRECTE DANS LE JOURNAL HTML
# ═══════════════════════════════════════════════════════════════════

def _format_date_fr(dt: datetime = None) -> str:
    """Formate une date en français majuscules (ex: 25 MARS 2026)."""
    mois_fr = ['', 'JANVIER', 'FÉVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN',
               'JUILLET', 'AOÛT', 'SEPTEMBRE', 'OCTOBRE', 'NOVEMBRE', 'DÉCEMBRE']
    if dt is None:
        dt = datetime.now()
    return f"{dt.day} {mois_fr[dt.month]} {dt.year}"


def _generate_journal_entry_html(video_info: Dict[str, Any], date_label: str = "") -> str:
    """Genere le HTML d'une entree journal au format LCDMH.
    
    Structure reelle du template :
    .journal-card (grid 2 colonnes) > .journal-thumb(.journal-badge + img) + .journal-body(h3 + p + a.btn)
    """
    if not date_label:
        date_label = _format_date_fr()
    
    video_url = video_info.get("url", "")
    title = video_info.get("title", "Video YouTube")
    description = video_info.get("description", "")[:250]
    if len(description) == 250:
        description += "..."
    thumb = video_info.get("thumb", "")
    
    return f'''
        <!-- Entree importee le {datetime.now().strftime('%Y-%m-%d %H:%M')} -->
        <div class="journal-card">
            <div class="journal-thumb">
                <span class="journal-badge">{escape(date_label)}</span>
                <a href="{escape(video_url)}" target="_blank">
                    <img src="{escape(thumb)}" alt="{escape(title)}" loading="lazy">
                </a>
            </div>
            <div class="journal-body">
                <h3>{escape(title)}</h3>
                <p>{escape(description) if description else "Nouvelle video du voyage."}</p>
                <a href="{escape(video_url)}" target="_blank" style="display:inline-block;width:auto;max-width:fit-content;padding:.55rem 1.2rem;background:#1a1a1a;color:#fff;border-radius:8px;font-size:.85rem;font-weight:600;text-decoration:none;">Voir la video</a>
            </div>
        </div>
'''


def _generate_main_page_video_card_html(video_info: Dict[str, Any], date_label: str = "", journal_href: str = "") -> str:
    """Genere le HTML d'une carte video pour la section jnl-grid de la page principale.
    
    Structure : .short-card > .short-thumb(.short-badge + img) + .short-body(h3 + p + btn)
    Le lien pointe vers le journal de bord pour garder le visiteur sur le site.
    """
    video_url = video_info.get("url", "")
    title = video_info.get("title", "Video YouTube")
    thumb = video_info.get("thumb", "")
    description = video_info.get("description", "")[:120]
    if len(description) == 120:
        description += "..."
    
    # Lien de la carte : journal de bord si disponible, sinon YouTube
    card_href = journal_href if journal_href else video_url
    card_target = "" if journal_href else ' target="_blank"'

    return f'''
        <!-- Video importee le {datetime.now().strftime('%Y-%m-%d %H:%M')} -->
        <div class="short-card">
            <div class="short-thumb">
                <span class="short-badge">{escape(date_label) if date_label else ""}</span>
                <a href="{escape(card_href)}"{card_target}>
                    <img src="{escape(thumb)}" alt="{escape(title)}" loading="lazy">
                </a>
            </div>
            <div class="short-body">
                <h3>{escape(title)}</h3>
                <p>{escape(description) if description else "Nouvelle video du voyage."}</p>
                <a href="{escape(card_href)}"{card_target} class="btn btn-dark">Voir le short</a>
            </div>
        </div>
'''


def _inject_video_into_main_html(
    main_path: Path,
    video_info: Dict[str, Any],
    date_label: str = "",
    journal_href: str = "",
) -> Dict[str, Any]:
    """
    Injecte une carte vidéo dans la section jnl-grid de la page principale.

    Args:
        main_path: Chemin vers le fichier HTML de la page principale
        video_info: Dict avec url, title, description, thumb
        date_label: Date à afficher
        journal_href: Lien vers la page journal de bord (si vide, lien YouTube)

    Returns:
        {"ok": bool, "message": str, "backup": str ou None}
    """
    result: Dict[str, Any] = {"ok": False, "message": "", "backup": None, "trace": []}

    if not main_path.exists():
        result["message"] = f"Page principale introuvable : {main_path}"
        return result

    try:
        content = main_path.read_text(encoding="utf-8")
    except Exception as exc:
        result["message"] = f"Impossible de lire la page principale : {exc}"
        return result

    result["trace"].append(f"[INJECT-MAIN] Fichier lu : {len(content)} caractères")
    entry_html = _generate_main_page_video_card_html(video_info, date_label, journal_href=journal_href)

    # Chercher le point d'insertion dans la section apercu / shorts
    insertion_patterns = [
        # Grille journal-preview (template Ecosse) — cible prioritaire
        ("journal-preview",  r'(<div[^>]*class="[^"]*journal-preview[^"]*"[^>]*>)', r'\1\n' + entry_html),
        # Grille apercu journal (ancien template LCDMH)
        ("jnl-grid",         r'(<div[^>]*class="[^"]*jnl-grid[^"]*"[^>]*>)', r'\1\n' + entry_html),
        # Grille coming-soon (section La Serie)
        ("coming-soon-grid", r'(<div[^>]*class="[^"]*coming-soon-grid[^"]*"[^>]*>)', r'\1\n' + entry_html),
        # Autres grilles possibles
        ("shorts-grid",      r'(<div[^>]*class="[^"]*shorts-grid[^"]*"[^>]*>)', r'\1\n' + entry_html),
        ("short-cards",      r'(<div[^>]*class="[^"]*short-cards[^"]*"[^>]*>)', r'\1\n' + entry_html),
        ("video-grid",       r'(<div[^>]*class="[^"]*video-grid[^"]*"[^>]*>)', r'\1\n' + entry_html),
    ]

    inserted = False
    for label, pattern, replacement in insertion_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
            result["trace"].append(f"[INJECT-MAIN] ✅ Pattern matché : '{label}'")
            inserted = True
            break
        else:
            result["trace"].append(f"[INJECT-MAIN] ✗ Pattern non trouvé : '{label}'")

    if not inserted:
        # Fallback : chercher la premiere jnl-card ou coming-soon-card et inserer avant
        for marker in ['class="jnl-card"', 'class="coming-soon-card"', 'class="short-card"']:
            if marker in content:
                idx = content.index(marker)
                tag_start = content.rfind('<', 0, idx)
                if tag_start >= 0:
                    content = content[:tag_start] + entry_html + '\n        ' + content[tag_start:]
                    result["trace"].append(f"[INJECT-MAIN] Fallback matche : '{marker}'")
                    inserted = True
                    break
        if not inserted:
            result["trace"].append(f"[INJECT-MAIN] Aucun pattern ni fallback trouve")

    if not inserted:
        result["message"] = "Point d'insertion introuvable sur la page principale (section vidéos)"
        return result

    # Backup
    backup_path = main_path.with_suffix(".html.backup")
    try:
        shutil.copy2(main_path, backup_path)
        result["backup"] = str(backup_path)
    except Exception:
        pass

    try:
        main_path.write_text(content, encoding="utf-8")
        result["ok"] = True
        result["message"] = f"Vidéo ajoutée dans {main_path.name}"
    except Exception as exc:
        result["message"] = f"Impossible d'écrire la page principale : {exc}"

    return result


def _find_main_html(publish_root: Path, slug: str) -> Optional[Path]:
    """Trouve le fichier HTML de la page principale."""
    candidates = [
        publish_root / "roadtrips" / f"{slug}.html",
        publish_root / f"{slug}.html",
        publish_root / "roadtrips" / f"{slug.lower()}.html",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _inject_video_into_journal_html(
    journal_path: Path,
    video_info: Dict[str, Any],
    date_label: str = "",
    position: str = "top"
) -> Dict[str, Any]:
    """
    Injecte une entrée vidéo directement dans le fichier HTML du journal.
    
    Args:
        journal_path: Chemin vers le fichier HTML du journal
        video_info: Dict avec url, title, description, thumb
        date_label: Date à afficher (ex: "25 MARS 2026")
        position: "top" (plus récent en haut) ou "bottom"
    
    Returns:
        {"ok": bool, "message": str, "backup": str ou None}
    """
    result = {"ok": False, "message": "", "backup": None, "trace": []}
    
    if not journal_path.exists():
        result["message"] = f"Fichier journal introuvable : {journal_path}"
        return result
    
    # Lire le contenu actuel
    try:
        content = journal_path.read_text(encoding="utf-8")
    except Exception as exc:
        result["message"] = f"Impossible de lire le journal : {exc}"
        return result
    
    result["trace"].append(f"[INJECT-JOURNAL] Fichier lu : {len(content)} caractères")
    
    # Générer le HTML de l'entrée
    entry_html = _generate_journal_entry_html(video_info, date_label)
    
    # Chercher le point d'insertion
    insertion_patterns = [
        # Kicker "Entrees du journal" suivi du contenu (template LCDMH reel)
        ("section-kicker",         r'(<div[^>]*class="[^"]*section-kicker[^"]*"[^>]*>[^<]*</div>\s*)', r'\1\n' + entry_html),
        ("section.journal-entries", r'(<section[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)', r'\1\n' + entry_html),
        ("div.journal-entries",    r'(<div[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)', r'\1\n' + entry_html),
        ("ENTREES DU JOURNAL",     r'(ENTR.ES DU JOURNAL</[^>]+>\s*)', r'\1\n' + entry_html),
        ("div#journal-content",    r'(<div[^>]*id="journal-content"[^>]*>)', r'\1\n' + entry_html),
    ]
    
    inserted = False
    for label, pattern, replacement in insertion_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
            result["trace"].append(f"[INJECT-JOURNAL] ✅ Pattern matché : '{label}'")
            inserted = True
            break
        else:
            result["trace"].append(f"[INJECT-JOURNAL] ✗ Pattern non trouvé : '{label}'")
    
    if not inserted:
        # Fallback : chercher la premiere journal-card existante et inserer avant
        for marker in ['class="journal-card"', 'class="journal-entry"']:
            if marker in content:
                idx = content.index(marker)
                tag_start = content.rfind('<', 0, idx)
                if tag_start >= 0:
                    content = content[:tag_start] + entry_html + '\n        ' + content[tag_start:]
                    result["trace"].append(f"[INJECT-JOURNAL] Fallback matche : '{marker}'")
                    inserted = True
                    break
        if not inserted:
            # Dernier fallback : chercher journal-empty et inserer avant
            if 'class="journal-empty"' in content:
                idx = content.index('class="journal-empty"')
                tag_start = content.rfind('<', 0, idx)
                if tag_start >= 0:
                    content = content[:tag_start] + entry_html + '\n        ' + content[tag_start:]
                    result["trace"].append(f"[INJECT-JOURNAL] Fallback matche : 'journal-empty'")
                    inserted = True
            if not inserted:
                result["trace"].append(f"[INJECT-JOURNAL] Aucun pattern ni fallback trouve")
    
    if not inserted:
        result["message"] = "Point d'insertion introuvable dans le fichier journal"
        return result
    
    # Créer un backup
    backup_path = journal_path.with_suffix(".html.backup")
    try:
        shutil.copy2(journal_path, backup_path)
        result["backup"] = str(backup_path)
    except Exception:
        pass  # Pas grave si le backup échoue
    
    # Écrire le fichier modifié
    try:
        journal_path.write_text(content, encoding="utf-8")
        result["ok"] = True
        result["message"] = f"Vidéo injectée dans {journal_path.name}"
    except Exception as exc:
        result["message"] = f"Impossible d'écrire le journal : {exc}"
    
    return result


def _auto_push_journal_to_github(
    publish_root: Path,
    repo_path: Path,
    journal_rel: str,
    commit_message: str = "",
    remote: str = "origin",
    branch: str = "",
    pull_before_push: bool = True,
) -> Dict[str, Any]:
    """
    Synchronise le fichier journal modifié vers le dépôt GitHub local,
    puis git add + commit + push automatiquement.

    Args:
        publish_root: Racine du site local (F:\LCDMH)
        repo_path:    Racine du dépôt GitHub local (F:\LCDMH_GitHub_Audit)
        journal_rel:  Chemin relatif du journal (ex: roadtrips/slug-journal.html)
        commit_message: Message de commit
        remote:       Nom du remote Git
        branch:       Branche cible (vide = courante)
        pull_before_push: Faire un git pull --rebase avant le push

    Returns:
        {"ok": bool, "message": str, "details": list[str]}
    """
    result: Dict[str, Any] = {"ok": False, "message": "", "details": []}
    src = publish_root / journal_rel
    dst = repo_path / journal_rel

    # ── 1. Copier le fichier journal vers le dépôt ──
    if not src.exists():
        result["message"] = f"Fichier source introuvable : {src}"
        return result
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        result["details"].append(f"[SYNC] {src} → {dst}")
    except Exception as exc:
        result["message"] = f"Copie échouée : {exc}"
        return result

    # ── 2. Git add ──
    ok, out, err = _run_git(repo_path, ["add", str(journal_rel)])
    if not ok:
        result["message"] = f"git add échoué : {err}"
        return result
    result["details"].append(f"[GIT] add {journal_rel}")

    # ── 3. Vérifier qu'il y a bien quelque chose à committer ──
    ok, out, err = _run_git(repo_path, ["diff", "--cached", "--quiet"])
    if ok:
        # Rien à committer (fichier identique)
        result["ok"] = True
        result["message"] = "Fichier déjà à jour dans le dépôt — rien à pousser."
        return result

    # ── 4. Git commit ──
    msg = commit_message or f"🎬 Ajout vidéo journal ({journal_rel})"
    ok, out, err = _run_git(repo_path, ["commit", "-m", msg])
    if not ok:
        result["message"] = f"git commit échoué : {err}"
        return result
    result["details"].append(f"[GIT] commit: {msg}")

    # ── 5. Pull --rebase (optionnel) ──
    target = branch.strip() or "main"
    if pull_before_push:
        ok_pull, out_pull, err_pull = _run_git(repo_path, ["pull", "--rebase", remote, target])
        result["details"].append(f"[GIT] pull --rebase {remote} {target} → {'OK' if ok_pull else err_pull}")

    # ── 6. Git push ──
    push_args = ["push", remote]
    if branch.strip():
        push_args.append(branch.strip())
    ok, out, err = _run_git(repo_path, push_args)
    if not ok:
        result["message"] = f"git push échoué : {err}"
        result["details"].append(f"[GIT] push FAILED: {err}")
        return result
    result["details"].append(f"[GIT] push {remote} → OK")

    result["ok"] = True
    result["message"] = f"✅ Vidéo injectée et publiée sur GitHub ({journal_rel})"
    return result


def _find_journal_html(publish_root: Path, slug: str) -> Optional[Path]:
    """Trouve le fichier journal HTML dans le dossier de publication."""
    candidates = [
        publish_root / "roadtrips" / f"{slug}-journal.html",
        publish_root / f"{slug}-journal.html",
        publish_root / "roadtrips" / f"{slug.lower()}-journal.html",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _write_playlist_trigger_request(project_dir, preview_lines, target, mode, kind, scheduled_for, schedule_mode, source_label, playlist_name, slug="", publish_root="", repo_path="") -> Path:
    trigger_dir = _playlist_trigger_dir(project_dir)
    trigger_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = trigger_dir / f"playlist-trigger-{stamp}.json"
    _write_json(path, {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scheduled_for": scheduled_for, "schedule_mode": schedule_mode,
        "source_label": source_label, "playlist_name": playlist_name,
        "target": target, "mode": mode, "kind": kind,
        "entries": preview_lines, "entry_count": len(preview_lines),
        "slug": slug, "publish_root": publish_root, "repo_path": repo_path,
    })
    return path


def _combine_today_with_time(value) -> datetime:
    now = datetime.now()
    combined = datetime.combine(now.date(), value)
    if combined <= now:
        combined += timedelta(days=1)
    return combined


# ═══════════════════════════════════════════════════════════════════
#  RENDU DES PAGES — UTILISE LE MOTEUR DE TEMPLATES
# ═══════════════════════════════════════════════════════════════════

def _copy_template_css(target_dir: Path, trace: Optional[List[str]] = None) -> List[Path]:
    """Copie les fichiers CSS du template dans le dossier cible.
    
    Cherche le dossier css/ dans :
    1. À côté du template réellement chargé (via tpl.load_template._last_found_dir)
    2. templates/css/ à côté du module
    3. Le dossier templates/ par défaut
    4. css/ à la racine du module
    """
    if trace is None:
        trace = []
    copied: List[Path] = []

    # Construire la liste de candidats, en priorité à côté du template trouvé
    candidates: List[Path] = []
    
    # 1. À côté du template trouvé
    last_dir = getattr(tpl.load_template, '_last_found_dir', None)
    if last_dir:
        candidates.append(Path(last_dir) / "css")
        candidates.append(Path(last_dir) / "templates" / "css")
    
    # 2. Chemins standards
    candidates.extend([
        MODULE_DIR / "templates" / "css",
        tpl.DEFAULT_TEMPLATES_DIR / "css",
        MODULE_DIR / "css",
    ])

    trace.append(f"[CSS] Recherche du dossier CSS...")
    css_source = None
    for candidate in candidates:
        exists = candidate.is_dir()
        trace.append(f"[CSS]   {candidate} → {'TROUVÉ ✅' if exists else 'absent'}")
        if exists and css_source is None:
            css_source = candidate

    if css_source is None:
        trace.append(f"[CSS] ❌ AUCUN DOSSIER CSS TROUVÉ — la page n'aura pas de style")
        trace.append(f"[CSS]   Créez le dossier templates/css/ dans F:\\Automate_YT\\ et mettez-y roadbook.css")
        return copied

    target_css = target_dir / "css"
    target_css.mkdir(parents=True, exist_ok=True)
    trace.append(f"[CSS] Dossier source : {css_source}")
    trace.append(f"[CSS] Dossier cible : {target_css}")

    for css_file in css_source.glob("*.css"):
        dst = target_css / css_file.name
        shutil.copy2(css_file, dst)
        copied.append(dst)
        trace.append(f"[CSS] ✅ Copié : {css_file.name} → {dst}")

    if not copied:
        trace.append(f"[CSS] ⚠️  Dossier CSS trouvé mais aucun fichier .css dedans")

    return copied


def _render_main_page(
    trip_title: str,
    trip_year: int,
    days_data: List[Dict[str, Any]],
    slug: str,
    hero_rel: str,
    qr_rel: str,
    kurviger_rel: str,
    pdf_rel: str,
    html_rel: str,
    journal_rel: str,
    journey_text: str,
    main_shorts: List[Dict[str, Any]],
    project_dir: str = "",
    kpis: Optional[List[Dict[str, str]]] = None,
    faq_items: Optional[List[Dict[str, str]]] = None,
    trace: Optional[List[str]] = None,
) -> str:
    """Génère la page principale via le moteur de templates."""
    if trace is None:
        trace = []
    trace.append(f"[MAIN PAGE] _render_main_page appelé")
    trace.append(f"[MAIN PAGE]   project_dir = {project_dir}")
    trace.append(f"[MAIN PAGE]   MODULE_DIR = {MODULE_DIR}")
    data = tpl.build_template_data(
        trip_title=trip_title,
        trip_year=trip_year,
        days_data=days_data,
        slug=slug,
        hero_src=hero_rel,
        qr_src=qr_rel,
        kurviger_href=kurviger_rel,
        pdf_href=pdf_rel,
        html_href=html_rel,
        journal_href=journal_rel,
        journey_text=journey_text,
        main_shorts=main_shorts,
        kpis=kpis,
        faq_items=faq_items,
    )
    trace.append(f"[MAIN PAGE] Données construites : {len(data)} clés")
    trace.append(f"[MAIN PAGE]   title = {data.get('title')}")
    trace.append(f"[MAIN PAGE]   total_km_label = {data.get('total_km_label')}")
    trace.append(f"[MAIN PAGE]   route_hint = {data.get('route_hint')}")
    trace.append(f"[MAIN PAGE]   has_shorts = {data.get('has_shorts')}")
    return tpl.render_page(
        "main_roadtrip",
        data,
        extra_dirs=[project_dir, str(MODULE_DIR)] if project_dir else [str(MODULE_DIR)],
        trace=trace,
    )


def _render_journal_page(
    trip_title: str,
    slug: str,
    journal_entries: List[Dict[str, Any]],
    main_href: str,
    intro: str = "",
    project_dir: str = "",
) -> str:
    """Génère la page journal via le moteur de templates."""
    # Nettoyage : s'assurer que trip_title ne contient pas déjà "Journal"
    clean_title = re.sub(r'\s*[-—]\s*Journal.*$', '', trip_title, flags=re.IGNORECASE).strip()
    data = {
        "title": f"{clean_title} — Journal de bord du voyageur",
        "page_title": f"{clean_title} — Journal de bord du voyageur",
        "main_href": main_href,
        "intro": intro or "Suivez l'aventure au jour le jour. Le journal complet regroupe les entrées quotidiennes, les shorts terrain et les notes publiées pendant le voyage.",
        "raw:journal_cards_html": tpl.journal_cards_html(journal_entries),
        "has_journal": bool(journal_entries),
    }
    return tpl.render_page(
        "journal",
        data,
        extra_dirs=[project_dir, str(MODULE_DIR)] if project_dir else [str(MODULE_DIR)],
    )


# ═══════════════════════════════════════════════════════════════════
#  GÉNÉRATION COMPLÈTE DU PACKAGE
# ═══════════════════════════════════════════════════════════════════

def _generate_journey_text_auto(days_data: List[Dict[str, Any]], trip_title: str = "") -> str:
    """Génère automatiquement le texte 'Esprit du parcours' basé sur les données réelles.
    
    Calcule dynamiquement :
    - Nombre de jours
    - Distance totale
    - Types d'hébergement
    - Pays traversés
    """
    if not days_data:
        return "Un voyage à moto à travers des paysages spectaculaires."
    
    # Nombre de jours
    nb_jours = len(days_data)
    
    # Distance totale
    total_km = 0
    for d in days_data:
        try:
            km = float(d.get("total_km", 0) or d.get("distance_km", 0) or 0)
            total_km += km
        except (ValueError, TypeError):
            pass
    
    # Comptage des hébergements par type
    hebergements = {"camping": 0, "bivouac": 0, "hotel": 0, "bb": 0, "autre": 0}
    pays_set = set()
    
    for d in days_data:
        # Type de nuit
        nuit_type = str(d.get("nuit_type", "") or d.get("stay_type", "")).lower()
        if "camping" in nuit_type or "camp" in nuit_type:
            hebergements["camping"] += 1
        elif "bivouac" in nuit_type or "bivvy" in nuit_type or "sauvage" in nuit_type:
            hebergements["bivouac"] += 1
        elif "hotel" in nuit_type or "hôtel" in nuit_type:
            hebergements["hotel"] += 1
        elif "b&b" in nuit_type or "bb" in nuit_type or "guesthouse" in nuit_type:
            hebergements["bb"] += 1
        else:
            hebergements["autre"] += 1
        
        # Pays
        pays = d.get("country", "") or d.get("pays", "")
        if pays:
            pays_set.add(pays)
    
    # Construction du texte
    texte_parts = []
    
    # Phrase d'intro avec nombre de jours
    if nb_jours == 1:
        texte_parts.append(f"Cette journée de road trip")
    elif nb_jours <= 7:
        texte_parts.append(f"Ce périple de {nb_jours} jours")
    elif nb_jours <= 14:
        texte_parts.append(f"Cette aventure de {nb_jours} jours")
    else:
        texte_parts.append(f"Ce voyage de {nb_jours} jours")
    
    # Distance
    if total_km > 0:
        if total_km >= 1000:
            texte_parts.append(f"couvre près de {int(total_km):,} km".replace(",", " "))
        else:
            texte_parts.append(f"parcourt {int(total_km)} km")
    
    # Pays
    if pays_set:
        pays_list = sorted(pays_set)
        if len(pays_list) == 1:
            texte_parts.append(f"à travers {pays_list[0]}")
        elif len(pays_list) == 2:
            texte_parts.append(f"entre {pays_list[0]} et {pays_list[1]}")
        else:
            texte_parts.append(f"à travers {', '.join(pays_list[:-1])} et {pays_list[-1]}")
    
    phrase1 = " ".join(texte_parts) + "."
    
    # Phrase sur les hébergements
    heb_parts = []
    if hebergements["camping"] > 0:
        heb_parts.append(f"{hebergements['camping']} nuit{'s' if hebergements['camping'] > 1 else ''} en camping")
    if hebergements["bivouac"] > 0:
        heb_parts.append(f"{hebergements['bivouac']} bivouac{'s' if hebergements['bivouac'] > 1 else ''}")
    if hebergements["hotel"] > 0:
        heb_parts.append(f"{hebergements['hotel']} nuit{'s' if hebergements['hotel'] > 1 else ''} en hôtel")
    if hebergements["bb"] > 0:
        heb_parts.append(f"{hebergements['bb']} B&B")
    
    if heb_parts:
        if len(heb_parts) == 1:
            phrase2 = f"Au programme : {heb_parts[0]}."
        elif len(heb_parts) == 2:
            phrase2 = f"Au programme : {heb_parts[0]} et {heb_parts[1]}."
        else:
            phrase2 = f"Au programme : {', '.join(heb_parts[:-1])} et {heb_parts[-1]}."
    else:
        phrase2 = ""
    
    # Phrase de conclusion contextuelle
    if "écosse" in trip_title.lower() or "scotland" in trip_title.lower():
        phrase3 = "Des Highlands sauvages aux côtes déchiquetées, un voyage au cœur des terres celtes."
    elif "irlande" in trip_title.lower() or "ireland" in trip_title.lower():
        phrase3 = "Des routes côtières aux vallées verdoyantes, l'Irlande à moto."
    elif "alpes" in trip_title.lower() or "alps" in trip_title.lower():
        phrase3 = "Cols mythiques et panoramas alpins au rendez-vous."
    elif "pyrénées" in trip_title.lower() or "pyrenees" in trip_title.lower():
        phrase3 = "Des cols pyrénéens aux vallées préservées."
    elif "corse" in trip_title.lower() or "corsica" in trip_title.lower():
        phrase3 = "L'île de beauté et ses routes spectaculaires."
    else:
        phrase3 = "Une aventure à moto, entre routes panoramiques et découvertes."
    
    # Assemblage final
    result = phrase1
    if phrase2:
        result += "\n\n" + phrase2
    result += "\n\n" + phrase3
    
    return result


def _zip_generated_outputs(result_paths: Dict[str, str]) -> bytes:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for path_str in result_paths.values():
            if not path_str:
                continue
            p = Path(path_str)
            if p.is_file():
                zf.write(p, arcname=p.name)
    return mem.getvalue()


def generate_roadtrip_package(
    project_dir: str | Path,
    site_root: str | Path,
    trip_title: str,
    trip_year: int,
    conso: float,
    uk_price: float,
    ie_price: float,
    journey_text: str,
    main_shorts_raw: str = "",
    journal_entries_raw: str = "",
    use_online: bool = False,
    overwrite_public_pages: bool = True,
    progress_callback=None,
    kpis: Optional[List[Dict[str, str]]] = None,
    faq_items: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Génère le package complet du road trip.

    Changement v2 : le rendu passe par lcdmh_template_engine au lieu
    de BeautifulSoup + HTML en dur.
    """
    project_dir = Path(project_dir).expanduser().resolve()
    site_root = Path(site_root).expanduser().resolve()
    slug = _slug(trip_title)
    result: Dict[str, Any] = {"ok": False, "warnings": [], "paths": {}, "slug": slug}

    # ═══ TRAÇAGE — initialisé dès le début pour capturer toutes les étapes ═══
    build_trace: List[str] = []
    build_trace.append(f"[BUILD] ═══════════════════════════════════════════════════════")
    build_trace.append(f"[BUILD] GÉNÉRATION ROAD TRIP — {trip_title}")
    build_trace.append(f"[BUILD] ═══════════════════════════════════════════════════════")
    build_trace.append(f"[BUILD] Démarrage : {datetime.now().isoformat(timespec='seconds')}")
    build_trace.append(f"[BUILD] project_dir = {project_dir}")
    build_trace.append(f"[BUILD] site_root = {site_root}")
    build_trace.append(f"[BUILD] MODULE_DIR = {MODULE_DIR}")
    build_trace.append(f"[BUILD] slug = {slug}")
    build_trace.append(f"[BUILD] trip_year = {trip_year}")
    build_trace.append(f"[BUILD] use_online = {use_online}")
    build_trace.append(f"")

    def step(pct: int, text: str):
        build_trace.append(f"[STEP {pct:3d}%] {text}")
        if progress_callback:
            progress_callback(pct, text)

    step(5, "Analyse du dossier projet…")
    detected = _detect_project_files(project_dir)
    build_trace.append(f"[DETECT] Fichiers détectés :")
    build_trace.append(f"[DETECT]   CSV : {detected.get('csv', 'NON TROUVÉ')}")
    build_trace.append(f"[DETECT]   Hero : {detected.get('hero', 'NON TROUVÉ')}")
    build_trace.append(f"[DETECT]   QR : {detected.get('qr', 'NON TROUVÉ')}")
    build_trace.append(f"[DETECT]   Kurviger : {detected.get('kurviger', 'NON TROUVÉ')}")
    errors = _validate_resources(detected)
    if errors:
        build_trace.append(f"[DETECT] ❌ ERREURS : {errors}")
        result["message"] = "\n".join(errors)
        result["build_trace"] = build_trace
        return result

    csv_path = detected["csv"]
    hero_path = detected["hero"]
    qr_path = detected["qr"]
    kurviger_path = detected["kurviger"]

    dirs = {
        "site_root": site_root,
        "roadtrips": site_root / "roadtrips",
        "data_trip": site_root / "data" / "roadtrips" / slug,
        "sources": site_root / "data" / "roadtrips" / slug / "sources",
        "images_trip": site_root / "images" / "roadtrips" / slug,
        "kurviger": site_root / "kurviger",
        "roadbooks": site_root / "roadbooks",
        "roadbooks_html": site_root / "roadbooks-html" / slug,
        "status": site_root / "data" / "roadtrips" / slug,
    }
    step(12, "Création des dossiers de publication…")
    build_trace.append(f"[DIRS] Dossiers créés :")
    for name, p in dirs.items():
        p.mkdir(parents=True, exist_ok=True)
        build_trace.append(f"[DIRS]   {name} = {p}")

    build_status_path = dirs["status"] / "build_status.json"
    _write_json(build_status_path, {
        "slug": slug, "trip_title": trip_title,
        "phase": "initialisation", "enrichment_complete": False, "render_complete": False,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    })

    step(18, "Prélecture du CSV…")
    points = RB_BASE.load_csv(str(csv_path))
    build_trace.append(f"[CSV] Points chargés : {len(points)}")
    pre_errors = _precheck_csv(points)
    if pre_errors:
        build_trace.append(f"[CSV] ❌ ERREURS : {pre_errors}")
        result["message"] = "\n".join(pre_errors)
        result["build_trace"] = build_trace
        return result

    step(26, "Calcul des journées…")
    days_data, warnings = RB_BASE.build_days(points, conso_l_100=conso, uk_price=uk_price, ie_price=ie_price)
    build_trace.append(f"[DAYS] Journées calculées : {len(days_data)}")
    build_trace.append(f"[DAYS] Avertissements : {len(warnings)}")
    result["warnings"] = warnings[:]
    if not days_data:
        build_trace.append(f"[DAYS] ❌ Aucune journée exploitable")
        result["message"] = "Aucune journée exploitable n'a pu être générée."
        result["build_trace"] = build_trace
        return result

    step(38, "Enrichissement des journées…")
    RB_BASE.enrich_days_data(days_data=days_data, trip_year=int(trip_year), use_online=bool(use_online), use_gemini=False, gemini_key=None)
    build_trace.append(f"[ENRICH] Enrichissement terminé (online={use_online})")

    # ═══ GÉNÉRATION AUTOMATIQUE DU TEXTE "ESPRIT DU PARCOURS" ═══
    # Si le texte contient le placeholder [AUTO], on le génère à partir des données réelles
    if journey_text.strip().startswith("[AUTO]") or not journey_text.strip():
        journey_text = _generate_journey_text_auto(days_data, trip_title)
        build_trace.append(f"[JOURNEY] ✅ Texte 'Esprit du parcours' généré automatiquement")
        build_trace.append(f"[JOURNEY]   Basé sur {len(days_data)} jours de données")
    else:
        build_trace.append(f"[JOURNEY] Texte personnalisé conservé ({len(journey_text)} caractères)")

    step(52, "Génération du roadbook HTML détaillé…")
    html_paths = RB_BASE.write_outputs(days_data=days_data, warnings=warnings, trip_title=trip_title, source_name=csv_path.name, output_dir=str(dirs["roadbooks_html"]))
    build_trace.append(f"[ROADBOOK] HTML généré :")
    build_trace.append(f"[ROADBOOK]   index = {html_paths.get('index', 'N/A')}")
    build_trace.append(f"[ROADBOOK]   jours = {html_paths.get('jours', 'N/A')}")

    # ── Copie du CSS override pour les pages jour ──
    roadbook_css_dir = dirs["roadbooks_html"] / "css"
    roadbook_css_dir.mkdir(parents=True, exist_ok=True)
    override_candidates = [
        MODULE_DIR / "templates" / "css" / "roadbook-jour-override.css",
        MODULE_DIR / "css" / "roadbook-jour-override.css",
    ]
    last_tpl_dir = getattr(tpl.load_template, '_last_found_dir', None)
    if last_tpl_dir:
        override_candidates.insert(0, Path(last_tpl_dir) / "css" / "roadbook-jour-override.css")
    for ov_path in override_candidates:
        if ov_path.is_file():
            shutil.copy2(ov_path, roadbook_css_dir / "roadbook-jour-override.css")
            build_trace.append(f"[CSS] ✅ roadbook-jour-override.css copié dans {roadbook_css_dir}")
            break
    else:
        build_trace.append(f"[CSS] ⚠️  roadbook-jour-override.css non trouvé — les pages jour utiliseront le style par défaut")

    if not Path(html_paths.get("index", "")).exists() or not Path(html_paths.get("jours", "")).exists():
        build_trace.append(f"[ROADBOOK] ❌ Génération incomplète — fichiers manquants")
        result["message"] = "La génération enrichie n'a pas produit toutes les pages attendues."
        result["build_trace"] = build_trace
        return result

    build_trace.append(f"[ROADBOOK] ✅ Tous les fichiers roadbook générés")
    _write_json(build_status_path, {
        "slug": slug, "trip_title": trip_title,
        "phase": "enrichissement_termine", "enrichment_complete": True, "render_complete": False,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "roadbook_index": str(Path(html_paths.get("index", "")).resolve()),
        "jours_count": len(days_data),
    })

    step(62, "Copie des ressources…")
    hero_dst = _copy_if_needed(hero_path, dirs["images_trip"] / hero_path.name)
    qr_dst = _copy_if_needed(qr_path, dirs["images_trip"] / qr_path.name)
    kurviger_dst = _copy_if_needed(kurviger_path, dirs["kurviger"] / f"{slug}{kurviger_path.suffix.lower()}")
    csv_dst = _copy_if_needed(csv_path, dirs["sources"] / f"{slug}{csv_path.suffix.lower()}")
    build_trace.append(f"[COPY] Ressources copiées :")
    build_trace.append(f"[COPY]   hero → {hero_dst}")
    build_trace.append(f"[COPY]   qr → {qr_dst}")
    build_trace.append(f"[COPY]   kurviger → {kurviger_dst}")
    build_trace.append(f"[COPY]   csv → {csv_dst}")

    step(72, "Création du HTML imprimable du PDF…")
    public_warnings = _public_warning_filter(warnings)
    trip_meta = {
        "trip_title": trip_title, "trip_year": trip_year,
        "roadbook_zone": trip_title, "vehicle_label": "Honda NT1100",
        "journey_text": journey_text, "traveler_name": "Yves Vella",
        "subtitle": "Roadbook prévisionnel", "public_warnings": public_warnings,
    }
    printable_html = AI.render_pdf_html(trip_meta, days_data, qr_path=qr_dst)
    printable_html_path = dirs["roadbooks_html"] / "roadbook_previsionnel.html"
    printable_html_path.write_text(printable_html, encoding="utf-8")
    build_trace.append(f"[PDF] HTML imprimable créé : {printable_html_path}")

    step(80, "Conversion HTML → PDF…")
    roadbook_pdf_path = dirs["roadbooks"] / f"{slug}-roadbook.pdf"
    ok_pdf, pdf_msg = AI.generate_pdf_from_html(printable_html_path, roadbook_pdf_path)
    if ok_pdf:
        build_trace.append(f"[PDF] ✅ PDF généré : {roadbook_pdf_path}")
    else:
        build_trace.append(f"[PDF] ⚠️  Échec PDF : {pdf_msg}")
        warnings.append(f"[pdf] {pdf_msg}")

    # ═══ RENDU VIA LE MOTEUR DE TEMPLATES ═══
    step(88, "Génération de la page principale du road trip…")
    build_trace.append(f"")
    build_trace.append(f"[TEMPLATE] ═══ RENDU VIA MOTEUR DE TEMPLATES ═══")
    build_trace.append(f"[TEMPLATE] tpl.DEFAULT_TEMPLATES_DIR = {tpl.DEFAULT_TEMPLATES_DIR}")

    main_shorts = _parse_video_lines(main_shorts_raw, try_fetch_title=True)
    journal_entries = _parse_video_lines(journal_entries_raw, try_fetch_title=True)
    if not main_shorts and journal_entries:
        main_shorts = journal_entries[:3]

    # Tracer les résultats du fetch YouTube
    all_videos = main_shorts + journal_entries
    fetched_ok = sum(1 for v in all_videos if v.get("title_auto"))
    fetched_fail = sum(1 for v in all_videos if not v.get("title_auto") and v.get("url"))
    build_trace.append(f"[YOUTUBE] Shorts page principale : {len(main_shorts)} vidéo(s)")
    build_trace.append(f"[YOUTUBE] Entrées journal : {len(journal_entries)} vidéo(s)")
    build_trace.append(f"[YOUTUBE] Titres récupérés automatiquement : {fetched_ok}/{len(all_videos)}")
    if fetched_fail:
        build_trace.append(f"[YOUTUBE] ⚠️  {fetched_fail} vidéo(s) sans titre auto — fallback 'Vidéo N' utilisé")
    for v in all_videos:
        failures = v.get("fetch_failures", "")
        if failures:
            build_trace.append(f"[YOUTUBE]   {failures}")
            warnings.append(failures)

    roadtrip_page_name = f"{slug}.html"
    journal_page_name = f"{slug}-journal.html"

    roadtrip_html = _render_main_page(
        trip_title=trip_title,
        trip_year=trip_year,
        days_data=days_data,
        slug=slug,
        hero_rel=f"/images/roadtrips/{slug}/{hero_dst.name}",
        qr_rel=f"/images/roadtrips/{slug}/{qr_dst.name}",
        kurviger_rel=f"/kurviger/{kurviger_dst.name}",
        pdf_rel=f"/roadbooks/{roadbook_pdf_path.name}",
        html_rel=f"/roadbooks-html/{slug}/index.html",
        journal_rel=f"/roadtrips/{journal_page_name}",
        journey_text=journey_text,
        main_shorts=main_shorts,
        project_dir=str(project_dir),
        kpis=kpis,
        faq_items=faq_items,
        trace=build_trace,
    )
    roadtrip_page_path = dirs["roadtrips"] / roadtrip_page_name
    if overwrite_public_pages or not roadtrip_page_path.exists():
        roadtrip_page_path.write_text(roadtrip_html, encoding="utf-8")
    build_trace.append(f"[BUILD] ✅ Page principale écrite : {roadtrip_page_path}")
    build_trace.append(f"[BUILD]   Taille HTML : {len(roadtrip_html)} caractères")

    # Copier le CSS du template à côté du HTML généré
    css_copied = _copy_template_css(dirs["roadtrips"], trace=build_trace)
    build_trace.append(f"[BUILD] CSS copiés : {len(css_copied)} fichier(s)")

    # Vérification finale : le CSS est-il accessible depuis le HTML ?
    css_ref_path = dirs["roadtrips"] / "css" / "roadbook.css"
    if css_ref_path.exists():
        build_trace.append(f"[BUILD] ✅ CSS vérifié : {css_ref_path} EXISTE")
    else:
        build_trace.append(f"[BUILD] ❌ CSS MANQUANT : {css_ref_path} N'EXISTE PAS — la page n'aura pas de style !")

    css_fusion_path = dirs["roadtrips"] / "css" / "roadbook-fusion.css"
    if css_fusion_path.exists():
        build_trace.append(f"[BUILD] ✅ CSS fusion vérifié : {css_fusion_path} EXISTE")
    else:
        build_trace.append(f"[BUILD] ❌ CSS fusion MANQUANT : {css_fusion_path}")

    # Vérification roadbook-blocs.css (styles des blocs Ressources, Immersion, Journal)
    css_blocs_path = dirs["roadtrips"] / "css" / "roadbook-blocs.css"
    if css_blocs_path.exists():
        build_trace.append(f"[BUILD] ✅ CSS blocs vérifié : {css_blocs_path} EXISTE")
    else:
        build_trace.append(f"[BUILD] ⚠️  CSS blocs MANQUANT : {css_blocs_path} — tentative de récupération fallback")
        # Fallback : chercher roadbook-blocs.css dans les emplacements connus
        blocs_fallback_candidates = [
            MODULE_DIR / "css" / "roadbook-blocs.css",
            MODULE_DIR / "templates" / "css" / "roadbook-blocs.css",
            MODULE_DIR / "roadbook-blocs.css",
        ]
        last_dir = getattr(tpl.load_template, '_last_found_dir', None)
        if last_dir:
            blocs_fallback_candidates.insert(0, Path(last_dir) / "css" / "roadbook-blocs.css")
            blocs_fallback_candidates.insert(1, Path(last_dir) / "roadbook-blocs.css")
        blocs_found = False
        for fb_path in blocs_fallback_candidates:
            if fb_path.is_file():
                target_css_dir = dirs["roadtrips"] / "css"
                target_css_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fb_path, css_blocs_path)
                css_copied.append(css_blocs_path)
                build_trace.append(f"[BUILD] ✅ CSS blocs récupéré depuis fallback : {fb_path} → {css_blocs_path}")
                blocs_found = True
                break
            else:
                build_trace.append(f"[BUILD]   fallback {fb_path} → absent")
        if not blocs_found:
            build_trace.append(f"[BUILD] ❌ CSS blocs INTROUVABLE — les blocs Ressources/Immersion/Journal n'auront pas de style !")
            build_trace.append(f"[BUILD]   Placez roadbook-blocs.css dans {MODULE_DIR / 'css'} ou {MODULE_DIR / 'templates' / 'css'}")

    # ═══ VÉRIFICATION COMPLÈTE DES CHEMINS ═══
    build_trace.append(f"")
    build_trace.append(f"[VERIFY] ═══ VÉRIFICATION DES FICHIERS RÉFÉRENCÉS ═══")
    build_trace.append(f"[VERIFY] Page HTML : {roadtrip_page_path}")
    build_trace.append(f"[VERIFY] Dossier roadtrips : {dirs['roadtrips']}")
    build_trace.append(f"[VERIFY] Site root : {site_root}")

    # Extraire tous les chemins référencés dans le HTML
    import re as _re
    urls_in_html = _re.findall(r"(?:href|src|url)\s*[\(=]\s*['\"]([^'\"]+)['\"]", roadtrip_html)
    build_trace.append(f"[VERIFY] URLs trouvées dans le HTML : {len(urls_in_html)}")

    for url in urls_in_html:
        if url.startswith("http") or url.startswith("//") or url.startswith("#") or url.startswith("mailto:"):
            continue  # liens externes, on skip
        
        # Résoudre le chemin relatif depuis le dossier du HTML
        if url.startswith("/"):
            # Chemin absolu depuis site_root
            resolved = site_root / url.lstrip("/")
        elif url.startswith("../"):
            # Chemin relatif vers le parent
            resolved = dirs["roadtrips"].parent / url.replace("../", "", 1)
        else:
            # Chemin relatif depuis le dossier du HTML
            resolved = dirs["roadtrips"] / url

        exists = resolved.exists()
        status = "✅ EXISTE" if exists else "❌ MANQUANT"
        build_trace.append(f"[VERIFY]   {url}")
        build_trace.append(f"[VERIFY]     → {resolved} : {status}")

    # Vérification spécifique de l'image hero
    build_trace.append(f"")
    build_trace.append(f"[HERO] ═══ VÉRIFICATION IMAGE HERO ═══")
    hero_rel_used = f"/images/roadtrips/{slug}/{hero_dst.name}"
    hero_resolved = site_root / "images" / "roadtrips" / slug / hero_dst.name
    build_trace.append(f"[HERO] Chemin dans le HTML : {hero_rel_used}")
    build_trace.append(f"[HERO] Résolu vers : {hero_resolved}")
    build_trace.append(f"[HERO] Fichier existe : {hero_resolved.exists()}")
    if hero_resolved.exists():
        build_trace.append(f"[HERO] ✅ Taille : {hero_resolved.stat().st_size / 1024:.0f} KB")
    else:
        build_trace.append(f"[HERO] ❌ IMAGE HERO INTROUVABLE — le bandeau sera noir")
        hero_dir = site_root / "images" / "roadtrips" / slug
        if hero_dir.exists():
            files = list(hero_dir.iterdir())
            build_trace.append(f"[HERO]   Contenu de {hero_dir} : {[f.name for f in files]}")
        else:
            build_trace.append(f"[HERO]   Le dossier {hero_dir} N'EXISTE PAS")
            build_trace.append(f"[HERO]   hero_dst = {hero_dst}")
            build_trace.append(f"[HERO]   hero_dst existe : {hero_dst.exists()}")

    # Dump des premières lignes du HTML pour vérifier le hero
    build_trace.append(f"")
    build_trace.append(f"[HTML] ═══ EXTRAIT DU HTML GÉNÉRÉ (hero) ═══")
    for i, line in enumerate(roadtrip_html.splitlines()[:20], 1):
        if "hero" in line.lower() or "background" in line.lower() or "image" in line.lower():
            build_trace.append(f"[HTML] L{i}: {line.strip()[:200]}")

    # URLs publiques attendues sur lcdmh.com
    build_trace.append(f"")
    build_trace.append(f"[PUBLIC] ═══ URLS PUBLIQUES ATTENDUES ═══")
    public_urls = {
        "Page principale": f"https://lcdmh.com/roadtrips/{slug}.html",
        "Journal": f"https://lcdmh.com/roadtrips/{slug}-journal.html",
        "Hero image": f"https://lcdmh.com/images/roadtrips/{slug}/{hero_dst.name}",
        "QR code": f"https://lcdmh.com/images/roadtrips/{slug}/{qr_dst.name}",
        "PDF": f"https://lcdmh.com/roadbooks/{roadbook_pdf_path.name}",
        "Roadbook HTML": f"https://lcdmh.com/roadbooks-html/{slug}/index.html",
        "Kurviger": f"https://lcdmh.com/kurviger/{kurviger_dst.name}",
        "CSS roadbook": f"https://lcdmh.com/roadtrips/css/roadbook.css",
        "CSS fusion": f"https://lcdmh.com/roadtrips/css/roadbook-fusion.css",
        "CSS blocs": f"https://lcdmh.com/roadtrips/css/roadbook-blocs.css",
    }
    for label, url in public_urls.items():
        build_trace.append(f"[PUBLIC]   {label}: {url}")

    # Sauvegarder le rapport de traçage
    trace_path = dirs["data_trip"] / "build_trace.txt"
    trace_path.write_text("\n".join(build_trace), encoding="utf-8")
    build_trace.append(f"[BUILD] Rapport de traçage sauvegardé : {trace_path}")

    result["build_trace"] = build_trace

    step(94, "Création de la sous-page Journal de bord…")
    journal_entries_path = dirs["data_trip"] / "journal_entries.json"
    _write_json(journal_entries_path, journal_entries)

    journal_html = _render_journal_page(
        trip_title=trip_title,
        slug=slug,
        journal_entries=journal_entries,
        main_href=f"/roadtrips/{roadtrip_page_name}",
        project_dir=str(project_dir),
    )
    journal_page_path = dirs["roadtrips"] / journal_page_name
    if overwrite_public_pages or not journal_page_path.exists():
        journal_page_path.write_text(journal_html, encoding="utf-8")

    # ═══ Métadonnées projet ═══
    project_json = {
        "slug": slug, "trip_title": trip_title, "trip_year": trip_year,
        "project_dir": str(project_dir), "site_root": str(site_root),
        "resource_files": {"hero": str(hero_dst), "qr": str(qr_dst), "kurviger": str(kurviger_dst), "csv": str(csv_dst)},
        "video_seed_main": main_shorts,
        "journal_entries_json": str(journal_entries_path),
        "generated": {
            "roadbook_html_index": str(Path(html_paths["index"]).resolve()),
            "roadbook_printable_html": str(printable_html_path.resolve()),
            "roadbook_pdf": str(roadbook_pdf_path.resolve()) if ok_pdf else None,
            "roadtrip_page": str(roadtrip_page_path.resolve()),
            "journal_page": str(journal_page_path.resolve()),
            "build_status": str(build_status_path.resolve()),
        },
        "publication_layout": {
            "main_page": roadtrip_page_name,
            "journal_page": journal_page_name,
            "images_dir": str((site_root / "images" / "roadtrips" / slug).resolve()),
        },
    }
    _write_json(dirs["data_trip"] / "project.json", project_json)
    _write_json(build_status_path, {
        "slug": slug, "trip_title": trip_title,
        "phase": "production_terminee", "enrichment_complete": True, "render_complete": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "jours_count": len(days_data),
        "roadtrip_page": str(roadtrip_page_path.resolve()),
        "journal_page": str(journal_page_path.resolve()),
    })

    step(100, "Terminé.")
    result["ok"] = True
    result["message"] = "Génération terminée."
    result["warnings"] = warnings
    result["paths"] = {
        "roadbook_index": str(Path(html_paths["index"]).resolve()),
        "roadbook_days": str(Path(html_paths["jours"]).resolve()),
        "warnings": str(Path(html_paths["warnings"]).resolve()),
        "printable_html": str(printable_html_path.resolve()),
        "roadbook_pdf": str(roadbook_pdf_path.resolve()) if ok_pdf else "",
        "roadtrip_page": str(roadtrip_page_path.resolve()),
        "journal_page": str(journal_page_path.resolve()),
        "project_json": str((dirs["data_trip"] / "project.json").resolve()),
        "journal_entries_json": str(journal_entries_path.resolve()),
        "hero": str(hero_dst.resolve()),
        "qr": str(qr_dst.resolve()),
        "kurviger": str(kurviger_dst.resolve()),
        "csv": str(csv_dst.resolve()),
        "build_status": str(build_status_path.resolve()),
        "work_root": str(site_root.resolve()),
    }
    return result


# ═══════════════════════════════════════════════════════════════════
#  GIT / GITHUB (inchangé)
# ═══════════════════════════════════════════════════════════════════

def _run_git(repo_path: Path, args: List[str]) -> Tuple[bool, str, str]:
    try:
        proc = subprocess.run(["git", *args], cwd=str(repo_path), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return False, "", str(exc)


def _expected_repo_paths(repo_path: Path, slug: str) -> Dict[str, Path]:
    return {
        "main_page": repo_path / "roadtrips" / f"{slug}.html",
        "journal_page": repo_path / "roadtrips" / f"{slug}-journal.html",
        "hero_dir": repo_path / "images" / "roadtrips" / slug,
        "data_dir": repo_path / "data" / "roadtrips" / slug,
        "pdf": repo_path / "roadbooks" / f"{slug}-roadbook.pdf",
        "kurviger": repo_path / "kurviger" / f"{slug}.kurviger",
        "project_json": repo_path / "data" / "roadtrips" / slug / "project.json",
        "journal_json": repo_path / "data" / "roadtrips" / slug / "journal_entries.json",
    }


def _publication_status(repo_path: str, slug: str, branch: str = "", remote: str = "origin") -> Dict[str, Any]:
    repo = Path(repo_path).expanduser().resolve()
    status: Dict[str, Any] = {
        "repo_path": str(repo), "slug": slug,
        "checked_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "exists": repo.exists(), "files": {}, "git": {},
    }
    if not repo.exists():
        status["error"] = f"Dépôt introuvable : {repo}"
        return status
    expected = _expected_repo_paths(repo, slug)
    hero_dir = expected["hero_dir"]
    status["files"] = {
        "page principale": expected["main_page"].exists(),
        "page journal": expected["journal_page"].exists(),
        "données": expected["data_dir"].exists(),
        "project.json": expected["project_json"].exists(),
        "journal_entries.json": expected["journal_json"].exists(),
        "PDF": expected["pdf"].exists(),
        "Kurviger": expected["kurviger"].exists(),
        "hero JPG/JPEG/WEBP": hero_dir.exists() and any(p.suffix.lower() in {".jpg", ".jpeg", ".webp"} for p in hero_dir.glob("*")),
        "QR PNG": hero_dir.exists() and any(p.suffix.lower() == ".png" for p in hero_dir.glob("*")),
    }
    ok, stdout, stderr = _run_git(repo, ["status", "--short", "--branch"])
    status["git"]["status"] = stdout or stderr
    ok, stdout, stderr = _run_git(repo, ["rev-parse", "HEAD"])
    status["git"]["head"] = stdout if ok else ""
    target_branch = branch.strip() or "main"
    _run_git(repo, ["fetch", remote, target_branch])
    ok, stdout, stderr = _run_git(repo, ["rev-parse", f"{remote}/{target_branch}"])
    status["git"]["remote_head"] = stdout if ok else ""
    status["git"]["pushed"] = bool(status["git"].get("head")) and status["git"].get("head") == status["git"].get("remote_head")
    ok, stdout, stderr = _run_git(repo, ["log", "--oneline", "-n", "1"])
    status["git"]["last_commit"] = stdout if ok else stderr
    return status


def _render_publication_status_box(status: Dict[str, Any]) -> None:
    file_lines = [f"{label} : {'OK' if ok else 'absent'}" for label, ok in status.get("files", {}).items()]
    git = status.get("git", {})
    git_lines = [
        f"Contrôle : {status.get('checked_at', '')}",
        f"HEAD local : {git.get('head', '') or 'indisponible'}",
        f"HEAD distant : {git.get('remote_head', '') or 'indisponible'}",
        f"Push confirmé : {'oui' if git.get('pushed') else 'non / à vérifier'}",
        f"Dernier commit : {git.get('last_commit', '') or 'indisponible'}",
    ]
    st.code("\n".join(file_lines + ["", *git_lines]), language="text")
    slug_val = (status.get("slug") or "").strip()
    # Nettoyage prefixe roadtrips si present
    if slug_val.startswith("roadtrips"):
        slug_val = slug_val[len("roadtrips"):].lstrip("-")
    if slug_val:
        st.markdown(
            f"**Liens publics de test**  \n"
            f"[Page principale](https://lcdmh.com/roadtrips/{slug_val}.html) · "
            f"[Journal](https://lcdmh.com/roadtrips/{slug_val}-journal.html) · "
            f"[PDF](https://lcdmh.com/roadbooks/{slug_val}-roadbook.pdf) · "
            f"[Roadbook HTML](https://lcdmh.com/roadbooks-html/{slug_val}/index.html)"
        )


def _filter_report_warnings(report, status_payload: Dict[str, Any]) -> List[str]:
    warnings = list(getattr(report, 'warnings', []) or [])
    files = status_payload.get('files', {}) if isinstance(status_payload, dict) else {}
    return [line for line in warnings if not ('Roadbook PDF absent' in line and files.get('PDF')) and not ('Trace Kurviger absente' in line and files.get('Kurviger'))]


def _render_github_publication_panel() -> None:
    publish_state = st.session_state.get("roadtrip_last_generation")
    if not publish_state:
        return
    st.divider()
    st.subheader("🌐 Vérification et publication GitHub")
    st.caption("Cette étape vérifie le dépôt local miroir GitHub puis peut pousser les changements vers GitHub.")
    repo_path = publish_state.get("repo_path", "")
    slug = publish_state.get("slug", "")
    # Nettoyage prefixe roadtrips si present
    if slug.startswith("roadtrips"):
        slug = slug[len("roadtrips"):].lstrip("-")
    main_page_name = publish_state.get("main_page_name", f"{slug}.html")
    journal_page_name = publish_state.get("journal_page_name", f"{slug}-journal.html")
    git_remote = publish_state.get("git_remote", "origin")
    git_branch = publish_state.get("git_branch", "")
    require_cname = bool(publish_state.get("require_cname", False))
    pull_before_push = bool(publish_state.get("pull_before_push", False))

    st.code(f"Dépôt local GitHub : {repo_path}\nSlug : {slug}\nPage principale : {main_page_name}\nPage journal : {journal_page_name}", language="text")

    if not GITHUB_PUBLISH_AVAILABLE:
        st.error(f"Module publish_site_to_github.py introuvable. Détail : {GITHUB_PUBLISH_IMPORT_ERROR}")
        return

    git_col1, git_col2 = st.columns(2)
    with git_col1:
        git_remote = st.text_input("Remote Git", value=git_remote, key="roadtrip_git_remote")
    with git_col2:
        git_branch = st.text_input("Branche Git (vide = courante)", value=git_branch, key="roadtrip_git_branch")
    opts1, opts2 = st.columns(2)
    with opts1:
        require_cname = st.checkbox("Exiger CNAME", value=require_cname, key="roadtrip_require_cname")
    with opts2:
        pull_before_push = st.checkbox("git pull --rebase avant push", value=pull_before_push, key="roadtrip_pull_before_push")
    publish_state["git_remote"] = git_remote
    publish_state["git_branch"] = git_branch
    publish_state["require_cname"] = require_cname
    publish_state["pull_before_push"] = pull_before_push
    st.session_state["roadtrip_last_generation"] = publish_state

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        if st.button("🔎 Vérifier la cohérence GitHub", use_container_width=True):
            try:
                report = verify_publish_tree(publish_root=repo_path, slug=slug, main_page_name=main_page_name, journal_page_name=journal_page_name, require_cname=require_cname)
                st.success(report.message) if report.ok else st.error(report.message)
                status_payload = _publication_status(repo_path=repo_path, slug=slug, branch=git_branch, remote=git_remote)
                st.session_state["roadtrip_git_status"] = status_payload
                _render_publication_status_box(status_payload)
                if report.infos:
                    with st.expander("Infos", expanded=False):
                        st.code("\n".join(report.infos), language="text")
                filtered = _filter_report_warnings(report, status_payload)
                if filtered:
                    with st.expander("Avertissements", expanded=True):
                        st.code("\n".join(filtered), language="text")
                if report.errors:
                    with st.expander("Erreurs", expanded=True):
                        st.code("\n".join(report.errors), language="text")
            except Exception as exc:
                st.error(f"Erreur vérification GitHub : {exc}")
    with c2:
        if st.button("🚀 Publier sur GitHub", type="primary", use_container_width=True):
            try:
                # ═══ COPIE AUTOMATIQUE publish_root → repo_path ═══
                publish_root_path = Path(publish_state.get("publish_root", "")).expanduser().resolve()
                repo_root_path = Path(repo_path).expanduser().resolve()
                sync_trace: List[str] = []
                if publish_root_path.exists() and repo_root_path.exists() and publish_root_path != repo_root_path:
                    sync_trace.append(f"[SYNC] Copie {publish_root_path} → {repo_root_path}")
                    sync_dirs = ["roadtrips", "images", "roadbooks", "roadbooks-html", "kurviger", "data"]
                    total_synced = 0
                    for dirname in sync_dirs:
                        src_dir = publish_root_path / dirname
                        dst_dir = repo_root_path / dirname
                        if src_dir.exists():
                            copied = _copy_tree(src_dir, dst_dir)
                            total_synced += len(copied)
                            sync_trace.append(f"[SYNC]   {dirname} : {len(copied)} fichier(s)")
                        else:
                            sync_trace.append(f"[SYNC]   {dirname} : source absente, ignoré")
                    sync_trace.append(f"[SYNC] ✅ Total synchronisé : {total_synced} fichier(s)")
                    st.info(f"Synchronisation site → repo : {total_synced} fichier(s) copiés")
                else:
                    sync_trace.append(f"[SYNC] Pas de copie nécessaire (même dossier ou dossier absent)")

                result = publish_site_to_github(repo_path=repo_path, slug=slug, main_page_name=main_page_name, journal_page_name=journal_page_name, commit_message=f"Publication automatique du road trip {slug}", remote_name=(git_remote.strip() or "origin"), branch=(git_branch.strip() or None), pull_before_push=bool(pull_before_push), require_clean_check=True, require_cname=bool(require_cname))
                if result.get("ok"):
                    st.success(result.get("message", "Publication GitHub terminée."))
                else:
                    st.error(result.get("message", "Échec publication GitHub."))
                status_payload = _publication_status(repo_path=repo_path, slug=slug, branch=git_branch, remote=git_remote)
                st.session_state["roadtrip_git_status"] = status_payload
                _render_publication_status_box(status_payload)
                if sync_trace:
                    with st.expander("📋 Rapport de synchronisation site → repo", expanded=False):
                        st.code("\n".join(sync_trace), language="text")
            except Exception as exc:
                st.error(f"Publication GitHub échouée : {exc}")
    if st.session_state.get("roadtrip_git_status"):
        with st.expander("Dernier contrôle Git", expanded=False):
            _render_publication_status_box(st.session_state["roadtrip_git_status"])
    with c3:
        if st.button("🧹 Oublier", use_container_width=True):
            st.session_state.pop("roadtrip_last_generation", None)
            st.session_state.pop("roadtrip_git_status", None)
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
#  PANNEAU YOUTUBE PLAYLIST (inchangé dans la logique)


# ═══════════════════════════════════════════════════════════════════
#  PANNEAU YOUTUBE — DEPLOIEMENT GITHUB ACTIONS
# ═══════════════════════════════════════════════════════════════════

def _render_youtube_playlist_panel(project_dir: str, publish_root: str, repo_path: str) -> None:
    st.subheader("📺 Surveillance Playlist YouTube")

    # Résolution du slug
    _ps = st.session_state.get("roadtrip_last_generation") or {}
    _panel_slug = _ps.get("slug", "")
    if not _panel_slug:
        _trip_title = st.session_state.get("roadtrip_trip_title", "")
        if _trip_title:
            _panel_slug = _slug(_trip_title)
    # Nettoyage prefixe roadtrips si present
    if _panel_slug.startswith("roadtrips"):
        _panel_slug = _panel_slug[len("roadtrips"):].lstrip("-")

    if not _panel_slug:
        st.info("Generez et publiez d'abord un road trip pour activer la surveillance.")
        return

    # Verifier que les pages existent
    main_path = _find_main_html(Path(publish_root), _panel_slug)
    journal_path = _find_journal_html(Path(publish_root), _panel_slug)
    if not main_path or not journal_path:
        st.warning(f"Pages introuvables pour **{_panel_slug}**. Publiez d'abord le road trip.")
        return

    # Compter les vignettes actuelles
    try:
        _mc = main_path.read_text(encoding="utf-8")
        main_card_count = (_mc.count('class="short-card"') +
                           _mc.count('class="journal-card"') +
                           _mc.count('class="ecosse-jcard"'))
    except Exception:
        main_card_count = 0

    st.caption(f"Road trip : **{_panel_slug}** | Page principale : {main_card_count}/3 vignettes")

    # ── Selection de la playlist ──
    try:
        _playlists = _api_list_playlists()
    except Exception:
        _playlists = []

    if not _playlists:
        st.warning("Impossible de charger les playlists YouTube.")
        return

    _playlist_options = {f"{p['title']} ({p['itemCount']})" : p['id'] for p in _playlists}

    _selected = st.selectbox(
        "Playlist a surveiller",
        options=list(_playlist_options.keys()),
        key="roadtrip_auto_playlist"
    )
    _playlist_id = _playlist_options.get(_selected, "")
    _playlist_name = _selected.split(" (")[0] if _selected else ""

    st.divider()
    st.markdown("**Programmation GitHub Actions**")

    # ── Import du module cron_manager ──
    try:
        import cron_manager as CM
    except ImportError:
        st.error("❌ Module cron_manager.py introuvable. Placez-le dans F:\\Automate_YT\\")
        return

    col_time, col_interval = st.columns(2)
    with col_time:
        from datetime import time as _time
        _start_time = st.time_input(
            "Heure de debut",
            value=_time(18, 0),
            step=3600,
            key="roadtrip_auto_start_time"
        )
    with col_interval:
        _interval_h = st.selectbox(
            "Intervalle entre chaque verification",
            options=CM.INTERVALS_HEURES,
            index=0,
            format_func=lambda x: f"Toutes les {x}h",
            key="roadtrip_auto_interval"
        )

    _start_hour = _start_time.strftime("%H:%M")
    _horaires = CM.recapitulatif_cron(_panel_slug, _start_hour, _interval_h)
    st.caption(
        f"Playlist : **{_playlist_name}** | "
        f"Debut : **{_start_hour}** | "
        f"Intervalle : **toutes les {_interval_h}h**"
    )
    st.caption(f"Horaires de verification (heure de Paris) : {_horaires}")

    st.divider()

    # ── Bouton deploiement ──
    if st.button("Deployer sur GitHub Actions", type="primary", use_container_width=True, key="btn_deploy_github_action"):
        with st.spinner("Deploiement en cours..."):
            res = CM.deployer_cron(
                slug=_panel_slug,
                playlist_id=_playlist_id,
                playlist_name=_playlist_name,
                heure_depart=_start_hour,
                intervalle_heures=_interval_h,
                repo_path=Path(repo_path),
                publish_root=Path(publish_root),
                auto_script_src=MODULE_DIR / "auto_publish_roadtrip.py",
            )
        if res["ok"]:
            st.success(f"Deploye sur GitHub Actions !")
            st.markdown(f"""
**Recapitulatif :**
- Workflow : `{res['workflow_file']}`
- Playlist : **{_playlist_name}**
- Debut : **{_start_hour}** (heure de Paris)
- Intervalle : **toutes les {_interval_h}h**
- {res['crons_count']} verifications par jour

**Horaires :** {_horaires}

**Fonctionnement :**
- A chaque declenchement, GitHub detecte les nouveaux shorts
- Short 1, 2, 3 → page principale + journal de bord
- Short 4, 5, 6... → journal de bord uniquement
- Les shorts les plus anciens non importes sont traites en premier
""")
            st.caption("Verifiez les secrets GitHub : YT_CLIENT_SECRETS et YT_TOKEN_ANALYTICS")
        else:
            st.error(f"Echec : {res['message']}")

    # ── Etat actuel des workflows (tous les projets) ──
    _repo_check = Path(repo_path).expanduser().resolve()
    all_crons = CM.lister_crons(repo_path=_repo_check)
    if all_crons:
        st.divider()
        st.markdown("**Workflows actifs (tous projets)**")
        for cron_info in all_crons:
            cfg = cron_info["config"]
            start = cfg.get("start_time", "?")
            interval = cfg.get("interval_hours", cfg.get("interval_minutes", "?"))
            # Rétro-compatibilité : si c'est l'ancien format en minutes
            if "interval_minutes" in cfg and "interval_hours" not in cfg:
                label_interval = f"{interval} min"
            else:
                label_interval = f"{interval}h"
            pl_name = cfg.get("playlist_name", "?")
            st.caption(
                f"🔹 **{cron_info['slug']}** — `{cron_info['file']}` — "
                f"Playlist : {pl_name} — "
                f"Debut : {start} — Intervalle : {label_interval} — "
                f"{cron_info['crons_count']} cron(s)"
            )

        # Bouton supprimer uniquement pour le slug courant
        current_wfs = [c for c in all_crons if c["slug"] == _panel_slug]
        if current_wfs:
            if st.button(f"Supprimer le workflow de {_panel_slug}", key="btn_delete_workflow"):
                res_del = CM.supprimer_cron(_panel_slug, repo_path=_repo_check)
                if res_del["ok"]:
                    st.success(f"Workflow supprime : {', '.join(res_del['deleted'])}")
                    st.rerun()
                else:
                    st.error(res_del["message"])


# ═══════════════════════════════════════════════════════════════════
#  PAGE STREAMLIT PRINCIPALE
# ═══════════════════════════════════════════════════════════════════

def page_generateur_roadbook() -> None:
    st.title("🛣️ Générateur Road Trip & Roadbook")
    st.caption("Surcouche LCDMH : roadbook détaillé, PDF, page principale, journal et contrôle Git/GitHub.")

    # ═══ Application des entrées en attente (évite conflit widget Streamlit) ═══
    if st.session_state.get("_pending_journal_entry"):
        st.session_state["roadtrip_journal_entries_raw"] = st.session_state.pop("_pending_journal_entry")
    if st.session_state.get("_pending_roadtrip_journal_entries_raw"):
        st.session_state["roadtrip_journal_entries_raw"] = st.session_state.pop("_pending_roadtrip_journal_entries_raw")
    if st.session_state.get("_pending_roadtrip_main_shorts_raw"):
        st.session_state["roadtrip_main_shorts_raw"] = st.session_state.pop("_pending_roadtrip_main_shorts_raw")
    
    # ═══ Reset de l'input vidéo après action réussie ═══
    if st.session_state.pop("_clear_video_input", False):
        st.session_state["roadtrip_single_video_url"] = ""

    with st.expander("📋 Règles métier & Convention de notation", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🚩 Symboles CSV (Kurviger)")
            st.markdown(
                "| Symbole | Signification |\n"
                "|---------|---------------|\n"
                "| `⚐` | Départ réel du voyage (J1) |\n"
                "| `Ⓥ` | Fin d'étape / nuit → J+1 |\n"
                "| `Ⓢ` | Point de passage (même jour) |\n"
                "| `⚑` | Fin du road trip |\n"
                "| `N1`, `N2` | Nombre de nuits au même lieu |\n"
            )
            st.markdown("**Fichiers**")
            st.markdown(
                "- JPG/JPEG/WEBP = image bandeau hero\n"
                "- PNG = QR code ressources\n"
                "- Templates dans `templates/`"
            )
            st.markdown("**Contexte par défaut**")
            st.markdown(
                "- 🏍️ Moto solo · ⛺ Tente · 💰 Budget éco"
            )
        
        with col2:
            st.markdown("#### ❓ Convention `*xxx xxx ?`")
            st.markdown(
                "| Exemple | Signification |\n"
                "|---------|---------------|\n"
                "| `*visite Édimbourg ?` | 🏛️ Que visiter à Édimbourg ? |\n"
                "| `*bivouac Dunnottar ?` | ⛺ Spot bivouac près de Dunnottar ? |\n"
                "| `*camping Sango prix ?` | 🏕️ Prix du camping Sango ? |\n"
                "| `*camping Sango 18€ option ?` | 🔄 18€ trouvé, y a-t-il MIEUX ? |\n"
                "| `*ferry Cromarty info prix ?` | ⛴️ Infos + prix ferry |\n"
                "| `*shuttle réservation prix ?` | 🚂 Comment réserver + combien ? |\n"
                "| `*drone Applecross ?` | 🎥 Spots drone à filmer ? |\n"
            )
            st.markdown("**Mots-clés actions** : `info`, `prix`, `option`, `réservation`")
            st.markdown("**Règle** : `*xxx ?` = question · sans `*` ni `?` = décidé")

    # Info moteur de templates
    templates_dir = tpl.get_templates_dir(str(MODULE_DIR))
    available = tpl.list_available_templates(templates_dir)
    with st.expander("📄 Templates disponibles", expanded=False):
        if available:
            for name, path in available.items():
                st.text(f"  {name} → {path}")
        else:
            st.warning(f"Aucun template trouvé dans {templates_dir}. Les templates par défaut seront utilisés.")

    defaults = {
        "roadtrip_project_dir": str(MODULE_DIR),
        "roadtrip_site_root": str(_detect_default_work_root()),
        "roadtrip_publish_root": str(_detect_default_publish_root()),
        "roadtrip_github_repo_path": str(DEFAULT_GITHUB_REPO),
        "roadtrip_trip_title": "Road trip moto Écosse 2026",
        "roadtrip_trip_year": 2026,
        "roadtrip_conso": 6.5,
        "roadtrip_uk_price": 1.565,
        "roadtrip_ie_price": 1.73,
        "roadtrip_use_online": False,
        "roadtrip_overwrite_pages": True,
        "roadtrip_update_nav": False,
        "roadtrip_unlock_site_root": False,
        "roadtrip_journey_text": (
            "[AUTO] — Laissez ce texte pour générer automatiquement l'introduction "
            "basée sur les données du CSV (nombre de jours, distance, hébergements)."
        ),
        "roadtrip_main_shorts_raw": "",
        "roadtrip_journal_entries_raw": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    current_project_dir = str(st.session_state.get("roadtrip_project_dir", "") or "").strip()
    previous_project_dir = str(st.session_state.get("_roadtrip_last_project_dir_for_build", "") or "")
    previous_auto_build = str(st.session_state.get("_roadtrip_auto_site_root", "") or "")
    unlock_site_root = bool(st.session_state.get("roadtrip_unlock_site_root", False))
    if current_project_dir:
        auto_build_root = str((Path(current_project_dir).expanduser() / "build"))
        current_site_root = str(st.session_state.get("roadtrip_site_root", "") or "").strip()
        if (not unlock_site_root) or current_project_dir != previous_project_dir or not current_site_root or current_site_root == previous_auto_build:
            st.session_state["roadtrip_site_root"] = auto_build_root
        st.session_state["_roadtrip_last_project_dir_for_build"] = current_project_dir
        st.session_state["_roadtrip_auto_site_root"] = auto_build_root

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Dossier projet / ressources", key="roadtrip_project_dir")
        st.checkbox("Déverrouiller le dossier temporaire", key="roadtrip_unlock_site_root")
        st.text_input("Dossier de travail temporaire", key="roadtrip_site_root", disabled=not bool(st.session_state.get("roadtrip_unlock_site_root", False)))
        st.text_input("Dossier de publication finale", key="roadtrip_publish_root")
        st.text_input("Dépôt local GitHub", key="roadtrip_github_repo_path")
        st.text_input("Titre du road trip", key="roadtrip_trip_title")
    with c2:
        st.number_input("Année du road trip", min_value=2024, max_value=2030, step=1, key="roadtrip_trip_year")
        st.number_input("Consommation L/100", min_value=1.0, max_value=15.0, step=0.1, format="%.1f", key="roadtrip_conso")
        st.number_input("Prix UK (£/L)", min_value=0.5, max_value=5.0, step=0.01, format="%.3f", key="roadtrip_uk_price")
        st.number_input("Prix Irlande (€/L)", min_value=0.5, max_value=5.0, step=0.01, format="%.3f", key="roadtrip_ie_price")
        st.checkbox("Enrichissement en ligne", key="roadtrip_use_online")
        st.checkbox("Écraser les pages existantes", value=True, key="roadtrip_overwrite_pages")
        st.checkbox("Mettre à jour le menu nav.html", key="roadtrip_update_nav")

    st.text_area("Texte immersif / introduction du voyage", height=140, key="roadtrip_journey_text")

    st.subheader("🎬 Shorts / vignettes page principale")
    st.caption("3 vignettes max sur la page d'accueil. Le reste va dans le journal.")
    st.text_area("Vignettes principales", height=120, placeholder="url|titre|description|date", key="roadtrip_main_shorts_raw")

    st.subheader("📖 Entrées de la sous-page journal")
    st.caption("Le journal est la page vivante du voyage.")
    st.text_area("Vidéos / shorts du journal", height=180, placeholder="url|titre|description|date", key="roadtrip_journal_entries_raw")

    st.info("Pipeline : CSV → enrichissement → validation → génération accueil + journal → publication.")

    project_dir = st.session_state["roadtrip_project_dir"]
    site_root = st.session_state["roadtrip_site_root"]
    publish_root = st.session_state["roadtrip_publish_root"]
    github_repo_path = st.session_state["roadtrip_github_repo_path"]
    trip_title = st.session_state["roadtrip_trip_title"]
    trip_year = int(st.session_state["roadtrip_trip_year"])
    conso = float(st.session_state["roadtrip_conso"])
    uk_price = float(st.session_state["roadtrip_uk_price"])
    ie_price = float(st.session_state["roadtrip_ie_price"])
    use_online = bool(st.session_state["roadtrip_use_online"])
    overwrite_pages = bool(st.session_state["roadtrip_overwrite_pages"])
    update_nav_on_publish = bool(st.session_state["roadtrip_update_nav"])
    journey_text = st.session_state["roadtrip_journey_text"]
    main_shorts_raw = st.session_state["roadtrip_main_shorts_raw"]
    journal_entries_raw = st.session_state["roadtrip_journal_entries_raw"]

    if st.button("🚀 Générer le road trip complet", type="primary", use_container_width=True):
        progress = st.progress(0, text="Préparation…")
        status = st.empty()

        def cb(pct: int, text: str):
            progress.progress(int(pct), text=text)
            status.info(text)

        try:
            result = generate_roadtrip_package(
                project_dir=project_dir, site_root=site_root,
                trip_title=trip_title, trip_year=trip_year,
                conso=conso, uk_price=uk_price, ie_price=ie_price,
                journey_text=journey_text,
                main_shorts_raw=main_shorts_raw, journal_entries_raw=journal_entries_raw,
                use_online=use_online, overwrite_public_pages=overwrite_pages,
                progress_callback=cb,
            )
            if not result.get("ok"):
                progress.empty()
                status.error(result.get("message") or "Échec de la génération.")
                if result.get("warnings"):
                    st.code("\n".join(result["warnings"]), language="text")
                return
            progress.progress(100, text="Génération terminée")
            status.success("Projet généré avec succès.")
            st.session_state["roadtrip_last_generation"] = {
                "result": result,
                "work_root": str(Path(site_root).expanduser().resolve()),
                "publish_root": str(Path(publish_root).expanduser().resolve()),
                "repo_path": str(Path(github_repo_path).expanduser().resolve()),
                "trip_title": trip_title, "slug": result["slug"],
                "main_page_name": f"{result['slug']}.html",
                "journal_page_name": f"{result['slug']}-journal.html",
                "git_remote": "origin", "git_branch": "main",
                "require_cname": False, "pull_before_push": False,
                "update_nav": bool(update_nav_on_publish),
            }
            st.success("✅ Génération terminée dans le dossier de travail temporaire.")
            if result.get("warnings"):
                with st.expander("Avertissements", expanded=False):
                    st.code("\n".join(result["warnings"]), language="text")
            # ═══ RAPPORT DE TRAÇAGE TEMPLATE ═══
            if result.get("build_trace"):
                trace_lines = result["build_trace"]
                has_error = any("❌" in line for line in trace_lines)
                has_warning = any("⚠️" in line for line in trace_lines)
                icon = "❌" if has_error else "⚠️" if has_warning else "✅"
                with st.expander(f"{icon} Rapport de traçage template ({len(trace_lines)} étapes)", expanded=has_error):
                    st.code("\n".join(trace_lines), language="text")
            st.markdown("**Fichiers écrits dans le dossier temporaire**")
            st.code("\n".join(result["paths"].values()), language="text")
            st.markdown(
                f"**Liens publics attendus**  \n"
                f"[Page principale](https://lcdmh.com/roadtrips/{result['slug']}.html) · "
                f"[Journal](https://lcdmh.com/roadtrips/{result['slug']}-journal.html) · "
                f"[PDF](https://lcdmh.com/roadbooks/{result['slug']}-roadbook.pdf) · "
                f"[Roadbook HTML](https://lcdmh.com/roadbooks-html/{result['slug']}/index.html)"
            )
            if result["paths"].get("roadbook_pdf"):
                pdf_bytes = Path(result["paths"]["roadbook_pdf"]).read_bytes()
                st.download_button("📄 Télécharger le PDF", data=pdf_bytes, file_name=Path(result["paths"]["roadbook_pdf"]).name, mime="application/pdf", use_container_width=True)
            zip_bytes = _zip_generated_outputs(result["paths"])
            st.download_button("📦 Télécharger le pack", data=zip_bytes, file_name=f"{result['slug']}-outputs.zip", mime="application/zip", use_container_width=True)
        except Exception as exc:
            progress.empty()
            status.error(f"Erreur pendant la génération : {exc}")

    publish_state = st.session_state.get("roadtrip_last_generation")
    if publish_state:
        st.divider()
        st.subheader("📤 Validation et publication")
        st.code(f"Travail temporaire : {publish_state['work_root']}\nPublication finale : {publish_state['publish_root']}\nSlug : {publish_state['slug']}", language="text")
        cpub1, cpub2 = st.columns([2, 1])
        with cpub1:
            if st.button("✅ Valider et publier vers le site", type="secondary", use_container_width=True):
                pub = publish_generated_roadtrip(work_root=publish_state["work_root"], publish_root=publish_state["publish_root"], slug=publish_state["slug"], trip_title=publish_state["trip_title"], update_navigation=bool(publish_state.get("update_nav", False)))
                if pub.get("ok"):
                    st.success(pub.get("message", "Publication terminée."))
                    if pub.get("nav_message"):
                        st.info(pub["nav_message"])
                    st.code("\n".join(pub.get("copied", [])), language="text")
                    st.session_state["roadtrip_git_status"] = _publication_status(repo_path=publish_state["repo_path"], slug=publish_state["slug"], branch=publish_state.get("git_branch", ""), remote=publish_state.get("git_remote", "origin"))
                else:
                    st.error(pub.get("message", "Échec publication."))
                # Toujours afficher le rapport de publication
                if pub.get("publish_trace"):
                    with st.expander("📋 Rapport de publication détaillé", expanded=not pub.get("ok", False)):
                        st.code("\n".join(pub["publish_trace"]), language="text")
        with cpub2:
            if st.button("🧹 Oublier cette génération", use_container_width=True):
                st.session_state.pop("roadtrip_last_generation", None)
                st.session_state.pop("roadtrip_git_status", None)
                st.rerun()

    _render_github_publication_panel()

    # ═══ IMPORT YOUTUBE & PROGRAMMATION ═══
    publish_state = st.session_state.get("roadtrip_last_generation")
    _render_youtube_playlist_panel(
        project_dir=str(st.session_state.get("roadtrip_project_dir", "")),
        publish_root=str(st.session_state.get("roadtrip_publish_root", "")),
        repo_path=str(st.session_state.get("roadtrip_github_repo_path", "")),
    )


if __name__ == "__main__":
    page_generateur_roadbook()
