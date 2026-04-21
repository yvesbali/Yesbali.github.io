#!/usr/bin/env python3
"""
LCDMH — Generator de baseline GEO (état T0 avant modifs)
=========================================================
Produit un snapshot figé des indicateurs GEO à un instant T, depuis les
fichiers locaux du repo. Le fichier généré est immuable et sert de référence
pour tous les diffs ultérieurs (T+7, T+14, T+30, T+60, T+90).

Sources lues :
  - seo_stats.json              : stats YouTube par vidéo (47 vidéos)
  - data/baselines/gsc_queries_<date>.csv : export GSC (requête, clics, impr, CTR, position)
  - data/baselines/targets_batch_01.json  : batch des vidéos ciblées ce cycle

Sortie :
  - data/baselines/baseline_T<label>_<date>.json

Usage :
    python scripts/geo_baseline.py                     # baseline T0 avec la date du jour
    python scripts/geo_baseline.py --label T0
    python scripts/geo_baseline.py --label T7 --gsc data/baselines/gsc_queries_2026-04-28.csv
"""

import argparse, csv, json, os, sys
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

def read_seo_stats(path):
    """Retourne une liste de dicts par vidéo avec le snapshot le plus récent non nul."""
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"⚠️  Impossible de lire {path} : {e}")
        return []
    out = []
    for vid, data in d.items():
        snaps = data.get("snapshots", [])
        best = None
        for s in snaps:
            if s.get("views_30d", 0) > 0 or s.get("impressions", 0) > 0:
                if best is None or s.get("taken_at", "") > best.get("taken_at", ""):
                    best = s
        if best is None and snaps:
            best = snaps[-1]
        src = (best or {}).get("sources", {}) or {}
        out.append({
            "video_id":        vid,
            "views_30d":       (best or {}).get("views_30d", 0),
            "impressions":     (best or {}).get("impressions", 0),
            "ctr_pct":         round((best or {}).get("ctr", 0), 2),
            "avg_view_pct":    round((best or {}).get("avg_view_pct", 0), 1),
            "avg_dur_s":       round((best or {}).get("avg_dur_s", 0)),
            "yt_search_pct":   round(src.get("YT_SEARCH", {}).get("pct", 0), 1),
            "related_video_pct": round(src.get("RELATED_VIDEO", {}).get("pct", 0), 1),
            "subscriber_pct":  round(src.get("SUBSCRIBER", {}).get("pct", 0), 1),
            "taken_at":        (best or {}).get("taken_at", ""),
        })
    return out

def read_gsc_csv(path):
    """Lit l'export GSC en CSV (colonnes: query,clicks,impressions,position)."""
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except Exception as e:
        print(f"⚠️  Impossible de lire {path} : {e}")
        return []
    out = []
    for r in rows:
        try:
            out.append({
                "query":       r["query"],
                "clicks":      int(r.get("clicks", 0) or 0),
                "impressions": int(r.get("impressions", 0) or 0),
                "position":    round(float(r.get("position", 0) or 0), 1),
            })
        except Exception:
            continue
    return out

def gsc_kpis(gsc):
    tot_clicks = sum(q["clicks"] for q in gsc)
    tot_impr   = sum(q["impressions"] for q in gsc)
    ctr        = round((tot_clicks / tot_impr * 100), 2) if tot_impr else 0
    top3       = sum(1 for q in gsc if q["position"] > 0 and q["position"] <= 3)
    top10      = sum(1 for q in gsc if q["position"] > 0 and q["position"] <= 10)
    top20      = sum(1 for q in gsc if q["position"] > 0 and q["position"] <= 20)
    return {
        "total_queries":       len(gsc),
        "total_clicks":        tot_clicks,
        "total_impressions":   tot_impr,
        "avg_ctr_pct":         ctr,
        "queries_in_top3":     top3,
        "queries_in_top10":    top10,
        "queries_in_top20":    top20,
    }

