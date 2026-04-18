#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_rel_sponsored.py — Ajoute rel="sponsored nofollow noopener" et
target="_blank" sur TOUS les liens d'affiliation sortants du site LCDMH.

Regle SEO (Google, 2020+) : un lien monetise DOIT porter rel="sponsored".
Nofollow reste utile en complement (Google l'accepte comme "hint").

Source de verite : liste des domaines affilies extraite de
data/partenaires.json + domaines additionnels classiques e-commerce.

Comportement :
  - Pour chaque <a href="..."> dont l'URL pointe vers un domaine
    affiliate, on modifie l'attribut rel pour inclure
    "sponsored nofollow noopener" (sans doublons).
  - On force target="_blank" (pratique standard pour lien affiliate).
  - On NE TOUCHE PAS aux liens internes ni aux autres liens externes
    (YouTube, Tipeee, Facebook, TikTok ne sont PAS affilies).

Appel :
  python3 add_rel_sponsored.py [--dry-run] [--root CHEMIN]

Sortie :
  Log ligne par ligne + resume (fichiers modifies, liens touches).
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Domaines consideres comme affilies (source: data/partenaires.json + classiques)
AFFILIATE_DOMAINS = (
    "carpuride.com",
    "aoocci.fr",
    "aoocci.com",
    "amazon.fr/dp",
    "amazon.fr/gp",
    "amazon.com/dp",
    "amazon.com/gp",
    "amzn.to",
    "amzn.eu",
    "olightstore",
    "olightworld",
    "olight-world",
    "komobi.com",
    "blackview.hk",
    "blackview.com",
    "innovv.com",
    "tidd.ly",          # raccourcisseur ShareASale/Impact
    "aliexpress.com",
    "s.click.aliexpress",
    "banggood.com",
    "awin1.com",        # reseau Awin
    "sjv.io",           # reseau Impact
)

REQUIRED_RELS = ("sponsored", "nofollow", "noopener")

SCAN_DIRS = [".", "articles"]

EXCLUDE_SUBSTR = (
    "LCDMH_Cadrage_Projet.html",
    "nav.html",
    "/_apercu_design_premium/",
    "/_audit/",
    "/_sauvegarde_",
    "/AUDIT_INGENIEUR_SEO/",
)

A_TAG_RE = re.compile(
    r'<a\b([^>]*?)\bhref\s*=\s*"([^"]*)"([^>]*)>',
    re.IGNORECASE,
)

REL_RE = re.compile(r'\brel\s*=\s*"([^"]*)"', re.IGNORECASE)
TARGET_RE = re.compile(r'\btarget\s*=\s*"[^"]*"', re.IGNORECASE)


def is_affiliate(url: str) -> bool:
    low = url.lower()
    return any(dom in low for dom in AFFILIATE_DOMAINS)


def ensure_rel(attrs: str) -> tuple[str, bool]:
    """Retourne (attrs_modifies, a_change)."""
    m = REL_RE.search(attrs)
    if m:
        current = set(m.group(1).split())
        merged = current | set(REQUIRED_RELS)
        if merged == current:
            return attrs, False
        new_rel = 'rel="' + " ".join(sorted(merged)) + '"'
        new_attrs = attrs[:m.start()] + new_rel + attrs[m.end():]
        return new_attrs, True
    # pas de rel, on en ajoute un
    new_attrs = attrs + ' rel="' + " ".join(REQUIRED_RELS) + '"'
    return new_attrs, True


def ensure_target_blank(attrs: str) -> tuple[str, bool]:
    m = TARGET_RE.search(attrs)
    if m:
        return attrs, False
    return attrs + ' target="_blank"', True


def patch_html(text: str) -> tuple[str, int]:
    """Retourne (nouveau_html, nb_liens_touches)."""
    touched = 0

    def repl(match: re.Match) -> str:
        nonlocal touched
        before = match.group(1)
        href = match.group(2)
        after = match.group(3)
        if not is_affiliate(href):
            return match.group(0)
        all_attrs = before + after
        new_attrs, changed1 = ensure_rel(all_attrs)
        new_attrs, changed2 = ensure_target_blank(new_attrs)
        if not (changed1 or changed2):
            return match.group(0)
        touched += 1
        # Reconstruit la balise ouvrante avec href propre au debut
        cleaned = new_attrs.strip()
        return f'<a href="{href}" {cleaned}>' if cleaned else f'<a href="{href}">'

    new_text = A_TAG_RE.sub(repl, text)
    return new_text, touched


def should_skip(path: Path, root: Path) -> bool:
    rel = str(path.relative_to(root)).replace("\\", "/")
    for token in EXCLUDE_SUBSTR:
        if token.strip("/") in rel:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    targets: list[Path] = []
    for d in SCAN_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in base.glob("*.html"):
            if should_skip(p, root):
                continue
            targets.append(p)

    total_files = 0
    total_links = 0
    for p in sorted(targets):
        try:
            raw = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new, n = patch_html(raw)
        if n > 0:
            total_files += 1
            total_links += n
            rel = p.relative_to(root)
            mark = "[+]" if not args.dry_run else "[~]"
            print(f"  {mark} {rel}  ->  {n} lien(s) affilies patches")
            if not args.dry_run:
                p.write_text(new, encoding="utf-8", newline="\n")

    print()
    print(f"Resume : {total_files} fichiers / {total_links} liens affilies "
          f"marques rel=\"sponsored nofollow noopener\" target=\"_blank\".")
    if args.dry_run:
        print("(dry-run : aucune ecriture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
