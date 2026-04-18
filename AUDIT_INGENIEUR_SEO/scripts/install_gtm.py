#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_gtm.py — Installe Google Tag Manager (GTM-MVJK8VFG) sur toutes
les pages HTML du site LCDMH.

Regles (non destructif, idempotent) :
  - Insere le snippet GTM head juste apres la balise <head> (1re occurrence)
  - Insere le snippet GTM body juste apres la balise <body> (1re occurrence)
  - Laisse intact le snippet gtag G-7GC33KPRMS existant (transition)
  - Skip tout fichier qui contient deja GTM-MVJK8VFG

Appel :
  python3 install_gtm.py [--dry-run] [--root CHEMIN]

Sortie :
  Log ligne par ligne + resume final ("N fichiers patches / M sautes").
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GTM_ID = "GTM-MVJK8VFG"

GTM_HEAD = (
    "\n<!-- Google Tag Manager -->\n"
    "<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':\n"
    "new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],\n"
    "j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=\n"
    "'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);\n"
    "})(window,document,'script','dataLayer','" + GTM_ID + "');</script>\n"
    "<!-- End Google Tag Manager -->\n"
)

GTM_BODY = (
    "\n<!-- Google Tag Manager (noscript) -->\n"
    "<noscript><iframe src=\"https://www.googletagmanager.com/ns.html?id=" + GTM_ID + "\"\n"
    "height=\"0\" width=\"0\" style=\"display:none;visibility:hidden\"></iframe></noscript>\n"
    "<!-- End Google Tag Manager (noscript) -->\n"
)

HEAD_OPEN = re.compile(r"<head(\s[^>]*)?>", re.IGNORECASE)
BODY_OPEN = re.compile(r"<body(\s[^>]*)?>", re.IGNORECASE)

# Dossiers a scanner, relatif a root
SCAN_DIRS = [".", "articles"]

# Fichiers a exclure (tests, maquettes, gabarits)
EXCLUDE_SUBSTR = (
    "LCDMH_Cadrage_Projet.html",
    "nav.html",           # nav injectee, pas de head/body propre
    "/_apercu_design_premium/",
    "/_audit/",
    "/_sauvegarde_",
)


def should_skip(path: Path, root: Path) -> bool:
    rel = str(path.relative_to(root)).replace("\\", "/")
    for token in EXCLUDE_SUBSTR:
        if token.strip("/") in rel:
            return True
    return False


def patch_file(path: Path, dry_run: bool = False) -> tuple[bool, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "skip (non-utf8)"

    if GTM_ID in raw:
        return False, "skip (deja patche)"

    head_match = HEAD_OPEN.search(raw)
    body_match = BODY_OPEN.search(raw)

    if not head_match or not body_match:
        return False, "skip (pas de <head> ou <body>)"

    new = (
        raw[: head_match.end()]
        + GTM_HEAD
        + raw[head_match.end(): body_match.end()]
        + GTM_BODY
        + raw[body_match.end():]
    )

    if dry_run:
        return True, "OK (dry-run)"

    path.write_text(new, encoding="utf-8", newline="\n")
    return True, "OK"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".",
                    help="Racine du repo LCDMH (def: .)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Ne rien ecrire, juste loguer")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERR: root introuvable : {root}", file=sys.stderr)
        return 2

    targets: list[Path] = []
    for d in SCAN_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in base.glob("*.html"):
            if should_skip(p, root):
                continue
            targets.append(p)

    patched = 0
    skipped = 0
    for p in sorted(targets):
        ok, msg = patch_file(p, dry_run=args.dry_run)
        rel = p.relative_to(root)
        print(f"  {'[+]' if ok else '[ ]'} {rel}  ->  {msg}")
        if ok:
            patched += 1
        else:
            skipped += 1

    print()
    print(f"Resume : {patched} patchees / {skipped} sautees / "
          f"{len(targets)} scannees.")
    print(f"GTM ID : {GTM_ID}")
    if args.dry_run:
        print("(dry-run : aucune ecriture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
