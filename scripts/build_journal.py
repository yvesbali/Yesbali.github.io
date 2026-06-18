#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstruit la page journal du road trip a partir de la playlist YouTube.
Tourne dans GitHub Actions. Aucune cle API. Page reconstruite a chaque run."""
from __future__ import annotations
import html, json, re, urllib.error, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HANDLE = "@LCDMH"
PLAYLIST_ID = "PLYEqidd8fqw5Joqcagj_9S8sG23nOw8XR"
SLUG = "road-trip-italie-dolomites-2026"
TITLE = "Road trip Italie Dolomites 2026"
START = datetime(2026, 5, 30, tzinfo=timezone.utc)
END = datetime(2026, 6, 13, tzinfo=timezone.utc)
OUT = Path("roadtrips") / f"{SLUG}-journal.html"
MAIN = f"/roadtrips/{SLUG}.html"
VIDEOS_JSON = Path("data") / "videos.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; LCDMH/1.0)"}
MOIS = ["", "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre"]

def get(url):
    r = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(r, timeout=30).read().decode("utf-8", "replace")

def channel_id():
    if VIDEOS_JSON.exists():
        try:
            data = json.loads(VIDEOS_JSON.read_text(encoding="utf-8"))
            cid = data.get("channel_id", "")
            if re.fullmatch(r"UC[0-9A-Za-z_-]{22}", cid):
                return cid
        except Exception:
            pass

    p = get(f"https://www.youtube.com/{HANDLE}")
    m = re.search(r'"channelId":"(UC[0-9A-Za-z_-]{22})"', p) or re.search(r'channel/(UC[0-9A-Za-z_-]{22})', p)
    if not m:
        raise SystemExit("channelId introuvable")
    return m.group(1)

def video_id_from_entry(entry):
    for key in ("url", "short_url", "thumb"):
        value = str(entry.get(key) or "")
        m = re.search(r"(?:v=|youtu\.be/|shorts/|/vi/)([A-Za-z0-9_-]{11})", value)
        if m:
            return m.group(1)
    return str(entry.get("id") or "")

def local_video_map():
    if not VIDEOS_JSON.exists():
        return {}
    data = json.loads(VIDEOS_JSON.read_text(encoding="utf-8"))
    out = {}
    for entry in data.get("videos", []) + data.get("shorts", []):
        vid = video_id_from_entry(entry)
        published = str(entry.get("published") or "")
        if not vid or not published:
            continue
        if len(published) == 10:
            dt = datetime.fromisoformat(published).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        out[vid] = {"id": vid, "title": entry.get("title", "") or "", "dt": dt}
    return out

def local_videos():
    return list(local_video_map().values())

def playlist_video_ids():
    p = get(f"https://www.youtube.com/playlist?list={PLAYLIST_ID}")
    ids = []
    for pattern in (r'"videoId":"([A-Za-z0-9_-]{11})"', r"watch\?v=([A-Za-z0-9_-]{11})"):
        for m in re.finditer(pattern, p):
            vid = m.group(1)
            if vid not in ids:
                ids.append(vid)
    return ids

def video_title_from_oembed(vid):
    try:
        raw = get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json")
        return json.loads(raw).get("title", "") or f"Video YouTube {vid}"
    except Exception:
        return f"Video YouTube {vid}"

def playlist_videos():
    local = local_video_map()
    out = []
    for vid in playlist_video_ids():
        if vid in local:
            out.append(local[vid])
        else:
            out.append({"id": vid, "title": video_title_from_oembed(vid), "dt": START})
    return out

def videos(cid):
    feed = get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    out = []
    for e in ET.fromstring(feed).findall("a:entry", ns):
        vid, t, pub = e.find("yt:videoId", ns), e.find("a:title", ns), e.find("a:published", ns)
        if vid is None or pub is None:
            continue
        out.append({"id": vid.text, "title": (t.text if t is not None else "") or "",
                    "dt": datetime.fromisoformat(pub.text.replace("Z", "+00:00"))})
    return out

def card(v):
    u = f"https://www.youtube.com/watch?v={v['id']}"
    th = f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg"
    d = f"{v['dt'].day} {MOIS[v['dt'].month]} {v['dt'].year}"
    return (f'<div class="jc"><div class="jt"><span class="jb">{html.escape(d)}</span>'
            f'<a href="{u}" target="_blank" rel="noopener"><img src="{th}" alt="" loading="lazy"></a></div>'
            f'<div class="jd"><h2>{html.escape(v["title"])}</h2>'
            f'<a class="bs" href="{u}" target="_blank" rel="noopener">Voir la video</a></div></div>')

def page(cards):
    body = cards or ('<article class="je"><h2>Le journal arrive bientot</h2>'
                     '<p>Les shorts publies pendant le voyage apparaitront ici automatiquement.</p></article>')
    css = ("*{box-sizing:border-box;margin:0;padding:0}body{font-family:Inter,Arial,sans-serif;"
           "background:#f7f7f5;color:#1a1a1a;line-height:1.6}a{color:inherit;text-decoration:none}"
           ".hd{background:linear-gradient(135deg,#163251,#244b73);color:#fff;padding:48px 24px;text-align:center}"
           ".hd h1{font-size:clamp(1.5rem,4vw,2.4rem);margin:0 0 .4rem}.hd p{color:#e0e5ed;max-width:680px;margin:.3rem auto}"
           ".btn{display:inline-block;margin-top:1rem;padding:.6rem 1.3rem;border-radius:8px;background:#e67e22;color:#fff;font-weight:700}"
           ".wrap{max-width:1000px;margin:0 auto;padding:2rem 20px 3rem}"
           ".kick{font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#e67e22;margin-bottom:1.2rem}"
           ".jc{display:grid;grid-template-columns:320px 1fr;background:#fff;border:1px solid #e5e5e5;border-radius:16px;overflow:hidden;margin-bottom:1.1rem;box-shadow:0 3px 10px rgba(0,0,0,.04)}"
           ".jt{position:relative;background:#f0ede8;min-height:170px}.jt img{width:100%;height:100%;object-fit:cover;display:block}"
           ".jb{position:absolute;left:12px;top:12px;background:#e67e22;color:#fff;padding:.3rem .7rem;border-radius:999px;font-size:.72rem;font-weight:800;text-transform:uppercase}"
           ".jd{padding:1.2rem 1.3rem;display:flex;flex-direction:column;justify-content:center}.jd h2{font-size:1.05rem;margin:0 0 .7rem}"
           ".bs{align-self:flex-start;padding:.5rem 1rem;border-radius:6px;background:#1a1a1a;color:#fff;font-weight:700;font-size:.8rem}"
           ".je{background:#fff;border:1px dashed #e5e5e5;border-radius:16px;padding:2.5rem;text-align:center;color:#777}"
           "@media(max-width:640px){.jc{grid-template-columns:1fr}.jt{min-height:200px}}")
    return (f'<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            f'<title>{html.escape(TITLE)} — Journal de bord du voyageur - Journal | LCDMH</title>'
            f'<style>{css}</style></head><body>'
            f'<header class="hd"><h1>{html.escape(TITLE)} — Journal de bord du voyageur</h1>'
            f'<p>Suivez l\'aventure au jour le jour. Les shorts et notes publies pendant le voyage.</p>'
            f'<a class="btn" href="{MAIN}">← Revenir a la page principale</a></header>'
            f'<main class="wrap"><div class="kick">Entrees du journal</div>{body}</main></body></html>')

def main():
    try:
        source = playlist_videos()
        if not source:
            raise RuntimeError("playlist vide")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"Playlist YouTube indisponible ({exc}); fallback flux chaine.")
        try:
            source = videos(channel_id())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc2:
            print(f"Flux YouTube indisponible ({exc2}); fallback data/videos.json.")
            source = local_videos()
    except RuntimeError as exc:
        print(f"Playlist YouTube indisponible ({exc}); fallback data/videos.json.")
        source = local_videos()
    if not source:
        raise SystemExit("Aucune video disponible pour reconstruire le journal.")

    vids = [v for v in source if START <= v["dt"] < END]
    vids.sort(key=lambda v: v["dt"], reverse=True)
    new = page("".join(card(v) for v in vids))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and OUT.read_text(encoding="utf-8") == new:
        print(f"Aucun changement ({len(vids)} entree(s)).")
        return 0
    OUT.write_text(new, encoding="utf-8")
    print(f"Journal reconstruit : {len(vids)} entree(s).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
