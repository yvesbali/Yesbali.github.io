"""
fetch_youtube.py — LCDMH
Génère :
  - data/videos.json       → flux général (dernières vidéos + Shorts)
  - data/trips/<slug>.json → un fichier par voyage (depuis playlist YouTube)

Variables d'environnement requises :
  YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
"""

import json
import os
import re
import requests
from datetime import datetime, timezone
from pathlib import Path

CHANNEL_ID  = "UCsmjag8fMTAqdawlg35T3Bg"
MAX_VIDEOS  = 4
MAX_SHORTS  = 6
SHORT_MAX_S = 65

DATA_DIR   = Path("data")
TRIPS_FILE = Path("trips.json")


def get_access_token() -> str:
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     os.environ["YOUTUBE_CLIENT_ID"],
        "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"],
        "grant_type":    "refresh_token",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def yt(token: str, endpoint: str, **params) -> dict:
    r = requests.get(
        f"https://www.googleapis.com/youtube/v3/{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def duration_to_seconds(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    return int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + int(m.group(3) or 0)


def best_thumb(thumbnails: dict) -> str:
    for q in ("maxres", "high", "medium", "default"):
        t = thumbnails.get(q, {}).get("url")
        if t:
            return t
    return ""


def fetch_video_details(token: str, video_ids: list) -> list:
    results = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        data  = yt(token, "videos",
                   part="snippet,contentDetails,statistics",
                   id=",".join(chunk))
        for item in data.get("items", []):
            sn  = item["snippet"]
            dur = duration_to_seconds(item["contentDetails"].get("duration", ""))
            st  = item.get("statistics", {})
            results.append({
                "id":         item["id"],
                "title":      sn.get("title", ""),
                "published":  sn.get("publishedAt", "")[:10],
                "duration_s": dur,
                "is_short":   0 < dur <= SHORT_MAX_S,
                "thumb":      best_thumb(sn.get("thumbnails", {})),
                "url":        f"https://www.youtube.com/watch?v={item['id']}",
                "short_url":  f"https://www.youtube.com/shorts/{item['id']}",
                "views":      int(st.get("viewCount", 0)),
                "likes":      int(st.get("likeCount", 0)),
            })
    return results


def build_general_feed(token: str) -> dict:
    print("  → Recherche des dernières publications...")
    search = yt(token, "search",
                part="snippet",
                channelId=CHANNEL_ID,
                order="date",
                type="video",
                maxResults=50)
    ids = [item["id"]["videoId"] for item in search.get("items", [])]
    all_vids = fetch_video_details(token, ids)
    videos = [v for v in all_vids if not v["is_short"]][:MAX_VIDEOS]
    shorts = [v for v in all_vids if v["is_short"]][:MAX_SHORTS]
    print(f"  OK {len(videos)} video(s) longue(s) · {len(shorts)} Short(s)")
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "videos":     videos,
        "shorts":     shorts,
    }


def build_trip_feed(token: str, trip: dict) -> dict:
    playlist_id = trip["playlist_id"]
    print(f"  → Playlist {playlist_id}...")
    ids = []
    page_token = None
    while True:
        params = dict(part="snippet", playlistId=playlist_id, maxResults=50)
        if page_token:
            params["pageToken"] = page_token
        data = yt(token, "playlistItems", **params)
        for item in data.get("items", []):
            vid = item["snippet"]["resourceId"].get("videoId")
            if vid:
                ids.append(vid)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    all_vids = fetch_video_details(token, ids) if ids else []
    all_vids.sort(key=lambda v: v["published"], reverse=True)
    videos = [v for v in all_vids if not v["is_short"]]
    shorts = [v for v in all_vids if v["is_short"]]
    print(f"  OK {len(videos)} video(s) · {len(shorts)} Short(s)")
    return {
        "updated_at":  datetime.now(timezone.utc).isoformat(),
        "trip_title":  trip["title"],
        "playlist_id": playlist_id,
        "videos":      videos,
        "shorts":      shorts,
    }


def main():
    print("Authentification YouTube...")
    token = get_access_token()

    print("\nFlux general")
    general = build_general_feed(token)
    out = DATA_DIR / "videos.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(general, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Sauvegarde : {out}")

    if not TRIPS_FILE.exists():
        print("\ntrips.json introuvable - pas de flux voyage genere")
        return

    trips = json.loads(TRIPS_FILE.read_text(encoding="utf-8"))
    trips_dir = DATA_DIR / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)

    for slug, trip in trips.items():
        playlist_id = trip.get("playlist_id", "")
        if not playlist_id or playlist_id.startswith("PLxxxxx"):
            print(f"  ⚠️  {trip['title']} — Playlist ID non configuré, ignoré")
            continue
        print(f"\n🗺️  Voyage : {trip['title']}")
        feed = build_trip_feed(token, trip)
        dest = trips_dir / f"{slug}.json"
        dest.write_text(json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  💾 {dest}")


if __name__ == "__main__":
    main()
