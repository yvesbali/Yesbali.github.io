#!/usr/bin/env python3
"""Alerte silencieuse : nouvelles ouvertures de liens partages /v/ sur la journee.

Appele par un cron toutes les 30 minutes. Compare le nombre d'ouvertures du jour
(GA4, evenement share_open) au dernier chiffre enregistre et n'affiche quelque
chose QUE s'il y a du nouveau — sinon sortie vide (aucun message a Yves).

Note : GA4 accuse un decalage de quelques minutes a ~1 h : c'est du quasi temps
reel, pas de l'instantane. Le detail code/canal reste dans le Google Form.
"""
import datetime, json, pathlib, re, sys, urllib.parse, urllib.request

TOKEN = "/home/ubuntu/.openclaw/workspace/ga4_token.json"
PID = "486269672"
EVT = "share_open"
STATE = pathlib.Path("/home/ubuntu/.hermes-assistant/cache/partages_state.json")


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
    jour = datetime.date.today().isoformat()
    at = access_token()
    rep = report(at, {
        "dateRanges": [{"startDate": "today", "endDate": "today"}],
        "dimensions": [{"name": "pagePathPlusQueryString"}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"filter": {"fieldName": "eventName",
                                       "stringFilter": {"matchType": "EXACT", "value": EVT}}},
        "limit": 5000,
    })
    lignes = {}
    for row in rep.get("rows", []):
        url = row["dimensionValues"][0]["value"]
        n = int(row["metricValues"][0]["value"])
        m = re.search(r"[?&]c=([^&]+)", url)
        code = urllib.parse.unquote(m.group(1)) if m else "(sans code)"
        v = re.search(r"/v/([^/.?]+)\.html", url)
        cle = f"{v.group(1) if v else url}|{code}"
        lignes[cle] = lignes.get(cle, 0) + n
    total = sum(lignes.values())

    state = {}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text())
        except Exception:
            state = {}
    if state.get("jour") != jour:
        state = {"jour": jour, "lignes": {}}
    avant = state.get("lignes", {})
    nouveaux = {k: v - avant.get(k, 0) for k, v in lignes.items() if v > avant.get(k, 0)}

    state["lignes"] = lignes
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False))

    if not nouveaux:
        return
    print(f"Liens partages ouverts depuis le dernier point : +{sum(nouveaux.values())} "
          f"(total du jour {total})")
    for k, n in sorted(nouveaux.items(), key=lambda x: -x[1]):
        video, code = k.split("|", 1)
        print(f"  +{n}  {video:14s} code {code}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Suivi partages en erreur : {e}", file=sys.stderr)
        sys.exit(1)
