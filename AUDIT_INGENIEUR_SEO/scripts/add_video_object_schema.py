#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_video_object_schema.py — Pour chaque page contenant un embed YouTube,
inject un schema VideoObject (Schema.org) base sur les VRAIES metadonnees
de la video recuperees via l'API YouTube Data v3.

Pre-requis :
  pip install google-api-python-client
  Variable env YT_API_KEY = cle API YouTube Data v3 (console.cloud.google.com)
  OU YT_TOKEN_ANALYTICS si OAuth deja configure.

Garanties :
  - Aucune donnee inventee : si l'API ne renvoie pas la video, on log et
    on saute la page.
  - Idempotent : si un VideoObject pour la meme videoId existe deja, on
    saute.
  - Ecrit le schema juste avant </head>.

Appel :
  YT_API_KEY=AIza... python3 add_video_object_schema.py [--root .] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

YT_ID_RE = re.compile(r'(?:youtube\.com/embed/|youtu\.be/)([A-Za-z0-9_-]{11})')
HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)


def get_youtube_client():
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("ERR: pip install google-api-python-client", file=sys.stderr)
        sys.exit(2)
    api_key = os.environ.get("YT_API_KEY") or os.environ.get(
        "YOUTUBE_API_KEY"
    )
    if not api_key:
        print("ERR: variable YT_API_KEY manquante.", file=sys.stderr)
        sys.exit(2)
    return build("youtube", "v3", developerKey=api_key)


def fetch_videos(client, video_ids: list[str]) -> dict:
    """Retourne dict {videoId: snippet+contentDetails+statistics}."""
    out = {}
    # API limite a 50 ids par appel
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i: i + 50]
        resp = client.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(batch),
        ).execute()
        for item in resp.get("items", []):
            out[item["id"]] = item
    return out


def build_video_object(item: dict) -> dict:
    snip = item["snippet"]
    details = item["contentDetails"]
    stats = item.get("statistics", {})
    vid = item["id"]
    return {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": snip["title"],
        "description": snip.get("description", "")[:500],
        "thumbnailUrl": [
            f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
        ],
        "uploadDate": snip["publishedAt"],
        "duration": details.get("duration", "PT0S"),
        "contentUrl": f"https://www.youtube.com/watch?v={vid}",
        "embedUrl": f"https://www.youtube.com/embed/{vid}",
        "publisher": {
            "@type": "Organization",
            "name": "LCDMH",
            "logo": {
                "@type": "ImageObject",
                "url": "https://lcdmh.com/apple-touch-icon.png",
            },
        },
        "interactionStatistic": {
            "@type": "InteractionCounter",
            "interactionType": {"@type": "WatchAction"},
            "userInteractionCount": int(stats.get("viewCount", 0)),
        },
    }


def patch(path: Path, new_blocks: list[str], dry_run: bool = False) -> bool:
    raw = path.read_text(encoding="utf-8")
    head_close = HEAD_CLOSE_RE.search(raw)
    if not head_close:
        return False
    inject = "\n" + "\n".join(
        f'<script type="application/ld+json">\n{b}\n</script>'
        for b in new_blocks
    ) + "\n"
    new = raw[:head_close.start()] + inject + raw[head_close.start():]
    if dry_run:
        return True
    path.write_text(new, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    # 1. Inventaire
    pages_videos: dict[Path, list[str]] = {}
    all_ids: set[str] = set()
    for p in sorted(list(root.glob("*.html")) + list((root / "articles").glob("*.html"))):
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        ids = list(dict.fromkeys(YT_ID_RE.findall(t)))
        if not ids:
            continue
        # Skip ids deja en VideoObject sur la meme page
        existing = re.findall(r'"contentUrl":\s*"https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})"', t)
        ids = [i for i in ids if i not in existing]
        if ids:
            pages_videos[p] = ids
            all_ids.update(ids)

    print(f"  {len(pages_videos)} pages a traiter / {len(all_ids)} videos uniques.")
    if not pages_videos:
        return 0

    # 2. Fetch metadata
    client = get_youtube_client()
    videos = fetch_videos(client, sorted(all_ids))
    print(f"  {len(videos)} videos remontees par l'API.")
    missing = sorted(all_ids - set(videos.keys()))
    if missing:
        print(f"  ATTENTION : {len(missing)} videos introuvables (privees, supprimees ?) : {missing}")

    # 3. Patch
    patched = 0
    for p, ids in pages_videos.items():
        blocks = []
        for vid in ids:
            if vid not in videos:
                continue
            schema = build_video_object(videos[vid])
            blocks.append(json.dumps(schema, ensure_ascii=False, indent=2))
        if not blocks:
            continue
        ok = patch(p, blocks, dry_run=args.dry_run)
        rel = p.relative_to(root)
        if ok:
            patched += 1
            print(f"  [+] {rel}  ->  {len(blocks)} VideoObject ajoutes")
        else:
            print(f"  [ ] {rel}  ->  pas de </head>")

    print()
    print(f"Resume : {patched}/{len(pages_videos)} pages enrichies.")
    if args.dry_run:
        print("(dry-run : aucune ecriture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
