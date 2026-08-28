# -*- coding: utf-8 -*-
"""Injecte le conteneur du bandeau « Bons plans LCDMH » dans chaque page HTML du site.

CENTRALISATION ABSOLUE (consigne Yves 28/08/2026) :
- Les DONNÉES (texte, code, lien, image, bouton, ordre) vivent dans promos/bons_plans.json
- Le RENDU est fait par assets/js/lcdmh-partners.js (fetch du JSON) au chargement de chaque page
- Ce script ne fait que déposer sur chaque page : le conteneur <div id="lcdmh-partners">
  + les liens CSS/JS. Modifier une promo = éditer le JSON (immédiat partout, sans relancer).

Usage :  python scripts/inject_bons_plans.py [--dry-run]
"""
import re, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_LINK = '<link rel="stylesheet" href="assets/css/lcdmh-partners.css">'
JS_TAG = '<script src="assets/js/lcdmh-partners.js" defer></script>'
OLD_CSS_LINK = 'css/bons-plans.css'
START = "<!-- LCDMH_BONS_PLANS:START -->"
END = "<!-- LCDMH_BONS_PLANS:END -->"
EXCLUDES = {"nav.html"}
CONTAINER = f"""{START}
<div id="lcdmh-partners"></div>
{END}"""


def inject_in_page(page: Path, dry: bool) -> bool:
    text = page.read_text(encoding="utf-8", errors="replace")
    new = text
    if START in text and END in text:
        new = re.sub(re.escape(START) + r".*?" + re.escape(END), CONTAINER, text, flags=re.S)
    else:
        if "<footer" in text:
            new = text.replace("<footer", CONTAINER + "\n<footer", 1)
        elif "</body>" in text:
            new = text.replace("</body>", CONTAINER + "\n</body>", 1)
        else:
            return False
    # CSS/JS : migrer l'ancien lien bons-plans.css vers le nouveau, puis ajouter les tags si absents
    if OLD_CSS_LINK in new and "lcdmh-partners.css" not in new:
        new = new.replace(f'href="{OLD_CSS_LINK}"', 'href="assets/css/lcdmh-partners.css"')
    if "lcdmh-partners.css" not in new and "<head>" in new:
        new = new.replace("<head>", f"<head>\n{CSS_LINK}", 1)
    if "lcdmh-partners.js" not in new and "</body>" in new:
        new = new.replace("</body>", f"{JS_TAG}\n</body>", 1)
    if new == text:
        return True  # déjà à jour
    if not dry:
        bak = page.with_suffix(page.suffix + ".bak_bonsplans")
        if not bak.exists():
            shutil.copy2(page, bak)
        page.write_text(new, encoding="utf-8")
    return True


def main():
    dry = "--dry-run" in sys.argv
    pages = [p for p in ROOT.rglob("*.html") if p.name not in EXCLUDES]
    ok, skipped = 0, 0
    for p in sorted(pages):
        if inject_in_page(p, dry):
            ok += 1
        else:
            skipped += 1
            print(f"  ⚠️  {p.relative_to(ROOT)} : pas de <footer>/</body>")
    print(f"{'[DRY-RUN] ' if dry else ''}Pages traitées : {ok} | ignorées : {skipped}")


if __name__ == "__main__":
    main()
