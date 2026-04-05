#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cron Recyclage Social LCDMH — v2 (sans yt-dlp)
=================================================
Script autonome pour GitHub Actions.
Lit le planning, recupere la miniature YouTube HD,
uploade sur Cloudinary, envoie a Make pour publication FB/IG.

Plus de telechargement video = plus de blocage YouTube bot.
"""

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import requests

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
# RECUPERER THUMBNAIL YOUTUBE (sans yt-dlp)
# ══════════════════════════════════════════════════════════════════
def get_thumbnail_url(video_id):
    """
    Recupere la meilleure miniature YouTube disponible.
    Essaie dans l'ordre : maxresdefault > sddefault > hqdefault.
    Pas besoin d'API key ni de token — les thumbnails sont publiques.
    """
    resolutions = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",   # 1280x720
        f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",       # 640x480
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",       # 480x360
    ]

    for url in resolutions:
        try:
            r = requests.head(url, timeout=10, allow_redirects=True)
            # YouTube renvoie une image grise de 120x90 si la resolution n'existe pas
            content_length = int(r.headers.get("Content-Length", 0))
            if r.status_code == 200 and content_length > 5000:
                return url
        except Exception:
            continue

    # Fallback absolu
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def telecharger_thumbnail(video_id):
    """Telecharge la miniature YouTube en local et retourne le chemin."""
    url = get_thumbnail_url(video_id)
    log(f"Thumbnail: {url}")

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()

        tmp_dir = tempfile.mkdtemp(prefix="lcdmh_thumb_")
        filepath = os.path.join(tmp_dir, f"{video_id}.jpg")

        with open(filepath, "wb") as f:
            f.write(r.content)

        size_kb = len(r.content) / 1024
        log(f"Thumbnail telechargee: {size_kb:.0f} Ko")
        return filepath

    except Exception as e:
        log(f"Erreur telechargement thumbnail: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# UPLOAD CLOUDINARY (image au lieu de video)
# ══════════════════════════════════════════════════════════════════
def uploader_cloudinary(filepath, video_id):
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/image/upload"

    try:
        with open(filepath, "rb") as f:
            response = requests.post(
                url,
                data={
                    "upload_preset": CLOUDINARY_PRESET,
                    "public_id": f"recyclage_thumbs/{video_id}",
                },
                files={"file": (f"{video_id}.jpg", f, "image/jpeg")},
                timeout=60,
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
def envoyer_make(image_url, caption, plateforme, youtube_url):
    payload = {
        "pin": MAKE_PIN,
        "platform": plateforme.lower(),
        "media_type": "image",
        "image_url": image_url,
        "video_url": youtube_url,
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

    # Grouper par video_id pour ne telecharger la thumbnail qu'une fois
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

        # 1. Telecharger la thumbnail YouTube (pas la video !)
        log(f"Recuperation thumbnail: {video.get('titre', '')[:50]}...")
        filepath = telecharger_thumbnail(vid)

        if not filepath:
            log(f"ECHEC thumbnail: {vid}")
            echecs += len(pubs)
            continue

        # 2. Upload Cloudinary (image)
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
