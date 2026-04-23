#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload_clip.py — Etape 5 (optionnelle) : uploader un clip sur YouTube.

Lit un fichier .republish.json produit par extract_clips.py et uploade le .mp4
associe via YouTube Data API v3 (videos.insert, upload resumable).

Par securite, le statut par defaut est 'unlisted' (non-liste, accessible par
lien seulement) : tu peux relire dans YouTube Studio puis passer en 'public'.
Peut etre change via --privacy public/unlisted/private ou via config.

Pre-requis :
  - Scope OAuth yt-force-ssl deja present (inclus dans generate_yt_token.py).
  - Pas besoin de lib google-api-python-client : on utilise requests + upload resumable.

Usage :
  python scripts/retention_extractor/upload_clip.py <sidecar.republish.json>
  python scripts/retention_extractor/upload_clip.py <sidecar.republish.json> --privacy public
  python scripts/retention_extractor/upload_clip.py --all --privacy unlisted --limit 3
  python scripts/retention_extractor/upload_clip.py --all --dry
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CONFIG_PATH,
    CONFIG_EXAMPLE_PATH,
    data_dir,
    get_access_token,
    load_config,
    out_dir,
    read_json,
    write_json,
)

UPLOAD_ENDPOINT = (
    "https://www.googleapis.com/upload/youtube/v3/videos"
    "?uploadType=resumable&part=snippet,status"
)

PLAYLISTS_ENDPOINT = "https://www.googleapis.com/youtube/v3/playlists"
PLAYLIST_ITEMS_ENDPOINT = "https://www.googleapis.com/youtube/v3/playlistItems"

DEFAULT_CATEGORY_ID = "19"  # Travel & Events
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB


# ──────────────────────────────────────────────────────────────────────
# Helpers playlists (ensure, add item)
# ──────────────────────────────────────────────────────────────────────
def _load_config_raw() -> tuple[dict, Path]:
    """
    Relit config.json en live (utile pour persister l'ID de playlist creee
    au milieu d'une run sans ecraser les edits de l'utilisateur). Si
    config.json n'existe pas encore on le cree a partir du template.
    """
    target = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data, target


