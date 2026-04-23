#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
detect_peaks.py — Etape 3 du pipeline retention_extractor.

Transforme chaque courbe data/retention/curves/<video_id>.json en un ou
plusieurs "plans de clip" stockes dans data/retention/peaks/<video_id>.json.

Algorithme (pure Python, pas de scipy) :
  1. Lire la colonne audienceWatchRatio (et relativeRetentionPerformance si dispo).
  2. Lisser la courbe (moving average, fenetre = smoothing_window).
  3. Baseline = mediane de la courbe lissee.
  4. Detecter les "zones de haute retention" = runs consecutifs ou
     audienceWatchRatio > baseline * peak_threshold_ratio.
  5. Rejeter les zones dont la largeur < min_zone_duration_ratio * total points.
  6. Pour chaque zone restante : calculer start/end en secondes sur la video,
     puis ajouter pad_seconds_before / pad_seconds_after.
  7. Clamper sur [0, duration_s] puis contraindre la duree finale dans
     [min_clip_duration_s, max_clip_duration_s] :
        - si trop court : etendre autour du centre de masse du pic.
        - si trop long  : recentrer sur le centre de masse et couper.
  8. Fusionner les fenetres qui se chevauchent (ou proches de
     min_gap_between_clips_s).
  9. Tri par score (aire sous la courbe au-dessus de la baseline) descendant,
     garder au max max_clips_per_video.
 10. Fallback : si aucune zone detectee, prendre la fenetre glissante de
     min_clip_duration_s avec la moyenne de audienceWatchRatio la plus elevee.

Sortie :
  data/retention/peaks/<video_id>.json
  {
    "video_id", "title", "duration_s",
    "baseline", "method", "clips": [
      {"start_s", "end_s", "duration_s", "score", "peak_center_s"},
      ...
    ]
  }

Le fichier global data/retention/plan.json agrege tous les clips de toutes
les videos, pret pour l'etape extract_clips.py.

Usage :
  python scripts/retention_extractor/detect_peaks.py
  python scripts/retention_extractor/detect_peaks.py --only <video_id> --debug
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    curves_dir,
    data_dir,
    fmt_ts,
    load_config,
    peaks_dir,
    read_json,
    write_json,
)


def moving_average(values: list[float], window: int) -> list[float]:
    if window <= 1 or len(values) < window:
        return list(values)
    half = window // 2
    out: list[float] = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def find_high_zones(
    smoothed: list[float],
    baseline: float,
    threshold_ratio: float,
    min_width: int,
) -> list[tuple[int, int]]:
    """Retourne la liste (start_idx, end_idx_inclus) des zones > baseline*ratio."""
    threshold = baseline * threshold_ratio
    zones: list[tuple[int, int]] = []
    in_zone = False
    zone_start = 0
    for i, v in enumerate(smoothed):
        if v > threshold:
            if not in_zone:
                in_zone = True
                zone_start = i
        else:
            if in_zone:
                end = i - 1
                if end - zone_start + 1 >= min_width:
                    zones.append((zone_start, end))
                in_zone = False
    if in_zone:
        end = len(smoothed) - 1
        if end - zone_start + 1 >= min_width:
            zones.append((zone_start, end))
    return zones


def zone_score(
    smoothed: list[float], baseline: float, zone: tuple[int, int]
) -> float:
    """Aire (somme) au-dessus de la baseline sur la zone."""
    s, e = zone
    return sum(max(0.0, smoothed[i] - baseline) for i in range(s, e + 1))


def zone_center_of_mass(
    smoothed: list[float], zone: tuple[int, int]
) -> float:
    """Indice (float) du centre de masse pondere par les valeurs."""
    s, e = zone
    num = 0.0
    den = 0.0
    for i in range(s, e + 1):
        num += i * smoothed[i]
        den += smoothed[i]
    return (num / den) if den > 0 else (s + e) / 2


