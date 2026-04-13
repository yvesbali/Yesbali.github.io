#!/usr/bin/env python3
"""
Script d'enrichissement SEO des pages LCDMH avec JSON-LD VideoObject.
Phase C bis - Ajout de JSON-LD VideoObject aux pages articles.

Fait le 2026-04-12.
"""

import json
import re
import os
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set
from urllib.parse import urlparse, parse_qs
import sys

# Chemins
GITHUB_ROOT = Path("/sessions/relaxed-keen-turing/mnt/LCDMH_GitHub_Audit")
REVIEW_DIR = GITHUB_ROOT / "_review"
AUTOMATE_YT_ROOT = Path("/sessions/relaxed-keen-turing/mnt/Automate_YT")

# Fichiers de données
GOOGLE_SUGGESTIONS_FILE = AUTOMATE_YT_ROOT / "data/google_suggestions.json"
CSV_FILE = AUTOMATE_YT_ROOT / "recommandations_playlists_auto.csv"
VIDEO_INVENTORY_FILE = AUTOMATE_YT_ROOT / "data/video_site_inventory.json"

# Pages principales (priorité haute)
PRIORITY_PAGES = [
    "carpuride.html",
    "pneus.html",
    "aoocci.html",
    "blackview.html",
    "olight.html",
    "komobi.html",
    "gps.html",
    "intercoms.html",
    "equipement.html",
    "photo-video.html",
    "tests-motos.html",
    "alpes-cols-mythiques.html",
]

# Mots-clés à rejeter (ne pas inclure dans keywords JSON-LD)
REJECTED_KEYWORDS = {
    "motogp",
    "motocross",
    "motoculture",
    "motorhome",
    "motorisé",
    "motorisation",
    "motorrad",
    "motorsport",
    "motor",
    "moto gp",
    "moto2",
    "moto3",
}

# Mots-clés rejetés pour la description (suggestions génériques)
REJECTED_SUGGESTIONS = {
    "idée",
    "pas cher",
    "autour de moi",
    "guide complet",
    "tutoriel",
    "mode d'emploi",
    "problème",
    "panne",
    "arnaque",
}

# Transports à rejeter
REJECTED_TRANSPORTS = {
    "voiture",
    "vélo",
    "camping-car",
    "camper-car",
    "train",
    "avion",
}


