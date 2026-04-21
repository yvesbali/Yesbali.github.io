#!/usr/bin/env python3
"""
generate_yt_token.py — Bootstrap OAuth2 pour générer yt_token_analytics.json
==============================================================================
À lancer UNE SEULE FOIS depuis ton poste Windows pour obtenir un refresh_token
persistant (valide tant que tu ne révoques pas l'accès dans ton compte Google).

Produit :
  yt_token_analytics.json  à la racine du repo, contenant :
    { "client_id": "...", "client_secret": "...", "refresh_token": "..." }

Ce fichier est ensuite lu en fallback par :
  - fetch_youtube.py
  - scripts/apply_descriptions_batch_01.py
  - scripts/geo_baseline.py / geo_snapshot.py

Pré-requis :
  1) Tu as créé un OAuth Client ID de type "Desktop" dans Google Cloud Console
     → APIs & Services → Credentials → Create Credentials → OAuth client ID
     → Application type = Desktop app
     → Tu y as récupéré client_id + client_secret
  2) L'écran de consentement OAuth de ton projet a bien YouTube Data API v3
     activée (scope youtube.readonly + youtube.force-ssl).
  3) Ton compte Google est owner ou manager de la chaîne LCDMH.

Usage :
  python scripts/generate_yt_token.py

Le script ouvre automatiquement ton navigateur, tu valides sur l'écran Google,
tu copies le code affiché, tu le colles dans le terminal. Terminé.

Sécurité :
  - yt_token_analytics.json est déjà dans .gitignore (vérifie).
  - Si jamais le fichier fuit, révoque l'accès sur :
    https://myaccount.google.com/permissions
"""

import json
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import requests

BASE = Path(__file__).resolve().parent.parent
OUT_PATH = BASE / "yt_token_analytics.json"

# Scopes nécessaires : lire les stats + éditer les snippets des vidéos
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

# Redirect OOB pour app Desktop (code visible dans le navigateur)
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def prompt(label: str, default: str = "") -> str:
    if default:
        v = input(f"{label} [{default}] : ").strip()
        return v or default
    return input(f"{label} : ").strip()


def main():
    print("=" * 70)
    print("  Bootstrap OAuth2 YouTube — génère yt_token_analytics.json")
    print("=" * 70)

    # 1) Lire client_id + client_secret
    print("\n[ÉTAPE 1] Identifiants OAuth (Google Cloud Console → Credentials)")
    client_id = prompt("  client_id (finit par .apps.googleusercontent.com)")
    if not client_id.endswith(".apps.googleusercontent.com"):
        print("  ⚠  Le client_id devrait finir par .apps.googleusercontent.com")
        cont = prompt("  Continuer quand même ? (y/N)", "N")
        if cont.lower() != "y":
            sys.exit(1)

    client_secret = prompt("  client_secret (commence par GOCSPX-)")
    if not client_secret.startswith("GOCSPX-"):
        print("  ⚠  Le client_secret devrait commencer par GOCSPX-")
        cont = prompt("  Continuer quand même ? (y/N)", "N")
        if cont.lower() != "y":
            sys.exit(1)

    # 2) Construire l'URL d'autorisation
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # force Google à re-émettre un refresh_token
    }
    url = AUTH_URL + "?" + urlencode(params)

    print("\n[ÉTAPE 2] Autorisation dans le navigateur")
    print("  L'URL suivante va s'ouvrir automatiquement :")
    print(f"  {url}\n")
    print("  1. Connecte-toi avec le compte Google propriétaire de la chaîne LCDMH.")
    print("  2. Accepte les permissions (YouTube Data API + YouTube Analytics).")
    print("  3. Google te montre un code — copie-le.")
    input("  Appuie sur Entrée pour ouvrir le navigateur...")
    webbrowser.open(url)

    # 3) Récupérer le code
    print("\n[ÉTAPE 3] Code d'autorisation")
    code = prompt("  Colle ici le code affiché par Google")
    if not code:
        print("  Aucun code fourni. Abandon.")
        sys.exit(1)

    # 4) Échanger contre un refresh_token
    print("\n[ÉTAPE 4] Échange du code contre un refresh_token...")
    r = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  ✖ Échec ({r.status_code}) : {r.text[:500]}")
        sys.exit(2)

    data = r.json()
    refresh_token = data.get("refresh_token")
    access_token = data.get("access_token")
    if not refresh_token:
        print("  ✖ Pas de refresh_token dans la réponse. Le compte a peut-être déjà")
        print("    un token pour ce client_id — révoque l'accès sur :")
        print("    https://myaccount.google.com/permissions")
        print("    puis relance ce script.")
        print(f"  Réponse complète : {data}")
        sys.exit(3)

    # 5) Écrire yt_token_analytics.json
    out = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n[OK] yt_token_analytics.json écrit : {OUT_PATH}")
    print(f"[OK] access_token (expire dans ~1h) : {access_token[:30]}...")

    # 6) Test rapide — récupérer la chaîne
    print("\n[ÉTAPE 5] Test — lecture channel mine=true")
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet,statistics", "mine": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if r.status_code == 200:
        items = r.json().get("items", [])
        if items:
            s = items[0]["snippet"]
            st = items[0]["statistics"]
            print(f"  ✓ Chaîne : {s.get('title')} (ID {items[0].get('id')})")
            print(f"    vidéos : {st.get('videoCount')} · abonnés : {st.get('subscriberCount')}")
        else:
            print("  ⚠  Pas de chaîne retournée — le compte n'est pas rattaché à une chaîne ?")
    else:
        print(f"  ⚠  Test lecture échoue ({r.status_code}) : {r.text[:300]}")

    # 7) Ajouter au .gitignore si absent
    gi = BASE / ".gitignore"
    if gi.exists():
        content = gi.read_text(encoding="utf-8")
        if "yt_token_analytics.json" not in content:
            with open(gi, "a", encoding="utf-8") as f:
                f.write("\n# OAuth2 YouTube (local bootstrap)\nyt_token_analytics.json\n")
            print(f"[OK] Ajouté yt_token_analytics.json à .gitignore")

    print("\n" + "=" * 70)
    print("  Tu peux maintenant lancer :")
    print("    python scripts/apply_descriptions_batch_01.py --dry")
    print("    python scripts/apply_descriptions_batch_01.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