def build_clip_window(
    zone: tuple[int, int],
    smoothed: list[float],
    num_points: int,
    duration_s: float,
    pad_before_s: float,
    pad_after_s: float,
    min_clip_s: float,
    max_clip_s: float,
) -> tuple[float, float, float]:
    """Retourne (start_s, end_s, peak_center_s) pour la fenetre d'extraction."""
    zs, ze = zone
    step_s = duration_s / max(1, num_points)

    zone_start_s = zs * step_s
    zone_end_s = (ze + 1) * step_s
    center_s = zone_center_of_mass(smoothed, zone) * step_s

    start_s = max(0.0, zone_start_s - pad_before_s)
    end_s = min(duration_s, zone_end_s + pad_after_s)

    length = end_s - start_s
    if length < min_clip_s:
        extra = (min_clip_s - length) / 2
        start_s = max(0.0, start_s - extra)
        end_s = min(duration_s, end_s + extra)
        # ajuster si on bute sur une borne
        if end_s - start_s < min_clip_s:
            if start_s == 0.0:
                end_s = min(duration_s, start_s + min_clip_s)
            else:
                start_s = max(0.0, end_s - min_clip_s)

    length = end_s - start_s
    if length > max_clip_s:
        half = max_clip_s / 2
        start_s = max(0.0, center_s - half)
        end_s = min(duration_s, start_s + max_clip_s)
        start_s = max(0.0, end_s - max_clip_s)

    return start_s, end_s, center_s


def merge_overlapping(
    clips: list[dict], min_gap_s: float
) -> list[dict]:
    """Fusionne les clips qui se chevauchent ou sont separes de moins de min_gap_s."""
    if not clips:
        return clips
    clips = sorted(clips, key=lambda c: c["start_s"])
    merged: list[dict] = [dict(clips[0])]
    for c in clips[1:]:
        last = merged[-1]
        if c["start_s"] - last["end_s"] < min_gap_s:
            last["end_s"] = max(last["end_s"], c["end_s"])
            last["duration_s"] = last["end_s"] - last["start_s"]
            last["score"] = last.get("score", 0.0) + c.get("score", 0.0)
            last["peak_center_s"] = (last["peak_center_s"] + c["peak_center_s"]) / 2
        else:
            merged.append(dict(c))
    return merged


def fallback_best_window(
    raw_values: list[float],
    num_points: int,
    duration_s: float,
    min_clip_s: float,
) -> tuple[float, float, float, float]:
    """Fenetre glissante de largeur min_clip_s qui maximise la moyenne de retention."""
    step_s = duration_s / max(1, num_points)
    window_pts = max(1, int(round(min_clip_s / step_s)))
    best_avg = -1.0
    best_idx = 0
    rolling = sum(raw_values[:window_pts])
    best_avg = rolling / window_pts
    for i in range(1, num_points - window_pts + 1):
        rolling += raw_values[i + window_pts - 1] - raw_values[i - 1]
        avg = rolling / window_pts
        if avg > best_avg:
            best_avg = avg
            best_idx = i
    start_s = best_idx * step_s
    end_s = min(duration_s, start_s + min_clip_s)
    center_s = (start_s + end_s) / 2
    return start_s, end_s, center_s, best_avg


