import json
from pathlib import Path

INPUT_FILE = "facebook_post_ready.json"
OUTPUT_FILE = "facebook_payload_test.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    root = Path.cwd()
    input_path = root / INPUT_FILE
    output_path = root / OUTPUT_FILE

    if not input_path.exists():
        print(f"Fichier introuvable : {INPUT_FILE}")
        return

    data = load_json(input_path)

    payload = {
        "mode": "test",
        "platform": "facebook_page",
        "message": data.get("facebook_post_long", ""),
        "link": data.get("url", ""),
        "image_url": data.get("image", ""),
        "title": data.get("titre", ""),
        "category": data.get("categorie_semaine", ""),
        "post_id": data.get("id", "")
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Payload Facebook test généré.")
    print(f"Fichier : {OUTPUT_FILE}")
    print("\n--- Aperçu ---\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()