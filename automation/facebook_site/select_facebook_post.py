import json
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


def normalize_posts(raw):
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]

    if isinstance(raw, dict) and "posts" in raw and isinstance(raw["posts"], list):
        return [p for p in raw["posts"] if isinstance(p, dict)]

    if isinstance(raw, dict):
        posts = []
        for key, value in raw.items():
            if isinstance(value, dict):
                item = value.copy()
                item.setdefault("id", key)
                posts.append(item)
        return posts

    return []


def next_category(state: dict) -> str:
    cycle = ["roadtrip", "materiel", "promo"]
    last = state.get("last_category")
    if last not in cycle:
        return cycle[0]
    idx = cycle.index(last)
    return cycle[(idx + 1) % len(cycle)]


def full_url(value: str) -> str:
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return BASE_URL + value.lstrip("/")


def pick_post(posts: list, wanted_category: str, published_ids: set):
    filtered = [
        p for p in posts
        if p.get("actif", True)
        and p.get("source") == "site"
        and p.get("categorie") == wanted_category
        and p.get("id") not in published_ids
    ]
    if filtered:
        return filtered[0]

    fallback = [
        p for p in posts
        if p.get("actif", True)
        and p.get("source") == "site"
        and p.get("id") not in published_ids
    ]
    if fallback:
        return fallback[0]

    return None


def main():
    root = Path.cwd()

    posts_path = root / INPUT_POSTS_FILE
    selected_path = root / OUTPUT_SELECTED_FILE
    state_path = root / STATE_FILE
    published_path = root / PUBLISHED_FILE

    if not posts_path.exists():
        print(f"Fichier introuvable : {INPUT_POSTS_FILE}")
        return

    raw_posts = load_json(posts_path, [])
    posts = normalize_posts(raw_posts)

    if not posts:
        print(f"Aucun post exploitable trouvé dans : {INPUT_POSTS_FILE}")
        return

    state = load_json(state_path, {})
    published_ids = load_published_ids(published_path)

    wanted_category = next_category(state)
    picked = pick_post(posts, wanted_category, published_ids)

    if not picked:
        print("Aucun post disponible : tout semble déjà publié ou inactif.")
        return

    now = datetime.now(TZ).isoformat()

    result = {
        "date_generation": now,
        "categorie_semaine": picked.get("categorie", ""),
        "id": picked.get("id", ""),
        "ton_facebook": picked.get("ton_facebook", ""),
        "titre": picked.get("titre", ""),
        "texte": picked.get("texte", ""),
        "image": full_url(picked.get("image", "")),
        "url": full_url(picked.get("url", "")),
        "source": picked.get("source", "site"),
        "actif": picked.get("actif", True)
    }

    save_json(selected_path, result)

    state["last_category"] = picked.get("categorie", wanted_category)
    state["last_post_id"] = picked.get("id", "")
    state["last_generation"] = now
    save_json(state_path, state)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nSélection enregistrée dans : {OUTPUT_SELECTED_FILE}")
    print(f"Historique enregistré dans : {STATE_FILE}")


if __name__ == "__main__":
    main()