def yt_kpis(vids):
    non_null = [v for v in vids if v["views_30d"] > 0 or v["impressions"] > 0]
    sum_views = sum(v["views_30d"] for v in vids)
    sum_impr  = sum(v["impressions"] for v in vids)
    # CTR pondéré par impressions (et non moyenne simple)
    ctr_w = round((sum(v["ctr_pct"] * v["impressions"] for v in vids) / sum_impr), 2) if sum_impr else 0
    avg_vp = round(sum(v["avg_view_pct"] for v in non_null) / len(non_null), 1) if non_null else 0
    return {
        "videos_total":        len(vids),
        "videos_with_data":    len(non_null),
        "sum_views_30d":       sum_views,
        "sum_impressions":     sum_impr,
        "avg_ctr_weighted":    ctr_w,
        "avg_view_pct_mean":   avg_vp,
    }

def load_targets(path):
    if not path.exists():
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"⚠️  Impossible de lire {path} : {e}")
        return None

def enrich_targets(targets, vids_by_id):
    """Injecte les stats T0 dans chaque vidéo target."""
    if not targets:
        return None
    for v in targets.get("videos", []):
        vid = v["video_id"]
        stats = vids_by_id.get(vid)
        if stats:
            v["_stats_T0"] = {k: stats[k] for k in ("views_30d", "impressions", "ctr_pct",
                               "avg_view_pct", "avg_dur_s", "yt_search_pct", "taken_at")}
        else:
            v["_stats_T0"] = None  # non trackée, à ajouter via fetch_youtube
    return targets

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="T0", help="Label du snapshot (T0, T7, T14, T30...)")
    ap.add_argument("--gsc",   default=None, help="Chemin vers le CSV GSC à utiliser")
    ap.add_argument("--seo",   default=str(BASE / "seo_stats.json"))
    ap.add_argument("--targets", default=str(BASE / "data/baselines/targets_batch_01.json"))
    ap.add_argument("--out-dir", default=str(BASE / "data/baselines"))
    args = ap.parse_args()

    today = date.today().isoformat()
    # GSC par défaut = le plus récent du dossier baselines
    if not args.gsc:
        candidates = sorted(Path(BASE / "data/baselines").glob("gsc_queries_*.csv"))
        if candidates:
            args.gsc = str(candidates[-1])
            print(f"ℹ️  GSC auto-sélectionné : {args.gsc}")
    if not args.gsc or not Path(args.gsc).exists():
        print("⚠️  Aucun fichier GSC trouvé. La section site sera vide.")
        args.gsc = None

    # Collecte
    vids = read_seo_stats(args.seo)
    gsc  = read_gsc_csv(args.gsc) if args.gsc else []
    vids_by_id = {v["video_id"]: v for v in vids}

    targets = load_targets(Path(args.targets))
    targets = enrich_targets(targets, vids_by_id)

    baseline = {
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

    out = Path(args.out_dir) / f"baseline_{args.label}_{today}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Baseline écrite : {out}")

    # Résumé console
    print("\n=== RÉSUMÉ BASELINE {} ===".format(args.label))
    if baseline["site_gsc"]["kpis"]:
        k = baseline["site_gsc"]["kpis"]
        print(f"  Site  : {k['total_queries']} requêtes, {k['total_impressions']} imp, "
              f"{k['total_clicks']} clics, CTR {k['avg_ctr_pct']}%, "
              f"top3={k['queries_in_top3']}, top10={k['queries_in_top10']}, top20={k['queries_in_top20']}")
    k = baseline["youtube"]["kpis"]
    print(f"  YT    : {k['videos_with_data']}/{k['videos_total']} vidéos actives, "
          f"{k['sum_views_30d']} vues/30j, CTR pondéré {k['avg_ctr_weighted']}%, "
          f"avg_view% moyen {k['avg_view_pct_mean']}%")
    if targets:
        found = sum(1 for v in targets.get("videos", []) if v.get("_stats_T0"))
        tot   = len(targets.get("videos", []))
        print(f"  Batch : {found}/{tot} vidéos trackées dans seo_stats (les autres à ajouter via fetch_youtube.py)")

if __name__ == "__main__":
    main()
