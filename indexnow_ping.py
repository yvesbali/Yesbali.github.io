#!/usr/bin/env python3
"""
================================================================
LCDMH — IndexNow Ping Script
================================================================
Envoie un ping IndexNow à Bing et Yandex pour toutes les URLs
du sitemap.xml de lcdmh.com.

Usage:
    python indexnow_ping.py                    # Toutes les URLs du sitemap
    python indexnow_ping.py --url https://lcdmh.com/equipement.html  # Une seule URL
    python indexnow_ping.py --dry-run          # Simulation sans envoyer

Prérequis:
    1. Le fichier 1ffe11fd716a4f389f34bc02922c1684.txt doit être
       à la racine de lcdmh.com (commit + push dans GitHub Pages)
    2. pip install requests (normalement déjà installé)

Auteur: Yves – LCDMH
================================================================
"""

import requests
import xml.etree.ElementTree as ET
import argparse
import time
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
INDEXNOW_KEY = "1ffe11fd716a4f389f34bc02922c1684"
SITE_HOST = "lcdmh.com"
SITEMAP_URL = "https://lcdmh.com/sitemap.xml"
KEY_LOCATION = f"https://{SITE_HOST}/{INDEXNOW_KEY}.txt"

# Moteurs supportant IndexNow
SEARCH_ENGINES = [
    "https://api.indexnow.org/indexnow",      # Bing + partenaires
    "https://yandex.com/indexnow",             # Yandex
]

# ============================================================
# FONCTIONS
# ============================================================

def get_urls_from_sitemap(sitemap_url):
    """Récupère toutes les URLs depuis le sitemap.xml"""
    print(f"\n📥 Lecture du sitemap : {sitemap_url}")
    try:
        response = requests.get(sitemap_url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Erreur lors de la lecture du sitemap : {e}")
        return []

    # Parser le XML (gérer le namespace)
    root = ET.fromstring(response.content)
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0] + "}"

    urls = []
    for url_elem in root.findall(f".//{namespace}url"):
        loc = url_elem.find(f"{namespace}loc")
        if loc is not None and loc.text:
            urls.append(loc.text.strip())

    print(f"✅ {len(urls)} URLs trouvées dans le sitemap")
    return urls


def ping_indexnow_batch(urls, dry_run=False):
    """
    Envoie les URLs en batch via POST à chaque moteur IndexNow.
    La méthode batch est recommandée pour plus de 1 URL.
    """
    if not urls:
        print("⚠️  Aucune URL à soumettre.")
        return

    payload = {
        "host": SITE_HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls
    }

    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }

    print(f"\n🚀 Soumission de {len(urls)} URLs à IndexNow...")
    print(f"   Clé : {INDEXNOW_KEY}")
    print(f"   Key location : {KEY_LOCATION}\n")

    for engine_url in SEARCH_ENGINES:
        engine_name = "Bing/IndexNow" if "indexnow.org" in engine_url else "Yandex"

        if dry_run:
            print(f"   🔵 [DRY-RUN] {engine_name} — {len(urls)} URLs (non envoyées)")
            continue

        try:
            response = requests.post(
                engine_url,
                json=payload,
                headers=headers,
                timeout=15
            )

            if response.status_code in (200, 202):
                print(f"   ✅ {engine_name} — {response.status_code} — {len(urls)} URLs acceptées")
            elif response.status_code == 429:
                print(f"   ⏳ {engine_name} — 429 Too Many Requests — réessaie plus tard")
            else:
                print(f"   ⚠️  {engine_name} — {response.status_code} — {response.text[:200]}")

        except requests.RequestException as e:
            print(f"   ❌ {engine_name} — Erreur réseau : {e}")

        # Pause entre les moteurs pour éviter le rate limiting
        time.sleep(1)


def ping_single_url(url, dry_run=False):
    """Envoie un ping pour une seule URL via GET (méthode simple)."""
    print(f"\n🚀 Soumission d'une URL unique : {url}")

    for engine_url in SEARCH_ENGINES:
        engine_name = "Bing/IndexNow" if "indexnow.org" in engine_url else "Yandex"

        params = {
            "url": url,
            "key": INDEXNOW_KEY,
            "keyLocation": KEY_LOCATION,
        }

        if dry_run:
            print(f"   🔵 [DRY-RUN] {engine_name} — {url} (non envoyé)")
            continue

        try:
            response = requests.get(engine_url, params=params, timeout=15)

            if response.status_code in (200, 202):
                print(f"   ✅ {engine_name} — {response.status_code} — URL acceptée")
            elif response.status_code == 429:
                print(f"   ⏳ {engine_name} — 429 Too Many Requests — réessaie plus tard")
            else:
                print(f"   ⚠️  {engine_name} — {response.status_code} — {response.text[:200]}")

        except requests.RequestException as e:
            print(f"   ❌ {engine_name} — Erreur réseau : {e}")

        time.sleep(1)


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="LCDMH IndexNow — Notifier Bing et Yandex des nouvelles pages"
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Soumettre une seule URL (ex: https://lcdmh.com/equipement.html)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulation — affiche les URLs sans les envoyer"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  LCDMH — IndexNow Ping")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if args.url:
        # Mode URL unique
        ping_single_url(args.url, dry_run=args.dry_run)
    else:
        # Mode batch — toutes les URLs du sitemap
        urls = get_urls_from_sitemap(SITEMAP_URL)
        if urls:
            # Afficher un aperçu
            print("\n📋 Aperçu des URLs :")
            for i, url in enumerate(urls[:5], 1):
                print(f"   {i}. {url}")
            if len(urls) > 5:
                print(f"   ... et {len(urls) - 5} autres")

            ping_indexnow_batch(urls, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print("  Terminé !")
    print("=" * 60)


if __name__ == "__main__":
    main()
