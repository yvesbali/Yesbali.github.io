#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cron Recyclage Social LCDMH — v4 (yt-dlp + deno + cookies)
=============================================================
Script autonome pour GitHub Actions.
Lit le planning, telecharge le short YouTube via yt-dlp + cookies,
uploade la video sur Cloudinary, envoie a Make pour publication FB/IG.

Cookies YouTube stockes dans le secret GitHub YOUTUBE_COOKIES.
"""

import json
import os
import subprocess
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
COOKIES_FILE = REPO_ROOT / "cookies.txt"


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
# TELECHARGER LE SHORT YOUTUBE (yt-dlp + cookies)
# ══════════════════════════════════════════════════════════════════
def telecharger_video(video_id):
    """
    Telecharge le short YouTube via yt-dlp avec cookies.
    Retourne le chemin du fichier video ou None.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    tmp_dir = tempfile.mkdtemp(prefix="lcdmh_short_")
    output_path = os.path.join(tmp_dir, f"{video_id}.mp4")

    cmd = [
        "yt-dlp",
        "-f", "best[height<=720]",
        "--no-playlist",
        "-o", output_path,
    ]

    # Ajouter les cookies si le fichier existe
    if COOKIES_FILE.exists():
        cmd.extend(["--cookies", str(COOKIES_FILE)])
        log("Cookies YouTube charges")
    else:
        log("ATTENTION: pas de fichier cookies.txt")

    cmd.append(url)

    try:
        log(f"yt-dlp: telechargement {video_id}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            log(f"Telecharge: {size_mb:.1f} Mo")
            return output_path
        else:
            log(f"yt-dlp erreur (code {result.returncode})")
            if result.stderr:
                err_lines = result.stderr.strip().split("\n")
                for line in err_lines[-3:]:
                    log(f"  stderr: {line}")
            return None

    except subprocess.TimeoutExpired:
        log("yt-dlp timeout (120s)")
        return None
    except FileNotFoundError:
        log("yt-dlp non installe!")
        return None
    except Exception as e:
        log(f"Erreur telechargement: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# FALLBACK: THUMBNAIL YOUTUBE (si yt-dlp echoue)
# ══════════════════════════════════════════════════════════════════
def get_thumbnail_url(video_id):
    """Recupere la meilleure miniature YouTube disponible."""
    resolutions = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
    ]
    for url in resolutions:
        try:
            r = requests.head(url, timeout=10, allow_redirects=True)
            content_length = int(r.headers.get("Content-Length", 0))
            if r.status_code == 200 and content_length > 5000:
                return url
        except Exception:
            continue
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def telecharger_thumbnail(video_id):
    """Telecharge la miniature YouTube en local."""
    url = get_thumbnail_url(video_id)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        tmp_dir = tempfile.mkdtemp(prefix="lcdmh_thumb_")
        filepath = os.path.join(tmp_dir, f"{video_id}.jpg")
        with open(filepath, "wb") as f:
            f.write(r.content)
        return filepath
    except Exception as e:
        log(f"Erreur thumbnail: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# UPLOAD CLOUDINARY
# ══════════════════════════════════════════════════════════════════
def uploader_cloudinary(filepath, video_id, is_video=True):
    """Upload un fichier sur Cloudinary (video ou image)."""
    resource_type = "video" if is_video else "image"
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/{resource_type}/upload"

    ext = "mp4" if is_video else "jpg"
    mime = "video/mp4" if is_video else "image/jpeg"
    folder = "recyclage_shorts" if is_video else "recyclage_thumbs"

    try:
        with open(filepath, "rb") as f:
            response = requests.post(
                url,
                data={
                    "upload_preset": CLOUDINARY_PRESET,
                    "public_id": f"{folder}/{video_id}",
                },
                files={"file": (f"{video_id}.{ext}", f, mime)},
                timeout=300 if is_video else 60,
            )

        if response.status_code == 200:
            secure_url = response.json().get("secure_url", "")
            log(f"Cloudinary OK ({resource_type}): {secure_url}")
            return secure_url, resource_type
        else:
            log(f"Cloudinary erreur {response.status_code}: {response.text[:300]}")
            return None, None
    except Exception as e:
        log(f"Erreur upload Cloudinary: {e}")
        return None, None


# ══════════════════════════════════════════════════════════════════
# ENVOYER A MAKE
# ══════════════════════════════════════════════════════════════════
def envoyer_make(media_url, caption, plateforme, youtube_url, media_type="video"):
    """Envoie le payload a Make.com via webhook."""
    payload = {
        "pin": MAKE_PIN,
        "platform": plateforme.lower(),
        "media_type": media_type,
        "caption": caption,
        "youtube_url": youtube_url,
        # Toujours envoyer les deux champs — Make routera selon media_type
        "video_url": media_url,
        "image_url": media_url,
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
def deja_publie(historique, video_id, plateforme, date_str):
    """Verifie si cette video a deja ete publiee sur cette plateforme a cette date."""
    for h in historique:
        if (h.get("video_id") == video_id
                and h.get("plateforme", "").lower() == plateforme.lower()
                and h.get("date") == date_str):
            return True
    return False


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

    historique = load_json(HISTORIQUE_FILE, [])

    # Filtrer les publications deja faites
    pubs_nouvelles = []
    for p in pubs_jour:
        vid = p.get("video_id", "")
        plat = p.get("plateforme", "")
        if deja_publie(historique, vid, plat, today_str):
            log(f"SKIP (deja publie): {vid} sur {plat}")
        else:
            pubs_nouvelles.append(p)

    if not pubs_nouvelles:
        log("Toutes les publications du jour ont deja ete faites")
        sys.exit(0)

    log(f"{len(pubs_nouvelles)} publication(s) a faire ({len(pubs_jour) - len(pubs_nouvelles)} deja faites)")

    # Grouper par video_id pour ne telecharger qu'une fois
    videos = {}
    for p in pubs_nouvelles:
        vid = p.get("video_id", "")
        if vid not in videos:
            videos[vid] = {"video": p, "publications": []}
        videos[vid]["publications"].append(p)

    succes = 0
    echecs = 0

    for vid, data in videos.items():
        video = data["video"]
        pubs = data["publications"]

        # ── ETAPE 1 : Telecharger le short via yt-dlp ──
        log(f"Telechargement short: {video.get('titre', '')[:50]}...")
        filepath = telecharger_video(vid)
        is_video = True

        # ── FALLBACK : Si yt-dlp echoue, utiliser la thumbnail ──
        if not filepath:
            log(f"Fallback thumbnail pour: {vid}")
            filepath = telecharger_thumbnail(vid)
            is_video = False

        if not filepath:
            log(f"ECHEC total (video + thumbnail): {vid}")
            echecs += len(pubs)
            continue

        # ── ETAPE 2 : Upload Cloudinary ──
        media_type_label = "video" if is_video else "image"
        log(f"Upload Cloudinary ({media_type_label}): {vid}...")
        cloudinary_url, resource_type = uploader_cloudinary(filepath, vid, is_video=is_video)

        if not cloudinary_url:
            nettoyer(filepath)
            log(f"ECHEC Cloudinary: {vid}")
            echecs += len(pubs)
            continue

        # ── ETAPE 3 : Envoyer a Make pour chaque plateforme ──
        for p in pubs:
            plateforme = p.get("plateforme", "Facebook")
            caption = generer_caption(p, plateforme)
            youtube_url = video.get("url", f"https://www.youtube.com/watch?v={vid}")

            make_media_type = "video" if is_video else "image"
            log(f"Envoi Make {plateforme} ({make_media_type}): {video.get('titre', '')[:40]}...")
            ok, msg = envoyer_make(cloudinary_url, caption, plateforme, youtube_url, media_type=make_media_type)

            if ok:
                succes += 1
                log(f"OK {plateforme}: {vid}")
                historique.append({
                    "video_id": vid,
                    "plateforme": plateforme,
                    "titre": video.get("titre", ""),
                    "type": p.get("type_contenu", ""),
                    "media_type": make_media_type,
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