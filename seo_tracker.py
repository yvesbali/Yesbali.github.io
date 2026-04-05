"""
LCDMH – SEO Tracker
====================
Mesure l'impact des optimisations de descriptions sur les performances YouTube.
Sauvegarde les stats AVANT optimisation, remesure J+30, génère un rapport HTML.

Usage PowerShell :
  python seo_tracker.py --mode snapshot   # Sauvegarde les stats actuelles (à faire AVANT d'optimiser)
  python seo_tracker.py --mode report     # Génère le rapport comparatif (à faire J+30 après)
  python seo_tracker.py --mode auto       # Snapshot + rapport en un seul appel
  python seo_tracker.py --video VIDEO_ID  # Tracker une vidéo spécifique
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Chargement .env
ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_OK = True
except ImportError:
    GOOGLE_OK = False

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
DIR             = Path(__file__).parent
CLIENT_SECRETS  = DIR / "client_secrets.json"
TOKEN_FILE      = DIR / "yt_token_analytics.json"
STATS_FILE      = DIR / "seo_stats.json"        # Historique toutes les mesures
REPORT_FILE     = DIR / f"seo_report_{datetime.now().strftime('%Y%m%d')}.html"

# ─────────────────────────────────────────────────────────────────────────────
#  COULEURS CONSOLE
# ─────────────────────────────────────────────────────────────────────────────
def _c(t, c): return f"\033[{c}m{t}\033[0m"
RED    = lambda t: _c(t, "91")
GREEN  = lambda t: _c(t, "92")
YELLOW = lambda t: _c(t, "93")
CYAN   = lambda t: _c(t, "96")
BOLD   = lambda t: _c(t, "1")
DIM    = lambda t: _c(t, "2")

def banner(t, s=""):
    w = 64
    print(); print("="*w)
    print(f"  {BOLD(t)}")
    if s: print(f"  {DIM(s)}")
    print(); print("="*w)

def ok(m):   print(GREEN(f"  OK  {m}"))
def warn(m): print(YELLOW(f"  ATTENTION  {m}"))
def err(m):  print(RED(f"  ERREUR  {m}"))
def info(m): print(CYAN(f"  ->  {m}"))

# ─────────────────────────────────────────────────────────────────────────────
#  AUTHENTIFICATION
# ─────────────────────────────────────────────────────────────────────────────
def get_clients():
    """Retourne (youtube_data, youtube_analytics)"""
    if not GOOGLE_OK:
        err("google-api-python-client manquant")
        sys.exit(1)

    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        ok("Token analytics sauvegardé")

    yt       = build("youtube",       "v3",   credentials=creds)
    yt_anal  = build("youtubeAnalytics", "v2", credentials=creds)
    return yt, yt_anal

# ─────────────────────────────────────────────────────────────────────────────
#  RÉCUPÉRATION STATS ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────
def get_video_stats(yt_anal, video_id: str, days_back: int = 30) -> dict:
    """
    Récupère CTR, impressions, vues, durée moyenne sur les X derniers jours.
    """
    end_date   = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        resp = yt_anal.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained",
            dimensions="video",
            filters=f"video=={video_id}",
            maxResults=1,
        ).execute()

        rows = resp.get("rows", [])
        if rows:
            r = rows[0]
            return {
                "views":              int(r[1]),
                "watch_minutes":      round(float(r[2]), 1),
                "avg_duration_s":     int(r[3]),
                "avg_view_pct":       round(float(r[4]), 1),
                "subs_gained":        int(r[5]),
                "period_days":        days_back,
                "start_date":         start_date,
                "end_date":           end_date,
            }
    except Exception as e:
        warn(f"Analytics erreur ({video_id}) : {e}")

    return {}

def estimate_impressions_from_sources(views, sources):
    """Estime CTR et impressions depuis les sources de trafic."""
    if views == 0:
        return {"impressions": 0, "ctr": 0, "source": "api_estimate", "confidence": "none"}
    CTR_BY_SOURCE = {
        "YT_SEARCH": 0.055, "RELATED_VIDEO": 0.035, "SUBSCRIBER": 0.15,
        "NOTIFICATION": 0.25, "YT_CHANNEL": 0.10, "PLAYLIST": 0.08,
        "EXT_URL": 0.0, "SHORTS": 0.0, "NO_LINK_OTHER": 0.03,
    }
    total_imp = 0
    views_ok = 0
    for sn, sd in sources.items():
        sv = sd.get("views", 0)
        ec = CTR_BY_SOURCE.get(sn, 0.04)
        if ec > 0 and sv > 0:
            total_imp += sv / ec
            views_ok += sv
    if total_imp == 0 and views > 0:
        total_imp = views / 0.05
        conf = "low"
    elif views_ok < views * 0.3:
        conf = "low"
    else:
        conf = "medium"
    est_ctr = (views / total_imp * 100) if total_imp > 0 else 0
    return {"impressions": int(round(total_imp)), "ctr": round(est_ctr, 2), "source": "api_estimate", "confidence": conf}


def get_impression_stats(video_id, views, sources):
    """CTR/impressions hybride : CSV YouTube Studio si dispo, sinon estimation API."""
    import csv as _csv
    csv_path = Path(__file__).parent / "yt_studio_export.csv"
    if csv_path.exists():
        try:
            lines = csv_path.read_text(encoding="utf-8-sig").strip().splitlines()
            reader = _csv.reader(lines)
            headers = [h.strip().lower() for h in next(reader)]
            imp_col = ctr_col = None
            for i, h in enumerate(headers):
                if "impression" in h and "ctr" not in h and "taux" not in h:
                    imp_col = i
                if "ctr" in h or ("taux" in h and "clic" in h):
                    ctr_col = i
            if imp_col is not None:
                for row in reader:
                    if video_id in str(row):
                        raw_imp = row[imp_col].replace(",", "").replace(" ", "").replace("\xa0", "") or "0"
                        imp_val = float(raw_imp)
                        ctr_val = 0
                        if ctr_col:
                            raw_ctr = row[ctr_col].replace("%", "").replace(",", ".").replace(" ", "").replace("\xa0", "") or "0"
                            ctr_val = float(raw_ctr)
                        return {"impressions": int(imp_val), "ctr": round(ctr_val, 2), "source": "youtube_studio_csv", "confidence": "high"}
        except Exception:
            pass
    return estimate_impressions_from_sources(views, sources)


def get_traffic_sources(yt_anal, video_id: str, days_back: int = 30) -> dict:
    """
    Récupère la répartition des sources de trafic.
    """
    end_date   = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    sources = {}
    try:
        resp = yt_anal.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="insightTrafficSourceType",
            filters=f"video=={video_id}",
            maxResults=10,
        ).execute()

        rows = resp.get("rows", [])
        total = sum(int(r[1]) for r in rows) or 1
        for r in rows:
            sources[r[0]] = {
                "views": int(r[1]),
                "pct":   round(int(r[1]) / total * 100, 1),
            }
    except Exception as e:
        warn(f"Sources trafic erreur ({video_id}) : {e}")

    return sources

# ─────────────────────────────────────────────────────────────────────────────
#  SNAPSHOT — SAUVEGARDE BASELINE
# ─────────────────────────────────────────────────────────────────────────────
def snapshot(yt, yt_anal, video_ids: list = None):
    """
    Sauvegarde les stats actuelles comme baseline pour comparaison future.
    Si video_ids=None, prend les vidéos récemment optimisées depuis last_optimization.json
    """
    # Charger les vidéos à tracker
    if video_ids:
        videos_to_track = video_ids
    else:
        # Lire le cache pour les 50 dernières vidéos optimisées
        cache_file = DIR / "videos_cache.json"
        if not cache_file.exists():
            err("Cache absent. Lance d'abord : python desc_optimizer.py --mode fetch")
            sys.exit(1)
        data   = json.loads(cache_file.read_text(encoding="utf-8"))
        videos = data["videos"][:50]
        videos_to_track = [v["id"] for v in videos]

    # Charger l'historique existant
    stats = {}
    if STATS_FILE.exists():
        stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))

    now = datetime.now().isoformat()
    info(f"Snapshot de {len(videos_to_track)} vidéos...")

    for i, vid_id in enumerate(videos_to_track, 1):
        info(f"  [{i}/{len(videos_to_track)}] {vid_id}")

        base  = get_video_stats(yt_anal, vid_id, days_back=30)
        srcs  = get_traffic_sources(yt_anal, vid_id, days_back=30)
        impr  = get_impression_stats(vid_id, base.get("views", 0), srcs)

        entry = {
            "taken_at":    now,
            "views_30d":   base.get("views", 0),
            "watch_min":   base.get("watch_minutes", 0),
            "avg_view_pct": base.get("avg_view_pct", 0),
            "avg_dur_s":   base.get("avg_duration_s", 0),
            "subs":        base.get("subs_gained", 0),
            "impressions": impr.get("impressions", 0),
            "ctr":         impr.get("ctr", 0),
            "sources":     srcs,
        }

        if vid_id not in stats:
            stats[vid_id] = {"snapshots": []}

        stats[vid_id]["snapshots"].append(entry)

        # Garder max 12 snapshots par vidéo (1 an mensuel)
        if len(stats[vid_id]["snapshots"]) > 12:
            stats[vid_id]["snapshots"] = stats[vid_id]["snapshots"][-12:]

    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    ok(f"Snapshot sauvegardé -> {STATS_FILE.name}")
    return stats

# ─────────────────────────────────────────────────────────────────────────────
#  RAPPORT HTML
# ─────────────────────────────────────────────────────────────────────────────
def trend_arrow(before, after):
    if after is None or before is None:
        return "—"
    diff = after - before
    if diff > 0:
        return f"<span style='color:#27ae60'>↑ +{diff:.1f}</span>"
    elif diff < 0:
        return f"<span style='color:#e74c3c'>↓ {diff:.1f}</span>"
    return "<span style='color:#888'>-> =</span>"

def diagnostic(ctr_before, ctr_after, views_before, views_after):
    """Diagnostic automatique : description OK ou vignette à retravailler ?"""
    if ctr_after is None:
        return "⏳ En attente de données J+30"

    # Si CTR=0 des deux cotes, diagnostiquer sur les vues
    if (ctr_before or 0) == 0 and (ctr_after or 0) == 0:
        vd = (views_after or 0) - (views_before or 0)
        if vd > 0:
            return "📈 <b>Vues en hausse</b> — tendance positive"
        elif vd < 0:
            return "📉 <b>Vues en baisse</b> — vérifier saisonnalité"
        else:
            return "➡️ <b>Stable</b> — pas de changement significatif"

    ctr_delta  = (ctr_after  or 0) - (ctr_before  or 0)
    view_delta = (views_after or 0) - (views_before or 0)

    if ctr_delta >= 0.5 and view_delta >= 0:
        return "✅ <b>Description efficace</b> — CTR en hausse"
    elif ctr_delta < 0 and view_delta > 0:
        return "🔍 <b>Vérifier la vignette</b> — vues ok mais CTR baisse"
    elif ctr_delta < -0.5:
        return "🖼️ <b>Vignette à retravailler</b> — CTR en baisse significative"
    elif ctr_delta >= 0 and view_delta < 0:
        return "📉 <b>Vues en baisse</b> — vérifier saisonnalité"
    else:
        return "ATTENTION️ <b>Résultat neutre</b> — attendre J+60 pour confirmer"

def generate_report(stats: dict, yt):
    """Génère le rapport HTML comparatif."""

    # Récupérer les titres des vidéos
    vid_ids = list(stats.keys())
    titles  = {}
    try:
        for i in range(0, len(vid_ids), 50):
            batch = vid_ids[i:i+50]
            resp  = yt.videos().list(part="snippet", id=",".join(batch)).execute()
            for item in resp.get("items", []):
                titles[item["id"]] = item["snippet"]["title"]
    except Exception as e:
        warn(f"Titres non récupérés : {e}")

    rows = ""
    for vid_id, data in stats.items():
        snaps = data.get("snapshots", [])
        if not snaps:
            continue

        title = titles.get(vid_id, vid_id)
        s0    = snaps[0]   # Baseline (avant optimisation)
        s1    = snaps[-1]  # Dernière mesure

        has_before_after = len(snaps) >= 2

        ctr_b   = s0.get("ctr", 0)
        ctr_a   = s1.get("ctr") if has_before_after else None
        views_b = s0.get("views_30d", 0)
        views_a = s1.get("views_30d") if has_before_after else None
        impr_b  = s0.get("impressions", 0)
        impr_a  = s1.get("impressions") if has_before_after else None
        pct_b   = s0.get("avg_view_pct", 0)
        pct_a   = s1.get("avg_view_pct") if has_before_after else None

        diag = diagnostic(ctr_b, ctr_a, views_b, views_a)

        rows += f"""
        <tr>
            <td>
                <a href="https://youtu.be/{vid_id}" target="_blank">{title[:55]}</a>
                <br><span style="font-size:11px;color:#999">{vid_id} · {len(snaps)} mesure(s)</span>
            </td>
            <td style="text-align:center">
                {ctr_b:.2f}%
                {"<br>" + trend_arrow(ctr_b, ctr_a) if has_before_after else ""}
            </td>
            <td style="text-align:center">
                {impr_b:,}
                {"<br>" + trend_arrow(impr_b, impr_a) if has_before_after else ""}
            </td>
            <td style="text-align:center">
                {views_b:,}
                {"<br>" + trend_arrow(views_b, views_a) if has_before_after else ""}
            </td>
            <td style="text-align:center">
                {pct_b:.1f}%
                {"<br>" + trend_arrow(pct_b, pct_a) if has_before_after else ""}
            </td>
            <td style="font-size:12px">{diag}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LCDMH – Rapport SEO {datetime.now().strftime('%d/%m/%Y')}</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 1100px; margin: 40px auto; padding: 20px; background: #f5f4f0; color: #1a1a18; }}
  h1 {{ color: #e67e22; margin-bottom: 5px; }}
  .sub {{ color: #666; font-size: 13px; margin-bottom: 25px; }}
  .stats {{ display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }}
  .stat {{ background: white; padding: 14px 22px; border-radius: 10px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.08); min-width: 120px; }}
  .stat .n {{ font-size: 28px; font-weight: bold; color: #e67e22; }}
  .stat .l {{ font-size: 11px; color: #888; margin-top: 2px; }}
  .legend {{ background: white; border-radius: 10px; padding: 15px 20px; margin: 16px 0; font-size: 13px; }}
  .legend h3 {{ margin: 0 0 8px; font-size: 13px; color: #333; }}
  .legend p {{ margin: 4px 0; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-top: 16px; }}
  th {{ background: #1a2b4a; color: white; padding: 12px 10px; text-align: left; font-size: 12px; }}
  td {{ padding: 10px; border-bottom: 1px solid #f0ede8; font-size: 13px; vertical-align: middle; }}
  tr:hover {{ background: #faf9f7; }}
  a {{ color: #2980b9; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
</style>
</head>
<body>
<h1>🏍️ LCDMH – Rapport SEO Descriptions</h1>
<p class="sub">Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} · Impact des optimisations de descriptions YouTube</p>

<div class="stats">
  <div class="stat"><div class="n">{len(stats)}</div><div class="l">Vidéos suivies</div></div>
  <div class="stat"><div class="n">{sum(1 for d in stats.values() if len(d.get('snapshots',[])) >= 2)}</div><div class="l">Avec données J+30</div></div>
  <div class="stat"><div class="n" style="color:#27ae60">{sum(1 for d in stats.values() if len(d.get('snapshots',[])) >= 2 and d['snapshots'][-1].get('ctr',0) > d['snapshots'][0].get('ctr',0))}</div><div class="l">CTR en hausse ↑</div></div>
  <div class="stat"><div class="n" style="color:#e74c3c">{sum(1 for d in stats.values() if len(d.get('snapshots',[])) >= 2 and d['snapshots'][-1].get('ctr',0) < d['snapshots'][0].get('ctr',0))}</div><div class="l">CTR en baisse ↓</div></div>
</div>

<div class="legend">
  <h3>📖 Guide de lecture</h3>
  <p>✅ <b>Description efficace</b> — Le CTR augmente après optimisation -> la description + thumbnail fonctionnent</p>
  <p>🖼️ <b>Vignette à retravailler</b> — Le CTR baisse ou stagne -> la description est OK mais la vignette bloque</p>
  <p>⏳ <b>En attente</b> — Snapshot initial pris, mesure J+30 pas encore disponible</p>
  <p style="color:#888;font-size:12px;margin-top:8px">Les flèches ↑↓ comparent la dernière mesure vs le snapshot initial (baseline avant optimisation)</p>
</div>

<table>
  <tr>
    <th>Vidéo</th>
    <th>CTR<br><span style="font-weight:normal;font-size:10px">% clics/impressions</span></th>
    <th>Impressions<br><span style="font-weight:normal;font-size:10px">30 derniers jours</span></th>
    <th>Vues<br><span style="font-weight:normal;font-size:10px">30 derniers jours</span></th>
    <th>Rétention<br><span style="font-weight:normal;font-size:10px">% moyen visionné</span></th>
    <th>Diagnostic</th>
  </tr>
  {rows}
</table>

<p style="color:#aaa;font-size:11px;margin-top:20px;text-align:center">
  LCDMH SEO Tracker · Données YouTube Analytics API · {datetime.now().strftime('%d/%m/%Y')}
</p>
</body>
</html>"""

    REPORT_FILE.write_text(html, encoding="utf-8")
    ok(f"Rapport -> {REPORT_FILE.name}")
    return REPORT_FILE

# ─────────────────────────────────────────────────────────────────────────────
#  POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="LCDMH – SEO Tracker v2 (Hybrid)")
    ap.add_argument("--mode",  default="auto", choices=["snapshot", "report", "auto"])
    ap.add_argument("--video", default=None, help="ID vidéo spécifique")
    ap.add_argument("--days",  default=30, type=int, help="Fenêtre d'analyse en jours")
    args = ap.parse_args()

    banner(
        "LCDMH – SEO Tracker v2 (Hybrid)",
        f"Mode : {args.mode.upper()}  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    if not GOOGLE_OK:
        err("google-api-python-client manquant : pip install google-api-python-client")
        sys.exit(1)

    yt, yt_anal = get_clients()

    video_ids = [args.video] if args.video else None

    if args.mode in ("snapshot", "auto"):
        info("Prise du snapshot...")
        stats = snapshot(yt, yt_anal, video_ids=video_ids)

    if args.mode in ("report", "auto"):
        if not STATS_FILE.exists():
            err("Aucun snapshot trouvé. Lance d'abord : python seo_tracker.py --mode snapshot")
            sys.exit(1)
        stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))
        info("Génération du rapport...")
        report_path = generate_report(stats, yt)

        # Ouvrir le rapport dans le navigateur
        try:
            import subprocess
            subprocess.Popen(f'start "" "{report_path}"', shell=True)
        except Exception:
            pass

    print()
    info(f"Stats sauvegardées -> {STATS_FILE.name}")
    if args.mode != "snapshot":
        info(f"Rapport HTML -> {REPORT_FILE.name}")
        info("Pour un suivi mensuel, relance ce script dans 30 jours")

if __name__ == "__main__":
    main()





