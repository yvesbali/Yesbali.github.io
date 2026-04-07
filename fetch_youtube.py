"""
fetch_youtube.py — Feed YouTube automatique pour lcdmh.com
Appelé par GitHub Actions (update_videos.yml) tous les matins à 6h UTC.

Produit :
  data/videos.json          → lu par js/youtube-feed.js (page d'accueil)
  data/trips/{slug}.json    → lu par js/trip-feed.js (pages voyage)

Le workflow fait ensuite git add data/ + commit + push automatiquement.
"""

import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

# ─────────────────────────────────────────────────────────────
# CONFIGURATION (secrets injectés par GitHub Actions)
# ─────────────────────────────────────────────────────────────
CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")

CHANNEL_ID = "UCsmjag8fMTAqdawlg35T3Bg"  # LCDMH

# Seuil en secondes pour distinguer un Short d'une vidéo longue
SHORT_MAX_SECONDS = 65

# Nombre max de vidéos récentes à afficher sur l'accueil
MAX_RECENT_VIDEOS = 12
MAX_RECENT_SHORTS = 8

# ─────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────
def get_access_token():
    """Récupère un access token frais via le refresh token OAuth2."""
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError(f"Pas d'access_token dans la réponse : {r.json()}")
    return token


# ─────────────────────────────────────────────────────────────
# YOUTUBE API HELPERS
# ─────────────────────────────────────────────────────────────
def iso8601_to_seconds(duration_str):
    """Convertit une durée ISO 8601 (PT1H2M33S) en secondes."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str or "")
    if not m:
        return 0
    h, mn, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mn * 60 + s


def get_uploads_playlist_id(token):
    """Récupère l'ID de la playlist 'Uploads' de la chaîne."""
    r = requests.get("https://www.googleapis.com/youtube/v3/channels", params={
        "part": "contentDetails",
        "id": CHANNEL_ID,
        "access_token": token,
    })
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise RuntimeError(f"Chaîne {CHANNEL_ID} introuvable")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def get_playlist_videos(token, playlist_id, max_results=50):
    """Récupère les vidéos d'une playlist avec pagination."""
    videos = []
    page_token = None

    while len(videos) < max_results:
        params = {
            "part": "snippet,contentDetails",
            "maxResults": min(50, max_results - len(videos)),
            "playlistId": playlist_id,
            "access_token": token,
        }
        if page_token:
            params["pageToken"] = page_token

        r = requests.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params=params,
        )
        r.raise_for_status()
        data = r.json()

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId")
            if not video_id:
                continue

            # Ignorer les vidéos supprimées ou privées
            title = snippet.get("title", "")
            if title in ("Deleted video", "Private video"):
                continue

            videos.append({
                "video_id": video_id,
                "title": title,
                "description": (snippet.get("description") or "")[:200],
                "published": (snippet.get("publishedAt") or "")[:10],
                "thumb": (
                    snippet.get("thumbnails", {}).get("high", {}).get("url")
                    or snippet.get("thumbnails", {}).get("medium", {}).get("url")
                    or snippet.get("thumbnails", {}).get("default", {}).get("url", "")
                ),
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return videos


def enrich_with_details(token, videos):
    """Ajoute durée et vues via l'endpoint videos (par batch de 50)."""
    for i in range(0, len(videos), 50):
        batch = videos[i:i + 50]
        ids = ",".join(v["video_id"] for v in batch)
        r = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
            "part": "contentDetails,statistics,status",
            "id": ids,
            "access_token": token,
        })
        r.raise_for_status()

        details_map = {}
        for item in r.json().get("items", []):
            details_map[item["id"]] = item

        for v in batch:
            detail = details_map.get(v["video_id"], {})
            duration_iso = detail.get("contentDetails", {}).get("duration", "")
            v["duration_s"] = iso8601_to_seconds(duration_iso)
            v["views"] = int(detail.get("statistics", {}).get("viewCount", 0))
            # Stocker le statut de confidentialité
            v["privacy"] = detail.get("status", {}).get("privacyStatus", "unknown")


