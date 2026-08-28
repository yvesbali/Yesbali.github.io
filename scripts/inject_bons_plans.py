# -*- coding: utf-8 -*-
"""Injecte le bloc « Bons plans LCDMH » dans chaque page HTML du site.

SOURCE UNIQUE : promos/bons_plans.json — modifier une promo = éditer ce JSON,
puis relancer ce script (il met à jour TOUTES les pages automatiquement).

Usage :  python scripts/inject_bons_plans.py [--dry-run]
"""
import json, re, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "promos" / "bons_plans.json"
CSS_LINK = '<link rel="stylesheet" href="css/bons-plans.css">'
START = "<!-- LCDMH_BONS_PLANS:START -->"
END = "<!-- LCDMH_BONS_PLANS:END -->"
EXCLUDES = {"nav.html"}


def render_block(offers: dict) -> str:
    titre = offers.get("titre", "🏷 Les bons plans équipement LCDMH")
    accroche = offers.get("accroche", "")
    cards = ""
    for o in offers.get("offres", []):
        lien = (o.get("lien") or "").strip()
        href = f' href="{lien}"' if lien else ""
        target = ' target="_blank" rel="noopener"' if lien else ""
        cards += f"""<div class="bp-card"><div class="bp-icon">{o.get('icone','🛍️')}</div>
<div class="bp-product">{o.get('produit','')}</div>
<div class="bp-code">{o.get('avantage','')}</div>
<a class="bp-cta"{href}{target}>{o.get('cta','Voir l\'offre →')}</a></div>
"""
    acc = f"<p>{accroche}</p>" if accroche else ""
    return f"""{START}
<section class="bp-block" id="bons-plans">
<div class="bp-head"><h2>{titre}</h2>{acc}</div>
<div class="bp-grid">{cards}</div>
</section>
{END}"""


def inject_in_page(page: Path, block: str, dry: bool) -> bool:
    text = page.read_text(encoding="utf-8", errors="replace")
    new = text
    if START in text and END in text:
        new = re.sub(re.escape(START) + r".*?" + re.escape(END), block, text, flags=re.S)
    else:
        # Insérer avant le footer (ou </body> en fallback)
        if "<footer" in text:
            new = text.replace("<footer", block + "\n<footer", 1)
        elif "</body>" in text:
            new = text.replace("</body>", block + "\n</body>", 1)
        else:
            return False
    # Ajouter le lien CSS dans le <head> si absent
    if 'bons-plans.css' not in new and "<head>" in new:
        new = new.replace("<head>", f"<head>\n{CSS_LINK}", 1)
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
    offers = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    block = render_block(offers)
    pages = [p for p in ROOT.rglob("*.html") if p.name not in EXCLUDES]
    ok, skipped = 0, 0
    for p in sorted(pages):
        if inject_in_page(p, block, dry):
            ok += 1
        else:
            skipped += 1
            print(f"  ⚠️  {p.relative_to(ROOT)} : pas de <footer>/</body>")
    print(f"{'[DRY-RUN] ' if dry else ''}Pages traitées : {ok} | ignorées : {skipped}")
    print(f"Bloc généré depuis : {JSON_PATH.name} ({len(offers.get('offres', []))} offres)")


if __name__ == "__main__":
    main()
