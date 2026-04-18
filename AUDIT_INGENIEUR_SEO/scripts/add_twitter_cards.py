#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_twitter_cards.py - Injecte les meta Twitter Card manquantes sur les pages LCDMH.

Principe
--------
Pour chaque page HTML du site :
  1. Lire les balises OpenGraph déjà présentes (og:title, og:description, og:image)
  2. Si elles existent et qu'aucune balise twitter:* n'est déjà là, injecter le bloc :
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="... (= og:title)">
        <meta name="twitter:description" content="... (= og:description)">
        <meta name="twitter:image" content="... (= og:image)">
  3. Insertion juste après la dernière balise og:* pour garder le head lisible
  4. Idempotent : ne fait rien si twitter:card est déjà présent

Exclusions
----------
- fichiers snippet (nav.html, header.html, footer.html, widget-roadtrip-snippet.html)
- dossiers _archive, data/articles, _review, _apercu_design_premium, AUDIT_INGENIEUR_SEO
- pages qui n'ont aucune balise og:title (on ne devine rien, on ne triche pas)

Usage
-----
    python add_twitter_cards.py --dry-run        # liste ce qui serait fait
    python add_twitter_cards.py                   # applique
    python add_twitter_cards.py --only articles/  # limite à un sous-dossier
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

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
    "data",  # versions historiques d'articles
}

OG_TITLE_RE = re.compile(
    r'<meta[^>]+property\s*=\s*["\']og:title["\'][^>]+content\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_DESC_RE = re.compile(
    r'<meta[^>]+property\s*=\s*["\']og:description["\'][^>]+content\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMG_RE = re.compile(
    r'<meta[^>]+property\s*=\s*["\']og:image["\'][^>]+content\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
TWITTER_CARD_RE = re.compile(r'<meta[^>]+name\s*=\s*["\']twitter:card["\']', re.IGNORECASE)

# Pour trouver le point d'insertion : après la dernière balise og:* du <head>
LAST_OG_RE = re.compile(
    r'(<meta[^>]+property\s*=\s*["\']og:[a-z_:]+["\'][^>]*>)',
    re.IGNORECASE,
)


def _html_escape(s: str) -> str:
    """Les contenus og:* sont déjà échappés en général, mais on fait un double-check minimal."""
    # On ne ré-échappe pas les entités déjà présentes, on remplace juste les guillemets nus
    return s.replace('"', "&quot;")


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


def patch_page(path: Path, dry_run: bool) -> tuple[str, str]:
    """Retourne (status, detail) où status est OK / SKIP / NO_OG / ALREADY."""
    text = path.read_text(encoding="utf-8", errors="replace")

    if TWITTER_CARD_RE.search(text):
        return "ALREADY", "twitter:card déjà présent"

    m_title = OG_TITLE_RE.search(text)
    m_desc = OG_DESC_RE.search(text)
    m_img = OG_IMG_RE.search(text)
    if not (m_title and m_desc and m_img):
        missing = [n for n, m in [("og:title", m_title), ("og:description", m_desc), ("og:image", m_img)] if not m]
        return "NO_OG", f"og manquant : {', '.join(missing)}"

    og_title = _html_escape(m_title.group(1))
    og_desc = _html_escape(m_desc.group(1))
    og_img = _html_escape(m_img.group(1))

    block_lines = [
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{og_title}">',
        f'<meta name="twitter:description" content="{og_desc}">',
        f'<meta name="twitter:image" content="{og_img}">',
    ]
    # Point d'insertion : après la dernière og:*
    last_og = None
    for m in LAST_OG_RE.finditer(text):
        last_og = m
    if not last_og:
        return "NO_OG", "aucune og:* détectée (paradoxal)"
    insert_pos = last_og.end()
    # Conserver l'indentation de la ligne de og:* pour rester cohérent
    line_start = text.rfind("\n", 0, last_og.start()) + 1
    indent = ""
    for ch in text[line_start : last_og.start()]:
        if ch in " \t":
            indent += ch
        else:
            break
    new_block = "\n" + "\n".join(indent + l for l in block_lines)
    new_text = text[:insert_pos] + new_block + text[insert_pos:]

    if dry_run:
        return "OK", "4 balises twitter:* seraient injectées après la dernière og:*"

    path.write_text(new_text, encoding="utf-8")
    return "OK", "4 balises twitter:* injectées"


def main() -> int:
    parser = argparse.ArgumentParser(description="Injection Twitter Card dérivée des og:* existants")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans écrire")
    parser.add_argument("--only", help="Filtre sous-chemin (ex: articles/)")
    parser.add_argument("--root", default=str(SITE_ROOT), help="Racine du site")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    pages = collect_pages(root, args.only)
    print(f"{len(pages)} pages candidates")

    stats = {"OK": 0, "ALREADY": 0, "NO_OG": 0}
    for p in pages:
        status, detail = patch_page(p, args.dry_run)
        stats[status] = stats.get(status, 0) + 1
        if status == "OK" or (status == "NO_OG" and args.dry_run):
            rel = p.relative_to(root)
            tag = "[DRY]" if args.dry_run else "[FIX]"
            print(f"{tag} {status:8s} {rel}  — {detail}")

    print()
    print(f"Résumé : OK={stats.get('OK',0)} · déjà conformes={stats.get('ALREADY',0)} · sans og={stats.get('NO_OG',0)}")
    return 0 if stats.get("NO_OG", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
