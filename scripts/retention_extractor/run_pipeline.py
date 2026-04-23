#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py — Orchestrateur du pipeline retention_extractor.

Enchaine les 4 etapes :
  1. list_candidates  (youtube Data API)
  2. fetch_retention  (youtube Analytics API)
  3. detect_peaks     (analyse locale)
  4. extract_clips    (yt-dlp + ffmpeg, 4K si dispo)

Chaque etape est idempotente : on peut relancer sans casser les etapes precedentes.
Les etapes peuvent etre sautees via --skip-*.

Usage :
  python scripts/retention_extractor/run_pipeline.py
  python scripts/retention_extractor/run_pipeline.py --dry           # jusqu'a extract sans telecharger
  python scripts/retention_extractor/run_pipeline.py --only <video_id>
  python scripts/retention_extractor/run_pipeline.py --limit 5
  python scripts/retention_extractor/run_pipeline.py --skip-extract  # plan sans telechargement
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(args: list[str]) -> int:
    print(f"\n$ {' '.join(args)}")
    result = subprocess.run(args)
    return result.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="Traite un seul video_id (propage aux etapes).")
    ap.add_argument("--limit", type=int, default=0,
                    help="Limite le nombre de candidats (etape 1) et de clips (etape 4).")
    ap.add_argument("--dry", action="store_true",
                    help="Passe --dry a extract_clips (ne telecharge rien).")
    ap.add_argument("--force-fetch", action="store_true",
                    help="Passe --force a fetch_retention (ignore le cache).")
    ap.add_argument("--debug-peaks", action="store_true",
                    help="Passe --debug a detect_peaks.")
    ap.add_argument("--skip-list", action="store_true")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--skip-detect", action="store_true")
    ap.add_argument("--skip-extract", action="store_true")
    args = ap.parse_args()

    py = sys.executable

    # Etape 1 : candidates
    if not args.skip_list:
        cmd = [py, str(HERE / "list_candidates.py")]
        if args.limit > 0:
            cmd += ["--limit", str(args.limit)]
        if run(cmd) != 0:
            print("[pipeline] Echec list_candidates.")
            return 1

    # Etape 2 : fetch retention
    if not args.skip_fetch:
        cmd = [py, str(HERE / "fetch_retention.py")]
        if args.only:
            cmd += ["--only", args.only]
        if args.force_fetch:
            cmd += ["--force"]
        if run(cmd) != 0:
            print("[pipeline] Echec fetch_retention.")
            return 2

    # Etape 3 : detect peaks
    if not args.skip_detect:
        cmd = [py, str(HERE / "detect_peaks.py")]
        if args.only:
            cmd += ["--only", args.only]
        if args.debug_peaks:
            cmd += ["--debug"]
        if run(cmd) != 0:
            print("[pipeline] Echec detect_peaks.")
            return 3

    # Etape 4 : extract
    if not args.skip_extract:
        cmd = [py, str(HERE / "extract_clips.py")]
        if args.only:
            cmd += ["--only", args.only]
        if args.limit > 0:
            cmd += ["--limit", str(args.limit)]
        if args.dry:
            cmd += ["--dry"]
        if run(cmd) != 0:
            print("[pipeline] Echec extract_clips.")
            return 4

    print("\n[pipeline] Termine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
