#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_clips.py — Etape 4 du pipeline retention_extractor.

Lit data/retention/plan.json et telecharge chaque fenetre de clip en 4K
(ou meilleure qualite disponible) directement decoupee via yt-dlp
--download-sections. Produit un .mp4 + un sidecar .json de republication.

Qualite video :
  - format par defaut (config "yt_dlp_format") :
      bv*[height=2160]+ba / bv*[height=1440]+ba / bv*[height=1080]+ba / ... / b
    -> tente 4K d'abord, puis degrade proprement.
  - si config "require_4k" = true, on skip la video si 2160p indisponible.
  - merge en mp4 (config "yt_dlp_merge_format").
  - keyframes precises aux cuts si "force_keyframes_at_cuts".

Sortie :
  out/clips/<video_id>/<video_id>_clip01_HH-MM-SS_HH-MM-SS.mp4
  out/clips/<video_id>/<video_id>_clip01_HH-MM-SS_HH-MM-SS.republish.json
      {
        "source_video_id", "source_url", "source_title",
        "start_ts", "end_ts", "duration_s",
        "suggested_title": "Souvenir : ...",
        "suggested_description": "...",
        "suggested_tags": [...]
      }

Pre-requis :
  pip install yt-dlp
  ffmpeg dans le PATH (yt-dlp l'utilise pour le decoupage).

Usage :
  python scripts/retention_extractor/extract_clips.py
  python scripts/retention_extractor/extract_clips.py --only <video_id>
  python scripts/retention_extractor/extract_clips.py --dry
  python scripts/retention_extractor/extract_clips.py --limit 3
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    data_dir,
    fmt_ts,
    fmt_ts_filename,
    load_config,
    out_dir,
    read_json,
    write_json,
)


def check_binaries(require_yt_dlp: bool = True) -> None:
    missing = []
    if require_yt_dlp and shutil.which("yt-dlp") is None:
        # fallback : python -m yt_dlp ?
        try:
            subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--version"],
                check=True, capture_output=True,
            )
        except Exception:
            missing.append("yt-dlp (pip install yt-dlp)")
    if shutil.which("ffmpeg") is None:
        missing.append("ffmpeg (https://ffmpeg.org/download.html)")
    if missing:
        print("[extract] Binaires manquants :")
        for m in missing:
            print(f"  - {m}")
        sys.exit(2)


def yt_dlp_cmd() -> list[str]:
    """Retourne la commande yt-dlp (binaire ou python -m yt_dlp)."""
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def build_title(template: str, video_title: str, start_ts: str) -> str:
    return template.format(title=video_title, start_ts=start_ts)


def build_description(
    template: str,
    video_title: str,
    video_url: str,
    published: str,
    clip_duration_s: float,
) -> str:
    clip_minutes = f"{clip_duration_s / 60:.1f}"
    return template.format(
        title=video_title,
        url=video_url,
        published=published,
        clip_minutes=clip_minutes,
    )


def download_clip(
    source_url: str,
    start_s: float,
    end_s: float,
    output_path: Path,
    fmt: str,
    merge_fmt: str,
    force_keyframes: bool,
    dry: bool = False,
) -> bool:
    """Lance yt-dlp sur une fenetre [start_s, end_s] avec qualite demandee."""
    section = f"*{fmt_ts(start_s)}-{fmt_ts(end_s)}"
    cmd = yt_dlp_cmd() + [
        "-f", fmt,
        "--merge-output-format", merge_fmt,
        "--download-sections", section,
        "-o", str(output_path),
        "--no-playlist",
        "--no-overwrites",
        "--no-part",
        "--quiet",
        "--no-warnings",
        "--progress",
    ]
    if force_keyframes:
        cmd.append("--force-keyframes-at-cuts")
    cmd.append(source_url)

    print(f"[extract] $ {' '.join(cmd)}")
    if dry:
        return True
    result = subprocess.run(cmd)
    return result.returncode == 0


