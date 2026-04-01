#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-Publish Lite LCDMH
========================
Script 100% autonome pour GitHub Actions.
Detecte les nouvelles videos YouTube et les injecte dans le journal du road trip.
Zero dependance PC — tourne entierement sur GitHub.

Usage:
    python scripts/auto_publish_lite.py --config data/roadtrips/MON-TRIP/auto_publish_config.json
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import escape
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════
REPO_ROOT = Path(__file__).resolve().parent.parent
YT_API_KEY_ENV = "YT_API_KEY"  # Cle API YouTube (secret GitHub)

# Fallback : utiliser le token OAuth si pas de cle API
YT_CLIENT_SECRETS_ENV = "YT_CLIENT_SECRETS"
YT_TOKEN_ENV = "YT_TOKEN_ANALYTICS"


def log(msg):
    print(f"[AUTO-PUBLISH] {msg}")


def load_json(path, default=None):
    if default is None:
        default = {}
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════
# YOUTUBE API (sans librairie externe)
# ══════════════════════════════════════════════════════════════════
def youtube_api_get(endpoint, params):
    """Appel simple a l'API YouTube Data v3 via urllib."""
    # Essayer avec la cle API d'abord
    api_key = os.environ.get(YT_API_KEY_ENV, "")

    if not api_key:
        # Essayer d'extraire depuis le token OAuth
        token_json = os.environ.get(YT_TOKEN_ENV, "")
        if token_json:
            try:
                token_data = json.loads(token_json)
                # Si c'est un token OAuth, on l'utilise comme Bearer
                access_token = token_data.get("token", "") or token_data.get("access_token", "")
                if access_token:
                    query = urllib.parse.urlencode(params)
                    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{query}"
                    req = urllib.request.Request(url)
                    req.add_header("Authorization", f"Bearer {access_token}")
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                log(f"OAuth token failed: {e}")

        # Essayer d'extraire la cle API depuis client_secrets
        secrets_json = os.environ.get(YT_CLIENT_SECRETS_ENV, "")
        if secrets_json:
            try:
                secrets = json.loads(secrets_json)
                api_key = (secrets.get("installed", {}).get("api_key", "")
                          or secrets.get("api_key", ""))
            except Exception:
                pass

    if not api_key:
        log("ERREUR: Aucune cle API YouTube trouvee.")
        log("Configurez le secret YT_API_KEY dans GitHub Settings > Secrets")
        return None

    params["key"] = api_key
    query = urllib.parse.urlencode(params)
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{query}"

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        log(f"YouTube API erreur {e.code}: {body}")
        return None
    except Exception as e:
        log(f"YouTube API erreur: {e}")
        return None


def get_playlist_videos(playlist_id, max_results=50):
    """Recupere les videos d'une playlist YouTube."""
    videos = []
    page_token = ""

    while True:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(max_results - len(videos), 50),
        }
        if page_token:
            params["pageToken"] = page_token

        data = youtube_api_get("playlistItems", params)
        if not data:
            break

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            resource = snippet.get("resourceId", {})
            video_id = resource.get("videoId", "")

            if not video_id:
                continue

            title = snippet.get("title", "")
            # Ignorer les videos supprimees/privees
            if title in ("Deleted video", "Private video", ""):
                continue

            published = snippet.get("publishedAt", "")
            description = snippet.get("description", "")[:500]
            thumbnail = ""
            thumbs = snippet.get("thumbnails", {})
            for quality in ("maxresdefault", "high", "medium", "default"):
                if quality in thumbs:
                    thumbnail = thumbs[quality].get("url", "")
                    break

            videos.append({
                "video_id": video_id,
                "title": title,
                "description": description,
                "published_at": published,
                "thumbnail": thumbnail,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            })

        page_token = data.get("nextPageToken", "")
        if not page_token or len(videos) >= max_results:
            break

    return videos


