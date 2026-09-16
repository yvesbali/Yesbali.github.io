#!/usr/bin/env python3
"""
build_maillage.py — GÉNÉRATEUR DE MAILLAGE LCDMH
================================================
Source unique : data/maillage.json
Bloc généré  : <section class="maillage-section"> entre les marqueurs
               <!-- MAILLAGE_STATIQUE_SEO --> ... <!-- FIN_MAILLAGE_STATIQUE_SEO -->

DÉTERMINISTE et IDEMPOTENT : deux exécutions consécutives ne modifient rien.

Usage :
    python scripts/build_maillage.py            # écrit
    python scripts/build_maillage.py --dry-run  # montre sans écrire
"""
import os, re, json, sys, hashlib, html, collections

# RACINE auto-détectée : le dépôt est le parent du dossier scripts/
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "data", "maillage.json")
MARQUEUR_DEB = "<!-- MAILLAGE_STATIQUE_SEO -->"
MARQUEUR_FIN = "<!-- FIN_MAILLAGE_STATIQUE_SEO -->"

# cibles qui sont du COMMERCIAL / NAVIGATION, pas de l'éditorial
EXCLUES_SORTIE = {"/codes-promo.html", "/mentions-legales.html", "/a-propos.html",
                  "/articles.html", "/roadbooks.html"}

MAX_LIENS = 8   # borne : la pertinence domine, on ne dépile pas 129 liens


def charger():
    with open(SOURCE, encoding="utf-8") as f:
        return json.load(f)


def relations_par_page(data):
    par = collections.defaultdict(list)
    for r in data["relations"]:
        if r["cible"] in EXCLUES_SORTIE:
            continue
        par[r["source"]].append(r)
    # tri déterministe : par type puis par cible (évite les variations d'ordre)
    ORDRE = ["PARENT", "CHILD", "DESTINATION", "PREPARATION", "EQUIPMENT",
             "NAVIGATION", "REGULATION", "EXPERIENCE", "COMPARISON", "SIBLING", "NEXT_STEP"]
    for u in par:
        par[u].sort(key=lambda x: (ORDRE.index(x["type"]) if x["type"] in ORDRE else 99, x["cible"]))
        par[u] = par[u][:MAX_LIENS]
    return par


def bloc_html(relations):
    """Génère le bloc. Sortie STRICTEMENT déterministe."""
    if not relations:
        return None
    lignes = [
        MARQUEUR_DEB,
        '    <section class="maillage-section" aria-label="À lire aussi">',
        '      <div class="maillage-inner">',
        '        <h3 class="maillage-title">📖 À lire aussi</h3>',
        '        <div class="maillage-grid">',
    ]
    for r in relations:
        a = html.escape(r["ancre"], quote=True)
        lignes.append(f'          <a href="{r["cible"]}" class="maillage-link">{a}</a>')
    lignes += [
        '        </div>',
        '      </div>',
        '    </section>',
        '    ' + MARQUEUR_FIN,
    ]
    return "\n".join(lignes)


def sha(txt):
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()[:12]


def main():
    dry = "--dry-run" in sys.argv
    data = charger()
    par_page = relations_par_page(data)

    pages, rapport = {}, []
    for root_, dirs, files in os.walk(RACINE):
        dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "ARCHIVES_SITE_2026"}]
        for f in files:
            if f.endswith(".html"):
                p = os.path.join(root_, f)
                u = "/" + os.path.relpath(p, RACINE).replace(os.sep, "/")
                pages[u] = p

    modifies = 0
    for u, p in sorted(pages.items()):
        t = open(p, encoding="utf-8", errors="ignore").read()
        rels = par_page.get(u, [])
        bloc = bloc_html(rels)

        # retirer tout bloc précédent (idempotence) + normaliser les blancs résiduels
        t2 = re.sub(r"[ \t]*\n?[ \t]*" + re.escape(MARQUEUR_DEB) + r".*?" + re.escape(MARQUEUR_FIN) + r"[ \t]*",
                    "", t, flags=re.S)
        t2 = re.sub(r"[ \t]*\n?[ \t]*" + re.escape(MARQUEUR_DEB) + r".*?(?=</body>)",
                    "", t2, flags=re.S)
        # supprimer les lignes vides surnuméraires avant </body> (source du défaut d'idempotence)
        t2 = re.sub(r"(?:\r?\n[ \t]*){3,}(?=</body>)", "\n\n", t2)

        if bloc:
            if "</body>" in t2:
                t2 = t2.replace("</body>", bloc + "\n</body>", 1)
            else:
                continue

        if sha(t) != sha(t2):
            modifies += 1
            rapport.append((u, len(rels)))
            if not dry:
                open(p, "w", encoding="utf-8").write(t2)

    mode = "DRY-RUN" if dry else "ÉCRITURE"
    print("=" * 90)
    print(f"BUILD MAILLAGE — {mode}")
    print("=" * 90)
    print(f"   source      : data/maillage.json ({len(data['relations'])} relations)")
    print(f"   pages       : {len(pages)}")
    print(f"   modifiées   : {modifies}")
    print(f"   bloc généré : {len(par_page)} pages avec relations")
    sans = [u for u in pages if u not in par_page]
    print(f"   sans relations : {len(sans)} pages")
    for s in sans[:6]:
        print(f"      {s}")
    if sans[6:]:
        print(f"      ... et {len(sans)-6} autres")


if __name__ == "__main__":
    main()
