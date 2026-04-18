#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_noindex_tests.py — Ajoute <meta name="robots" content="noindex,
nofollow"> dans le <head> des pages de test, maquettes et cadrage
interne. Idempotent : ne touche pas les pages ayant deja noindex.

Liste des pages ciblees (resultat d'audit 2026-04-18) :
  - roadtrips/road-trip-moto-test-2026-3.html
  - roadtrips/road-trip-moto-test-2026-3-journal.html
  - roadtrips/maquette_capnord_complete_v2.html
  - LCDMH_Cadrage_Projet.html (interne, deja Disallow dans robots.txt)

Appel :
  python3 add_noindex_tests.py [--root .] [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TARGETS = (
    "roadtrips/road-trip-moto-test-2026-3.html",
    "roadtrips/road-trip-moto-test-2026-3-journal.html",
    "roadtrips/maquette_capnord_complete_v2.html",
    "LCDMH_Cadrage_Projet.html",
)

HEAD_OPEN = re.compile(r"<head(\s[^>]*)?>", re.IGNORECASE)
NOINDEX_META = '\n<meta name="robots" content="noindex, nofollow">\n'
ROBOTS_META_RE = re.compile(
    r'<meta\s+name\s*=\s*"robots"\s+content\s*=\s*"([^"]*)"',
    re.IGNORECASE,
)


def patch(path: Path, dry_run: bool = False) -> tuple[bool, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"err lecture ({exc})"

    m = ROBOTS_META_RE.search(raw)
    if m:
        val = m.group(1).lower()
        if "noindex" in val:
            return False, "skip (noindex deja present)"
        # Replace existing robots meta with noindex
        new_meta = '<meta name="robots" content="noindex, nofollow"'
        new = raw[:m.start()] + new_meta + raw[m.end():]
    else:
        head = HEAD_OPEN.search(raw)
        if not head:
            return False, "skip (pas de <head>)"
        new = raw[:head.end()] + NOINDEX_META + raw[head.end():]

    if dry_run:
        return True, "OK (dry-run)"
    path.write_text(new, encoding="utf-8", newline="\n")
    return True, "OK"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    ok = 0
    for rel in TARGETS:
        p = root / rel
        if not p.exists():
            print(f"  [ ] {rel}  ->  fichier introuvable")
            continue
        changed, msg = patch(p, dry_run=args.dry_run)
        print(f"  {'[+]' if changed else '[ ]'} {rel}  ->  {msg}")
        if changed:
            ok += 1

    print()
    print(f"Resume : {ok}/{len(TARGETS)} pages patchees noindex.")
    if args.dry_run:
        print("(dry-run : aucune ecriture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
