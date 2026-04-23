#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_candidates.py — Etape 1 du pipeline retention_extractor.

Objectif : produire data/retention/candidates.json avec la liste des videos
  "moto France" eligibles pour l'extraction de clips a forte retention.

Regles appliquees (toutes configurables dans config.json) :
  - On lit la playlist Uploads de la chaine.
  - On exclut les videos presentes dans exclude_playlists (ex: Cap Nord).
  - On exclut par mots-cles de titre (ex: "cap nord", "norvege", "jour X").
  - On ne garde que les videos publiques dont duration_s >= min_duration_s.
  - On ne garde que les videos avec viewCount >= min_views.
  - On ne garde que les videos publiees apres published_after.
  - Optionnel : include_title_keywords (whitelist additionnelle).

Sortie : data/retention/candidates.json
  {
    "updated_at": "...",
    "criteria": {...},
    "count": N,
    "videos": [
      {"video_id", "title", "duration_s", "views", "published", "url"},
      ...
    ]
  }

Usage :
  python scripts/retention_extractor/list_candidates.py
  python scripts/retention_extractor/list_candidates.py --limit 20
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    data_dir,
    get_access_token,
    iso8601_duration_to_seconds,
    load_config,
    out_dir,
    read_json,
    write_json,
)


def already_processed_video_ids() -> set[str]:
    """
    Retourne les video_id deja traites par le pipeline. On considere qu'une
    video est 'deja traitee' si au moins un sidecar .republish.json existe
    dans out/clips/<video_id>/. On lit le champ source_video_id du sidecar
    pour etre resistant aux renommages de dossiers.

    On exclut uniquement les sidecars dont le status est 'published' ou
    'rejected' (deja valides ou rejetes). Les 'pending_review' restent
    candidats parce que l'utilisateur n'a pas encore tranche.
    """
    seen: set[str] = set()
    clips_root = out_dir()
    if not clips_root.exists():
        return seen
    for sidecar in clips_root.rglob("*.republish.json"):
        data = read_json(sidecar) or {}
        status = (data.get("status") or "").lower()
        vid = data.get("source_video_id") or sidecar.parent.name
        if not vid:
            continue
        # Par defaut on skippe : toute video ayant deja un clip extrait est
        # consideree comme deja traitee (ca inclut les uploads pending_review).
        # Si tu veux reintegrer les pending_review, change cette condition.
        if status in ("published", "rejected", "pending_review", "") or data.get("uploads"):
            seen.add(vid)
    return seen


def get_uploads_playlist_id(token: str, channel_id: str) -> str:
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "contentDetails", "id": channel_id, "access_token": token},
        timeout=30,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise RuntimeError(f"Chaine {channel_id} introuvable")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_playlist_video_ids(token: str, playlist_id: str) -> list[str]:
    ids: list[str] = []
    page_token = None
    while True:
        params = {
            "part": "contentDetails",
            "maxResults": 50,
            "playlistId": playlist_id,
            "access_token": token,
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId")
            if vid:
                ids.append(vid)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return ids


def fetch_video_details(token: str, video_ids: list[str]) -> list[dict]:
    """Par batch de 50, recupere snippet + contentDetails + statistics + status."""
    out = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet,contentDetails,statistics,status",
                "id": ",".join(batch),
                "access_token": token,
            },
            timeout=30,
        )
        r.raise_for_status()
        out.extend(r.json().get("items", []))
    return out


