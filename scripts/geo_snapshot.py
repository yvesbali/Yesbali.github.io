#!/usr/bin/env python3
"""
LCDMH — Snapshot GEO périodique + diff vs baseline T0
=====================================================
Compare un snapshot T+N (T7, T14, T30, T60, T90) contre la baseline T0 et
produit :
  - un fichier baseline_T<N>_<date>.json (même format que la baseline)
  - un fichier diff_T0_vs_T<N>_<date>.json avec les deltas (Δ)

Sources lues :
  - data/baselines/baseline_T0_*.json   : baseline figée (la plus récente)
  - data/baselines/gsc_queries_*.csv    : nouvel export GSC
  - seo_stats.json                      : stats YouTube à jour

Sortie :
  - data/baselines/baseline_T<N>_<date>.json
  - data/baselines/diff_T0_vs_T<N>_<date>.json

Usage :
    python scripts/geo_snapshot.py --label T7
    python scripts/geo_snapshot.py --label T30 --gsc data/baselines/gsc_queries_2026-05-21.csv
    python scripts/geo_snapshot.py --label T14 --baseline data/baselines/baseline_T0_2026-04-21.json
"""

import argparse, csv, json, os, sys
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# On réutilise les fonctions de geo_baseline.py pour garantir une logique identique
sys.path.insert(0, str(BASE / "scripts"))
from geo_baseline import (
    read_seo_stats, read_gsc_csv, gsc_kpis, yt_kpis,
    load_targets, enrich_targets,
)


def find_latest_baseline(base_dir: Path, label: str = "T0") -> Path | None:
    """Retourne le fichier baseline_<label>_*.json le plus récent."""
    candidates = sorted(base_dir.glob(f"baseline_{label}_*.json"))
    return candidates[-1] if candidates else None


def diff_scalar(a, b):
    """Retourne la différence b-a ; None si une des deux valeurs est None."""
    if a is None or b is None:
        return None
    try:
        return round(b - a, 2)
    except Exception:
        return None


def diff_pct(a, b):
    """Retourne l'évolution relative en % ((b-a)/a * 100). None si a=0 ou None."""
    if a is None or b is None or a == 0:
        return None
    try:
        return round((b - a) / a * 100, 1)
    except Exception:
        return None


def diff_gsc_kpis(k0, k1):
    """Diff entre deux dicts de KPI GSC."""
    if not k0 or not k1:
        return None
    keys = ["total_queries", "total_clicks", "total_impressions",
            "avg_ctr_pct", "queries_in_top3", "queries_in_top10", "queries_in_top20"]
    out = {}
    for k in keys:
        a, b = k0.get(k), k1.get(k)
        out[k] = {"T0": a, "current": b, "delta": diff_scalar(a, b), "delta_pct": diff_pct(a, b)}
    return out


def diff_gsc_queries(q0, q1):
    """Diff query-par-query : nouveaux, disparus, position/clics/impressions."""
    by_q0 = {q["query"]: q for q in q0}
    by_q1 = {q["query"]: q for q in q1}

    queries_T0 = set(by_q0.keys())
    queries_T1 = set(by_q1.keys())

    new_queries    = sorted(queries_T1 - queries_T0)
    lost_queries   = sorted(queries_T0 - queries_T1)
    common         = queries_T0 & queries_T1

    movers = []
    for q in common:
        a, b = by_q0[q], by_q1[q]
        d_pos    = diff_scalar(a["position"], b["position"])      # positif = on recule
        d_clicks = diff_scalar(a["clicks"], b["clicks"])
        d_impr   = diff_scalar(a["impressions"], b["impressions"])
        movers.append({
            "query":          q,
            "pos_T0":         a["position"],
            "pos_current":    b["position"],
            "delta_pos":      d_pos,          # négatif = on gagne (ex. 20 → 8 donne -12)
            "clicks_T0":      a["clicks"],
            "clicks_current": b["clicks"],
            "delta_clicks":   d_clicks,
            "impr_T0":        a["impressions"],
            "impr_current":   b["impressions"],
            "delta_impr":     d_impr,
        })

    # Top movers positifs (position qui baisse = on monte dans Google)
    top_winners = sorted([m for m in movers if m["delta_pos"] is not None and m["delta_pos"] < 0],
                         key=lambda m: m["delta_pos"])[:20]
    top_losers  = sorted([m for m in movers if m["delta_pos"] is not None and m["delta_pos"] > 0],
                         key=lambda m: -m["delta_pos"])[:20]

    return {
        "counts": {
            "queries_T0":       len(queries_T0),
            "queries_current":  len(queries_T1),
            "new_queries":      len(new_queries),
            "lost_queries":     len(lost_queries),
            "common_queries":   len(common),
        },
        "new_queries":   new_queries,
        "lost_queries":  lost_queries,
        "top_winners":   top_winners,
        "top_losers":    top_losers,
    }


def diff_yt_kpis(k0, k1):
    if not k0 or not k1:
        return None
    keys = ["videos_total", "videos_with_data", "sum_views_30d",
            "sum_impressions", "avg_ctr_weighted", "avg_view_pct_mean"]
    out = {}
    for k in keys:
        a, b = k0.get(k), k1.get(k)
        out[k] = {"T0": a, "current": b, "delta": diff_scalar(a, b), "delta_pct": diff_pct(a, b)}
    return out


