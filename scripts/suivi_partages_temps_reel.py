#!/usr/bin/env python3
"""Suivi TEMPS REEL des liens partages /v/ (GA4, 30 dernieres minutes).

L'API realtime de GA4 ne remonte que les 30 dernieres minutes.
On lit les pages vues par titre (unifiedScreenName) et on ne garde que les titres
qui correspondent a une page de partage /v/ du depot — donc : quelles videos
partagees viennent d'etre ouvertes, et combien de fois.

Code et canal : lus dans le Google Form (champ origine = plateforme|hote) et dans
le bilan GA4 (scripts/bilan_partages.py, dimension pagePathPlusQueryString).

Usage:
  python3 scripts/suivi_partages_temps_reel.py
  python3 scripts/suivi_partages_temps_reel.py --json

Token : /home/ubuntu/.openclaw/workspace/ga4_token.json (jamais affiche).
"""
import argparse, json, pathlib, re, urllib.request

TOKEN = "/home/ubuntu/.openclaw/workspace/ga4_token.json"
PID = "486269672"
VDIR = pathlib.Path(__file__).resolve().parent.parent / "v"


def access_token():
    t = json.load(open(TOKEN))
    body = json.dumps({"client_id": t["client_id"], "client_secret": t["client_secret"],
                       "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode()
    r = urllib.request.Request("https://oauth2.googleapis.com/token", data=body,
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=25).read())["access_token"]


def rt(at, payload):
    req = urllib.request.Request(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{PID}:runRealtimeReport",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + at, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=40).read())


def titres_partage():
    """titre de page -> identifiant video, pour les 89 pages /v/."""
    m = {}
    for f in VDIR.glob("*.html"):
        s = f.read_text(encoding="utf-8", errors="ignore")
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        if t:
            m[t.group(1).strip()] = f.stem
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    at = access_token()
    titres = titres_partage()

    rep = rt(at, {"limit": 200, "dimensions": [{"name": "unifiedScreenName"}],
                  "metrics": [{"name": "eventCount"}]})
    total = 0
    lignes = []
    for row in rep.get("rows", []):
        titre = row["dimensionValues"][0]["value"]
        n = int(row["metricValues"][0]["value"])
        vid = titres.get(titre)
        if vid:
            total += n
            lignes.append({"video": vid, "titre": titre, "vues": n})
    lignes.sort(key=lambda x: -x["vues"])

    if a.json:
        print(json.dumps({"total": total, "videos": lignes}, ensure_ascii=False, indent=1))
        return

    print(f"Ouvertures de liens partages, 30 dernieres minutes : {total}")
    if not lignes:
        print("  aucune ouverture enregistree sur les pages /v/")
    for l in lignes:
        print(f"  {l['vues']:>3}  {l['video']:14s} {l['titre'][:60]}")


if __name__ == "__main__":
    main()
