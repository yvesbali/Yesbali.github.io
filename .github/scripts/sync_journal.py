#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
.github/scripts/sync_journal.py — LCDMH
Robot de synchronisation journal de bord road trip.

Tourne toutes les soirs à 18h UTC via GitHub Actions.
Pour chaque road trip actif (trip_status != 'termine') :
  1. Lit data/videos.json (déjà mis à jour par fetch_youtube.py)
  2. Charge roadtrips/{slug}/journal.json
  3. Détecte les nouveaux shorts non encore dans le journal
  4. Les ajoute au journal.json
  5. Régénère journal.html depuis le template
  6. Régénère les pages jour concernées (ajout de la vidéo dans la section journal)

Les shorts sont associés à un jour selon leur date de publication.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from jinja2 import Environment, FileSystemLoader
    JINJA2_OK = True
except ImportError:
    JINJA2_OK = False

# ── Config ───────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parents[2]
TRIPS_DIR   = REPO_ROOT / "roadtrips"
VIDEOS_JSON = REPO_ROOT / "data" / "videos.json"
TEMPLATE_JOURNAL = REPO_ROOT / "template_roadtrip_journal.html"
TEMPLATE_DAY     = REPO_ROOT / "template_roadtrip_day.html"


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def log(msg: str):
    print(f"[sync_journal] {msg}", flush=True)


def extract_youtube_id(url: str) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().replace("www.", "")
    path = (parsed.path or "").strip("/")

    if host == "youtu.be":
        cand = path.split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", cand):
            return cand

    if "youtube.com" in host:
        if "watch" in path:
            qs = parse_qs(parsed.query)
            v = (qs.get("v") or [None])[0]
            if v and re.fullmatch(r"[A-Za-z0-9_-]{11}", v):
                return v
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live"):
            cand = parts[1]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", cand):
                return cand
    return None


def get_thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def detect_video_kind(url: str) -> str:
    return "short" if "/shorts/" in (url or "").lower() else "video"


def parse_published_date(published: str) -> Optional[date]:
    if not published:
        return None
    try:
        return datetime.fromisoformat(published[:10]).date()
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(published[:10], fmt).date()
        except ValueError:
            continue
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT DES DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

