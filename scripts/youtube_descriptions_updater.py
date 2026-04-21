# -*- coding: utf-8 -*-
"""
youtube_descriptions_updater.py
────────────────────────────────────────────────────────────────────────────
Met à jour les descriptions des 14 vidéos Cap Nord sur la chaîne LCDMH
avec le template GEO-ready (première ligne factuelle + lien article pilier
+ bloc identité LCDMH cohérent + chapitres + équipement).

Auteur : LCDMH — Assistant IA (2026-04)
Dépendances : requests (déjà présent dans l'infra existante).

UTILISATION :
    # Test à blanc (n'écrit rien, affiche ce qui serait envoyé)
    python scripts/youtube_descriptions_updater.py --dry-run

    # Exécution réelle
    python scripts/youtube_descriptions_updater.py

    # Une seule vidéo (par ID) pour valider le format
    python scripts/youtube_descriptions_updater.py --video-id XbA7du0oX-I

AUTHENTIFICATION :
    Réutilise le même système que fetch_youtube.py :
      - Variable d'env YT_TOKEN_ANALYTICS (JSON avec client_id, client_secret,
        refresh_token)
      - Fallback : YOUTUBE_CLIENT_ID / _SECRET / _REFRESH_TOKEN

    IMPORTANT : le refresh_token doit avoir le scope
      https://www.googleapis.com/auth/youtube.force-ssl
    (nécessaire pour videos.update). Si vous avez uniquement le scope
    readonly utilisé par fetch_youtube.py, il faut refaire le flux OAuth2
    côté Google Cloud Console.

FICHIERS LUS :
    data/cap_nord_youtube_videos.json  → liste des 14 vidéos + métadonnées
    GEO_PATCHES/youtube_description_template.md  → référence du gabarit

FICHIERS ÉCRITS :
    logs/youtube_descriptions_YYYY-MM-DD.log  → journal d'exécution
    data/cap_nord_descriptions_backup_YYYY-MM-DD.json  → backup complet
        des descriptions avant modification (obligatoire, pour pouvoir
        rollback en cas de problème)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_ROOT / "data" / "cap_nord_youtube_videos.json"
LOGS_DIR = REPO_ROOT / "logs"
BACKUP_DIR = REPO_ROOT / "data"

YT_API_BASE = "https://www.googleapis.com/youtube/v3"

# Bloc "Qui est LCDMH" — IDENTIQUE sur les 14 vidéos pour renforcer l'entité
WHOAMI_BLOCK = """🙋 QUI EST LCDMH ?
LCDMH — La Chaîne du Motard Heureux — est la chaîne de Yves,
motard voyageur basé à Annecy. Road trips moto en solo longue
distance (Cap Nord 10 000 km en 2025, Europe-Asie, Alpes),
bivouac moto et tests d'équipement terrain.
🌐 Site : https://lcdmh.com
📧 Contact : via https://lcdmh.com/a-propos.html"""

EQUIPMENT_BLOCK = """🧰 ÉQUIPEMENT UTILISÉ DANS LA SÉRIE
• Moto : Honda NT1100 DCT
• GPS : Aoocci (test sur https://lcdmh.com/gps.html)
• Apps : Entur (ferries norvégiens), FerryPay, Revolut
• Bivouac : tente 3 saisons, duvet grand froid
• Détails : https://lcdmh.com/equipement.html"""

HASHTAGS = "#CapNord #RoadTripMoto #NordkappMoto #HondaNT1100 #BivouacMoto #VoyageMotoNorvège #LCDMH"

SEPARATOR = "═══════════════════════════════════════════"

ARTICLE_PILIER_URL = "https://lcdmh.com/cap-nord-moto.html"


