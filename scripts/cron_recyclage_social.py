#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cron Recyclage Social LCDMH
============================
Script autonome pour GitHub Actions.
Lit le planning, publie les shorts du jour via Make webhook.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════
MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/pdsvn5c6n9i2qdrtaeusjmk1bjwmko86"
MAKE_PIN = "0172"
CLOUDINARY_CLOUD = "dwls7akrc"
CLOUDINARY_PRESET = "instagram_roadtrip_unsigned"

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "social_recyclage"
PLANNING_FILE = DATA_DIR / "planning_v8.json"
HISTORIQUE_FILE = DATA_DIR / "historique_publications.json"


def log(msg):
    print(f"[RECYCLAGE] {msg}")


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════
# TELECHARGER SHORT
# ══════════════════════════════════════════════════════════════════
def telecharger_short(video_url, video_id):
    tmp_dir = tempfile.mkdtemp(prefix="lcdmh_short_")
    output_path = os.path.join(tmp_dir, f"{video_id}.mp4")

    try:
        import yt_dlp
        opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_path,
            "format": "best[ext=mp4][height<=1080]/best[ext=mp4]/best",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video_url])
    except ImportError:
        exe = shutil.which("yt-dlp")
        if not exe:
            log("yt-dlp non disponible")
            return None
        cmd = [exe, "-f", "best[ext=mp4][height<=1080]/best[ext=mp4]/best",
               "-o", output_path, "--no-warnings", video_url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"yt-dlp erreur: {result.stderr[:200]}")
            return None
    except Exception as e:
        log(f"Erreur telechargement: {e}")
        return None

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return output_path

    for f in os.listdir(tmp_dir):
        fp = os.path.join(tmp_dir, f)
        if os.path.getsize(fp) > 0:
            return fp

    return None


# ══════════════════════════════════════════════════════════════════
# UPLOAD CLOUDINARY
# ══════════════════════════════════════════════════════════════════
def uploader_cloudinary(filepath, video_id):
    import requests

    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/video/upload"

    try:
        with open(filepath, "rb") as f:
            response = requests.post(
                url,
                data={
                    "upload_preset": CLOUDINARY_PRESET,
                    "public_id": f"recyclage_shorts/{video_id}",
                    "resource_type": "video",
                },
                files={"file": (f"{video_id}.mp4", f, "video/mp4")},
                timeout=180,
            )

        if response.status_code == 200:
            secure_url = response.json().get("secure_url", "")
            log(f"Cloudinary OK: {secure_url}")
            return secure_url
        else:
            log(f"Cloudinary erreur {response.status_code}: {response.text[:300]}")
            return None
    except Exception as e:
        log(f"Erreur upload Cloudinary: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# ENVOYER A MAKE
# ══════════════════════════════════════════════════════════════════
def envoyer_make(video_url, caption, plateforme, youtube_url):
    import requests

    payload = {
        "pin": MAKE_PIN,
        "platform": plateforme.lower(),
        "video_url": video_url,
        "caption": caption,
        "youtube_url": youtube_url,
    }

    try:
        response = requests.post(
            MAKE_WEBHOOK_URL,
            json=payload,
            timeout=120,
        )
        if response.status_code == 200:
            return True, "OK"
        else:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return False, f"Erreur: {e}"


# ══════════════════════════════════════════════════════════════════
# GENERER CAPTION
# ══════════════════════════════════════════════════════════════════
def generer_caption(pub, plateforme):
    titre = pub.get("titre", "")
    url = pub.get("url", "")
    type_contenu = pub.get("type_contenu", "souvenir")
    marque = pub.get("marque", "")
    code = pub.get("code", "")
    lien = pub.get("lien", "")

    utm = f"utm_source={plateforme.lower()}&utm_medium=social&utm_campaign={type_contenu}_lcdmh"
    url_tracked = f"{url}?{utm}" if "?" not in url else f"{url}&{utm}"

    lines = []

    if type_contenu == "pub":
        lines.append("Mon avis sur ce produit, sans filtre.")
        lines.append("")
        lines.append(f"La video complete : {url_tracked}")
        if code:
            lines.append(f"Code promo : {code}")
        if lien:
            lines.append(lien)
    else:
        lines.append("Tu vois, c'est le genre de moment qui te reste en tete.")
        lines.append("")
        lines.append(f"La video complete : {url_tracked}")

    if plateforme.lower() == "instagram":
        lines.append("")
        lines.append("#moto #roadtrip #motard #LCDMH #shorts #reels")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# NETTOYAGE
# ══════════════════════════════════════════════════════════════════
def nettoyer(filepath):
    try:
        if filepath and os.path.exists(filepath):
            parent = os.path.dirname(filepath)
            os.remove(filepath)
            if parent and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    today_str = str(date.today())
    log(f"Date du jour: {today_str}")

    planning = load_json(PLANNING_FILE, [])
    if not planning:
        log("Planning vide ou introuvable")
        sys.exit(0)

    pubs_jour = [p for p in planning if p.get("date") == today_str]
    if not pubs_jour:
        log("Aucune publication prevue aujourd'hui")
        sys.exit(0)

    log(f"{len(pubs_jour)} publication(s) prevue(s)")

    historique = load_json(HISTORIQUE_FILE, [])

    # Grouper par video_id pour ne telecharger qu'une fois
    videos = {}
    for p in pubs_jour:
        vid = p.get("video_id", "")
        if vid not in videos:
            videos[vid] = {"video": p, "publications": []}
        videos[vid]["publications"].append(p)

    succes = 0
    echecs = 0

    for vid, data in videos.items():
        video = data["video"]
        pubs = data["publications"]

        # 1. Telecharger
        video_url = video.get("url", f"https://www.youtube.com/watch?v={vid}")
        log(f"Telechargement: {video.get('titre', '')[:50]}...")
        filepath = telecharger_short(video_url, vid)

        if not filepath:
            log(f"ECHEC telechargement: {vid}")
            echecs += len(pubs)
            continue

        # 2. Upload Cloudinary
        log(f"Upload Cloudinary: {vid}...")
        cloudinary_url = uploader_cloudinary(filepath, vid)

        if not cloudinary_url:
            nettoyer(filepath)
            log(f"ECHEC Cloudinary: {vid}")
            echecs += len(pubs)
            continue

        # 3. Envoyer a Make pour chaque plateforme
        for p in pubs:
            plateforme = p.get("plateforme", "Facebook")
            caption = generer_caption(p, plateforme)
            youtube_url = video.get("url", f"https://www.youtube.com/watch?v={vid}")

            log(f"Envoi Make {plateforme}: {video.get('titre', '')[:40]}...")
            ok, msg = envoyer_make(cloudinary_url, caption, plateforme, youtube_url)

            if ok:
                succes += 1
                log(f"OK {plateforme}: {vid}")
                historique.append({
                    "video_id": vid,
                    "plateforme": plateforme,
                    "titre": video.get("titre", ""),
                    "type": p.get("type_contenu", ""),
                    "date": today_str,
                    "clics": 0,
                })
            else:
                echecs += 1
                log(f"ECHEC {plateforme}: {msg}")

        nettoyer(filepath)

    # Sauvegarder historique
    save_json(HISTORIQUE_FILE, historique)

    log(f"Termine: {succes} succes, {echecs} echecs")

    if echecs > 0 and succes == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
