# -*- coding: utf-8 -*-
"""auto_publish_roadtrip.py v2 — Script execute par GitHub Actions.

Utilise les credentials OAuth existants (YT_CLIENT_SECRETS + YT_TOKEN_ANALYTICS)
pour interroger l'API YouTube, recuperer les videos d'une playlist,
et injecter les nouvelles dans le journal de bord + page principale.

Secrets GitHub requis (deja configures):
    YT_CLIENT_SECRETS  — contenu JSON du fichier client_secrets.json
    YT_TOKEN_ANALYTICS — contenu JSON du token OAuth

Usage (GitHub Actions):
    python scripts/auto_publish_roadtrip.py \
        --config data/roadtrips/{slug}/auto_publish_config.json

Usage (local):
    python scripts/auto_publish_roadtrip.py \
        --config F:\LCDMH\data\roadtrips\{slug}\auto_publish_config.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional


# === YouTube API via OAuth ===

def _setup_credentials() -> Path:
    """Ecrit les fichiers credentials depuis les variables d'environnement."""
    creds_dir = Path("/tmp/yt_creds") if not sys.platform.startswith("win") else Path("_yt_creds")
    creds_dir.mkdir(parents=True, exist_ok=True)

    # Client secrets
    cs = os.environ.get("YT_CLIENT_SECRETS", "")
    if cs:
        (creds_dir / "client_secrets.json").write_text(cs, encoding="utf-8")

    # Token OAuth
    tok = os.environ.get("YT_TOKEN_ANALYTICS", "")
    if not tok:
        tok = os.environ.get("YT_TOKEN", "")
    if tok:
        (creds_dir / "token.json").write_text(tok, encoding="utf-8")

    return creds_dir


def _get_youtube_service():
    """Cree un service YouTube Data API v3 via OAuth."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        print("ERREUR: pip install google-api-python-client google-auth")
        sys.exit(1)

    creds_dir = _setup_credentials()
    token_path = creds_dir / "token.json"

    if not token_path.exists():
        print(f"ERREUR: token OAuth introuvable. Secrets GitHub manquants?")
        sys.exit(1)

    token_data = json.loads(token_path.read_text(encoding="utf-8"))
    creds = Credentials.from_authorized_user_info(token_data)

    return build("youtube", "v3", credentials=creds)


def fetch_playlist_videos(playlist_id: str) -> List[Dict[str, Any]]:
    """Recupere toutes les videos d'une playlist YouTube via OAuth."""
    service = _get_youtube_service()
    videos: List[Dict[str, Any]] = []
    page_token = None

    while True:
        resp = service.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()

        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            video_id = content.get("videoId", "")

            if not video_id:
                continue

            title = snippet.get("title", "")
            if title in ("Deleted video", "Private video"):
                continue

            thumbs = snippet.get("thumbnails", {})
            thumb = ""
            for key in ("maxres", "standard", "high", "medium", "default"):
                if key in thumbs:
                    thumb = thumbs[key].get("url", "")
                    if thumb:
                        break
            if not thumb:
                thumb = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

            videos.append({
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
                "description": snippet.get("description", ""),
                "thumb": thumb,
                "published": snippet.get("publishedAt", "")[:10],
                "position": snippet.get("position", 0),
            })

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    videos.sort(key=lambda v: v.get("position", 0))
    return videos


# === Detection des videos deja presentes ===

def _extract_existing_video_ids(html_content: str) -> set:
    pattern = r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})'
    return set(re.findall(pattern, html_content))


# === Generation HTML ===

def _format_date_fr() -> str:
    mois = ['', 'JANVIER', 'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN',
            'JUILLET', 'AOUT', 'SEPTEMBRE', 'OCTOBRE', 'NOVEMBRE', 'DECEMBRE']
    now = datetime.now()
    return f"{now.day} {mois[now.month]} {now.year}"


def _make_journal_card(video: Dict[str, Any], date_label: str) -> str:
    url = escape(video.get("url", ""))
    title = escape(video.get("title", "Video"))
    desc = escape((video.get("description") or "")[:250])
    thumb = escape(video.get("thumb", ""))
    dl = escape(date_label)
    return f'''
        <!-- Entree importee le {datetime.now().strftime('%Y-%m-%d %H:%M')} par GitHub Actions -->
        <div class="journal-card">
            <div class="journal-thumb">
                <span class="journal-badge">{dl}</span>
                <a href="{url}" target="_blank">
                    <img src="{thumb}" alt="{title}" loading="lazy">
                </a>
            </div>
            <div class="journal-body">
                <h3>{title}</h3>
                <p>{desc}</p>
                <a href="{url}" target="_blank" style="display:inline-block;width:auto;max-width:fit-content;padding:.55rem 1.2rem;background:#1a1a1a;color:#fff;border-radius:8px;font-size:.85rem;font-weight:600;text-decoration:none;">Voir la video</a>
            </div>
        </div>
'''


