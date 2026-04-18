#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_picture_tags.py
=====================
Wrap <img src="X.jpg|X.png"> with <picture><source srcset="X.webp" type="image/webp"><img ...></picture>
ONLY if X.webp exists on disk at the resolved path. Idempotent (skips images already inside a <picture>).

Pre-requis : aucun (stdlib only).

Appel :
  python3 patch_picture_tags.py [--root .] [--dry-run] [--only path/to/file.html ...]

Strategie :
  - Parcourt tous les *.html (exclut _review, _archive, AUDIT_INGENIEUR_SEO, backup, .git, node_modules)
  - Pour chaque <img src="X">, calcule le chemin .webp equivalent
  - Verifie que le .webp existe sur disque (sinon skip)
  - Wrap avec <picture> SAUF si l'img est deja dans un <picture> (heuristique : pas de </picture>
    sans <picture> ouvert avant, et pas de <source srcset="X.webp" juste avant)
  - Conserve TOUS les attributs de l'<img> d'origine (alt, class, loading, width, height, etc.)

Sortie :
  - Liste des patches par fichier
  - Compteurs : fichiers modifies, balises <img> wrappees, balises sautees
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {"_review", "_archive", "AUDIT_INGENIEUR_SEO", "backup", "backup_originaux",
             "node_modules", ".git", "_apercu_design_premium", "data"}

# Match <img ...src="X.jpg|jpeg|png"...>  (case-insensitive)
IMG_RE = re.compile(
    r'<img\b([^>]*?)\bsrc=(["\'])([^"\']+\.(?:jpe?g|png))\2([^>]*)>',
    re.IGNORECASE,
)


def resolve_src_to_disk(src: str, html_path: Path, repo_root: Path) -> Path | None:
    """Resolve an HTML src attribute to an absolute disk path."""
    src = src.split("?")[0].split("#")[0]
    if src.startswith("http://") or src.startswith("https://") or src.startswith("//"):
        return None  # external
    if src.startswith("/"):
        return repo_root / src.lstrip("/")
    return (html_path.parent / src).resolve()


def is_inside_picture(content: str, img_start: int) -> bool:
    """Return True if the <img> at img_start is already inside a <picture> block."""
    # Find the most recent <picture or </picture before img_start
    open_idx = content.rfind("<picture", 0, img_start)
    close_idx = content.rfind("</picture>", 0, img_start)
    return open_idx > close_idx  # open without matching close = we are inside


def patch_file(path: Path, repo_root: Path, dry_run: bool) -> tuple[int, int, int]:
    """Return (wrapped, skipped_already_wrapped, skipped_no_webp)."""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return (0, 0, 0)

    new_parts = []
    last = 0
    wrapped = 0
    skipped_wrapped = 0
    skipped_no_webp = 0

    for m in IMG_RE.finditer(content):
        new_parts.append(content[last:m.start()])
        full = m.group(0)
        before_attrs = m.group(1) or ""
        quote = m.group(2)
        src = m.group(3)
        after_attrs = m.group(4) or ""

        if is_inside_picture(content, m.start()):
            new_parts.append(full)
            skipped_wrapped += 1
            last = m.end()
            continue

        disk_src = resolve_src_to_disk(src, path, repo_root)
        if disk_src is None:
            new_parts.append(full)
            last = m.end()
            continue

        # Compute .webp counterpart
        if src.lower().endswith((".jpg", ".jpeg")):
            webp_src = re.sub(r"\.jpe?g$", ".webp", src, flags=re.IGNORECASE)
        else:
            webp_src = re.sub(r"\.png$", ".webp", src, flags=re.IGNORECASE)

        disk_webp = resolve_src_to_disk(webp_src, path, repo_root)
        if disk_webp is None or not disk_webp.exists():
            new_parts.append(full)
            skipped_no_webp += 1
            last = m.end()
            continue

        # Build <picture> wrapper, preserving original <img> verbatim
        wrapper = (
            f'<picture>'
            f'<source srcset={quote}{webp_src}{quote} type="image/webp">'
            f'{full}'
            f'</picture>'
        )
        new_parts.append(wrapper)
        wrapped += 1
        last = m.end()

    new_parts.append(content[last:])
    new_content = "".join(new_parts)

    if wrapped > 0 and new_content != content and not dry_run:
        path.write_text(new_content, encoding="utf-8")

    return (wrapped, skipped_wrapped, skipped_no_webp)


def walk_html(repo_root: Path, only: list[Path] | None):
    if only:
        for p in only:
            if p.exists() and p.suffix.lower() == ".html":
                yield p
        return
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if f.endswith(".html"):
                yield Path(root) / f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", help="Specific HTML files to patch")
    args = ap.parse_args()

    repo_root = Path(args.root).resolve()
    only_paths = [Path(p).resolve() for p in args.only] if args.only else None

    total_files_modified = 0
    total_wrapped = 0
    total_skipped_wrapped = 0
    total_skipped_no_webp = 0

    for html in walk_html(repo_root, only_paths):
        wrapped, skip_w, skip_nw = patch_file(html, repo_root, args.dry_run)
        if wrapped > 0:
            total_files_modified += 1
            rel = html.relative_to(repo_root) if html.is_relative_to(repo_root) else html
            tag = "[+]" if not args.dry_run else "[~]"
            print(f"  {tag} {rel}  ({wrapped} img wrap)")
        total_wrapped += wrapped
        total_skipped_wrapped += skip_w
        total_skipped_no_webp += skip_nw

    print()
    print(f"Files modified : {total_files_modified}")
    print(f"<img> wrapped  : {total_wrapped}")
    print(f"Skipped (deja dans <picture>) : {total_skipped_wrapped}")
    print(f"Skipped (pas de .webp dispo)  : {total_skipped_no_webp}")
    if args.dry_run:
        print("(dry-run : aucune ecriture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
