#!/usr/bin/env python3
"""
fetch_gsc.py — Export quotidien Search Console -> CSV
======================================================
Appelle l'API searchanalytics.query() et écrit un CSV à l'emplacement lu par
append_daily_log.py :  data/baselines/gsc_queries_YYYY-MM-DD.csv

Fenêtre par défaut : 28 jours glissants (comme l'UI GSC par défaut),
se terminant à J-3 pour laisser le temps aux données de se stabiliser
(GSC a un lag typique de 48-72h).

Credentials : gsc_token.json (OAuth user avec refresh_token) à la racine du
repo — gitignored. Peut aussi être passé via la variable d'env GSC_TOKEN_JSON.

Usage :
  python scripts/fetch_gsc.py
  python scripts/fetch_gsc.py --lag 2 --window 7      # fenêtre plus étroite
  python scripts/fetch_gsc.py --site https://lcdmh.com
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
TOKEN_FILE = BASE / "gsc_token.json"
OUT_DIR = BASE / "data" / "baselines"
DEFAULT_SITE = "https://lcdmh.com"
DEFAULT_WINDOW = 28   # jours
DEFAULT_LAG = 3       # jours — end_date = today - lag
ROW_LIMIT = 1000


def load_credentials() -> dict:
    """Lit le token OAuth depuis env var (prioritaire) ou fichier local."""
    raw = os.environ.get("GSC_TOKEN_JSON")
    if raw:
        return json.loads(raw)
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    print(f"ERREUR : ni GSC_TOKEN_JSON (env) ni {TOKEN_FILE} disponibles.")
    sys.exit(1)


def refresh_access_token(creds: dict) -> str:
    """Échange le refresh_token contre un access_token frais."""
    required = ("refresh_token", "client_id", "client_secret")
    missing = [k for k in required if not creds.get(k)]
    if missing:
        print(f"ERREUR : token incomplet, champs manquants : {missing}")
        sys.exit(1)
    r = requests.post(
        creds.get("token_uri", "https://oauth2.googleapis.com/token"),
        data={
            "client_id":     creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type":    "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    tok = r.json().get("access_token")
    if not tok:
        print(f"ERREUR : pas d'access_token dans la réponse : {r.text}")
        sys.exit(1)
    return tok


def query_search_analytics(access_token: str, site_url: str,
                           start: str, end: str) -> list:
    """Appelle searchanalytics.query et retourne la liste de lignes brutes."""
    url = (
        "https://searchconsole.googleapis.com/webmasters/v3/sites/"
        f"{requests.utils.quote(site_url, safe='')}/searchAnalytics/query"
    )
    body = {
        "startDate":  start,
        "endDate":    end,
        "dimensions": ["query"],
        "rowLimit":   ROW_LIMIT,
    }
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type":  "application/json"},
        json=body,
        timeout=60,
    )
    if r.status_code != 200:
        print(f"ERREUR API GSC {r.status_code} : {r.text[:500]}")
        sys.exit(1)
    return r.json().get("rows", [])


def write_csv(rows: list, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query", "clicks", "impressions", "position"])
        for r in rows:
            keys = r.get("keys", [])
            query = keys[0] if keys else ""
            w.writerow([
                query,
                int(r.get("clicks", 0) or 0),
                int(r.get("impressions", 0) or 0),
                round(float(r.get("position", 0) or 0), 1),
            ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                    help=f"Fenêtre en jours (défaut {DEFAULT_WINDOW})")
    ap.add_argument("--lag", type=int, default=DEFAULT_LAG,
                    help=f"Jours de lag avant aujourd'hui (défaut {DEFAULT_LAG})")
    ap.add_argument("--site", default=DEFAULT_SITE,
                    help=f"URL propriété GSC (défaut {DEFAULT_SITE})")
    ap.add_argument("--date", default=None,
                    help="Date de nommage du CSV au format YYYY-MM-DD "
                         "(défaut : aujourd'hui)")
    args = ap.parse_args()

    end_date   = date.today() - timedelta(days=args.lag)
    start_date = end_date - timedelta(days=args.window - 1)
    label_date = args.date or date.today().isoformat()
    out_path   = OUT_DIR / f"gsc_queries_{label_date}.csv"

    print(f"GSC site   : {args.site}")
    print(f"Fenêtre    : {start_date} -> {end_date}  ({args.window}j)")
    print(f"Sortie     : {out_path}")

    creds = load_credentials()
    token = refresh_access_token(creds)
    rows  = query_search_analytics(token, args.site,
                                   start_date.isoformat(), end_date.isoformat())

    write_csv(rows, out_path)

    total_clicks = sum(int(r.get("clicks", 0) or 0) for r in rows)
    total_impr   = sum(int(r.get("impressions", 0) or 0) for r in rows)
    print(f"OK {len(rows)} requêtes | {total_clicks} clics | {total_impr} impressions")


if __name__ == "__main__":
    main()