def title_matches(title: str, keywords: list[str]) -> bool:
    t = title.lower()
    return any(kw.lower() in t for kw in keywords)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="Limite le nombre de candidats retenus.")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--include-processed", action="store_true",
                    help="Inclut aussi les videos deja traitees (par defaut on les skippe).")
    args = ap.parse_args()

    cfg = load_config()
    channel_id = cfg["channel_id"]
    include_playlists: list[str] = cfg.get("include_playlists", [])
    exclude_playlists: list[str] = cfg.get("exclude_playlists", [])
    exclude_keywords: list[str] = cfg.get("exclude_title_keywords", [])
    include_keywords: list[str] = cfg.get("include_title_keywords", [])
    min_duration = int(cfg.get("min_duration_s", 360))
    min_views = int(cfg.get("min_views", 500))
    published_after = cfg.get("published_after", "2000-01-01")

    print(f"[list] Config : {cfg.get('_loaded_from')}")
    print(f"[list] Channel : {channel_id}")
    print(f"[list] Filtres  : duree>={min_duration}s, vues>={min_views}, apres={published_after}")
    print(f"[list] Include  : {len(include_playlists)} playlist(s) whitelist")
    print(f"[list] Exclude  : {len(exclude_playlists)} playlist(s), {len(exclude_keywords)} mot(s)-cle(s)")

    token = get_access_token()
    print("[list] Token OAuth OK")

    # 1) IDs a exclure
    excluded_ids: set[str] = set()
    for pid in exclude_playlists:
        if not pid or "xxxx" in pid.lower():
            continue
        try:
            pids = list_playlist_video_ids(token, pid)
            excluded_ids.update(pids)
            print(f"[list]   playlist exclue {pid} : {len(pids)} videos")
        except Exception as exc:
            print(f"[list]   ⚠ playlist {pid} inaccessible : {exc}")

    # 2) IDs whitelist (optionnel) : si include_playlists est rempli, on ne
    #    considere QUE les videos membres de ces playlists. Sinon, on prend
    #    toute la playlist Uploads comme avant.
    included_ids: set[str] | None = None
    if include_playlists:
        included_ids = set()
        for pid in include_playlists:
            if not pid or "xxxx" in pid.lower():
                continue
            try:
                pids = list_playlist_video_ids(token, pid)
                included_ids.update(pids)
                print(f"[list]   playlist whitelist {pid} : {len(pids)} videos")
            except Exception as exc:
                print(f"[list]   ⚠ playlist {pid} inaccessible : {exc}")

    # 3) IDs depuis la playlist Uploads
    uploads_id = get_uploads_playlist_id(token, channel_id)
    all_ids = list_playlist_video_ids(token, uploads_id)
    print(f"[list] Uploads : {len(all_ids)} videos totales")

    # 4) Enrichissement + filtrage (include_playlists appliquee AVANT exclude)
    if included_ids is not None:
        candidate_ids = [vid for vid in all_ids if vid in included_ids and vid not in excluded_ids]
        print(f"[list] Apres whitelist : {len(candidate_ids)} videos")
    else:
        candidate_ids = [vid for vid in all_ids if vid not in excluded_ids]
    details = fetch_video_details(token, candidate_ids)
    details_map = {d["id"]: d for d in details}

    # Deduplication : on skippe les videos deja extraites dans un run precedent.
    processed_ids: set[str] = set()
    if not args.include_processed:
        processed_ids = already_processed_video_ids()
        if processed_ids:
            print(f"[list] Deja traitees : {len(processed_ids)} video(s) skippees "
                  f"(utilise --include-processed pour les reintegrer)")

    kept: list[dict] = []
    stats = {"not_public": 0, "too_short": 0, "too_few_views": 0, "too_old": 0,
             "title_excluded": 0, "title_not_included": 0, "no_detail": 0,
             "already_processed": 0}

    for vid in candidate_ids:
        if vid in processed_ids:
            stats["already_processed"] += 1
            continue
        d = details_map.get(vid)
        if not d:
            stats["no_detail"] += 1
            continue

        if d.get("status", {}).get("privacyStatus") != "public":
            stats["not_public"] += 1
            continue

        title = d.get("snippet", {}).get("title", "")
        published = (d.get("snippet", {}).get("publishedAt") or "")[:10]
        duration = iso8601_duration_to_seconds(d.get("contentDetails", {}).get("duration", ""))
        views = int(d.get("statistics", {}).get("viewCount", 0))

        if duration < min_duration:
            stats["too_short"] += 1
            continue
        if views < min_views:
            stats["too_few_views"] += 1
            continue
        if published and published < published_after:
            stats["too_old"] += 1
            continue
        if exclude_keywords and title_matches(title, exclude_keywords):
            stats["title_excluded"] += 1
            if args.verbose:
                print(f"[list]   - exclu (titre) : {title}")
            continue
        if include_keywords and not title_matches(title, include_keywords):
            stats["title_not_included"] += 1
            continue

        kept.append({
            "video_id": vid,
            "title": title,
            "duration_s": duration,
            "views": views,
            "published": published,
            "url": f"https://www.youtube.com/watch?v={vid}",
        })

    # Tri : les plus vues d'abord (proxy raisonnable pour "meilleur candidat")
    kept.sort(key=lambda v: v["views"], reverse=True)
    if args.limit > 0:
        kept = kept[: args.limit]

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": {
            "channel_id": channel_id,
            "min_duration_s": min_duration,
            "min_views": min_views,
            "published_after": published_after,
            "include_playlists": include_playlists,
            "exclude_playlists": exclude_playlists,
            "exclude_title_keywords": exclude_keywords,
            "include_title_keywords": include_keywords,
        },
        "stats": stats,
        "count": len(kept),
        "videos": kept,
    }

    out_path = data_dir() / "candidates.json"
    write_json(out_path, payload)

    print("")
    print(f"[list] Stats filtrage : {stats}")
    print(f"[list] {len(kept)} videos retenues")
    print(f"[list] -> {out_path}")
    if kept and args.verbose:
        print("[list] Top 5 :")
        for v in kept[:5]:
            print(f"  - {v['video_id']}  {v['views']:>6} vues  {v['duration_s']//60:>3} min  {v['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