def split_videos_shorts(videos):
    """Sépare les vidéos longues et les Shorts."""
    longs = []
    shorts = []
    for v in videos:
        entry = {
            "title": v["title"],
            "description": v.get("description", ""),
            "published": v["published"],
            "thumb": v["thumb"],
            "duration_s": v.get("duration_s", 0),
            "views": v.get("views", 0),
        }
        if v.get("duration_s", 0) <= SHORT_MAX_SECONDS:
            entry["short_url"] = f"https://youtube.com/shorts/{v['video_id']}"
            shorts.append(entry)
        else:
            entry["url"] = f"https://www.youtube.com/watch?v={v['video_id']}"
            longs.append(entry)
    return longs, shorts


# ─────────────────────────────────────────────────────────────
# GÉNÉRATION DES JSON
# ─────────────────────────────────────────────────────────────
def build_main_feed(token):
    """Construit data/videos.json (feed général de la page d'accueil)."""
    print("  Récupération de la playlist Uploads...")
    uploads_id = get_uploads_playlist_id(token)
    print(f"  Playlist Uploads : {uploads_id}")

    # Récupérer assez de vidéos pour avoir du contenu dans les deux catégories
    raw = get_playlist_videos(token, uploads_id, max_results=80)
    print(f"  {len(raw)} vidéos récupérées")

    enrich_with_details(token, raw)
    
    # Filtrer : ne garder que les vidéos publiques
    raw = [v for v in raw if v.get("privacy", "unknown") == "public"]
    print(f"  {len(raw)} vidéos publiques après filtrage")
    
    videos, shorts = split_videos_shorts(raw)

    feed = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "channel_id": CHANNEL_ID,
        "videos": videos[:MAX_RECENT_VIDEOS],
        "shorts": shorts[:MAX_RECENT_SHORTS],
    }

    out = Path("data/videos.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ {out} — {len(feed['videos'])} vidéos + {len(feed['shorts'])} shorts")


def build_trip_feeds(token):
    """Construit data/trips/{slug}.json pour chaque voyage dans trips.json."""
    trips_path = Path("trips.json")
    if not trips_path.exists():
        print("  ⚠️  trips.json absent, pas de feed par voyage")
        return

    trips = json.loads(trips_path.read_text(encoding="utf-8"))
    out_dir = Path("data/trips")
    out_dir.mkdir(parents=True, exist_ok=True)

    for slug, info in trips.items():
        playlist_id = info.get("playlist_id", "")

        # Ignorer les playlist_id fictifs
        if not playlist_id or "xxxx" in playlist_id.lower():
            print(f"  ⏭️  {slug} — playlist_id fictif, ignoré")
            continue

        print(f"  Playlist {slug} ({playlist_id})...")
        try:
            raw = get_playlist_videos(token, playlist_id, max_results=50)
            enrich_with_details(token, raw)
            videos, shorts = split_videos_shorts(raw)

            feed = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "trip_title": info.get("title", slug),
                "trip_slug": slug,
                "playlist_id": playlist_id,
                "videos": videos,
                "shorts": shorts,
            }

            out = out_dir / f"{slug}.json"
            out.write_text(json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ✅ {out} — {len(videos)} vidéos + {len(shorts)} shorts")

        except Exception as e:
            print(f"  ❌ {slug} — erreur : {e}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🎬 LCDMH — Mise à jour du feed YouTube")
    print(f"  Date : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("❌ Secrets manquants (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN)")
        print("   Configure-les dans Settings > Secrets > Actions de ton dépôt GitHub.")
        exit(1)

    token = get_access_token()
    print("  🔑 Token OAuth2 obtenu")

    print("\n📺 Feed général (data/videos.json)")
    build_main_feed(token)

    print("\n🗺️  Feeds par voyage (data/trips/)")
    build_trip_feeds(token)

    print("\n✅ Terminé.")
