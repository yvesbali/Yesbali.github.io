#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_lazy_loading.py - Ajoute loading="lazy" aux <img> sous le fold.

Règle
-----
- La première image du body (souvent le hero/LCP) ne doit PAS être lazy
  (ça pénalise LCP, Core Web Vital).
- Toutes les suivantes devraient avoir loading="lazy".

Principe
--------
Pour chaque page, on parse les <img> dans l'ordre. On skip les N premières
images (par défaut 1) et on ajoute loading="lazy" aux suivantes si elles
n'en ont pas déjà.

Idempotent : ne touche pas les <img> qui ont déjà un attribut loading="...".
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[2]

SNIPPETS = {"nav.html", "header.html", "footer.html", "widget-roadtrip-snippet.html"}
EXCLUDED_DIR_PARTS = {
    "AUDIT_INGENIEUR_SEO", ".git", "_archive", "node_modules", "build",
    "_review", "_apercu_design_premium", "data",
}

IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
LOADING_RE = re.compile(r'\bloading\s*=', re.IGNORECASE)


def collect_pages(root: Path) -> list[Path]:
    pages = []
    for p in root.rglob("*.html"):
        if any(part in EXCLUDED_DIR_PARTS for part in p.parts):
            continue
        if p.name in SNIPPETS:
            continue
        pages.append(p)
    return sorted(pages)


def add_lazy(tag: str) -> str:
    if tag.endswith("/>"):
        return tag[:-2].rstrip() + ' loading="lazy" />'
    return tag[:-1].rstrip() + ' loading="lazy">'


def patch_page(path: Path, skip_first: int, dry_run: bool) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # Ne scanner que le body
    body_m = re.search(r"<body\b", text, re.IGNORECASE)
    if not body_m:
        return 0, 0
    body_start = body_m.start()
    head = text[:body_start]
    body = text[body_start:]

    count = 0
    idx_in_body = [0]

    def repl(m: re.Match) -> str:
        nonlocal count
        idx_in_body[0] += 1
        tag = m.group(0)
        if idx_in_body[0] <= skip_first:
            return tag
        if LOADING_RE.search(tag):
            return tag
        count += 1
        return add_lazy(tag)

    new_body = IMG_RE.sub(repl, body)
    total = idx_in_body[0]

    if count and not dry_run:
        path.write_text(head + new_body, encoding="utf-8")
    return total, count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-first", type=int, default=1, help="nb d'images au-dessus du fold à ne pas rendre lazy")
    parser.add_argument("--only", help="filtre sous-chemin")
    parser.add_argument("--root", default=str(SITE_ROOT))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    pages = collect_pages(root)
    if args.only:
        pages = [p for p in pages if args.only in str(p.relative_to(root)).replace("\\", "/")]

    touched = 0
    total_imgs = 0
    total_lazy = 0
    for p in pages:
        total, count = patch_page(p, args.skip_first, args.dry_run)
        if count:
            touched += 1
        total_imgs += total
        total_lazy += count
        if count:
            rel = p.relative_to(root)
            tag = "[DRY]" if args.dry_run else "[FIX]"
            print(f"{tag} {rel}  ({count} images + lazy, skip {args.skip_first})")

    print()
    print(f"Résumé : {touched} pages, {total_lazy} <img> rendues lazy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
