#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compress_heavy_images.py - Recompresse les images > 500 KiB in-place.

Règle section 12.5.8 du cadrage : images ≤ 500 KiB sur disque.
Impact direct sur LCP (Largest Contentful Paint), un Core Web Vital.

Principe
--------
  1. Scanner toutes les images du site (jpg, jpeg, png, webp)
  2. Pour chaque > 500 KiB :
     - JPG/JPEG → recompresser qualité 82, progressif, optimize=True
     - PNG     → convertir en JPG qualité 82 (si pas de transparence) ou optimize_level=9
     - WebP    → recompresser qualité 80
  3. Garder les dimensions identiques, sauvegarder in-place
  4. Écrire un rapport avec avant/après

Usage
-----
    python compress_heavy_images.py --dry-run
    python compress_heavy_images.py
    python compress_heavy_images.py --target 450   # seuil de recompression en KiB
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERREUR : Pillow requis (pip install Pillow)", file=sys.stderr)
    sys.exit(2)

SITE_ROOT = Path(__file__).resolve().parents[2]

EXCLUDED_DIR_PARTS = {
    "AUDIT_INGENIEUR_SEO",
    ".git",
    "_archive",
    "node_modules",
    "build",
    "_review",
    "_apercu_design_premium",
    "data",  # copies historiques Facebook, ne servent pas au site
}

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def collect_images(root: Path) -> list[Path]:
    out = []
    for p in root.rglob("*"):
        if p.suffix.lower() not in IMG_EXT:
            continue
        if any(part in EXCLUDED_DIR_PARTS for part in p.parts):
            continue
        out.append(p)
    return out


SKIP_NAMES = {"favicon.png", "favicon.ico"}


def _compress_to_buf(im: Image.Image, ext: str) -> tuple[bytes, str]:
    """Compresse en mémoire et retourne (bytes, method_label)."""
    from io import BytesIO
    buf = BytesIO()
    if ext in (".jpg", ".jpeg"):
        im2 = im.convert("RGB")
        im2.save(buf, "JPEG", quality=82, progressive=True, optimize=True)
        return buf.getvalue(), "JPEG q=82 progressive"
    if ext == ".png":
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        if has_alpha:
            im.save(buf, "PNG", optimize=True)
            return buf.getvalue(), "PNG optimisé (alpha)"
        # PNG sans alpha : on quantise pour réduire la taille sans changer de format
        im2 = im.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
        im2.save(buf, "PNG", optimize=True)
        return buf.getvalue(), "PNG palette 256c optimisé"
    if ext == ".webp":
        im.save(buf, "WEBP", quality=78, method=6)
        return buf.getvalue(), "WebP q=78"
    return b"", "type non traité"


def compress_one(path: Path, dry_run: bool) -> tuple[int, int, str]:
    """Retourne (taille_avant, taille_apres, method)."""
    size_before = path.stat().st_size
    ext = path.suffix.lower()

    if path.name in SKIP_NAMES:
        return size_before, size_before, "SKIP (fichier spécial)"

    try:
        im = Image.open(path)
    except Exception as e:
        return size_before, size_before, f"ERREUR ouverture : {e}"

    try:
        compressed, method = _compress_to_buf(im, ext)
    except Exception as e:
        return size_before, size_before, f"ERREUR compression : {e}"

    size_after = len(compressed)
    # Filet de sécurité : on n'écrit JAMAIS si le résultat est plus gros
    if size_after >= size_before:
        return size_before, size_before, f"SKIP ({method} grossirait : {size_before//1024}→{size_after//1024} KiB)"

    if not dry_run:
        # Backup
        backup = path.with_suffix(path.suffix + ".orig")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
        path.write_bytes(compressed)

    return size_before, size_after, method


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target", type=int, default=500, help="seuil KiB au-dessus duquel on compresse")
    parser.add_argument("--root", default=str(SITE_ROOT))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    imgs = collect_images(root)
    threshold = args.target * 1024
    heavy = [p for p in imgs if p.stat().st_size > threshold]
    heavy.sort(key=lambda p: -p.stat().st_size)

    print(f"{len(imgs)} images scannées, {len(heavy)} > {args.target} KiB")

    total_before = 0
    total_after = 0
    for p in heavy:
        before, after, method = compress_one(p, args.dry_run)
        total_before += before
        total_after += after
        rel = p.relative_to(root)
        saved = before - after
        pct = 100 * saved / before if before else 0
        tag = "[DRY]" if args.dry_run else "[FIX]"
        print(f"{tag} {rel}  {before//1024}→{after//1024} KiB (-{pct:.0f}%)  [{method}]")

    print()
    saved_total = total_before - total_after
    print(f"Total : {total_before//1024} → {total_after//1024} KiB  (gain {saved_total//1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