def _make_main_card(video: Dict[str, Any], date_label: str, slug: str) -> str:
    title = escape(video.get("title", "Video"))
    desc = escape((video.get("description") or "")[:120])
    thumb = escape(video.get("thumb", ""))
    dl = escape(date_label)
    journal_href = escape(f"/roadtrips/{slug}-journal.html")
    return f'''
        <!-- Video importee le {datetime.now().strftime('%Y-%m-%d %H:%M')} par GitHub Actions -->
        <div class="short-card">
            <div class="short-thumb">
                <span class="short-badge">{dl}</span>
                <a href="{journal_href}">
                    <img src="{thumb}" alt="{title}" loading="lazy">
                </a>
            </div>
            <div class="short-body">
                <h3>{title}</h3>
                <p>{desc}</p>
                <a href="{journal_href}" class="btn btn-dark">Voir le short</a>
            </div>
        </div>
'''


# === Injection ===

def inject_into_journal(journal_path: Path, card_html: str) -> bool:
    content = journal_path.read_text(encoding="utf-8")
    pattern = r'(<div[^>]*class="[^"]*section-kicker[^"]*"[^>]*>[^<]*</div>\s*)'
    if re.search(pattern, content, re.IGNORECASE):
        content = re.sub(pattern, r'\1\n' + card_html, content, count=1, flags=re.IGNORECASE)
        journal_path.write_text(content, encoding="utf-8")
        return True
    if 'class="journal-empty"' in content:
        idx = content.index('class="journal-empty"')
        tag_start = content.rfind('<', 0, idx)
        if tag_start >= 0:
            content = content[:tag_start] + card_html + '\n        ' + content[tag_start:]
            journal_path.write_text(content, encoding="utf-8")
            return True
    return False


def inject_into_main(main_path: Path, card_html: str, max_cards: int = 3) -> bool:
    content = main_path.read_text(encoding="utf-8")
    if content.count('class="short-card"') >= max_cards:
        print(f"  Page principale deja pleine ({max_cards}/{max_cards}), skip")
        return False
    pattern = r'(<div[^>]*class="[^"]*jnl-grid[^"]*"[^>]*>)'
    if re.search(pattern, content, re.IGNORECASE):
        content = re.sub(pattern, r'\1\n' + card_html, content, count=1, flags=re.IGNORECASE)
        main_path.write_text(content, encoding="utf-8")
        return True
    return False


# === Main ===

def main():
    parser = argparse.ArgumentParser(description="Auto-publish road trip videos")
    parser.add_argument("--config", required=True, help="Path to auto_publish_config.json")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas modifier les fichiers")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERREUR: config introuvable: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    slug = config["slug"]
    playlist_id = config["playlist_id"]
    journal_rel = config.get("journal_page", f"roadtrips/{slug}-journal.html")
    main_rel = config.get("main_page", f"roadtrips/{slug}.html")
    max_cards = config.get("max_main_cards", 3)

    repo_root = Path(".")
    journal_path = repo_root / journal_rel
    main_path = repo_root / main_rel

    print(f"=== Auto-publish pour {slug} ===")
    print(f"Playlist: {config.get('playlist_name', playlist_id)}")
    print(f"Journal: {journal_path} (existe: {journal_path.exists()})")
    print(f"Page principale: {main_path} (existe: {main_path.exists()})")

    if not journal_path.exists():
        print(f"ERREUR: journal introuvable: {journal_path}")
        sys.exit(1)

    # Recuperer les videos
    print(f"\nRecuperation des videos de la playlist...")
    try:
        videos = fetch_playlist_videos(playlist_id)
    except Exception as exc:
        print(f"ERREUR API YouTube: {exc}")
        sys.exit(1)

    print(f"  {len(videos)} video(s) dans la playlist")

    if not videos:
        print("Aucune video, rien a faire.")
        return

    # Videos deja presentes
    journal_content = journal_path.read_text(encoding="utf-8")
    existing_ids = _extract_existing_video_ids(journal_content)
    if main_path.exists():
        existing_ids.update(_extract_existing_video_ids(main_path.read_text(encoding="utf-8")))

    new_videos = [v for v in videos if v["video_id"] not in existing_ids]
    print(f"  {len(new_videos)} nouvelle(s) video(s) a publier")

    if not new_videos:
        print("Tout est deja a jour.")
        return

    if args.dry_run:
        print("\n[DRY RUN] Videos qui seraient publiees:")
        for v in new_videos:
            print(f"  - {v['title']}")
        return

    # Injecter
    date_label = _format_date_fr()
    journal_modified = False
    main_modified = False

    for i, video in enumerate(new_videos):
        print(f"\n  [{i+1}/{len(new_videos)}] {video['title']}")

        card = _make_journal_card(video, date_label)
        ok = inject_into_journal(journal_path, card)
        if ok:
            journal_modified = True
            print(f"    Journal: OK")
        else:
            print(f"    Journal: ECHEC")

        if main_path.exists():
            card = _make_main_card(video, date_label, slug)
            ok = inject_into_main(main_path, card, max_cards)
            if ok:
                main_modified = True
                print(f"    Page principale: OK")

    # Sauvegarder l'etat
    state_path = config_path.parent / "published_videos.json"
    published = []
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                published = json.load(f)
        except Exception:
            pass

    for v in new_videos:
        published.append({
            "video_id": v["video_id"],
            "title": v["title"],
            "published_at": datetime.now().isoformat(timespec="seconds"),
        })

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(published, f, ensure_ascii=False, indent=2)

    print(f"\n=== Termine: {len(new_videos)} video(s) publiee(s) ===")


if __name__ == "__main__":
    main()