def diff_yt_videos(v0_list, v1_list):
    """Diff YouTube vidéo-par-vidéo."""
    by0 = {v["video_id"]: v for v in v0_list}
    by1 = {v["video_id"]: v for v in v1_list}
    common = set(by0) & set(by1)
    rows = []
    for vid in common:
        a, b = by0[vid], by1[vid]
        rows.append({
            "video_id":              vid,
            "views_30d_T0":          a["views_30d"],
            "views_30d_current":     b["views_30d"],
            "delta_views":           diff_scalar(a["views_30d"], b["views_30d"]),
            "delta_views_pct":       diff_pct(a["views_30d"], b["views_30d"]),
            "ctr_T0":                a["ctr_pct"],
            "ctr_current":           b["ctr_pct"],
            "delta_ctr":             diff_scalar(a["ctr_pct"], b["ctr_pct"]),
            "yt_search_T0":          a["yt_search_pct"],
            "yt_search_current":     b["yt_search_pct"],
            "delta_yt_search":       diff_scalar(a["yt_search_pct"], b["yt_search_pct"]),
            "avg_view_pct_T0":       a["avg_view_pct"],
            "avg_view_pct_current":  b["avg_view_pct"],
            "delta_avg_view_pct":    diff_scalar(a["avg_view_pct"], b["avg_view_pct"]),
        })
    # Sort by delta_views desc (biggest winners first)
    rows.sort(key=lambda r: (r["delta_views"] or 0), reverse=True)
    return rows


