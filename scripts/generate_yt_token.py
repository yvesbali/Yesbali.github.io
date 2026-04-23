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

import http.server
import json
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

BASE = Path(__file__).resolve().parent.parent
OUT_PATH = BASE / "yt_token_analytics.json"

# Scopes nécessaires : lire les stats + éditer les snippets + upload des vidéos
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _OAuthHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler qui capture le code OAuth renvoye par Google en redirect."""
    captured_code: str | None = None
    captured_error: str | None = None

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            _OAuthHandler.captured_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;padding:40px;"
                b"text-align:center'><h1>OK !</h1>"
                b"<p>Authentification reussie. Tu peux fermer cette fenetre "
                b"et retourner au terminal.</p></body></html>"
            )
        elif "error" in params:
            _OAuthHandler.captured_error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h1>Erreur</h1><p>{params['error'][0]}</p>"
                "</body></html>".encode("utf-8")
            )
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args, **kwargs):  # silence les logs HTTP
        pass


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

    # 2) Démarrer un serveur loopback qui récupérera le code automatiquement
    #    (OOB urn:ietf:wg:oauth:2.0:oob a été déprécié par Google en 2023)
    port = _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}/"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # force Google à re-émettre un refresh_token
    }
    url = AUTH_URL + "?" + urlencode(params)

    print(f"\n[ÉTAPE 2] Autorisation dans le navigateur (redirect {redirect_uri})")
    print("  Un serveur local va démarrer pour capturer le code Google.")
    print("  1. Connecte-toi avec le compte Google propriétaire de la chaîne LCDMH.")
    print("  2. Accepte TOUTES les permissions (3 scopes).")
    print("  3. Google te redirigera automatiquement ici. Pas besoin de copier un code.")
    input("  Appuie sur Entrée pour ouvrir le navigateur...")

    # Lancer le serveur HTTP dans un thread
    server = http.server.HTTPServer(("127.0.0.1", port), _OAuthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    webbrowser.open(url)

    # Attendre que le code soit capturé (max 5 min)
    print("  En attente de la redirection Google...")
    import time
    deadline = time.time() + 300
    while time.time() < deadline:
        if _OAuthHandler.captured_code or _OAuthHandler.captured_error:
            break
        time.sleep(0.5)
    server.shutdown()

    if _OAuthHandler.captured_error:
        print(f"  ✖ Google a refusé : {_OAuthHandler.captured_error}")
        sys.exit(2)
    code = _OAuthHandler.captured_code
    if not code:
        print("  ✖ Pas de code reçu dans les 5 min. Abandon.")
        sys.exit(1)
    print(f"  ✓ Code reçu : {code[:20]}...")

    # 4) Échanger contre un refresh_token
    print("\n[ÉTAPE 4] Échange du code contre un refresh_token...")
    r = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
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
