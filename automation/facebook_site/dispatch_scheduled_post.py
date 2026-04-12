"""
dispatch_scheduled_post.py
--------------------------
Lit la bibliothèque facebook_payload_test.json (26 posts planifiés),
trouve le post dont la date correspond à aujourd'hui (ou le prochain non-publié),
et génère le payload au format simple que Make.com attend.

Sortie : facebook/facebook_payload_live.json  (format Make.com)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Paris")

LIBRARY_FILE = Path("facebook/facebook_payload_test.json")
OUTPUT_FILE = Path("facebook/facebook_payload_live.json")
PUBLISHED_FILE = Path("automation/facebook_site/dispatch_published.json")


def load_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default if default is not None else {}


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def find_todays_post(posts: list, published_ids: set) -> dict | None:
    today = datetime.now(TZ).strftime("%Y-%m-%d")

    # 1) Exact match on today's date
    for post in posts:
        if post.get("scheduled_date") == today and post["id"] not in published_ids:
            return post

    # 2) Fallback: first unpublished post whose date is <= today (catch up missed ones)
    for post in posts:
        sd = post.get("scheduled_date", "")
        if sd and sd <= today and post["id"] not in published_ids:
            return post

    return None


def build_payload(post: dict) -> dict:
    vid = post.get("video_id", "")
    image = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else "https://lcdmh.com/images/logo-social.jpg"

    return {
        "mode": "scheduled",
        "platform": "facebook_page",
        "message": post.get("message", ""),
        "link": post.get("link", ""),
        "image_url": image,
        "title": post.get("message", "").split("\n")[0],
        "category": post.get("category", ""),
        "post_id": post.get("id", ""),
    }


def main():
    if not LIBRARY_FILE.exists():
        print(f"Bibliothèque introuvable : {LIBRARY_FILE}")
        return

    library = load_json(LIBRARY_FILE)
    posts = library.get("posts", [])
    if not posts:
        print("Aucun post dans la bibliothèque.")
        return

    published_data = load_json(PUBLISHED_FILE, {"published_ids": []})
    published_ids = set(published_data.get("published_ids", []))

    post = find_todays_post(posts, published_ids)

    if not post:
        print("Aucun post à publier aujourd'hui (tous déjà publiés ou pas encore planifiés).")
        return

    payload = build_payload(post)
    save_json(OUTPUT_FILE, payload)

    # Mark as dispatched
    published_ids.add(post["id"])
    published_data["published_ids"] = sorted(published_ids)
    published_data["last_dispatch"] = datetime.now(TZ).isoformat()
    published_data["last_post_id"] = post["id"]
    save_json(PUBLISHED_FILE, published_data)

    print(f"Post du jour : {post['id']} ({post.get('scheduled_date', '?')})")
    print(f"Payload écrit dans : {OUTPUT_FILE}")
    print()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