def diff_batch_targets(t0, t1):
    """Diff ciblé sur les vidéos du batch (lecture rapide du ROI du cycle)."""
    if not t0 or not t1:
        return None
    by0 = {v["video_id"]: v for v in t0.get("videos", [])}
    by1 = {v["video_id"]: v for v in t1.get("videos", [])}
    out = []
    for vid, v1 in by1.items():
        v0 = by0.get(vid, {})
        s0 = v0.get("_stats_T0") or {}
        s1 = v1.get("_stats_T0") or {}   # dans le nouveau snapshot c'est aussi "_stats_T0" (snapshot courant)
        out.append({
            "video_id":             vid,
            "title":                v1.get("title"),
            "cluster":              v1.get("cluster"),
            "views_30d_T0":         s0.get("views_30d"),
            "views_30d_current":    s1.get("views_30d"),
            "delta_views":          diff_scalar(s0.get("views_30d"), s1.get("views_30d")),
            "delta_views_pct":      diff_pct(s0.get("views_30d"), s1.get("views_30d")),
            "ctr_T0":               s0.get("ctr_pct"),
            "ctr_current":          s1.get("ctr_pct"),
            "delta_ctr":            diff_scalar(s0.get("ctr_pct"), s1.get("ctr_pct")),
            "yt_search_T0":         s0.get("yt_search_pct"),
            "yt_search_current":    s1.get("yt_search_pct"),
            "delta_yt_search":      diff_scalar(s0.get("yt_search_pct"), s1.get("yt_search_pct")),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label",    required=True, help="Label du snapshot (T7, T14, T30, T60, T90)")
    ap.add_argument("--baseline", default=None, help="Chemin baseline T0 (auto si omis)")
    ap.add_argument("--gsc",      default=None, help="Chemin GSC CSV du jour (auto si omis)")
    ap.add_argument("--seo",      default=str(BASE / "seo_stats.json"))
    ap.add_argument("--targets",  default=str(BASE / "data/baselines/targets_batch_01.json"))
    ap.add_argument("--out-dir",  default=str(BASE / "data/baselines"))
    args = ap.parse_args()

    today = date.today().isoformat()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Baseline T0
    if not args.baseline:
        auto = find_latest_baseline(out_dir, "T0")
        if not auto:
            print("❌ Aucune baseline T0 trouvée dans data/baselines/. Lance d'abord geo_baseline.py.")
            sys.exit(1)
        args.baseline = str(auto)
        print(f"ℹ️  Baseline T0 auto-sélectionnée : {args.baseline}")
    baseline_T0 = json.load(open(args.baseline, encoding="utf-8"))

    # 2. GSC courant
    if not args.gsc:
        candidates = sorted((BASE / "data/baselines").glob("gsc_queries_*.csv"))
        # On prend le plus récent différent de celui de T0
        t0_src = baseline_T0.get("source_files", {}).get("gsc")
        t0_path = (BASE / t0_src).resolve() if t0_src else None
        for c in reversed(candidates):
            if t0_path is None or c.resolve() != t0_path:
                args.gsc = str(c)
                break
        if args.gsc:
            print(f"ℹ️  GSC courant auto-sélectionné : {args.gsc}")
    if not args.gsc or not Path(args.gsc).exists():
        print("⚠️  Aucun GSC courant différent de T0. Mets à jour data/baselines/gsc_queries_<date>.csv.")
        args.gsc = None

    # 3. Construire le snapshot courant (même format que baseline)
    vids = read_seo_stats(args.seo)
    gsc  = read_gsc_csv(args.gsc) if args.gsc else []
    vids_by_id = {v["video_id"]: v for v in vids}
    targets = load_targets(Path(args.targets))
    targets = enrich_targets(targets, vids_by_id)

    snapshot = {
        "schema_version": 1,
        "label":          args.label,
        "generated_at":   datetime.now().isoformat(timespec="seconds"),
        "source_files": {
            "seo_stats": os.path.relpath(args.seo, BASE),
            "gsc":       os.path.relpath(args.gsc, BASE) if args.gsc else None,
            "targets":   os.path.relpath(args.targets, BASE),
        },
        "site_gsc": {
            "kpis":    gsc_kpis(gsc) if gsc else None,
            "queries": gsc,
        },
        "youtube": {
            "kpis":   yt_kpis(vids),
            "videos": vids,
        },
        "batch_targets": targets,
    }
    out_snap = out_dir / f"baseline_{args.label}_{today}.json"
    out_snap.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Snapshot {args.label} écrit : {out_snap}")

    # 4. Diff T0 vs courant
    diff = {
        "schema_version":   1,
        "T0_label":         baseline_T0.get("label", "T0"),
        "current_label":    args.label,
        "T0_generated_at":  baseline_T0.get("generated_at"),
        "current_generated_at": snapshot["generated_at"],
        "T0_source_gsc":    baseline_T0.get("source_files", {}).get("gsc"),
        "current_source_gsc": snapshot["source_files"]["gsc"],

        "site_gsc": {
            "kpis":    diff_gsc_kpis(baseline_T0["site_gsc"].get("kpis"),
                                     snapshot["site_gsc"].get("kpis")),
            "queries": diff_gsc_queries(baseline_T0["site_gsc"].get("queries") or [],
                                        snapshot["site_gsc"].get("queries") or []),
        },
        "youtube": {
            "kpis":   diff_yt_kpis(baseline_T0["youtube"].get("kpis"),
                                   snapshot["youtube"].get("kpis")),
            "videos": diff_yt_videos(baseline_T0["youtube"].get("videos") or [],
                                     snapshot["youtube"].get("videos") or []),
        },
        "batch_targets": diff_batch_targets(baseline_T0.get("batch_targets"),
                                            snapshot.get("batch_targets")),
    }
    out_diff = out_dir / f"diff_T0_vs_{args.label}_{today}.json"
    out_diff.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Diff T0 vs {args.label} écrit : {out_diff}")

    # 5. Résumé console
    print(f"\n=== RÉSUMÉ DIFF T0 → {args.label} ===")
    k = diff["site_gsc"]["kpis"]
    if k:
        print(f"  Site  : impressions {k['total_impressions']['T0']} → {k['total_impressions']['current']} "
              f"(Δ {k['total_impressions']['delta']}, {k['total_impressions']['delta_pct']}%)")
        print(f"          clics {k['total_clicks']['T0']} → {k['total_clicks']['current']} "
              f"(Δ {k['total_clicks']['delta']}, {k['total_clicks']['delta_pct']}%)")
        print(f"          top10 {k['queries_in_top10']['T0']} → {k['queries_in_top10']['current']} "
              f"(Δ {k['queries_in_top10']['delta']})")
    c = diff["site_gsc"]["queries"]["counts"]
    print(f"  Queries: {c['new_queries']} nouvelles, {c['lost_queries']} perdues, "
          f"{c['common_queries']} communes")
    if diff["site_gsc"]["queries"]["top_winners"]:
        print(f"\n  TOP 5 GAINS position (négatif = on monte) :")
        for m in diff["site_gsc"]["queries"]["top_winners"][:5]:
            print(f"    • {m['query']!r} : pos {m['pos_T0']} → {m['pos_current']} (Δ {m['delta_pos']})")
    if diff["site_gsc"]["queries"]["top_losers"]:
        print(f"\n  TOP 5 PERTES position :")
        for m in diff["site_gsc"]["queries"]["top_losers"][:5]:
            print(f"    • {m['query']!r} : pos {m['pos_T0']} → {m['pos_current']} (Δ {m['delta_pos']})")

    yk = diff["youtube"]["kpis"]
    if yk:
        print(f"\n  YT    : vues 30j {yk['sum_views_30d']['T0']} → {yk['sum_views_30d']['current']} "
              f"(Δ {yk['sum_views_30d']['delta']}, {yk['sum_views_30d']['delta_pct']}%)")

    # Batch ROI
    if diff["batch_targets"]:
        print(f"\n  BATCH : ROI par vidéo (batch courant) :")
        for v in diff["batch_targets"]:
            delta_v = v.get("delta_views")
            delta_s = v.get("delta_yt_search")
            print(f"    • {v['video_id']} — {v['title'][:60]}…")
            print(f"        vues 30j: {v['views_30d_T0']} → {v['views_30d_current']} (Δ {delta_v})  "
                  f"YT_SEARCH%: {v['yt_search_T0']} → {v['yt_search_current']} (Δ {delta_s})")


if __name__ == "__main__":
    main()