def load_google_suggestions() -> Dict:
    """Charge les suggestions Google."""
    if not GOOGLE_SUGGESTIONS_FILE.exists():
        print(f"[!] {GOOGLE_SUGGESTIONS_FILE} introuvable")
        return {}
    with open(GOOGLE_SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_csv_data() -> Dict[str, Tuple[str, str]]:
    """Charge le CSV (video_id -> (titre, playlist))."""
    result = {}
    if not CSV_FILE.exists():
        print(f"[!] {CSV_FILE} introuvable")
        return result
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_id = row.get("video_id", "").strip()
            title = row.get("video_title", "").strip()
            playlist = row.get("playlist_actuelle", "").strip()
            if video_id and title:
                result[video_id] = (title, playlist)
    return result


def load_video_inventory() -> Dict:
    """Charge l'inventaire vidéo du site."""
    if not VIDEO_INVENTORY_FILE.exists():
        print(f"[!] {VIDEO_INVENTORY_FILE} introuvable")
        return {}
    with open(VIDEO_INVENTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("videos_on_site", {})


def detect_video_type(playlist: str) -> str:
    """Détecte le type de vidéo depuis la playlist."""
    playlist_lower = (playlist or "").lower()

    if "alpes" in playlist_lower and "tous les sens" in playlist_lower:
        return "serie"
    elif "road trip" in playlist_lower or "roadtrip" in playlist_lower:
        return "road_trip"
    elif "test" in playlist_lower or "gps" in playlist_lower or "pneus" in playlist_lower or \
         "téléphone" in playlist_lower or "setup" in playlist_lower or "matériel" in playlist_lower or \
         "entretien" in playlist_lower or "équipement" in playlist_lower:
        return "test_materiel"
    elif "sécurité" in playlist_lower or "filmer" in playlist_lower:
        return "pratique"
    else:
        return "autre"


def filter_suggestions(suggestions: List[str], video_title: str) -> List[str]:
    """Filtre les suggestions Google selon les règles critiques."""
    filtered = []

    for s in suggestions:
        s_lower = s.lower()

        # Vérifier rejets basiques
        if any(kw in s_lower for kw in REJECTED_KEYWORDS):
            continue
        if any(kw in s_lower for kw in REJECTED_SUGGESTIONS):
            continue
        if any(transport in s_lower for transport in REJECTED_TRANSPORTS):
            continue

        # Vérifier si c'est assez spécifique
        if len(s.split()) < 2:
            continue

        filtered.append(s)

    # Limiter à 5 suggestions
    return filtered[:5]


def extract_video_ids(html_content: str) -> Set[str]:
    """Extrait tous les video_id YouTube du contenu HTML."""
    video_ids = set()

    # Patterns pour extraire les video_id
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'img\.youtube\.com/vi/([a-zA-Z0-9_-]{11})',
        r'i\.ytimg\.com/vi/([a-zA-Z0-9_-]{11})',
        r'"videoId":"([a-zA-Z0-9_-]{11})"',
        r"'videoId':'([a-zA-Z0-9_-]{11})'",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        video_ids.update(matches)

    return video_ids


def check_existing_jsonld(html_content: str, video_id: str) -> bool:
    """Vérifie si un JSON-LD VideoObject existe déjà pour ce video_id."""
    # Chercher si video_id est déjà dans un JSON-LD
    escaped_id = re.escape(video_id)
    if re.search(f'"{escaped_id}"', html_content):
        # Vérifier si c'est dans un bloc JSON-LD VideoObject
        if '"@type":"VideoObject"' in html_content or '"@type": "VideoObject"' in html_content:
            return True
    return False


def create_jsonld_videoobject(video_id: str, title: str,
                              suggestions: List[str],
                              video_type: str) -> str:
    """Crée le JSON-LD VideoObject ou Review+VideoObject."""

    # Description factuelle courte basée UNIQUEMENT sur le titre
    description = title[:150]
    if len(title) > 40:
        description = title.split(" ")[0:5]
        description = " ".join(description)

    # Limiter à 20-40 mots
    words = description.split()
    if len(words) > 40:
        description = " ".join(words[:40])

    # Créer le VideoObject
    video_object = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": title,
        "description": description,
        "thumbnailUrl": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "contentUrl": f"https://www.youtube.com/watch?v={video_id}",
        "embedUrl": f"https://www.youtube.com/embed/{video_id}",
    }

    # Ajouter keywords si suggestions
    if suggestions:
        keywords = ", ".join(suggestions[:5])
        video_object["keywords"] = keywords

    # Si test_materiel, envelopper dans Review
    if video_type == "test_materiel":
        # Extraire produit et marque du titre
        product_name = title.split(":")[0].strip() if ":" in title else title[:50]

        review_object = {
            "@context": "https://schema.org",
            "@type": "Review",
            "itemReviewed": {
                "@type": "Product",
                "name": product_name,
                "brand": "LCDMH"
            },
            "author": {
                "@type": "Person",
                "name": "Yves — LCDMH"
            },
            "reviewBody": description,
            "video": video_object
        }
        # JSON compact sans indentation
        return json.dumps(review_object, ensure_ascii=False, separators=(',', ':'))
    else:
        # JSON compact sans indentation
        return json.dumps(video_object, ensure_ascii=False, separators=(',', ':'))


def process_page(source_path: Path, review_path: Path,
                 csv_data: Dict, google_suggestions: Dict,
                 video_inventory: Dict) -> Tuple[int, List[str]]:
    """Traite une page HTML."""

    if not source_path.exists():
        print(f"[!] {source_path} introuvable")
        return 0, []

    with open(source_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Extraire tous les video_id
    video_ids = extract_video_ids(html_content)
    if not video_ids:
        return 0, []

    jsonld_blocks = []
    processed_count = 0
    logs = []

    for video_id in video_ids:
        # Vérifier s'il existe déjà
        if check_existing_jsonld(html_content, video_id):
            logs.append(f"  ⊙ {video_id} : déjà présent, skip")
            continue

        # Chercher titre et playlist
        title = None
        playlist = None

        # D'abord dans CSV
        if video_id in csv_data:
            title, playlist = csv_data[video_id]
        # Sinon dans google_suggestions
        elif video_id in google_suggestions:
            title = google_suggestions[video_id].get("title", "Vidéo YouTube")
            playlists = google_suggestions[video_id].get("playlists", [])
            if playlists:
                playlist = playlists[0]

        if not title:
            title = "Vidéo YouTube"

        # Détecter type
        video_type = detect_video_type(playlist)

        # Chercher suggestions
        suggestions = []
        if video_id in google_suggestions:
            raw_suggs = google_suggestions[video_id].get("suggestions_raw", [])
            suggestions = filter_suggestions(raw_suggs, title)

        # Créer JSON-LD
        jsonld_str = create_jsonld_videoobject(video_id, title, suggestions, video_type)
        jsonld_blocks.append(jsonld_str)
        processed_count += 1
        logs.append(f"  + {video_id} : {title[:60]}")

    if not jsonld_blocks:
        return 0, logs

    # Ajouter les JSON-LD à la page avant </body>
    # Chaque bloc JSON-LD entre ses propres tags <script>
    jsonld_scripts = []
    for block in jsonld_blocks:
        jsonld_scripts.append(f'<script type="application/ld+json">{block}</script>')

    jsonld_html = "\n    ".join(jsonld_scripts)

    # Ajouter avant </body>
    if "</body>" in html_content:
        html_content = html_content.replace(
            "</body>",
            f"    {jsonld_html}\n</body>",
            1
        )
    else:
        # Fallback : ajouter à la fin
        html_content += f"\n    {jsonld_html}\n"

    # Créer dossiers review si besoin
    review_path.parent.mkdir(parents=True, exist_ok=True)

    # Écrire le fichier enrichi
    with open(review_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return processed_count, logs


def main():
    print("\n=== SEO Enrichment Phase C bis: JSON-LD VideoObject ===")
    print(f"Generated: {datetime.now().isoformat()}\n")

    # Charger données
    print("[*] Chargement des données...")
    google_suggestions = load_google_suggestions()
    csv_data = load_csv_data()
    video_inventory = load_video_inventory()
    print(f"  - Google suggestions: {len(google_suggestions)} vidéos")
    print(f"  - CSV data: {len(csv_data)} vidéos")
    print(f"  - Video inventory: {len(video_inventory)} vidéos\n")

    # Lister les pages à traiter
    print("[*] Pages à traiter...")
    pages_to_process = []

    # Pages principales
    for page in PRIORITY_PAGES:
        source = GITHUB_ROOT / page
        if source.exists():
            pages_to_process.append((source, REVIEW_DIR / page, page))

    # Pages articles
    articles_dir = GITHUB_ROOT / "articles"
    if articles_dir.exists():
        for article in articles_dir.glob("*.html"):
            rel_path = article.relative_to(GITHUB_ROOT)
            review_path = REVIEW_DIR / rel_path
            pages_to_process.append((article, review_path, str(rel_path)))

    print(f"  Trouvées: {len(pages_to_process)} pages\n")

    # Traiter chaque page
    total_enriched = 0
    total_logs = []

    for source_path, review_path, rel_name in pages_to_process:
        print(f"[+] {rel_name}")
        count, logs = process_page(source_path, review_path, csv_data,
                                    google_suggestions, video_inventory)
        if count > 0:
            total_enriched += count
            for log in logs:
                print(log)
            print(f"  → {count} JSON-LD créés")
        else:
            if logs:
                for log in logs:
                    print(log)
            else:
                print("  → Aucune vidéo trouvée")
        total_logs.extend(logs)

    print(f"\n[✓] Total enrichis: {total_enriched} JSON-LD VideoObjects\n")

    # Ajouter au CHANGELOG
    changelog_path = REVIEW_DIR / "CHANGELOG.md"
    if changelog_path.exists():
        with open(changelog_path, "a", encoding="utf-8") as f:
            f.write(f"\n## Phase C bis - JSON-LD VideoObject Enrichment\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(f"- Total VideoObject enriched: {total_enriched}\n")
            f.write(f"- Pages processed: {len(pages_to_process)}\n")
            f.write(f"- Rules applied: Filter suggestions, detect video type, avoid duplicates\n\n")

    print("[✓] Complété!")


if __name__ == "__main__":
    main()
