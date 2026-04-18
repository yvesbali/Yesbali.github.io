#!/usr/bin/env python3
"""
fix_uploaddate_timezone.py

Corrige toutes les valeurs `"uploadDate": "YYYY-MM-DD"` en
`"uploadDate": "YYYY-MM-DDT00:00:00Z"` pour satisfaire l'exigence
Google Search Console :
  - "Valeur de date et heure incorrecte pour uploadDate"
  - "Il manque le fuseau horaire a la propriete uploadDate"

Choix honnete : T00:00:00Z (UTC minuit) au lieu d'inventer une heure
reelle d'upload YouTube dont on n'a pas la donnee exacte cote site.

Idempotent : skip les dates qui ont deja un T ou un timezone.

Usage :
  cd F:\\LCDMH_GitHub_Audit
  python AUDIT_INGENIEUR_SEO/scripts/fix_uploaddate_timezone.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Match "uploadDate": "YYYY-MM-DD" (sans T ni timezone deja present)
PATTERN = re.compile(
    r'("uploadDate"\s*:\s*")'    # prefix : "uploadDate": "
    r'(\d{4}-\d{2}-\d{2})'       # YYYY-MM-DD
    r'(")',                      # closing quote
)


def fix_file(path: Path) -> tuple[int, int]:
    """Returns (matches_found, substitutions_made)."""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"[SKIP encodage] {path}")
        return (0, 0)

    matches = PATTERN.findall(content)
    if not matches:
        return (0, 0)

    new_content = PATTERN.sub(r'\g<1>\g<2>T00:00:00Z\g<3>', content)
    if new_content == content:
        return (len(matches), 0)

    path.write_text(new_content, encoding="utf-8")
    return (len(matches), len(matches))


def main() -> int:
    html_files = list(REPO_ROOT.rglob("*.html"))
    # Exclure node_modules, _archive, .git si presents
    html_files = [
        p for p in html_files
        if not any(part.startswith(".") or part in ("node_modules", "_archive")
                   for part in p.parts)
    ]

    total_matches = 0
    total_fixed = 0
    files_touched = 0

    for path in html_files:
        matches, fixed = fix_file(path)
        if matches:
            total_matches += matches
            total_fixed += fixed
            if fixed:
                files_touched += 1
                rel = path.relative_to(REPO_ROOT)
                print(f"[PATCH] {rel} -> {fixed} uploadDate corriges")

    print()
    print(f"Total uploadDate detectes sans timezone : {total_matches}")
    print(f"Total uploadDate corriges               : {total_fixed}")
    print(f"Fichiers modifies                        : {files_touched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
