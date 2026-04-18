#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_images_webp.py — Convertit tous les JPG/PNG de /images/ et
/articles/images/ en WebP (qualite 85), en conservant l'original.
Idempotent.

Pre-requis : pip install Pillow

Appel :
  python3 convert_images_webp.py [--root .] [--quality 85] [--dry-run]
                                 [--dirs images,articles/images]

Strategie :
  - Pour chaque *.jpg/jpeg/png, on cree le WebP correspondant a cote
    (ex: image.jpg -> image.webp). L'original reste.
  - On patch PAS les <img> des pages HTML automatiquement (risque de
    casser un cache / un layout). Plutot, on genere un CSV listant les
    images converties pour que tu modifies ensuite chaque page en
    passant a <picture><source srcset=".webp"><img src=".jpg"></picture>.

Sortie :
  - Liste des conversions
  - Fichier AUDIT_INGENIEUR_SEO/journaux/conversions_webp.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERR: pip install Pillow", file=sys.stderr)
    sys.exit(2)


def convert(src: Path, quality: int, dry_run: bool) -> tuple[bool, int, str]:
    """Retourne (ok, octets_economisees, msg)."""
    dst = src.with_suffix(".webp")
    if dst.exists():
        return False, 0, "skip (.webp deja present)"
    if dry_run:
        return True, 0, "OK (dry-run)"
    try:
        im = Image.open(src)
        # On conserve la transparence pour les PNG
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            im.save(dst, "WEBP", quality=quality, method=6)
        else:
            im = im.convert("RGB")
            im.save(dst, "WEBP", quality=quality, method=6)
    except Exception as exc:
        return False, 0, f"err ({exc})"
    saved = src.stat().st_size - dst.stat().st_size
    return True, saved, f"OK ({src.stat().st_size//1024}k -> {dst.stat().st_size//1024}k)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--quality", type=int, default=85)
    ap.add_argument("--dirs", default="images,articles/images,roadtrips/images")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    dirs = [d.strip() for d in args.dirs.split(",") if d.strip()]

    journal_path = root / "AUDIT_INGENIEUR_SEO" / "journaux" / "conversions_webp.csv"
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    total_ok = 0
    total_saved = 0
    rows = [("src", "dst", "ko_economises", "status")]

    for d in dirs:
        base = root / d
        if not base.exists():
            print(f"  [SKIP] {d} (inexistant)")
            continue
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            for src in base.rglob(ext):
                ok, saved, msg = convert(src, args.quality, args.dry_run)
                rel_src = src.relative_to(root)
                rel_dst = src.with_suffix(".webp").relative_to(root)
                print(f"  {'[+]' if ok else '[ ]'} {rel_src}  ->  {msg}")
                if ok:
                    total_ok += 1
                    total_saved += saved
                rows.append((str(rel_src), str(rel_dst), saved // 1024, msg))

    with journal_path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)

    print()
    print(f"Resume : {total_ok} images converties, "
          f"{total_saved // 1024} Ko economises.")
    print(f"Journal : {journal_path.relative_to(root)}")
    if args.dry_run:
        print("(dry-run : aucune ecriture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
