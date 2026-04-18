#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_image_dimensions.py - Ajoute width/height aux <img> qui n'en ont pas.

Pourquoi
--------
Une image sans width/height force le navigateur à faire le layout DEUX fois,
ce qui fait sauter les blocs quand l'image charge (CLS = Cumulative Layout Shift).
C'est l'un des trois Core Web Vitals (avec LCP et INP). Google pénalise les
pages avec un CLS élevé.

Principe
--------
  1. Pour chaque page HTML publique, lister les <img src=...> qui n'ont PAS
     width+height
  2. Résoudre le src sur disque, lire les dimensions réelles via PIL
  3. Injecter width="W" height="H" juste avant la fermeture du tag
  4. Idempotent : ne fait rien sur les <img> qui ont déjà width ET height

Usage
-----
    python add_image_dimensions.py --dry-run
    python add_image_dimensions.py
    python add_image_dimensions.py --only articles/
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERREUR : Pillow requis (pip install Pillow)", file=sys.stderr)
    sys.exit(2)

SITE_ROOT = Path(__file__).resolve().parents[2]

SNIPPETS = {"nav.html", "header.html", "footer.html", "widget-roadtrip-snippet.html"}
EXCLUDED_DIR_PARTS = {
    "AUDIT_INGENIEUR_SEO",
    ".git",
    "_archive",
    "node_modules",
    "build",
    "_review",
    "_apercu_design_premium",
    "data",
}

IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
SRC_RE = re.compile(r'''\bsrc\s*=\s*["']([^"']+)["']''', re.IGNORECASE)
WIDTH_RE = re.compile(r'\bwidth\s*=', re.IGNORECASE)
HEIGHT_RE = re.compile(r'\bheight\s*=', re.IGNORECASE)


def collect_pages(root: Path, only: str | None) -> list[Path]:
    pages: list[Path] = []
    for p in root.rglob("*.html"):
        if any(part in EXCLUDED_DIR_PARTS for part in p.parts):
            continue
        if p.name in SNIPPETS:
            continue
        if only and only not in str(p.relative_to(root)).replace("\\", "/"):
            continue
        pages.append(p)
    return sorted(pages)


def resolve_src(src: str, html_path: Path, root: Path) -> Path | None:
    src = src.strip().split("?")[0].split("#")[0]
    if src.startswith(("http://", "https://", "data:")):
        return None
    if src.startswith("/"):
        return (root / src.lstrip("/")).resolve()
    return (html_path.parent / src).resolve()


def get_dimensions(img_path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(img_path) as im:
            return im.size  # (w, h)
    except Exception:
        return None


def inject_wh(tag: str, w: int, h: int) -> str:
    # Insère width/height juste avant le '>' final, après le dernier attribut
    if tag.endswith("/>"):
        body = tag[:-2].rstrip()
        return f'{body} width="{w}" height="{h}" />'
    if tag.endswith(">"):
        body = tag[:-1].rstrip()
        return f'{body} width="{w}" height="{h}">'
    return tag


def patch_page(path: Path, root: Path, dry_run: bool) -> tuple[int, int, int, list[str]]:
    """Retourne (total_imgs, modifiees, echouees, log)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    total = 0
    modified = 0
    failed = 0
    log: list[str] = []

    def replace_img(m: re.Match) -> str:
        nonlocal total, modified, failed
        tag = m.group(0)
        total += 1
        if WIDTH_RE.search(tag) and HEIGHT_RE.search(tag):
            return tag
        src_m = SRC_RE.search(tag)
        if not src_m:
            return tag
        src = src_m.group(1)
        candidate = resolve_src(src, path, root)
        if candidate is None or not candidate.exists():
            failed += 1
            log.append(f"  !! src introuvable : {src}")
            return tag
        dims = get_dimensions(candidate)
        if dims is None:
            failed += 1
            log.append(f"  !! dimensions illisibles : {src}")
            return tag
        w, h = dims
        modified += 1
        log.append(f"  ++ {src}  → {w}×{h}")
        return inject_wh(tag, w, h)

    new_text = IMG_RE.sub(replace_img, text)

    if modified and not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return total, modified, failed, log


def main() -> int:
    parser = argparse.ArgumentParser(description="Injecte width/height manquants sur les <img>")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", help="filtre sous-chemin (ex: articles/)")
    parser.add_argument("--root", default=str(SITE_ROOT))
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    pages = collect_pages(root, args.only)

    pages_touched = 0
    total_modified = 0
    total_failed = 0

    for p in pages:
        total, modified, failed, log = patch_page(p, root, args.dry_run)
        if modified == 0 and failed == 0:
            continue
        if modified:
            pages_touched += 1
        total_modified += modified
        total_failed += failed
        rel = p.relative_to(root)
        tag = "[DRY]" if args.dry_run else "[FIX]"
        print(f"{tag} {rel}  ({modified} patch, {failed} echec sur {total} img)")
        if args.verbose:
            for l in log:
                print(l)

    print()
    print(f"Résumé : {pages_touched} pages touchées · {total_modified} <img> patchées · {total_failed} échecs")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