def load_videos_json() -> List[Dict]:
    if not VIDEOS_JSON.exists():
        log(f"⚠️ {VIDEOS_JSON} introuvable")
        return []
    with open(VIDEOS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    # videos.json peut être une liste directe ou {"videos": [...]}
    if isinstance(data, list):
        return data
    return data.get("videos", [])


def load_journal(trip_dir: Path) -> Dict:
    journal_path = trip_dir / "journal.json"
    if journal_path.exists():
        with open(journal_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": [], "trip_slug": trip_dir.name, "last_updated": ""}


def save_journal(trip_dir: Path, journal: Dict):
    journal["last_updated"] = datetime.now().isoformat()
    journal_path = trip_dir / "journal.json"
    with open(journal_path, "w", encoding="utf-8") as f:
        json.dump(journal, f, ensure_ascii=False, indent=2)
    log(f"✅ journal.json sauvegardé — {len(journal['entries'])} entrées")


def load_trip_config(trip_dir: Path) -> Optional[Dict]:
    """Charge la config du trip depuis trip_config.json s'il existe."""
    config_path = trip_dir / "trip_config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION DES NOUVEAUX SHORTS
# ══════════════════════════════════════════════════════════════════════════════

def filter_trip_videos(videos: List[Dict], trip_config: Optional[Dict]) -> List[Dict]:
    """
    Filtre les vidéos pertinentes pour ce road trip.
    Critères : mots-clés dans le titre OU dans la période du voyage.
    """
    if not trip_config:
        return []

    keywords = [k.lower() for k in trip_config.get("video_keywords", [])]
    trip_start = parse_published_date(trip_config.get("date_start", ""))
    trip_end   = parse_published_date(trip_config.get("date_end", ""))

    matching = []
    for v in videos:
        title = (v.get("title") or v.get("video_title") or "").lower()
        url   = v.get("url") or v.get("short_url") or v.get("video_url") or ""
        pub   = parse_published_date(v.get("published") or v.get("published_at") or "")
        kind  = detect_video_kind(url)

        # Match par mots-clés
        kw_match = any(kw in title for kw in keywords) if keywords else False

        # Match par période (shorts publiés pendant le voyage)
        period_match = False
        if trip_start and pub:
            if trip_end:
                period_match = trip_start <= pub <= trip_end
            else:
                period_match = pub >= trip_start

        if kw_match or period_match:
            # Enrichir avec les métadonnées manquantes
            vid_id = extract_youtube_id(url)
            if vid_id:
                v_enriched = dict(v)
                v_enriched["youtube_id"] = vid_id
                v_enriched["youtube_kind"] = kind
                v_enriched["youtube_url"] = url
                v_enriched["youtube_thumbnail_url"] = v.get("thumb") or get_thumbnail_url(vid_id)
                v_enriched["published_date"] = pub.isoformat() if pub else ""
                matching.append(v_enriched)

    return matching


def find_new_videos(matching_videos: List[Dict], existing_entries: List[Dict]) -> List[Dict]:
    """Retourne les vidéos non encore dans le journal."""
    existing_ids = {e.get("youtube_id") for e in existing_entries if e.get("youtube_id")}
    new = []
    for v in matching_videos:
        vid_id = v.get("youtube_id")
        if vid_id and vid_id not in existing_ids:
            new.append(v)
    return new


def create_journal_entry(video: Dict, entry_num: int, trip_config: Optional[Dict] = None) -> Dict:
    """Crée une entrée journal depuis une vidéo YouTube."""
    pub = video.get("published_date") or video.get("published") or ""
    pub_date = parse_published_date(pub)

    # Déterminer le jour du voyage
    jour_num = None
    if pub_date and trip_config:
        trip_start = parse_published_date(trip_config.get("date_start", ""))
        if trip_start and pub_date >= trip_start:
            jour_num = (pub_date - trip_start).days + 1

    title = (video.get("title") or video.get("video_title") or
             video.get("youtube_title_auto") or f"Jour {jour_num or entry_num}")

    return {
        "entry_num": entry_num,
        "youtube_id": video["youtube_id"],
        "youtube_url": video["youtube_url"],
        "youtube_kind": video["youtube_kind"],
        "youtube_thumbnail_url": video["youtube_thumbnail_url"],
        "youtube_title_auto": title,
        "title": title,
        "description": video.get("description") or video.get("desc") or "",
        "date": pub_date.strftime("%d %B %Y") if pub_date else "",
        "date_iso": pub_date.isoformat() if pub_date else "",
        "jour_num": jour_num,
        "lieu": "",
        "day_url": f"roadbook/jour-{jour_num:02d}.html" if jour_num else "",
    }


# ══════════════════════════════════════════════════════════════════════════════
# GÉNÉRATION HTML
# ══════════════════════════════════════════════════════════════════════════════

def render_template_simple(template_path: Path, context: Dict) -> str:
    if JINJA2_OK:
        env = Environment(loader=FileSystemLoader(str(template_path.parent)), autoescape=False)
        tpl = env.get_template(template_path.name)
        return tpl.render(**context)
    # Fallback
    tpl = template_path.read_text(encoding="utf-8")
    for key, val in context.items():
        tpl = tpl.replace("{{ " + key + " }}", str(val or ""))
    return tpl


def regenerate_journal_html(trip_dir: Path, journal: Dict, trip_config: Optional[Dict]):
    if not TEMPLATE_JOURNAL.exists():
        log(f"⚠️ Template journal introuvable : {TEMPLATE_JOURNAL}")
        return

    total_days = trip_config.get("total_days", 0) if trip_config else 0
    nb_entries = len(journal.get("entries", []))
    progress = int(nb_entries / total_days * 100) if total_days > 0 else 0

    status = "a-venir"
    if nb_entries > 0 and nb_entries < total_days:
        status = "en-cours"
    elif nb_entries >= total_days and total_days > 0:
        status = "termine"

    context = {
        "trip_title": trip_config.get("title", "") if trip_config else "",
        "trip_slug":  trip_config.get("slug", trip_dir.name) if trip_config else trip_dir.name,
        "trip_year":  trip_config.get("year", datetime.now().year) if trip_config else datetime.now().year,
        "trip_days":  total_days,
        "trip_distance": trip_config.get("distance_km", "") if trip_config else "",
        "entries": sorted(journal.get("entries", []), key=lambda x: x.get("entry_num", 0), reverse=True),
        "progress_pct": progress,
        "trip_status": status,
    }

    html = render_template_simple(TEMPLATE_JOURNAL, context)
    (trip_dir / "journal.html").write_text(html, encoding="utf-8")
    log(f"✅ journal.html régénéré ({nb_entries} entrées)")


def update_day_page(trip_dir: Path, jour_num: int, entry: Dict, trip_config: Optional[Dict]):
    """Met à jour une page détail jour pour ajouter la vidéo du journal."""
    day_file = trip_dir / "roadbook" / f"jour-{jour_num:02d}.html"
    if not day_file.exists():
        log(f"⚠️ Page jour introuvable : {day_file}")
        return

    # Lire la page existante et injecter la vidéo dans la section journal
    content = day_file.read_text(encoding="utf-8")

    # Remplacer la section "Le short de cette journée n'a pas encore été publié"
    placeholder = "Le short de cette journée n'a pas encore été publié."
    if placeholder in content and entry.get("youtube_thumbnail_url"):
        thumb = entry["youtube_thumbnail_url"]
        url   = entry["youtube_url"]
        title = entry.get("title", "Short du jour")
        kind  = entry.get("youtube_kind", "short")
        badge_label = "SHORT" if kind == "short" else "VIDÉO"
        badge_color = "#ff0000" if kind == "short" else "#1565c0"

        new_video_block = f"""
      <div class="video-body">
        <a href="{url}" target="_blank" rel="noopener" class="video-thumb">
          <img src="{thumb}" alt="{title}" loading="lazy">
          <div class="play-over"><div class="play-circ">▶</div></div>
        </a>
        <div class="video-info">
          <span class="vid-badge" style="background:{badge_color}">{badge_label}</span>
          <div class="vid-title">{title}</div>
          <a href="{url}" target="_blank" rel="noopener" class="vid-btn">▶ Voir le {kind}</a>
        </div>
      </div>"""

        content = content.replace(
            f'<div class="video-none">\n      🎬 {placeholder}\n    </div>',
            new_video_block
        )
        day_file.write_text(content, encoding="utf-8")
        log(f"✅ jour-{jour_num:02d}.html mis à jour avec la vidéo")


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

def process_trip(trip_dir: Path, videos: List[Dict]) -> int:
    """Traite un road trip. Retourne le nombre de nouvelles entrées ajoutées."""
    slug = trip_dir.name
    log(f"\n── Traitement du road trip : {slug}")

    trip_config = load_trip_config(trip_dir)
    if not trip_config:
        log(f"  ⚠️ Pas de trip_config.json — vérification par présence du dossier seulement")

    journal = load_journal(trip_dir)
    existing_entries = journal.get("entries", [])

    # Filtrer les vidéos pertinentes
    matching = filter_trip_videos(videos, trip_config)
    log(f"  📺 {len(matching)} vidéos correspondantes trouvées")

    # Détecter les nouvelles
    new_videos = find_new_videos(matching, existing_entries)
    log(f"  🆕 {len(new_videos)} nouvelles vidéos à ajouter")

    if not new_videos:
        return 0

    # Trier par date de publication (du plus ancien au plus récent)
    new_videos.sort(key=lambda v: v.get("published_date") or "")

    # Ajouter au journal
    next_num = max((e.get("entry_num", 0) for e in existing_entries), default=0) + 1
    added = 0
    for v in new_videos:
        entry = create_journal_entry(v, next_num, trip_config)
        existing_entries.append(entry)
        log(f"  ✅ Entrée {next_num} ajoutée : {entry['title'][:60]}")

        # Mettre à jour la page jour si le numéro de jour est connu
        if entry.get("jour_num"):
            update_day_page(trip_dir, entry["jour_num"], entry, trip_config)

        next_num += 1
        added += 1

    journal["entries"] = existing_entries
    save_journal(trip_dir, journal)
    regenerate_journal_html(trip_dir, journal, trip_config)
    return added


def main():
    log("=== Sync Journal Road Trip démarré ===")
    log(f"Répertoire : {REPO_ROOT}")

    if not VIDEOS_JSON.exists():
        log("❌ data/videos.json introuvable — abandon")
        sys.exit(1)

    videos = load_videos_json()
    log(f"📺 {len(videos)} vidéos chargées depuis data/videos.json")

    if not TRIPS_DIR.exists():
        log(f"⚠️ Dossier roadtrips/ introuvable ({TRIPS_DIR}) — aucun trip à traiter")
        sys.exit(0)

    # Trouver tous les road trips (dossiers avec journal.json ou trip_config.json)
    trip_dirs = [
        d for d in TRIPS_DIR.iterdir()
        if d.is_dir() and (
            (d / "journal.json").exists() or
            (d / "trip_config.json").exists()
        )
    ]
    log(f"🗂️ {len(trip_dirs)} road trip(s) trouvé(s) : {[d.name for d in trip_dirs]}")

    total_added = 0
    for trip_dir in trip_dirs:
        try:
            added = process_trip(trip_dir, videos)
            total_added += added
        except Exception as e:
            log(f"❌ Erreur sur {trip_dir.name} : {e}")

    log(f"\n=== Terminé — {total_added} nouvelles entrées ajoutées ===")


if __name__ == "__main__":
    main()