# ═══════════════════════════════════════════════════════════════════════════
# AUTH (identique à fetch_youtube.py)
# ═══════════════════════════════════════════════════════════════════════════
def get_access_token():
    """Obtient un access_token frais via refresh_token OAuth2."""
    # Méthode 1 : YT_TOKEN_ANALYTICS (JSON complet)
    token_json = os.environ.get("YT_TOKEN_ANALYTICS", "")
    if token_json:
        try:
            token_data = json.loads(token_json)
            client_id = token_data.get("client_id")
            client_secret = token_data.get("client_secret")
            refresh_token = token_data.get("refresh_token")
            if all([client_id, client_secret, refresh_token]):
                print("  🔑 Auth via YT_TOKEN_ANALYTICS")
                return _refresh(client_id, client_secret, refresh_token)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ⚠️ Erreur parsing YT_TOKEN_ANALYTICS : {e}")

    # Méthode 2 : 3 secrets séparés
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    if all([client_id, client_secret, refresh_token]):
        print("  🔑 Auth via secrets séparés")
        return _refresh(client_id, client_secret, refresh_token)

    raise RuntimeError(
        "Aucune méthode d'auth disponible. Configurez YT_TOKEN_ANALYTICS "
        "ou YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN."
    )


def _refresh(client_id, client_secret, refresh_token):
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError("Pas d'access_token dans la réponse OAuth2.")
    return token


