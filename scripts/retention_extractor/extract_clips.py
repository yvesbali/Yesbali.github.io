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
    """
    Telecharge un segment [start_s, end_s] via la strategie 2-passes (plan B) :
      1. yt-dlp telecharge la VIDEO COMPLETE dans un fichier temporaire.
      2. ffmpeg decoupe localement (rapide, fiable, bypass total du SABR
         streaming et des challenges JS de YouTube sur --download-sections).
      3. Le fichier temporaire complet est supprime.

    Pourquoi ? --download-sections passe par ffmpeg qui se connecte aux URLs
    googlevideo.com en streaming. YouTube protege ces URLs avec SABR +
    challenges JS qui peuvent bloquer silencieusement le download. En
    telechargeant la video complete en une passe, yt-dlp utilise ses clients
    optimises (android_vr, etc.) qui ne sont pas soumis a SABR.
    """
    # Dossier temporaire pour la video complete (a cote du clip final)
    full_dir = output_path.parent / ".tmp_full"
    full_dir.mkdir(parents=True, exist_ok=True)
    full_tpl = str(full_dir / f"{output_path.stem}_FULL.%(ext)s")

    # ─── ETAPE A : telechargement de la video complete ───
    dl_cmd = yt_dlp_cmd() + [
        "-f", fmt,
        "--merge-output-format", merge_fmt,
        "-o", full_tpl,
        "--no-playlist",
        "--no-overwrites",
        "--no-part",
        "--newline",
        "--progress",
        "--remote-components", "ejs:github",
    ]
    dl_cmd.append(source_url)

    print(f"[extract] $ {' '.join(dl_cmd)}")
    if dry:
        return True

    result = subprocess.run(dl_cmd)
    if result.returncode != 0:
        print(f"[extract] yt-dlp a echoue (code {result.returncode})")
        return False

    # yt-dlp a cree le fichier merge : <stem>_FULL.<merge_fmt>
    full_candidates = list(full_dir.glob(f"{output_path.stem}_FULL.*"))
    if not full_candidates:
        print(f"[extract] fichier complet introuvable dans {full_dir}")
        return False
    full_video = full_candidates[0]
    print(f"[extract] video complete : {full_video.name} "
          f"({full_video.stat().st_size / 1024 / 1024:.0f} MiB)")

    # ─── ETAPE B : decoupe locale via ffmpeg ───
    duration = end_s - start_s
    ff_cmd = [
        "ffmpeg", "-y", "-loglevel", "warning", "-stats",
        "-ss", fmt_ts(start_s),
        "-i", str(full_video),
        "-t", f"{duration:.2f}",
    ]
    if force_keyframes:
        # Re-encode pour couper precisement aux timestamps demandes.
        ff_cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                   "-c:a", "aac", "-b:a", "192k"]
    else:
        # Stream copy : 100x plus rapide mais coupe sur keyframes proches.
        ff_cmd += ["-c", "copy"]
    ff_cmd += ["-movflags", "+faststart", str(output_path)]

    print(f"[extract] $ {' '.join(ff_cmd)}")
    result = subprocess.run(ff_cmd)
    if result.returncode != 0:
        print(f"[extract] ffmpeg decoupe a echoue (code {result.returncode})")
        return False

    # ─── ETAPE C : nettoyage (avec retry car Windows peut verrouiller le handle) ───
    for attempt in range(3):
        try:
            if full_video.exists():
                full_video.unlink()
            if full_dir.exists() and not any(full_dir.iterdir()):
                full_dir.rmdir()
            break
        except OSError as exc:
            if attempt < 2:
                import time
                time.sleep(1.5)
                continue
            print(f"[extract] avertissement nettoyage : {exc}")
            print(f"[extract]   -> supprime manuellement : {full_dir}")

    return output_path.exists()


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