def process_curve(curve: dict, cfg: dict, debug: bool = False) -> dict:
    """Traite une courbe -> structure {baseline, method, clips}."""
    rows = curve.get("rows") or []
    duration_s = float(curve.get("duration_s") or 0)
    title = curve.get("title", "")
    video_id = curve["video_id"]

    # La colonne 0 est elapsedVideoTimeRatio. Les metriques suivent.
    headers = [h.get("name") for h in curve.get("column_headers", [])]
    try:
        awr_col = headers.index("audienceWatchRatio")
    except ValueError:
        awr_col = 1  # fallback : 2e colonne

    raw = []
    for row in rows:
        try:
            raw.append(float(row[awr_col]))
        except (IndexError, TypeError, ValueError):
            raw.append(0.0)

    result: dict[str, Any] = {
        "video_id": video_id,
        "title": title,
        "duration_s": duration_s,
        "points": len(raw),
        "baseline": 0.0,
        "method": "none",
        "clips": [],
    }

    if not raw or duration_s <= 0:
        result["method"] = "empty"
        return result

    smoothing = int(cfg.get("smoothing_window", 3))
    threshold_ratio = float(cfg.get("peak_threshold_ratio", 1.05))
    min_zone_ratio = float(cfg.get("min_zone_duration_ratio", 0.03))
    pad_before = float(cfg.get("pad_seconds_before", 60))
    pad_after = float(cfg.get("pad_seconds_after", 60))
    min_clip = float(cfg.get("min_clip_duration_s", 180))
    max_clip = float(cfg.get("max_clip_duration_s", 360))
    max_clips = int(cfg.get("max_clips_per_video", 2))
    min_gap = float(cfg.get("min_gap_between_clips_s", 30))

    smoothed = moving_average(raw, smoothing)
    baseline = statistics.median(smoothed)
    result["baseline"] = round(baseline, 4)

    min_width = max(1, int(round(min_zone_ratio * len(smoothed))))
    zones = find_high_zones(smoothed, baseline, threshold_ratio, min_width)
    if debug:
        print(f"[detect][{video_id}] points={len(raw)} baseline={baseline:.3f} "
              f"min_width={min_width} -> {len(zones)} zone(s)")

    clips: list[dict] = []
    if zones:
        result["method"] = "peak_zones"
        for z in zones:
            start_s, end_s, center_s = build_clip_window(
                z, smoothed, len(smoothed), duration_s,
                pad_before, pad_after, min_clip, max_clip,
            )
            clips.append({
                "start_s": round(start_s, 2),
                "end_s": round(end_s, 2),
                "duration_s": round(end_s - start_s, 2),
                "peak_center_s": round(center_s, 2),
                "score": round(zone_score(smoothed, baseline, z), 4),
                "start_ts": fmt_ts(start_s),
                "end_ts": fmt_ts(end_s),
            })
        clips = merge_overlapping(clips, min_gap)
        clips.sort(key=lambda c: c["score"], reverse=True)
        clips = clips[:max_clips]
    else:
        result["method"] = "fallback_best_window"
        start_s, end_s, center_s, avg = fallback_best_window(
            raw, len(raw), duration_s, min_clip,
        )
        clips.append({
            "start_s": round(start_s, 2),
            "end_s": round(end_s, 2),
            "duration_s": round(end_s - start_s, 2),
            "peak_center_s": round(center_s, 2),
            "score": round(avg, 4),
            "start_ts": fmt_ts(start_s),
            "end_ts": fmt_ts(end_s),
        })

    # Tri final par ordre chronologique pour lisibilite du plan
    clips.sort(key=lambda c: c["start_s"])
    result["clips"] = clips
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="Ne traite qu'un seul video_id.")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    curves = sorted(curves_dir().glob("*.json"))
    if args.only:
        curves = [p for p in curves if p.stem == args.only]

    if not curves:
        print(f"[detect] Aucune courbe dans {curves_dir()}. Lance fetch_retention.py d'abord.")
        return 1

    plan: list[dict] = []
    out_dir = peaks_dir()
    for path in curves:
        curve = read_json(path)
        if not curve:
            continue
        result = process_curve(curve, cfg, debug=args.debug)
        write_json(out_dir / path.name, result)

        for c in result["clips"]:
            plan.append({
                "video_id": result["video_id"],
                "title": result["title"],
                "duration_s": result["duration_s"],
                "clip_index": len([p for p in plan if p["video_id"] == result["video_id"]]),
                "start_s": c["start_s"],
                "end_s": c["end_s"],
                "duration_clip_s": c["duration_s"],
                "start_ts": c["start_ts"],
                "end_ts": c["end_ts"],
                "score": c["score"],
                "method": result["method"],
            })
        print(f"[detect] {result['video_id']}  {result['method']:<20}  {len(result['clips'])} clip(s)")

    plan.sort(key=lambda c: c["score"], reverse=True)
    plan_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {k: cfg[k] for k in sorted(cfg) if not k.startswith("_")},
        "clip_count": len(plan),
        "clips": plan,
    }
    write_json(data_dir() / "plan.json", plan_payload)

    print("")
    print(f"[detect] {len(plan)} clips planifies sur {len(curves)} videos")
    print(f"[detect] -> {data_dir() / 'plan.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
