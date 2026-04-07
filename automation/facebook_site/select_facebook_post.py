import json
import random
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

INPUT_POSTS_FILE = "site_posts_v1.json"
OUTPUT_SELECTED_FILE = "facebook_post_selected.json"
STATE_FILE = "site_posts_state.json"
PUBLISHED_FILE = "facebook_published_ids.json"

TZ = ZoneInfo("Europe/Paris")
BASE_URL = "https://lcdmh.com/"

def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_published_ids(path: Path):
    data = load_json(path, {"published_ids": []})
    return set(data.get("published_ids", []))

def extract_youtube_id(url):
    """Extrait l'ID de la vidéo depuis une URL YouTube standard ou courte"""
    if not url: return ""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else ""

def normalize_posts(raw):
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]
    if isinstance(raw, dict) and "posts" in raw and isinstance(raw["posts"], list):
        return [p for p in raw["posts"] if isinstance(p, dict)]
    return []

def next_category(state: dict) -> str:
    cycle = ["roadtrip", "materiel", "promo"]
    last = state.get("last_category")
    if last not in cycle:
        return cycle[0]
    idx = cycle.index(last)
    return cycle[(idx + 1) % len(cycle)]

def full_url(value: str) -> str:
    if not value: return ""
    if value.startswith("http"): return value
    return BASE_URL + value.lstrip("/")

def pick_post_randomly(posts: list, wanted_category: str, published_ids: set):
    # 1. On cherche les posts de la catégorie voulue non publiés
    candidates = [
        p for p in posts
        if p.get("actif", True)
        and p.get("categorie") == wanted_category
        and p.get("id") not in published_ids
    ]
    
    # 2. Si on en trouve, on en prend un AU HASARD (Flashback)
    if candidates:
        return random.choice(candidates)

    # 3. Fallback : si la catégorie est vide, on prend n'importe quoi au hasard (non publié)
    fallbacks = [
        p for p in posts
        if p.get("actif", True)
        and p.get("id") not in published_ids
    ]
    if fallbacks:
        return random.choice(fallbacks)

    return None

def main():
    root = Path.cwd()
    posts_path = root / INPUT_POSTS_FILE
    selected_path = root / OUTPUT_SELECTED_FILE
    state_path = root / STATE_FILE
    published_path = root / PUBLISHED_FILE

    if not posts_path.exists():
        print(f"Fichier introuvable")
        return

    posts = normalize_posts(load_json(posts_path, []))
    if not posts: return

    state = load_json(state_path, {})
    published_ids = load_published_ids(published_path)

    wanted_category = next_category(state)
    picked = pick_post_randomly(posts, wanted_category, published_ids)

    if not picked:
        print("Plus rien à publier, on réinitialise l'historique pour recommencer le cycle.")
        published_ids = set() # On vide pour recommencer à piocher dans les vieux souvenirs
        picked = pick_post_randomly(posts, wanted_category, published_ids)

    now = datetime.now(TZ).isoformat()
    yt_id = extract_youtube_id(picked.get("url", ""))

    result = {
        "date_generation": now,
        "categorie": picked.get("categorie", ""),
        "id": picked.get("id", ""),
        "title": picked.get("titre", ""), # Champ utilisé par Pinterest
        "message": picked.get("texte", ""), # Champ utilisé par Facebook
        "image_site": full_url(picked.get("image", "")),
        "link": picked.get("url", ""),
        "videoId": yt_id # L'ID magique pour la miniature YouTube dans Make
    }

    save_json(selected_path, result)

    state["last_category"] = picked.get("categorie", wanted_category)
    state["last_post_id"] = picked.get("id", "")
    state["last_generation"] = now
    save_json(state_path, state)

    print(f"Flashback sélectionné : {result['title']}")

if __name__ == "__main__":
    main()
