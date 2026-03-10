import json
import random
from pathlib import Path

INPUT_FILE = "facebook_post_selected.json"
OUTPUT_TEXT_FILE = "facebook_post_ready.txt"
OUTPUT_JSON_FILE = "facebook_post_ready.json"

SOUVENIR_HEADERS = [
    "🕰️ Souvenir de road trip",
    "📍 Souvenir de voyage",
    "🏍️ Petit retour sur un beau road trip",
]

SOUVENIR_LINES = [
    "Quel beau souvenir de voyage à moto.",
    "Cette route-là, je ne suis pas prêt de l’oublier.",
    "Rien que de revoir ça, ça donne envie de repartir.",
    "Il y a des routes qu’on n’oublie jamais.",
    "Encore un souvenir de voyage qui donne envie de rouler.",
    "Cette étape-là, c’était vraiment quelque chose.",
    "Un petit retour sur un très beau moment de route.",
    "Des paysages comme ça, on en redemande.",
    "Ce road trip reste un très beau souvenir.",
    "Qu’est-ce que c’était bien…",
    "Franchement, quel souvenir incroyable.",
    "Cette route était magnifique.",
]

TEST_HEADERS = [
    "🔁 Retour sur un test",
    "🧪 Petit rappel matériel",
    "🏍️ Retour sur un équipement utile",
]

TEST_LINES = [
    "Petit rappel sur un équipement qui peut vraiment être utile.",
    "Retour sur un test qui peut aider avant d’acheter.",
    "Un contenu utile à revoir avant de s’équiper.",
    "Ce test peut encore servir à beaucoup de motards.",
    "Un petit rappel matériel qui peut éviter une erreur d’achat.",
    "Si tu cherches ce type d’équipement, ce contenu peut t’intéresser.",
    "Un essai à revoir tranquillement avant de faire ton choix.",
    "Ce retour d’expérience reste toujours d’actualité.",
    "Un test pratique à garder sous la main.",
]

PROMO_HEADERS = [
    "📌 Petit rappel utile",
    "💡 Bon plan du moment",
    "🏍️ Petit rappel partenaire",
]

PROMO_LINES = [
    "Petit rappel si tu cherchais un bon plan sur ce produit.",
    "Je remets ici l’info pour ceux que ça peut aider.",
    "Petit rappel utile pour ceux qui regardent ce matériel.",
    "Si tu pensais à ce produit, voici la page à revoir.",
    "Je te remets ici le lien et les infos utiles.",
    "Petit rappel sur cette offre ou ce code utile.",
    "Pour ceux que ça intéresse, je remets l’info ici.",
    "Bon plan à garder de côté si besoin.",
    "Je remets ici les infos utiles pour ne pas les perdre.",
]

PROMO_BRAND_LINES = {
    "aoocci": [
        "Petit rappel code promo Aoocci.",
        "Je remets ici le bon plan Aoocci.",
    ],
    "carpuride": [
        "Petit rappel code promo Carpuride.",
        "Je remets ici le bon plan Carpuride.",
    ],
    "blackview": [
        "Petit rappel bon plan Blackview.",
        "Je remets ici les infos utiles pour Blackview.",
    ],
    "komobi": [
        "Petit rappel utile sur Komobi.",
        "Je remets ici les infos Komobi.",
    ],
    "olight": [
        "Petit rappel bon plan Olight.",
        "Je remets ici les infos utiles sur Olight.",
    ],
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def choose_intro(data):
    ton = data.get("ton_facebook", "").strip().lower()
    post_id = data.get("id", "").strip().lower()
    titre = data.get("titre", "").strip().lower()

    if ton == "souvenir":
        return random.choice(SOUVENIR_HEADERS), random.choice(SOUVENIR_LINES)

    if ton == "test":
        return random.choice(TEST_HEADERS), random.choice(TEST_LINES)

    if ton == "promo":
        for brand, lines in PROMO_BRAND_LINES.items():
            if brand in post_id or brand in titre:
                return random.choice(PROMO_HEADERS), random.choice(lines)
        return random.choice(PROMO_HEADERS), random.choice(PROMO_LINES)

    categorie = data.get("categorie_semaine", "").strip().lower()
    if categorie == "roadtrip":
        return random.choice(SOUVENIR_HEADERS), random.choice(SOUVENIR_LINES)
    if categorie == "materiel":
        return random.choice(TEST_HEADERS), random.choice(TEST_LINES)
    if categorie == "promo":
        return random.choice(PROMO_HEADERS), random.choice(PROMO_LINES)

    return "🏍️ À revoir", "Je remets ici un contenu utile du site."


def build_post(data):
    titre = data.get("titre", "").strip()
    image = data.get("image", "").strip()
    texte = data.get("texte", "").strip()

    header, intro = choose_intro(data)

    post_long = f"""{header}

{intro}

🏍️ {titre}

{texte}
"""

    post_short = f"""{header}

🏍️ {titre}
"""

    return post_long.strip(), post_short.strip(), image, header, intro


def main():
    root = Path.cwd()

    input_path = root / INPUT_FILE
    output_text_path = root / OUTPUT_TEXT_FILE
    output_json_path = root / OUTPUT_JSON_FILE

    if not input_path.exists():
        print("Fichier introuvable :", INPUT_FILE)
        return

    data = load_json(input_path)

    post_long, post_short, image, header, intro = build_post(data)

    output_text_path.write_text(post_long, encoding="utf-8")

    ready = {
        "id": data.get("id", ""),
        "categorie_semaine": data.get("categorie_semaine", ""),
        "ton_facebook": data.get("ton_facebook", ""),
        "header": header,
        "intro": intro,
        "titre": data.get("titre", ""),
        "texte": data.get("texte", ""),
        "url": data.get("url", ""),
        "image": image,
        "facebook_post_long": post_long,
        "facebook_post_short": post_short
    }

    output_json_path.write_text(
        json.dumps(ready, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Post Facebook généré.\n")
    print("------ VERSION LONGUE ------\n")
    print(post_long)

    print("\n------ IMAGE ------")
    print(image)

    print("\n------ MÉTADONNÉES ------")
    print("ID :", ready["id"])
    print("Catégorie :", ready["categorie_semaine"])
    print("Ton Facebook :", ready["ton_facebook"])

    print("\nFichiers créés :")
    print(OUTPUT_TEXT_FILE)
    print(OUTPUT_JSON_FILE)


if __name__ == "__main__":
    main()