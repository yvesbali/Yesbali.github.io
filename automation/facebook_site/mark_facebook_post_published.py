import json
import os

payload_file = "facebook_payload_test.json"
published_file = "facebook_published_ids.json"

# lire le payload actuel
with open(payload_file, "r", encoding="utf-8") as f:
    payload = json.load(f)

post_id = payload["post_id"]

# charger la liste des posts déjà publiés
if os.path.exists(published_file):
    with open(published_file, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {"published_ids": []}

# vérifier si déjà présent
if post_id in data["published_ids"]:
    print("Post déjà enregistré comme publié :", post_id)
else:
    data["published_ids"].append(post_id)

    with open(published_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("Post marqué comme publié :", post_id)