# ═══════════════════════════════════════════════════════════════════════════
# YOUTUBE API
# ═══════════════════════════════════════════════════════════════════════════
def fetch_video(token, video_id):
    """Récupère snippet + status d'une vidéo. Obligatoire avant update
    (l'API exige le snippet complet dans le PUT)."""
    r = requests.get(
        f"{YT_API_BASE}/videos",
        params={"part": "snippet,status", "id": video_id, "access_token": token},
        timeout=30,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise RuntimeError(f"Vidéo {video_id} introuvable ou non accessible.")
    return items[0]


def update_video_description(token, video_item, new_description, dry_run=False):
    """Met à jour UNIQUEMENT la description, en préservant tout le reste."""
    snippet = video_item["snippet"]
    video_id = video_item["id"]

    # Payload PUT : l'API exige au minimum categoryId + title + description.
    new_snippet = {
        "title": snippet["title"],
        "description": new_description,
        "categoryId": snippet.get("categoryId", "19"),  # 19 = Travel & Events
    }
    if "tags" in snippet:
        new_snippet["tags"] = snippet["tags"]
    if "defaultLanguage" in snippet:
        new_snippet["defaultLanguage"] = snippet["defaultLanguage"]
    if "defaultAudioLanguage" in snippet:
        new_snippet["defaultAudioLanguage"] = snippet["defaultAudioLanguage"]

    payload = {"id": video_id, "snippet": new_snippet}

    if dry_run:
        print(f"  🧪 [DRY-RUN] Ne pas envoyer. Description prévue ({len(new_description)} car.) :")
        print("  " + "─" * 70)
        for line in new_description.split("\n")[:6]:
            print(f"    {line}")
        print("    [...]")
        print("  " + "─" * 70)
        return {"dry_run": True}

    r = requests.put(
        f"{YT_API_BASE}/videos",
        params={"part": "snippet", "access_token": token},
        json=payload,
        timeout=30,
    )
    if not r.ok:
        print(f"  ❌ HTTP {r.status_code} : {r.text}")
        r.raise_for_status()
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATE — construit la description finale pour une vidéo
# ═══════════════════════════════════════════════════════════════════════════
def build_description(video_meta, playlist_id, existing_chapters_block=None):
    """
    Assemble la description finale selon le template GEO-ready.

    video_meta : dict issu de data/cap_nord_youtube_videos.json
    playlist_id : ID de la playlist Cap Nord 2025
    existing_chapters_block : si la vidéo a déjà des chapitres dans sa
        description actuelle, on les préserve (format "00:00 …").
        Sinon on met un placeholder à compléter à la main.
    """
    first_line = video_meta["first_line"]
    location = video_meta["location"]
    km = video_meta.get("km")
    narrative = video_meta["narrative"]

    km_line = f"📏 {km} km parcourus cette journée" if km else ""

    playlist_url = (
        f"https://www.youtube.com/playlist?list={playlist_id}"
        if playlist_id and not playlist_id.startswith("PL_REMPLACER")
        else "(playlist à configurer dans data/cap_nord_youtube_videos.json)"
    )

    chapters_section = (
        existing_chapters_block
        if existing_chapters_block
        else "00:00 Introduction\n(Chapitres à compléter après upload de la vidéo)"
    )

    parts = [
        first_line,
        "",
        f"📍 {location}",
        "🏍️ Honda NT1100 · Road trip solo · Mai–Juin 2025",
    ]
    if km_line:
        parts.append(km_line)
    parts.extend([
        "",
        SEPARATOR,
        "",
        narrative,
        "",
        SEPARATOR,
        "",
        "📖 GUIDE COMPLET DU VOYAGE (itinéraire, budget, ferries, bivouac) :",
        f"▶ {ARTICLE_PILIER_URL}",
        "",
        "🎬 PLAYLIST COMPLÈTE « Cap Nord 2025 » (14 épisodes) :",
        f"▶ {playlist_url}",
        "",
        SEPARATOR,
        "",
        "⏱️ CHAPITRES",
        chapters_section,
        "",
        SEPARATOR,
        "",
        EQUIPMENT_BLOCK,
        "",
        SEPARATOR,
        "",
        WHOAMI_BLOCK,
        "",
        SEPARATOR,
        "",
        HASHTAGS,
    ])
    return "\n".join(parts)


def extract_existing_chapters(description):
    """Extrait le bloc de chapitres YouTube d'une description existante.
    Un chapitre YouTube = ligne qui commence par un timestamp HH:MM ou MM:SS.
    Le bloc doit commencer par 00:00 pour être reconnu par YouTube."""
    import re
    lines = description.split("\n")
    chapters = []
    in_block = False
    for line in lines:
        if re.match(r"^\s*00:00\b", line):
            in_block = True
        if in_block:
            if re.match(r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s+\S", line):
                chapters.append(line.strip())
            elif chapters:
                # ligne non-chapitre après au moins 1 chapitre → fin du bloc
                break
    if len(chapters) >= 3:
        return "\n".join(chapters)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Update YouTube descriptions for Cap Nord series")
    parser.add_argument("--dry-run", action="store_true", help="Ne rien écrire, juste afficher")
    parser.add_argument("--video-id", help="Limiter à une seule vidéo (par ID)")
    args = parser.parse_args()

    LOGS_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"youtube_descriptions_{today}.log"
    backup_path = BACKUP_DIR / f"cap_nord_descriptions_backup_{today}.json"

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    playlist_id = data.get("playlist_id", "")
    videos = data["videos"]
    if args.video_id:
        videos = [v for v in videos if v["video_id"] == args.video_id]
        if not videos:
            print(f"❌ Vidéo {args.video_id} introuvable dans {DATA_FILE}")
            sys.exit(1)

    print(f"🚀 {len(videos)} vidéo(s) à traiter — mode {'DRY-RUN' if args.dry_run else 'LIVE'}")
    token = get_access_token()

    backups = []
    log_lines = [f"# Log exécution {today}\n"]

    for v in videos:
        ep = v.get("episode")
        vid = v["video_id"]
        print(f"\n▶ EP{ep:02d} — {vid} — {v['first_line'][:80]}…")
        try:
            item = fetch_video(token, vid)
            old_desc = item["snippet"].get("description", "")
            backups.append({
                "episode": ep,
                "video_id": vid,
                "title": item["snippet"].get("title"),
                "old_description": old_desc,
            })

            # Préserver les chapitres existants si présents
            existing_chapters = extract_existing_chapters(old_desc)
            if existing_chapters:
                print(f"  ✓ Chapitres existants conservés ({existing_chapters.count(chr(10))+1} chapitres)")

            new_desc = build_description(v, playlist_id, existing_chapters)
            update_video_description(token, item, new_desc, dry_run=args.dry_run)
            status = "DRY-RUN" if args.dry_run else "UPDATED"
            log_lines.append(f"[{status}] EP{ep:02d} {vid} — {len(new_desc)} car.")
            print(f"  ✅ {status}")
        except Exception as e:
            err = f"[ERROR] EP{ep} {vid} — {e}"
            print(f"  ❌ {err}")
            log_lines.append(err)

    # Backup OBLIGATOIRE avant toute modif réelle
    if not args.dry_run and backups:
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump({"backed_up_at": datetime.now().isoformat(), "videos": backups}, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Backup : {backup_path}")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    print(f"📄 Log : {log_path}")
    print("\n✅ Terminé.")


if __name__ == "__main__":
    main()
