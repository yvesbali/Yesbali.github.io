# -*- coding: utf-8 -*-
"""
LCDMH — Auto-publish Road Trip CLI v1.0
=======================================
Script CLI pour GitHub Actions qui surveille une playlist YouTube
et injecte automatiquement les nouvelles vidéos dans les pages road trip.

Usage:
    python auto_publish_roadtrip.py --config data/roadtrips/xxx/auto_publish_config.json

Le script lit la config, récupère les vidéos de la playlist YouTube,
et injecte les nouvelles dans le journal + page principale.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parent.parent  # Racine du repo GitHub


# ═══════════════════════════════════════════════════════════════════
#  YOUTUBE API (via secrets GitHub)
# ═══════════════════════════════════════════════════════════════════

def get_youtube_service():
    """Crée un service YouTube API à partir des secrets GitHub."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    
    # Lire les credentials depuis les variables d'environnement
    client_secrets_json = os.environ.get("YT_CLIENT_SECRETS", "")
    token_json = os.environ.get("YT_TOKEN_ANALYTICS", "")
    
    if not client_secrets_json or not token_json:
        raise RuntimeError(
            "Variables d'environnement manquantes: YT_CLIENT_SECRETS et/ou YT_TOKEN_ANALYTICS. "
            "Vérifiez les secrets GitHub."
        )
    
    try:
        token_data = json.loads(token_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"YT_TOKEN_ANALYTICS n'est pas un JSON valide: {e}")
    
    # Créer les credentials
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes", ["https://www.googleapis.com/auth/youtube.readonly"]),
    )
    
    return build("youtube", "v3", credentials=creds)


def fetch_playlist_videos(playlist_id: str) -> List[Dict[str, Any]]:
    """Récupère toutes les vidéos d'une playlist YouTube."""
    service = get_youtube_service()
    
    items: List[Dict[str, Any]] = []
    token = None
    
    while True:
        response = service.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=token
        ).execute()
        
        items.extend(response.get("items", []))
        token = response.get("nextPageToken")
        if not token:
            break
    
    # Récupérer les métadonnées détaillées des vidéos
    video_ids = [item.get("contentDetails", {}).get("videoId", "") for item in items]
    video_ids = [v for v in video_ids if v]
    
    videos_meta: Dict[str, Dict] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        if not chunk:
            continue
        resp = service.videos().list(
            part="snippet,contentDetails,status",
            id=",".join(chunk),
            maxResults=50
        ).execute()
        for v in resp.get("items", []):
            videos_meta[v.get("id", "")] = v
    
    # Construire la liste des vidéos
    result: List[Dict[str, Any]] = []
    for item in items:
        video_id = item.get("contentDetails", {}).get("videoId", "")
        if not video_id:
            continue
        
        meta = videos_meta.get(video_id, {})
        snippet = meta.get("snippet", item.get("snippet", {}))
        content = meta.get("contentDetails", {})
        position = item.get("snippet", {}).get("position", 0)
        
        # Calculer la durée
        duration_s = parse_iso8601_duration(content.get("duration", ""))
        
        # Extraire la date de publication
        published = snippet.get("publishedAt", "")
        date_label = format_date_label(published) if published else ""
        
        # Thumbnail
        thumbs = snippet.get("thumbnails", {})
        thumb = (
            thumbs.get("maxres", {}).get("url") or
            thumbs.get("high", {}).get("url") or
            thumbs.get("medium", {}).get("url") or
            thumbs.get("default", {}).get("url") or
            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        )
        
        result.append({
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": snippet.get("title", f"Vidéo {position + 1}"),
            "description": snippet.get("description", ""),
            "thumb": thumb,
            "date_label": date_label,
            "published_at": published,
            "position": position,
            "is_short": 0 < duration_s <= 70,
        })
    
    # Trier par position
    result.sort(key=lambda x: x.get("position", 0))
    return result


def parse_iso8601_duration(duration: str) -> int:
    """Parse une durée ISO 8601 (ex: PT1M30S) en secondes."""
    if not duration:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def format_date_label(iso_date: str) -> str:
    """Convertit une date ISO en label français (ex: 25 MARS 2026)."""
    if not iso_date:
        return ""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        months_fr = [
            "", "JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN",
            "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"
        ]
        return f"{dt.day} {months_fr[dt.month]} {dt.year}"
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════
#  DÉTECTION VIDÉOS DÉJÀ INJECTÉES
# ═══════════════════════════════════════════════════════════════════

def get_injected_video_ids(html_path: Path) -> List[str]:
    """Extrait les IDs des vidéos déjà injectées dans une page HTML."""
    if not html_path.exists():
        return []
    
    content = html_path.read_text(encoding="utf-8", errors="replace")
    
    # Pattern pour trouver les URLs YouTube
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'data-video-id="([a-zA-Z0-9_-]{11})"',
    ]
    
    video_ids = set()
    for pattern in patterns:
        matches = re.findall(pattern, content)
        video_ids.update(matches)
    
    return list(video_ids)