def check_available_qualities(source_url: str) -> list[int]:
    """Retourne la liste des hauteurs disponibles (pour require_4k)."""
    cmd = yt_dlp_cmd() + ["-F", "--no-playlist", "--quiet", source_url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        print(f"[extract] Impossible d'interroger yt-dlp -F : {exc}")
        return []
    heights: set[int] = set()
    for line in (res.stdout or "").splitlines():
        for token in line.split():
            if "x" in token:
                parts = token.split("x")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    heights.add(int(parts[1]))
    return sorted(heights)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="Ne traite qu'un seul video_id.")
    ap.add_argument("--limit", type=int, default=0, help="Limite le nombre de clips traites.")
    ap.add_argument("--dry", action="store_true", help="Affiche sans telecharger.")
    ap.add_argument("--skip-4k-check", action="store_true",
                    help="Ignore la verif 2160p meme si require_4k=true.")
    args = ap.parse_args()

    cfg = load_config()
    plan = read_json(data_dir() / "plan.json")
    if not plan:
        print("[extract] data/retention/plan.json absent. Lance detect_peaks.py d'abord.")
        return 1

    if not args.dry:
        check_binaries(require_yt_dlp=True)

    candidates = read_json(data_dir() / "candidates.json") or {"videos": []}
    cand_by_id = {v["video_id"]: v for v in candidates.get("videos", [])}

    fmt = cfg.get("yt_dlp_format",
                  "bv*[height=2160]+ba/bv*[height=1440]+ba/bv*[height=1080]+ba/b")
    merge_fmt = cfg.get("yt_dlp_merge_format", "mp4")
    require_4k = bool(cfg.get("require_4k", False)) and not args.skip_4k_check
    force_kf = bool(cfg.get("force_keyframes_at_cuts", True))
    title_tpl = cfg.get("republish_title_template", "Souvenir : {title}")
    desc_tpl = cfg.get("republish_description_template",
                       "Extrait : {url}\nPublication originale : {published}.")
    tags = cfg.get("republish_tags", [])

    clips = plan["clips"]
    if args.only:
        clips = [c for c in clips if c["video_id"] == args.only]
    if args.limit > 0:
        clips = clips[: args.limit]

    if not clips:
        print("[extract] Rien a extraire.")
        return 0

    base_out = out_dir(cfg)
    print(f"[extract] {len(clips)} clip(s) a traiter -> {base_out}")
    print(f"[extract] Format yt-dlp : {fmt}")
    print(f"[extract] Require 4K : {require_4k}")

    # Compteur par video pour numeroter les clips
    counters: dict[str, int] = {}
    report: list[dict] = []
    ok = skipped = failed = 0

    for clip in clips:
        vid = clip["video_id"]
        counters[vid] = counters.get(vid, 0) + 1
        n = counters[vid]
        source_url = f"https://www.youtube.com/watch?v={vid}"

        # Verif 4K si exige
        if require_4k and not args.dry:
            heights = check_available_qualities(source_url)
            if 2160 not in heights:
                print(f"[extract] {vid} : 2160p indisponible ({sorted(heights)}), skip.")
                skipped += 1
                report.append({"video_id": vid, "status": "skipped_no_4k", "heights": heights})
                continue

        start_s, end_s = float(clip["start_s"]), float(clip["end_s"])
        start_fs, end_fs = fmt_ts_filename(start_s), fmt_ts_filename(end_s)

        video_dir = base_out / vid
        video_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{vid}_clip{n:02d}_{start_fs}_{end_fs}.mp4"
        output_path = video_dir / filename

        if output_path.exists():
            print(f"[extract] {vid} clip{n:02d} deja present, skip : {output_path.name}")
            skipped += 1
            continue

        success = download_clip(
            source_url=source_url,
            start_s=start_s,
            end_s=end_s,
            output_path=output_path,
            fmt=fmt,
            merge_fmt=merge_fmt,
            force_keyframes=force_kf,
            dry=args.dry,
        )
        if not success:
            failed += 1
            report.append({"video_id": vid, "clip_index": n, "status": "yt_dlp_failed"})
            continue
        ok += 1

        # Sidecar metadata republication
        cand = cand_by_id.get(vid, {})
        sidecar = {
            "source_video_id": vid,
            "source_url": source_url,
            "source_title": clip["title"],
            "source_published": cand.get("published", ""),
            "source_views": cand.get("views", 0),
            "start_s": start_s,
            "end_s": end_s,
            "duration_s": round(end_s - start_s, 2),
            "start_ts": clip["start_ts"],
            "end_ts": clip["end_ts"],
            "score": clip.get("score"),
            "method": clip.get("method"),
            "clip_file": str(output_path.relative_to(base_out.parent)),
            "suggested_title": build_title(title_tpl, clip["title"], clip["start_ts"]),
            "suggested_description": build_description(
                desc_tpl, clip["title"], source_url,
                cand.get("published", ""), end_s - start_s,
            ),
            "suggested_tags": tags,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        sidecar_path = output_path.with_suffix(".republish.json")
        if not args.dry:
            write_json(sidecar_path, sidecar)
        print(f"[extract] OK {vid} clip{n:02d}  "
              f"{clip['start_ts']}->{clip['end_ts']}  "
              f"titre='{sidecar['suggested_title']}'")

        report.append({"video_id": vid, "clip_index": n, "status": "ok",
                       "output": str(output_path)})

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": ok, "skipped": skipped, "failed": failed,
        "items": report,
    }
    if not args.dry:
        write_json(data_dir() / "extract_report.json", summary)

    print("")
    print(f"[extract] OK={ok}  SKIPPED={skipped}  FAILED={failed}")
    return 0 if failed == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
