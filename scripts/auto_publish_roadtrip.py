# -*- coding: utf-8 -*-
"""Auto-publish road trip videos — LCDMH (GitHub Actions).

Detecte les nouveaux shorts d'une playlist YouTube et les injecte
dans la page principale (max 3) et le journal de bord.
Les plus anciens non importes sont traites en premier.

Usage (workflow GitHub Actions) :
    python scripts/auto_publish_roadtrip.py \
        --config data/roadtrips/SLUG/auto_publish_config.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List


def _get_youtube_service():
    token_json = os.environ.get("YT_TOKEN_ANALYTICS", "")
    if not token_json:
        raise RuntimeError("Variable YT_TOKEN_ANALYTICS absente")
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(json.loads(token_json))
    return build("youtube", "v3", credentials=creds)


def _fetch_playlist_videos(service, playlist_id: str) -> List[Dict[str, Any]]:
    items, token = [], None
    while True:
        resp = service.playlistItems().list(part="snippet,contentDetails", playlistId=playlist_id, maxResults=50, pageToken=token).execute()
        items.extend(resp.get("items", []) or [])
        token = resp.get("nextPageToken")
        if not token:
            break
    video_ids, item_map = [], {}
    for item in items:
        vid = (item.get("contentDetails") or {}).get("videoId", "")
        if vid:
            video_ids.append(vid)
            item_map[vid] = item
    videos_meta = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        for v in service.videos().list(part="snippet,contentDetails", id=",".join(chunk), maxResults=50).execute().get("items", []):
            videos_meta[v["id"]] = v
    results = []
    for vid in video_ids:
        meta = videos_meta.get(vid, {})
        snippet = meta.get("snippet", {})
        content = meta.get("contentDetails", {})
        dur = _iso_dur(content.get("duration", ""))
        pos = int(item_map.get(vid, {}).get("snippet", {}).get("position", 0) or 0)
        thumbs = snippet.get("thumbnails", {})
        thumb = ""
        for k in ("maxres", "high", "medium", "default"):
            if k in thumbs and thumbs[k].get("url"):
                thumb = thumbs[k]["url"]
                break
        results.append({"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "title": snippet.get("title", f"Video {vid}"), "description": (snippet.get("description") or "")[:250], "thumb": thumb or f"https://img.youtube.com/vi/{vid}/hqdefault.jpg", "published_at": snippet.get("publishedAt", ""), "date_label": _date_fr_iso(snippet.get("publishedAt", "")), "is_short": 0 < dur <= 70, "position": pos})
    results.sort(key=lambda v: v["position"])
    return results


def _iso_dur(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    return (int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + int(m.group(3) or 0)) if m else 0

MOIS = ['','JANVIER','FEVRIER','MARS','AVRIL','MAI','JUIN','JUILLET','AOUT','SEPTEMBRE','OCTOBRE','NOVEMBRE','DECEMBRE']

def _date_fr(dt=None):
    dt = dt or datetime.now()
    return f"{dt.day} {MOIS[dt.month]} {dt.year}"

def _date_fr_iso(iso):
    if not iso:
        return _date_fr()
    try:
        return _date_fr(datetime.fromisoformat(iso.replace("Z", "+00:00")))
    except Exception:
        return _date_fr()


def _known_ids(path: Path) -> set:
    if not path.exists():
        return set()
    return {m.group(1) for m in re.finditer(r'youtube\.com/(?:watch\?v=|shorts/|vi/)([a-zA-Z0-9_-]{11})', path.read_text(encoding="utf-8", errors="ignore"))}


def _count_cards(path: Path) -> int:
    if not path.exists():
        return 0
    c = path.read_text(encoding="utf-8", errors="ignore")
    return c.count('class="short-card"') + c.count('class="journal-card"') + c.count('class="ecosse-jcard"')


def _main_card(v, date_label, journal_href=""):
    href = journal_href or v["url"]
    tgt = "" if journal_href else ' target="_blank"'
    d = v.get("description","")[:120]
    if len(d)==120: d+="..."
    return f'''
        <!-- Auto-publish {datetime.now().strftime('%Y-%m-%d %H:%M')} -->
        <div class="short-card">
            <div class="short-thumb"><span class="short-badge">{escape(date_label)}</span><a href="{escape(href)}"{tgt}><img src="{escape(v['thumb'])}" alt="{escape(v['title'])}" loading="lazy"></a></div>
            <div class="short-body"><h3>{escape(v['title'])}</h3><p>{escape(d) if d else "Nouvelle video du voyage."}</p><a href="{escape(href)}"{tgt} class="btn btn-dark">Voir le short</a></div>
        </div>
'''

def _journal_card(v, date_label):
    d = v.get("description","")[:250]
    if len(d)==250: d+="..."
    return f'''
        <!-- Auto-publish {datetime.now().strftime('%Y-%m-%d %H:%M')} -->
        <div class="journal-card">
            <div class="journal-thumb"><span class="journal-badge">{escape(date_label)}</span><a href="{escape(v['url'])}" target="_blank"><img src="{escape(v['thumb'])}" alt="{escape(v['title'])}" loading="lazy"></a></div>
            <div class="journal-body"><h3>{escape(v['title'])}</h3><p>{escape(d) if d else "Nouvelle video du voyage."}</p><a href="{escape(v['url'])}" target="_blank" style="display:inline-block;padding:.55rem 1.2rem;background:#1a1a1a;color:#fff;border-radius:8px;font-size:.85rem;font-weight:600;text-decoration:none;">Voir la video</a></div>
        </div>
'''


def _inject_main(path, html):
    c = path.read_text(encoding="utf-8")
    for p in [r'(<div[^>]*class="[^"]*journal-preview[^"]*"[^>]*>)', r'(<div[^>]*class="[^"]*jnl-grid[^"]*"[^>]*>)']:
        if re.search(p, c, re.IGNORECASE):
            path.write_text(re.sub(p, r'\1\n'+html, c, count=1, flags=re.IGNORECASE), encoding="utf-8")
            return True
    return False

def _inject_journal(path, html):
    c = path.read_text(encoding="utf-8")
    for p in [r'(<div[^>]*class="[^"]*section-kicker[^"]*"[^>]*>[^<]*</div>\s*)', r'(<section[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)', r'(<div[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)', r'(ENTR.ES DU JOURNAL</[^>]+>\s*)', r'(<div[^>]*id="journal-content"[^>]*>)']:
        if re.search(p, c, re.IGNORECASE):
            path.write_text(re.sub(p, r'\1\n'+html, c, count=1, flags=re.IGNORECASE), encoding="utf-8")
            return True
    for mk in ['class="journal-card"', 'class="journal-empty"']:
        if mk in c:
            i = c.index(mk); ts = c.rfind('<',0,i)
            if ts >= 0:
                path.write_text(c[:ts]+html+'\n'+c[ts:], encoding="utf-8")
                return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    slug = cfg["slug"]
    main_p = Path(cfg.get("main_page", f"roadtrips/{slug}.html"))
    journal_p = Path(cfg.get("journal_page", f"roadtrips/{slug}-journal.html"))
    mx = int(cfg.get("max_main_cards", 3))
    print(f"Slug: {slug} | Playlist: {cfg.get('playlist_name','')} ({cfg['playlist_id']})")
    if not main_p.exists() or not journal_p.exists():
        print(f"ERREUR: fichiers manquants main={main_p.exists()} journal={journal_p.exists()}")
        sys.exit(1)
    svc = _get_youtube_service()
    vids = _fetch_playlist_videos(svc, cfg["playlist_id"])
    shorts = [v for v in vids if v.get("is_short")]
    known = _known_ids(main_p) | _known_ids(journal_p)
    new = [v for v in shorts if v["video_id"] not in known]
    print(f"Playlist: {len(vids)} videos, {len(shorts)} shorts, {len(known)} deja injectees, {len(new)} nouvelles")
    if not new:
        print("Rien de nouveau.")
        sys.exit(0)
    mc = _count_cards(main_p)
    for v in new:
        dl = v.get("date_label") or _date_fr()
        print(f"-> {v['title']} ({v['video_id']})")
        if _inject_journal(journal_p, _journal_card(v, dl)):
            print(f"   Journal OK")
        if mc < mx:
            if _inject_main(main_p, _main_card(v, dl, f"/roadtrips/{slug}-journal.html")):
                mc += 1
                print(f"   Page principale ({mc}/{mx}) OK")
        else:
            print(f"   Page principale PLEINE ({mc}/{mx})")
    print(f"Termine: {len(new)} video(s)")

if __name__ == "__main__":
    main()