# ═══════════════════════════════════════════════════════════════════
#  GÉNÉRATION HTML
# ═══════════════════════════════════════════════════════════════════

def generate_journal_entry_html(video: Dict[str, Any]) -> str:
    """Génère le HTML d'une entrée journal."""
    title = escape(video.get("title", ""))
    desc = escape(video.get("description", "")[:200])
    thumb = video.get("thumb", "")
    url = video.get("url", "")
    date_label = video.get("date_label", "")
    
    return f'''
        <article class="journal-card" data-video-id="{video.get('video_id', '')}">
            <a href="{url}" target="_blank" rel="noopener" class="journal-card-link">
                <div class="journal-thumb">
                    <img src="{thumb}" alt="{title}" loading="lazy">
                    <span class="play-icon">▶</span>
                </div>
                <div class="journal-content">
                    <time class="journal-date">{date_label}</time>
                    <h3 class="journal-title">{title}</h3>
                    <p class="journal-excerpt">{desc}</p>
                </div>
            </a>
        </article>'''


def generate_main_card_html(video: Dict[str, Any], journal_href: str = "") -> str:
    """Génère le HTML d'une carte pour la page principale."""
    title = escape(video.get("title", ""))
    thumb = video.get("thumb", "")
    url = video.get("url", "")
    date_label = video.get("date_label", "")
    href = journal_href if journal_href else url
    
    return f'''
        <a href="{href}" class="jnl-card" data-video-id="{video.get('video_id', '')}">
            <div class="jnl-thumb">
                <img src="{thumb}" alt="{title}" loading="lazy">
            </div>
            <div class="jnl-info">
                <span class="jnl-date">{date_label}</span>
                <h4>{title}</h4>
            </div>
        </a>'''


# ═══════════════════════════════════════════════════════════════════
#  INJECTION HTML
# ═══════════════════════════════════════════════════════════════════

def inject_into_journal(journal_path: Path, video: Dict[str, Any]) -> Dict[str, Any]:
    """Injecte une vidéo dans le fichier journal HTML."""
    result = {"ok": False, "message": "", "trace": []}
    
    if not journal_path.exists():
        result["message"] = f"Journal introuvable: {journal_path}"
        return result
    
    content = journal_path.read_text(encoding="utf-8")
    entry_html = generate_journal_entry_html(video)
    
    # Patterns d'insertion (après l'ouverture de la section)
    patterns = [
        (r'(<div[^>]*class="[^"]*section-kicker[^"]*"[^>]*>[^<]*</div>\s*)', r'\1\n' + entry_html),
        (r'(<section[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)', r'\1\n' + entry_html),
        (r'(<div[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)', r'\1\n' + entry_html),
    ]
    
    inserted = False
    for pattern, replacement in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
            result["trace"].append(f"✅ Pattern matché")
            inserted = True
            break
    
    if not inserted:
        # Fallback: chercher la première journal-card et insérer avant
        if 'class="journal-card"' in content:
            idx = content.index('class="journal-card"')
            tag_start = content.rfind('<', 0, idx)
            if tag_start >= 0:
                content = content[:tag_start] + entry_html + '\n        ' + content[tag_start:]
                inserted = True
                result["trace"].append("✅ Fallback matché")
    
    if not inserted:
        result["message"] = "Point d'insertion introuvable dans le journal"
        return result
    
    # Backup + écriture
    backup = journal_path.with_suffix(".html.backup")
    shutil.copy2(journal_path, backup)
    journal_path.write_text(content, encoding="utf-8")
    
    result["ok"] = True
    result["message"] = f"Vidéo injectée dans {journal_path.name}"
    return result


def inject_into_main(main_path: Path, video: Dict[str, Any], journal_href: str = "") -> Dict[str, Any]:
    """Injecte une vidéo dans la page principale HTML."""
    result = {"ok": False, "message": "", "trace": []}
    
    if not main_path.exists():
        result["message"] = f"Page principale introuvable: {main_path}"
        return result
    
    content = main_path.read_text(encoding="utf-8")
    entry_html = generate_main_card_html(video, journal_href)
    
    # Patterns d'insertion
    patterns = [
        (r'(<div[^>]*class="[^"]*journal-preview[^"]*"[^>]*>)', r'\1\n' + entry_html),
        (r'(<div[^>]*class="[^"]*jnl-grid[^"]*"[^>]*>)', r'\1\n' + entry_html),
        (r'(<div[^>]*class="[^"]*coming-soon-grid[^"]*"[^>]*>)', r'\1\n' + entry_html),
    ]
    
    inserted = False
    for pattern, replacement in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
            inserted = True
            break
    
    if not inserted:
        # Fallback
        if 'class="jnl-card"' in content:
            idx = content.index('class="jnl-card"')
            tag_start = content.rfind('<', 0, idx)
            if tag_start >= 0:
                content = content[:tag_start] + entry_html + '\n        ' + content[tag_start:]
                inserted = True
    
    if not inserted:
        result["message"] = "Point d'insertion introuvable sur la page principale"
        return result
    
    backup = main_path.with_suffix(".html.backup")
    shutil.copy2(main_path, backup)
    main_path.write_text(content, encoding="utf-8")
    
    result["ok"] = True
    result["message"] = f"Vidéo injectée dans {main_path.name}"
    return result