def _persist_playlist_id(kind: str, playlist_id: str) -> None:
    """
    kind = 'pending' ou 'published'. Ecrit l'ID dans config.json (creation
    si besoin, on NE modifie PAS config.example.json).
    """
    key = f"destination_{kind}_playlist_id"
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        # Copie le template pour ne pas perdre les autres reglages.
        data = json.loads(CONFIG_EXAMPLE_PATH.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    data[key] = playlist_id
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ensure_playlist(token: str, title: str) -> str | None:
    """
    Retourne l'ID d'une playlist 'À publier' ou 'Souvenirs LCDMH'.

      - Lit la config : si destination_{kind}_playlist_id est rempli, on le retourne.
      - Sinon on cree la playlist via playlists.insert et on persiste l'ID.

    'kind' est deduit du titre (match exact avec les deux champs de config).
    Si quoi que ce soit echoue (quota 403, reseau), on retourne None et on
    laisse l'upload continuer sans crasher le pipeline.
    """
    try:
        cfg, _ = _load_config_raw()
    except Exception as exc:
        print(f"[upload]   ensure_playlist: config illisible ({exc})")
        return None

    pending_title = cfg.get("destination_pending_playlist_title", "À publier")
    published_title = cfg.get("destination_published_playlist_title", "Souvenirs LCDMH")

    if title == pending_title:
        kind = "pending"
        privacy = "unlisted"
    elif title == published_title:
        kind = "published"
        privacy = "public"
    else:
        print(f"[upload]   ensure_playlist: titre inconnu '{title}'")
        return None

    cached = cfg.get(f"destination_{kind}_playlist_id", "") or ""
    if cached:
        return cached

    # Creation
    payload = {
        "snippet": {"title": title, "description": "Créée par retention_extractor"},
        "status": {"privacyStatus": privacy},
    }
    try:
        r = requests.post(
            PLAYLISTS_ENDPOINT,
            params={"part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            data=json.dumps(payload),
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"[upload]   ensure_playlist: erreur reseau ({exc})")
        return None

    if r.status_code not in (200, 201):
        print(f"[upload]   ensure_playlist ({title}) -> {r.status_code} : {r.text[:300]}")
        return None

    new_id = r.json().get("id")
    if not new_id:
        print(f"[upload]   ensure_playlist: reponse sans id ({r.text[:200]})")
        return None

    try:
        _persist_playlist_id(kind, new_id)
    except Exception as exc:
        print(f"[upload]   ensure_playlist: persist config echoue ({exc})")

    print(f"[upload]   playlist creee '{title}' -> {new_id}")
    return new_id


def add_video_to_playlist(token: str, playlist_id: str, video_id: str) -> bool:
    """Ajoute video_id a la playlist. Retourne True/False (ne crash pas)."""
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
        print(f"[upload]   add_to_playlist: erreur reseau ({exc})")
        return False

    if r.status_code not in (200, 201):
        print(f"[upload]   add_to_playlist -> {r.status_code} : {r.text[:300]}")
        return False
    return True


def build_metadata(sidecar: dict, privacy: str, category_id: str,
                   language: str = "fr") -> dict:
    return {
        "snippet": {
            "title": sidecar["suggested_title"][:100],
            "description": sidecar["suggested_description"][:5000],
            "tags": sidecar.get("suggested_tags", [])[:30],
            "categoryId": category_id,
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }


def initiate_upload(
    token: str, metadata: dict, file_size: int
) -> str:
    """Retourne l'URL resumable ou leve en cas d'erreur."""
    r = requests.post(
        UPLOAD_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(file_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        data=json.dumps(metadata),
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Init upload refuse ({r.status_code}) : {r.text[:500]}")
    location = r.headers.get("Location")
    if not location:
        raise RuntimeError("Pas de header Location dans la reponse d'init upload")
    return location


def upload_chunks(
    session_url: str,
    file_path: Path,
    progress_cb=None,
) -> dict:
    """Upload par chunks avec retry simple. Retourne le payload final."""
    total = file_path.stat().st_size
    offset = 0
    with file_path.open("rb") as f:
        while offset < total:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            end = offset + len(chunk) - 1
            headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{end}/{total}",
                "Content-Type": "video/mp4",
            }
            # Retry x3 sur erreurs reseau / 5xx / 308 resume
            attempt = 0
            while True:
                attempt += 1
                try:
                    r = requests.put(session_url, headers=headers, data=chunk, timeout=300)
                except requests.RequestException as exc:
                    if attempt >= 3:
                        raise
                    print(f"  [upload] erreur reseau ({exc}), retry {attempt}/3...")
                    time.sleep(2 ** attempt)
                    continue

                if r.status_code in (200, 201):
                    if progress_cb:
                        progress_cb(end + 1, total)
                    return r.json()
                if r.status_code == 308:
                    # resume incomplet, avancer offset d'apres Range header
                    rng = r.headers.get("Range", "")
                    if rng.startswith("bytes=0-"):
                        offset = int(rng.split("-")[1]) + 1
                    else:
                        offset = end + 1
                    if progress_cb:
                        progress_cb(offset, total)
                    break  # passer au chunk suivant
                if r.status_code >= 500 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(
                    f"Upload chunk refuse ({r.status_code}) offset={offset} : {r.text[:300]}"
                )
            offset = end + 1
    raise RuntimeError("Upload termine sans reponse finale 200/201")


def upload_one(
    sidecar_path: Path,
    privacy: str,
    category_id: str,
    language: str = "fr",
    dry: bool = False,
) -> dict:
    sidecar = read_json(sidecar_path)
    if not sidecar:
        raise RuntimeError(f"Sidecar introuvable ou vide : {sidecar_path}")

    clip_file = sidecar.get("clip_file")
    if not clip_file:
        raise RuntimeError("Champ clip_file manquant dans le sidecar")

    # clip_file est relatif a parent de out_dir (out/clips/vid/file.mp4)
    base = out_dir().parent  # repo/out
    mp4 = (base / clip_file).resolve()
    if not mp4.exists():
        # fallback : meme dossier que le sidecar
        mp4 = sidecar_path.with_suffix(".mp4")
    if not mp4.exists():
        raise RuntimeError(f"MP4 introuvable pour {sidecar_path}")

    metadata = build_metadata(sidecar, privacy, category_id, language=language)
    size = mp4.stat().st_size
    print(f"[upload] {mp4.name}  ({size/1024/1024:.1f} MiB)")
    print(f"[upload]   title    : {metadata['snippet']['title']}")
    print(f"[upload]   privacy  : {metadata['status']['privacyStatus']}")
    print(f"[upload]   lang     : {metadata['snippet']['defaultLanguage']}")

    if dry:
        return {"status": "dry", "title": metadata["snippet"]["title"]}

    token = get_access_token()
    session_url = initiate_upload(token, metadata, size)
    print(f"[upload]   session  : {session_url[:80]}...")

    def progress(done: int, total: int) -> None:
        pct = done / total * 100
        print(f"\r[upload]   progress : {done/1024/1024:6.1f} / {total/1024/1024:.1f} MiB ({pct:5.1f} %)",
              end="", flush=True)

    result = upload_chunks(session_url, mp4, progress_cb=progress)
    print("")  # newline apres progress

    video_id = result.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
    print(f"[upload] OK -> {video_url}")

    # ─── Ajout automatique a la playlist 'À publier' (review buffer) ───
    # Tolerant aux erreurs : si quotaExceeded / 403 / reseau, on enchaine.
    pending_playlist_id: str | None = None
    added_to_pending = False
    if video_id:
        try:
            cfg_live, _ = _load_config_raw()
            pending_title = cfg_live.get(
                "destination_pending_playlist_title", "À publier"
            )
            pending_playlist_id = ensure_playlist(token, pending_title)
            if pending_playlist_id:
                added_to_pending = add_video_to_playlist(
                    token, pending_playlist_id, video_id
                )
                if added_to_pending:
                    print(f"[upload]   ajoute a playlist '{pending_title}'")
        except Exception as exc:
            # on ne casse pas l'upload si la playlist echoue
            print(f"[upload]   ajout playlist ignore ({exc})")

    # Mise a jour du sidecar avec le resultat
    sidecar.setdefault("uploads", []).append({
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "video_id": video_id,
        "privacy": privacy,
        "url": video_url,
        "language": language,
        "pending_playlist_id": pending_playlist_id,
        "added_to_pending": added_to_pending,
    })
    # Statut initial : en revue tant que privacy != public
    if privacy != "public":
        sidecar.setdefault("status", "pending_review")
    else:
        sidecar.setdefault("status", "published")
    write_json(sidecar_path, sidecar)

    return {
        "status": "ok",
        "video_id": video_id,
        "url": video_url,
        "title": metadata["snippet"]["title"],
        "pending_playlist_id": pending_playlist_id,
    }


def find_sidecars(clips_root: Path) -> list[Path]:
    return sorted(clips_root.rglob("*.republish.json"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sidecar", nargs="?", help="Chemin d'un .republish.json precis.")
    ap.add_argument("--all", action="store_true", help="Uploade tous les sidecars non encore uploades.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--privacy", default="unlisted", choices=["public", "unlisted", "private"])
    ap.add_argument("--category-id", default=DEFAULT_CATEGORY_ID)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    privacy = args.privacy or cfg.get("default_upload_privacy", "unlisted")
    language = cfg.get("upload_language", "fr")

    if args.sidecar and not args.all:
        result = upload_one(Path(args.sidecar), privacy, args.category_id,
                            language=language, dry=args.dry)
        return 0 if result["status"] in ("ok", "dry") else 1

    clips_root = out_dir()
    sidecars = find_sidecars(clips_root)
    if not sidecars:
        print(f"[upload] Aucun sidecar dans {clips_root}")
        return 1

    # Ignore ceux deja uploades (sauf --dry)
    pending: list[Path] = []
    for sc in sidecars:
        data = read_json(sc) or {}
        if data.get("uploads") and not args.dry:
            continue
        pending.append(sc)
    if args.limit > 0:
        pending = pending[: args.limit]

    if not pending:
        print("[upload] Tout est deja uploade. Utilise --dry pour re-simuler.")
        return 0

    print(f"[upload] {len(pending)} clip(s) a uploader (privacy={privacy})")
    ok = failed = 0
    for sc in pending:
        try:
            result = upload_one(sc, privacy, args.category_id,
                                language=language, dry=args.dry)
            if result["status"] in ("ok", "dry"):
                ok += 1
            else:
                failed += 1
        except Exception as exc:
            print(f"[upload] ECHEC {sc.name} : {exc}")
            failed += 1
        # pause douce pour ne pas saturer
        time.sleep(1)

    print("")
    print(f"[upload] OK={ok}  FAILED={failed}")

    summary_path = data_dir() / "upload_report.json"
    report = read_json(summary_path) or {"history": []}
    report["history"].append({
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "ok": ok, "failed": failed, "privacy": privacy, "dry": args.dry,
    })
    write_json(summary_path, report)

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
