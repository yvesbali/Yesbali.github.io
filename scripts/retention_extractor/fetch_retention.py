#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_retention.py — Etape 2 du pipeline retention_extractor.

Lit data/retention/candidates.json, et pour chaque video recupere la courbe
de retention via YouTube Analytics API :

  GET https://youtubeanalytics.googleapis.com/v2/reports
      ?ids=channel==MINE
      &metrics=audienceWatchRatio,relativeRetentionPerformance
      &dimensions=elapsedVideoTimeRatio
      &filters=video==<VIDEO_ID>
      &startDate=YYYY-MM-DD&endDate=YYYY-MM-DD

Produit :
  data/retention/curves/<video_id>.json
  {
    "video_id", "title", "duration_s",
    "fetched_at", "start_date", "end_date",
    "rows": [[elapsedRatio, audienceWatchRatio, relativeRetentionPerformance], ...]
  }

Usage :
  python scripts/retention_extractor/fetch_retention.py
  python scripts/retention_extractor/fetch_retention.py --only <video_id>
  python scripts/retention_extractor/fetch_retention.py --force  # re-fetch meme si deja en cache
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    curves_dir,
    data_dir,
    get_access_token,
    load_config,
    read_json,
    write_json,
)

ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"


def fetch_retention_for_video(
    token: str,
    video_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Retourne le payload brut de l'API Analytics pour une video."""
    r = requests.get(
        ANALYTICS_URL,
        params={
            "ids": "channel==MINE",
            "metrics": "audienceWatchRatio,relativeRetentionPerformance",
            "dimensions": "elapsedVideoTimeRatio",
            "filters": f"video=={video_id}",
            "startDate": start_date,
            "endDate": end_date,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if r.status_code == 403:
        raise PermissionError(f"403 Forbidden pour {video_id} : {r.text[:200]}")
    if r.status_code == 400:
        raise ValueError(f"400 Bad Request pour {video_id} : {r.text[:200]}")
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="Ne traite qu'un seul video_id.")
    ap.add_argument("--force", action="store_true", help="Ignore le cache existant.")
    ap.add_argument("--sleep", type=float, default=0.3, help="Pause entre requetes (s).")
    args = ap.parse_args()

    cfg = load_config()
    start_date = cfg.get("analytics_start_date") or "2020-01-01"
    end_date = cfg.get("analytics_end_date") or date.today().isoformat()
    print(f"[fetch] Analytics range : {start_date} -> {end_date}")

    candidates_path = data_dir() / "candidates.json"
    candidates = read_json(candidates_path)
    if not candidates:
        print(f"[fetch] Introuvable : {candidates_path}. Lance d'abord list_candidates.py")
        return 1

    videos = candidates["videos"]
    if args.only:
        videos = [v for v in videos if v["video_id"] == args.only]
        if not videos:
            print(f"[fetch] {args.only} absent des candidats.")
            return 1

    token = get_access_token()
    print(f"[fetch] Token OAuth OK. {len(videos)} video(s) a traiter.")

    out_dir = curves_dir()
    ok, skipped, failed = 0, 0, 0
    failures: list[dict] = []

    for idx, v in enumerate(videos, 1):
        vid = v["video_id"]
        out_path = out_dir / f"{vid}.json"
        if out_path.exists() and not args.force:
            skipped += 1
            continue

        try:
            raw = fetch_retention_for_video(token, vid, start_date, end_date)
        except PermissionError as exc:
            # Typiquement : video trop jeune ou pas assez de vues pour Analytics
            print(f"[fetch] {idx:>3}/{len(videos)} {vid}  403 : {exc}")
            failed += 1
            failures.append({"video_id": vid, "title": v["title"], "error": str(exc)})
            time.sleep(args.sleep)
            continue
        except Exception as exc:
            print(f"[fetch] {idx:>3}/{len(videos)} {vid}  ERREUR : {exc}")
            failed += 1
            failures.append({"video_id": vid, "title": v["title"], "error": str(exc)})
            time.sleep(args.sleep)
            continue

        rows = raw.get("rows") or []
        payload = {
            "video_id": vid,
            "title": v["title"],
            "duration_s": v["duration_s"],
            "views": v.get("views", 0),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "start_date": start_date,
            "end_date": end_date,
            "column_headers": raw.get("columnHeaders", []),
            "rows": rows,
        }
        write_json(out_path, payload)
        ok += 1
        print(f"[fetch] {idx:>3}/{len(videos)} {vid}  {len(rows)} pts  {v['title'][:60]}")
        time.sleep(args.sleep)

    if failures:
        write_json(data_dir() / "fetch_failures.json", {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "count": len(failures),
            "failures": failures,
        })

    print("")
    print(f"[fetch] OK={ok}  SKIPPED(cache)={skipped}  FAILED={failed}")
    print(f"[fetch] -> {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
