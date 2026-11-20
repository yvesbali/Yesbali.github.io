#!/usr/bin/env python3
"""Bilan des liens de partage /v/ sur une periode (GA4, standard).

Pour chaque lien ouvert : la page + le code (?c=...), donc le canal quand un code
par canal est utilise (e68aqq-fb, e68aqq-wa...).

Usage:
  python3 scripts/bilan_partages.py                 # 7 derniers jours
  python3 scripts/bilan_partages.py --jours 30
  python3 scripts/bilan_partages.py --date-debut 2026-11-19 --date-fin 2026-11-20
"""
import argparse, datetime, json, re, urllib.parse, urllib.request
from collections import Counter

TOKEN = "/home/ubuntu/.openclaw/workspace/ga4_token.json"
PID = "486269672"
EVT = "share_open"


def access_token():
    t = json.load(open(TOKEN))
    body = json.dumps({"client_id": t["client_id"], "client_secret": t["client_secret"],
                       "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode()
    r = urllib.request.Request("https://oauth2.googleapis.com/token", data=body,
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=25).read())["access_token"]


def report(at, payload):
    req = urllib.request.Request(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{PID}:runReport",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + at, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=int, default=7)
    ap.add_argument("--date-debut")
    ap.add_argument("--date-fin")
    a = ap.parse_args()
    if a.date_debut:
        debut, fin = a.date_debut, a.date_fin or a.date_debut
    else:
        fin = datetime.date.today().isoformat()
        debut = (datetime.date.today() - datetime.timedelta(days=a.jours - 1)).isoformat()

    at = access_token()
    rep = report(at, {
        "dateRanges": [{"startDate": debut, "endDate": fin}],
        "dimensions": [{"name": "pagePathPlusQueryString"}, {"name": "date"}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"filter": {"fieldName": "eventName",
                                       "stringFilter": {"matchType": "EXACT", "value": EVT}}},
        "orderBys": [{"dimension": {"dimensionName": "date"}}],
        "limit": 10000,
    })

    lignes = []
    for row in rep.get("rows", []):
        url = row["dimensionValues"][0]["value"]
        jour = row["dimensionValues"][1]["value"]
        jour = f"{jour[6:8]}/{jour[4:6]}/{jour[:4]}"
        n = int(row["metricValues"][0]["value"])
        code = ""
        m = re.search(r"[?&]c=([^&]+)", url)
        if m:
            code = urllib.parse.unquote(m.group(1))
        video = re.search(r"/v/([^/.?]+)\.html", url)
        lignes.append({"jour": jour, "code": code, "video": video.group(1) if video else url,
                       "n": n})

    print(f"Liens partages ouverts — {debut} -> {fin} : "
          f"{sum(l['n'] for l in lignes)} ouvertures, {len(lignes)} lignes\n")
    if not lignes:
        return
    par_code = Counter()
    par_video = Counter()
    for l in lignes:
        par_code[l["code"] or "(sans code)"] += l["n"]
        par_video[l["video"]] += l["n"]
    print("Par code (le suffixe indique le canal) :")
    for c, n in par_code.most_common():
        print(f"  {c:20s} {n}")
    print("\nPar video :")
    for v, n in par_video.most_common():
        print(f"  {v:20s} {n}")
    print("\nDetail par jour :")
    for l in lignes[:200]:
        print(f"  {l['jour']}  {l['code'] or '(sans code)':16s} {l['video']:16s} {l['n']}")


if __name__ == "__main__":
    main()