def count_main_cards(main_path: Path) -> int:
    """Compte le nombre de cartes vidéo sur la page principale."""
    if not main_path.exists():
        return 0
    content = main_path.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(r'class="jnl-card"', content))


# ═══════════════════════════════════════════════════════════════════
#  MAIN CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Auto-publish road trip videos from YouTube playlist")
    parser.add_argument("--config", required=True, help="Path to auto_publish_config.json")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas modifier les fichiers")
    args = parser.parse_args()
    
    # Charger la configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ Config introuvable: {config_path}")
        sys.exit(1)
    
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    
    print("=" * 60)
    print("LCDMH — Auto-publish Road Trip CLI")
    print(f"Config: {config_path}")
    print("=" * 60)
    
    # Extraire les paramètres
    playlist_id = config.get("playlist_id", "")
    playlist_name = config.get("playlist_name", "")
    journal_page = config.get("journal_page", "")
    main_page = config.get("main_page", "")
    max_main_cards = config.get("max_main_cards", 3)
    slug = config.get("slug", "")
    
    print(f"\n📋 Playlist: {playlist_name}")
    print(f"   ID: {playlist_id}")
    print(f"   Journal: {journal_page}")
    print(f"   Main: {main_page}")
    print(f"   Max cards: {max_main_cards}")
    
    # Chemins des fichiers HTML
    journal_path = REPO_ROOT / journal_page
    main_path = REPO_ROOT / main_page
    
    print(f"\n📂 Chemins:")
    print(f"   Journal: {journal_path} {'✅' if journal_path.exists() else '❌'}")
    print(f"   Main: {main_path} {'✅' if main_path.exists() else '❌'}")
    
    if not journal_path.exists():
        print(f"\n❌ Le fichier journal n'existe pas: {journal_path}")
        sys.exit(1)
    
    # Récupérer les vidéos de la playlist
    print(f"\n🎬 Récupération des vidéos YouTube...")
    try:
        videos = fetch_playlist_videos(playlist_id)
        print(f"   {len(videos)} vidéos trouvées dans la playlist")
    except Exception as e:
        print(f"❌ Erreur YouTube API: {e}")
        sys.exit(1)
    
    if not videos:
        print("   Aucune vidéo dans la playlist.")
        sys.exit(0)
    
    # Trouver les vidéos déjà injectées
    journal_injected = set(get_injected_video_ids(journal_path))
    main_injected = set(get_injected_video_ids(main_path)) if main_path.exists() else set()
    
    print(f"\n📊 État actuel:")
    print(f"   Vidéos dans journal: {len(journal_injected)}")
    print(f"   Vidéos dans main: {len(main_injected)}")
    
    # Trouver les nouvelles vidéos
    new_videos = [v for v in videos if v["video_id"] not in journal_injected]
    
    if not new_videos:
        print("\n✅ Aucune nouvelle vidéo à injecter.")
        sys.exit(0)
    
    print(f"\n🆕 {len(new_videos)} nouvelle(s) vidéo(s) à injecter:")
    for v in new_videos:
        print(f"   • {v['title'][:50]}...")
    
    if args.dry_run:
        print("\n🔍 Mode dry-run: aucune modification effectuée.")
        sys.exit(0)
    
    # Injecter les nouvelles vidéos
    injected_count = 0
    current_main_cards = count_main_cards(main_path) if main_path.exists() else 0
    journal_href = f"/roadtrips/{slug}-journal.html" if slug else ""
    
    for video in new_videos:
        print(f"\n→ Injection: {video['title'][:40]}...")
        
        # Toujours injecter dans le journal
        result = inject_into_journal(journal_path, video)
        if result["ok"]:
            print(f"   ✅ Journal OK")
            injected_count += 1
        else:
            print(f"   ❌ Journal: {result['message']}")
            continue
        
        # Injecter dans la page principale si on n'a pas atteint la limite
        if main_path.exists() and current_main_cards < max_main_cards:
            result_main = inject_into_main(main_path, video, journal_href)
            if result_main["ok"]:
                print(f"   ✅ Main OK")
                current_main_cards += 1
            else:
                print(f"   ⚠️ Main: {result_main['message']}")
        elif current_main_cards >= max_main_cards:
            print(f"   ℹ️ Main: limite {max_main_cards} cartes atteinte")
    
    # Mettre à jour la date dans la config
    config["updated_at"] = datetime.now().isoformat()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ {injected_count} vidéo(s) injectée(s)")
    print(f"{'='*60}")
    
    if injected_count == 0:
        sys.exit(0)
    
    # Note: Le commit/push est géré par le workflow GitHub Actions
    sys.exit(0)


if __name__ == "__main__":
    main()
