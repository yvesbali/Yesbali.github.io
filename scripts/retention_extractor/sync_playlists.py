#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_playlists.py — Synchronisation des playlists 'À publier' / 'Souvenirs LCDMH'.

Pour chaque sidecar dans out/clips/**/*.republish.json :
  - Recupere privacyStatus courant de la video uploadee (videos.list).
  - Si privacyStatus == 'public' ET clip encore dans 'À publier' :
      * le retire de 'À publier' (playlistItems.delete)
      * l'ajoute a 'Souvenirs LCDMH' (playlistItems.insert)
      * marque status = 'published' dans le sidecar
  - Si privacyStatus != 'public' et statut absent :
      * marque status = 'pending_review'

Idempotent et safe a relancer. N'ecrit rien en --dry.

Usage :
  python scripts/retention_extractor/sync_playlists.py
  python scripts/retention_extractor/sync_playlists.py --dry
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    get_access_token,
    load_config,
    out_dir,
    read_json,
    write_json,
)
from upload_clip import ensure_playlist  # noqa: E402

PLAYLIST_ITEMS_ENDPOINT = "https://www.googleapis.com/youtube/v3/playlistItems"
VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"


def fetch_privacy_status(token: str, video_ids: list[str]) -> dict[str, str]:
    """Batch videos.list (part=status) pour recuperer privacyStatus par id."""
    out: dict[str, str] = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        try:
            r = requests.get(
                VIDEOS_ENDPOINT,
                params={
                    "part": "status",
                    "id": ",".join(batch),
                    "access_token": token,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            print(f"[sync] videos.list: erreur reseau ({exc})")
            continue
        if r.status_code != 200:
            print(f"[sync] videos.list -> {r.status_code} : {r.text[:200]}")
            continue
        for item in r.json().get("items", []):
            out[item["id"]] = item.get("status", {}).get("privacyStatus", "")
    return out


def find_playlist_item_id(token: str, playlist_id: str, video_id: str) -> str | None:
    """
    Cherche l'ID de l'entree playlistItems correspondant a video_id dans
    playlist_id. Retourne None si introuvable (pagination supportee).
    """
    page_token = None
    while True:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "videoId": video_id,
            "maxResults": 50,
            "access_token": token,
        }
        if page_token:
            params["pageToken"] = page_token
        try:
            r = requests.get(PLAYLIST_ITEMS_ENDPOINT, params=params, timeout=30)
        except requests.RequestException as exc:
            print(f"[sync] playlistItems.list: erreur reseau ({exc})")
            return None
        if r.status_code != 200:
            print(f"[sync] playlistItems.list -> {r.status_code} : {r.text[:200]}")
            return None
        data = r.json()
        for item in data.get("items", []):
            if item.get("snippet", {}).get("resourceId", {}).get("videoId") == video_id:
                return item["id"]
        page_token = data.get("nextPageToken")
        if not page_token:
            return None


def remove_from_playlist(token: str, playlist_item_id: str) -> bool:
    try:
        r = requests.delete(
            PLAYLIST_ITEMS_ENDPOINT,
            params={"id": playlist_item_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"[sync] playlistItems.delete: erreur reseau ({exc})")
        return False
    if r.status_code not in (200, 204):
        print(f"[sync] playlistItems.delete -> {r.status_code} : {r.text[:200]}")
        return False
    return True


def add_to_playlist(token: str, playlist_id: str, video_id: str) -> bool:
    payload = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    try:
        r = requests.post(
            PLAYLIST_ITEMS_ENDPOINT,
            params={"part": "snippet"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            data=json.dumps(payload),
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"[sync] playlistItems.insert: erreur reseau ({exc})")
        return False
    if r.status_code not in (200, 201):
        print(f"[sync] playlistItems.insert -> {r.status_code} : {r.text[:200]}")
        return False
    return True


def iter_sidecars(clips_root: Path):
    for sc in sorted(clips_root.rglob("*.republish.json")):
        data = read_json(sc)
        if not data:
            continue
        yield sc, data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry", action="store_true",
                    help="Affiche les actions sans rien ecrire ni modifier.")
    args = ap.parse_args()

    cfg = load_config()
    clips_root = out_dir(cfg)

    pending_title = cfg.get("destination_pending_playlist_title", "À publier")
    published_title = cfg.get("destination_published_playlist_title", "Souvenirs LCDMH")

    # Collecte des sidecars qui ont au moins un upload
    targets: list[tuple[Path, dict, str]] = []  # (sidecar_path, data, last_video_id)
    for sc, data in iter_sidecars(clips_root):
        uploads = data.get("uploads") or []
        if not uploads:
            continue
        last = uploads[-1]
        vid = last.get("video_id")
        if not vid:
            continue
        targets.append((sc, data, vid))

    if not targets:
        print("[sync] Aucun sidecar avec upload. Rien a faire.")
        return 0

    print(f"[sync] {len(targets)} clip(s) a synchroniser")
    print(f"[sync] pending   : '{pending_title}'")
    print(f"[sync] published : '{published_title}'")
    if args.dry:
        print("[sync] ** DRY RUN ** (aucune modification)")

    try:
        token = get_access_token()
    except Exception as exc:
        print(f"[sync] Impossible d'obtenir un access_token : {exc}")
        return 1

    # Resolution des IDs de playlists (creation si besoin, sauf dry)
    pending_id: str | None = cfg.get("destination_pending_playlist_id") or None
    published_id: str | None = cfg.get("destination_published_playlist_id") or None
    if not args.dry:
        pending_id = pending_id or ensure_playlist(token, pending_title)
        published_id = published_id or ensure_playlist(token, published_title)
    if not pending_id:
        print("[sync] ⚠ pas d'ID 'pending' connu, on ne pourra pas retirer des items.")
    if not published_id:
        print("[sync] ⚠ pas d'ID 'published' connu, on ne pourra pas ajouter d'items.")

    # Recupere privacyStatus de toutes les videos en un batch
    video_ids = [vid for _, _, vid in targets]
    privacy_map = fetch_privacy_status(token, video_ids) if not args.dry else {}

    changed = promoted = marked_pending = 0
    for sc, data, vid in targets:
        current_status = data.get("status")
        privacy = privacy_map.get(vid, "")

        if args.dry:
            print(f"[sync] DRY {sc.name}  video={vid}  privacy={privacy!r}  status={current_status!r}")
            continue

        if not privacy:
            print(f"[sync] {vid} : privacyStatus inconnu (video supprimee ?), skip.")
            continue

        if privacy == "public":
            if current_status == "published":
                # deja synchronise
                continue
            # Promotion : retirer de pending, ajouter a published
            did_remove = False
            if pending_id:
                item_id = find_playlist_item_id(token, pending_id, vid)
                if item_id:
                    did_remove = remove_from_playlist(token, item_id)
                    if did_remove:
                        print(f"[sync] {vid} retire de '{pending_title}'")
            did_add = False
            if published_id:
                did_add = add_to_playlist(token, published_id, vid)
                if did_add:
                    print(f"[sync] {vid} ajoute a '{published_title}'")

            data["status"] = "published"
            data.setdefault("playlist_history", []).append({
                "at": datetime.now(timezone.utc).isoformat(),
                "action": "promote_to_published",
                "removed_from_pending": did_remove,
                "added_to_published": did_add,
            })
            write_json(sc, data)
            promoted += 1
            changed += 1
        else:
            # Non public : si pas de status encore, marquer pending_review
            if current_status is None:
                data["status"] = "pending_review"
                write_json(sc, data)
                marked_pending += 1
                changed += 1

        # petit delai pour eviter de saturer l'API
        time.sleep(0.2)

    print("")
    print(f"[sync] promus published={promoted}  marques pending_review={marked_pending}  "
          f"total changes={changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