# ══════════════════════════════════════════════════════════════════
# GENERATION HTML
# ══════════════════════════════════════════════════════════════════
def generate_journal_card(video, index):
    """Genere le HTML d'une carte journal pour une video."""
    vid = video["video_id"]
    title = escape(video["title"])
    description = escape(video.get("description", "")[:200])
    thumbnail = video.get("thumbnail", f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg")
    url = video["url"]
    published = video.get("published_at", "")

    # Formater la date
    date_str = ""
    if published:
        try:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            date_str = dt.strftime("%d/%m/%Y")
        except Exception:
            date_str = published[:10]

    return f'''    <article class="journal-card" data-video-id="{vid}">
        <div class="journal-thumb">
            <a href="{url}" target="_blank" rel="noopener">
                <img src="{thumbnail}" alt="{title}" loading="lazy">
            </a>
            <span class="journal-badge">VIDEO</span>
        </div>
        <div class="journal-body">
            <h2>{title}</h2>
            <p>{description}</p>
            <a class="btn-sm" href="{url}" target="_blank" rel="noopener">Voir la video</a>
        </div>
    </article>
    <!-- Entree importee le {datetime.now().strftime('%Y-%m-%d %H:%M')} -->'''


def inject_into_journal(journal_path, new_cards_html):
    """Injecte les nouvelles cartes dans le journal HTML."""
    content = Path(journal_path).read_text(encoding="utf-8")

    # Cas 1 : remplacer le bloc "journal-empty" (journal vierge)
    empty_pattern = r'<article class="journal-empty">.*?</article>'
    if re.search(empty_pattern, content, re.DOTALL):
        content = re.sub(empty_pattern, new_cards_html, content, flags=re.DOTALL)
        Path(journal_path).write_text(content, encoding="utf-8")
        return True

    # Cas 2 : ajouter avant </main> (journal avec des entrees existantes)
    if "</main>" in content:
        content = content.replace("</main>", f"{new_cards_html}\n</main>")
        Path(journal_path).write_text(content, encoding="utf-8")
        return True

    log(f"ERREUR: impossible d'injecter dans {journal_path}")
    return False


def get_existing_video_ids(journal_path):
    """Recupere les video_id deja presents dans le journal."""
    if not Path(journal_path).exists():
        return set()
    content = Path(journal_path).read_text(encoding="utf-8")
    return set(re.findall(r'data-video-id="([^"]+)"', content))


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Auto-publish YouTube videos to LCDMH journal")
    parser.add_argument("--config", required=True, help="Path to auto_publish_config.json")
    args = parser.parse_args()

    # Charger la config
    config_path = REPO_ROOT / args.config
    if not config_path.exists():
        log(f"Config introuvable: {config_path}")
        sys.exit(1)

    config = load_json(config_path)
    slug = config.get("slug", "")
    playlist_id = config.get("playlist_id", "")
    journal_page = config.get("journal_page", "")

    log(f"Slug: {slug}")
    log(f"Playlist: {playlist_id}")
    log(f"Journal: {journal_page}")

    if not playlist_id:
        log("ERREUR: playlist_id manquant dans la config")
        sys.exit(1)

    if not journal_page:
        log("ERREUR: journal_page manquant dans la config")
        sys.exit(1)

    # Chemin du journal
    journal_path = REPO_ROOT / journal_page
    if not journal_path.exists():
        log(f"ERREUR: Journal introuvable: {journal_path}")
        sys.exit(1)

    # Recuperer les videos deja dans le journal
    existing_ids = get_existing_video_ids(journal_path)
    log(f"Videos deja dans le journal: {len(existing_ids)}")

    # Recuperer les videos de la playlist YouTube
    log("Appel API YouTube...")
    videos = get_playlist_videos(playlist_id)

    if not videos:
        log("Aucune video trouvee dans la playlist")
        sys.exit(0)

    log(f"Videos dans la playlist: {len(videos)}")

    # Filtrer les nouvelles videos
    new_videos = [v for v in videos if v["video_id"] not in existing_ids]

    if not new_videos:
        log("Aucune nouvelle video a publier")
        sys.exit(0)

    log(f"Nouvelles videos a injecter: {len(new_videos)}")

    # Trier par date de publication (plus anciennes en premier)
    new_videos.sort(key=lambda v: v.get("published_at", ""))

    # Generer le HTML
    cards_html = "\n".join(
        generate_journal_card(v, i) for i, v in enumerate(new_videos)
    )

    # Injecter dans le journal
    if inject_into_journal(journal_path, cards_html):
        log(f"OK: {len(new_videos)} video(s) injectee(s) dans le journal")
    else:
        log("ERREUR: injection echouee")
        sys.exit(1)

    # Mettre a jour journal_entries.json
    entries_path = REPO_ROOT / "data" / "roadtrips" / slug / "journal_entries.json"
    entries = load_json(entries_path, [])
    for v in new_videos:
        entries.append({
            "video_id": v["video_id"],
            "title": v["title"],
            "url": v["url"],
            "thumbnail": v["thumbnail"],
            "published_at": v["published_at"],
            "injected_at": datetime.now().isoformat(),
        })
    save_json(entries_path, entries)

    # Mettre a jour la config
    config["updated_at"] = datetime.now().isoformat()
    save_json(config_path, config)

    log("Termine avec succes!")


if __name__ == "__main__":
    main()
