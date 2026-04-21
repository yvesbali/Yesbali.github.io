#!/usr/bin/env python3
"""
apply_descriptions_batch_01.py — Publie les 5 descriptions batch_01 sur YouTube
===============================================================================
Lit :
  GEO_PATCHES/youtube_descriptions_batch_01.md  (blocs entre triple backticks)
Écrit (API YT Data v3) :
  videos.update(part=snippet) pour chaque video_id du batch

Sécurité :
  - AVANT toute écriture : backup complet via videos.list dans
    logs/yt_backup_<video_id>_<date>.json
  - APRÈS écriture : log des diffs dans logs/yt_apply_<date>.json
  - --dry : tout sauf la requête update (test de lecture + parsing)

Usage :
  python scripts/apply_descriptions_batch_01.py --dry                      # test sans écrire
  python scripts/apply_descriptions_batch_01.py                            # applique
  python scripts/apply_descriptions_batch_01.py --only AYjFZ1QfCWY         # une seule vidéo
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
MD_PATH = BASE / "GEO_PATCHES/youtube_descriptions_batch_01.md"
LOG_DIR = BASE / "logs"
TARGETS_PATH = BASE / "data/baselines/targets_batch_01.json"

# Ordre identique à targets_batch_01.json
EXPECTED_ORDER = ["AYjFZ1QfCWY", "jKEeq45vtPU", "eNVD7c6g3wM", "dOjvRtEitX4", "xQSpEY5EsEc"]


def get_access_token() -> str:
    """Échange refresh_token contre access_token (même logique que fetch_youtube.py)."""
    tok = os.environ.get("YT_TOKEN_ANALYTICS", "")
    if tok:
        try:
            d = json.loads(tok)
            cid, cs, rt = d.get("client_id"), d.get("client_secret"), d.get("refresh_token")
            if all([cid, cs, rt]):
                r = requests.post("https://oauth2.googleapis.com/token", data={
                    "client_id": cid, "client_secret": cs,
                    "refresh_token": rt, "grant_type": "refresh_token",
                }, timeout=30)
                r.raise_for_status()
                return r.json()["access_token"]
        except Exception as e:
            print(f"[ERR] YT_TOKEN_ANALYTICS invalide : {e}", file=sys.stderr)

    cid = os.environ.get("YOUTUBE_CLIENT_ID")
    cs = os.environ.get("YOUTUBE_CLIENT_SECRET")
    rt = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    if all([cid, cs, rt]):
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": cid, "client_secret": cs,
            "refresh_token": rt, "grant_type": "refresh_token",
        }, timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]

    # Fallback : fichier yt_token_analytics.json à la racine (créé par workflows)
    local = BASE / "yt_token_analytics.json"
    if local.exists():
        d = json.load(open(local, encoding="utf-8"))
        cid, cs, rt = d.get("client_id"), d.get("client_secret"), d.get("refresh_token")
        if all([cid, cs, rt]):
            r = requests.post("https://oauth2.googleapis.com/token", data={
                "client_id": cid, "client_secret": cs,
                "refresh_token": rt, "grant_type": "refresh_token",
            }, timeout=30)
            r.raise_for_status()
            return r.json()["access_token"]

    raise RuntimeError(
        "Credentials YouTube introuvables.\n"
        "Définis YT_TOKEN_ANALYTICS (JSON avec client_id+client_secret+refresh_token)\n"
        "OU les 3 variables YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN,\n"
        "OU place yt_token_analytics.json à la racine du repo."
    )


def parse_descriptions(md_text: str) -> dict:
    """
    Extrait {video_id: description_text} depuis le markdown.
    Chaque bloc de description est entouré de triple backticks.
    On s'appuie sur l'en-tête « Vidéo N — <VIDEO_ID> (...) » qui précède le bloc.
    """
    out = {}
    # Regex : capture un bloc ``` ... ``` précédé par un heading contenant un videoId entre parenthèses
    heading_re = re.compile(
        r"##\s+Vid[ée]o\s+\d+\s+[—-]\s+([A-Za-z0-9_-]{11})",
        re.UNICODE,
    )
    # On scanne linéairement : dès qu'on trouve un heading, on cherche le prochain bloc ```
    lines = md_text.splitlines()
    i = 0
    current_vid = None
    while i < len(lines):
        m = heading_re.search(lines[i])
        if m:
            current_vid = m.group(1)
            i += 1
            continue
        if current_vid and lines[i].strip().startswith("```"):
            # Début du bloc code
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            desc = "\n".join(buf).rstrip() + "\n"
            out[current_vid] = desc
            current_vid = None
        i += 1
    return out


def get_video(access_token: str, video_id: str) -> dict:
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,status,contentDetails", "id": video_id},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise RuntimeError(f"Vidéo {video_id} introuvable.")
    return items[0]


def update_description(access_token: str, video_id: str, snippet: dict, new_desc: str) -> dict:
    """
    Update la description via videos.update?part=snippet.
    On PRÉSERVE title/categoryId/tags/defaultLanguage/defaultAudioLanguage, sinon YouTube les efface.
    """
    body = {
        "id": video_id,
        "snippet": {
            "title": snippet["title"],
            "categoryId": snippet["categoryId"],
            "description": new_desc,
        },
    }
    if "tags" in snippet:
        body["snippet"]["tags"] = snippet["tags"]
    if "defaultLanguage" in snippet:
        body["snippet"]["defaultLanguage"] = snippet["defaultLanguage"]
    if "defaultAudioLanguage" in snippet:
        body["snippet"]["defaultAudioLanguage"] = snippet["defaultAudioLanguage"]

    r = requests.put(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"PUT videos — status {r.status_code} — {r.text[:400]}")
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="parse + get_video sans videos.update")
    ap.add_argument("--only", help="ne traiter qu'une seule video_id")
    ap.add_argument("--check-placeholders", action="store_true",
                    help="bloque la publication si XX:XX ou [LIEN AMAZON] encore présent")
    ap.set_defaults(check_placeholders=True)
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    # 1. Parse des descriptions
    md = MD_PATH.read_text(encoding="utf-8")
    descs = parse_descriptions(md)
    print(f"[INFO] {len(descs)} descriptions parsées.")
    for vid in EXPECTED_ORDER:
        if vid not in descs:
            print(f"[WARN] {vid} non trouvée dans le markdown.")

    if args.only:
        if args.only not in descs:
            print(f"[ERR] --only {args.only} non trouvée.")
            sys.exit(2)
        descs = {args.only: descs[args.only]}

    # 2. Vérif placeholders
    placeholders_found = {}
    for vid, d in descs.items():
        issues = []
        if re.search(r"XX:XX", d):
            issues.append("XX:XX dans les chapitres")
        if "[LIEN AMAZON AFFILIÉ]" in d or "[LIEN AMAZON]" in d or "[REMPLACER" in d or "[modèle à préciser]" in d:
            issues.append("placeholder [LIEN AMAZON] / [REMPLACER] / [modèle à préciser]")
        if issues:
            placeholders_found[vid] = issues

    if placeholders_found and args.check_placeholders and not args.dry:
        print("[BLOQUÉ] Placeholders encore présents :")
        for vid, issues in placeholders_found.items():
            print(f"  {vid} : {', '.join(issues)}")
        print("\nRelance avec --no-check-placeholders pour forcer, ou édite le markdown.")
        sys.exit(3)
    elif placeholders_found:
        print("[WARN] Placeholders présents mais on continue (dry ou --no-check-placeholders) :")
        for vid, issues in placeholders_found.items():
            print(f"  {vid} : {', '.join(issues)}")

    # 3. Auth
    print("[INFO] Auth YouTube...")
    tok = get_access_token()
    print("[OK] access_token obtenu.")

    # 4. Boucle backup + update
    log = {"applied_at": datetime.now().isoformat(timespec="seconds"), "dry": args.dry, "videos": []}
    for vid in EXPECTED_ORDER:
        if vid not in descs:
            continue
        try:
            item = get_video(tok, vid)
            snippet = item["snippet"]
            old_desc = snippet.get("description", "")

            # Backup JSON complet (snippet + status + contentDetails)
            backup_path = LOG_DIR / f"yt_backup_{vid}_{today}.json"
            backup_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")

            new_desc = descs[vid]
            entry = {
                "video_id": vid,
                "title": snippet.get("title"),
                "old_description_len": len(old_desc),
                "new_description_len": len(new_desc),
                "backup_file": str(backup_path.relative_to(BASE)),
                "status": "dry-run" if args.dry else "pending",
            }

            if args.dry:
                print(f"[DRY] {vid} — {snippet.get('title')[:70]!r} — old={len(old_desc)} → new={len(new_desc)} chars")
            else:
                resp = update_description(tok, vid, snippet, new_desc)
                entry["status"] = "updated"
                entry["applied_description_len"] = len(resp["snippet"]["description"])
                print(f"[OK] {vid} — description mise à jour "
                      f"(old={len(old_desc)}, new={len(new_desc)} chars).")

            log["videos"].append(entry)
        except Exception as e:
            print(f"[ERR] {vid} : {e}")
            log["videos"].append({"video_id": vid, "status": "error", "error": str(e)})

    log_path = LOG_DIR / f"yt_apply_batch_01_{today}.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Log : {log_path}")


if __name__ == "__main__":
    main()
