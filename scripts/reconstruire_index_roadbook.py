#!/usr/bin/env python3
"""
ROADBOOKS — RECONSTRUCTION DE L'INDEX D'UN VOYAGE

RAISON D'ÊTRE :
  L'index du roadbook Écosse ne listait que 4 jours sur 28 : les 24 autres
  pages existaient mais AUCUN lien ne pointait vers elles → invisibles pour
  Google et inaccessibles pour un visiteur. Une page sans lien entrant
  n'est jamais explorée.

CIBLE (capteurs validés sur l'index suisse déjà correct) :
  - titre de la carte du jour N = « 1ᵉʳ lieu du jour N → 1ᵉʳ lieu du jour N+1 »
    (dernier jour : le lieu de départ seul)
  - sous-titre = « durée · X points utiles retenus » où X = (nombre de h3 − 1)
  - km = première valeur « N km » de la page

⚠️ GARDE-FOU : un index qui liste déjà tous ses jours n'est JAMAIS réécrit.
   (Une première version de ce script avait dégradé l'index suisse en
   remplaçant de bons titres par des mauvais. Ne pas reproduire.)

Usage :
  python3 reconstruire_index_roadbook.py <dossier-voyage>
  python3 reconstruire_index_roadbook.py --tous
"""
import os, re, sys, glob, html

REPO = "/home/ubuntu/Yesbali.github.io"
RACINE_RB = f"{REPO}/roadbooks-html"

# en-têtes qui ne sont PAS des lieux d'étape
BRUIT = re.compile(
    r"^\s*(?:[^\w\s]|étape\b|le\s+commentaire|commentaire\b|à\s+lire|"
    r"points?\s+forts|direct\b|point\s+du\s+parcours|\*|shuttle)", re.I)


def texte(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def analyse(p):
    """Informations nécessaires à une carte d'index, lues dans la page jour."""
    c = open(p, encoding="utf-8", errors="ignore").read()
    m = re.search(r"<title[^>]*>(.*?)</title>", c, re.S | re.I)
    badge = texte(m.group(1)) if m else os.path.basename(p)

    km = None
    m = re.search(r"(\d[\d\s\xa0.,]*)\s*km\b", c[:12000], re.I)
    if m: km = re.sub(r"\s+", "", m.group(1)).strip()

    duree = None
    m = re.search(r"(\d+\s*h\s*\d{2})\s*(?:Temps route|Temps)", c[:12000], re.I)
    if not m:
        m = re.search(r"Temps route\s*</?[^>]*>\s*(\d+\s*h\s*\d{2})", c, re.I)
    if m: duree = re.sub(r"\s+", "", m.group(1)).strip()

    nb_h3 = len(re.findall(r"<h3", c, re.I))
    points = max(nb_h3 - 1, 0)

    # premier « vrai » titre = lieu de départ de l'étape
    depart = None
    for h in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", c, re.S | re.I):
        t = texte(h)
        if len(t) < 3 or BRUIT.match(t):
            continue
        depart = t
        break

    return {"badge": badge, "km": km, "duree": duree,
            "points": points, "depart": depart}


def carte(jour, info, arrivee):
    if arrivee and info["depart"]:
        titre = f'{info["depart"]} → {arrivee}'
    elif info["depart"]:
        titre = info["depart"]
    else:
        titre = f"Étape {jour}"
    sous = " · ".join(x for x in [info["duree"],
                                  f'{info["points"]} points utiles retenus' if info["points"] else ""] if x) or "voir le détail"
    km = f'{info["km"]} km' if info["km"] else "—"
    return f'''        <a href="jours/jour-{jour}.html" style="
            display:block;
            text-decoration:none;
            color:#0f172a;
            background:#fff;
            border:1px solid #cbd5e1;
            border-radius:16px;
            padding:18px;">
            <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;">
                <strong style="font-size:20px;color:#172554;">{info["badge"]}</strong>
                <span style="background:#f59e0b;color:white;padding:6px 12px;border-radius:999px;font-weight:bold;">
                    {km}
                </span>
            </div>
            <h2 style="margin:12px 0 8px 0;">{titre}</h2>
            <p style="margin:0;color:#475569;">{sous}</p>
        </a>'''


def traiter(dossier):
    index = os.path.join(dossier, "index.html")
    jours_dir = os.path.join(dossier, "jours")
    if not os.path.exists(index) or not os.path.isdir(jours_dir):
        print(f"  ⏭️  {os.path.basename(dossier)} : index ou dossier jours absent")
        return
    pages = sorted(glob.glob(f"{jours_dir}/jour-*.html"))
    if not pages:
        print(f"  ⏭️  {os.path.basename(dossier)} : aucune page jour")
        return

    src = open(index, encoding="utf-8").read()
    deja = sorted(set(re.findall(r'href="jours/jour-(\d{2})\.html"', src)))
    nums = [re.search(r"jour-(\d{2})\.html", os.path.basename(p)).group(1) for p in pages]

    if len(deja) == len(nums):
        print(f"  ✓ {os.path.basename(dossier)} : déjà complet ({len(deja)} jours) — non touché")
        return

    # infos de chaque jour (départ) + du jour suivant (arrivée)
    infos = {n: analyse(p) for n, p in zip(nums, pages)}
    cartes = []
    for i, n in enumerate(nums):
        arrivee = infos[nums[i + 1]]["depart"] if i + 1 < len(nums) else None
        if n not in deja:
            cartes.append(carte(n, infos[n], arrivee))

    m = re.search(r'(<div class="grid">)(.*?)(\n\s*</div>\s*</div>)', src, re.S)
    if not m:
        print(f"  ❌ {os.path.basename(dossier)} : grille introuvable")
        return
    nouveau = src[:m.end(2)] + "\n" + "\n".join(cartes) + "\n    " + src[m.end(2):]
    open(index, "w", encoding="utf-8").write(nouveau)
    print(f"  ✅ {os.path.basename(dossier)} : {len(deja)} → {len(deja)+len(cartes)} jours listés")


def main():
    if "--tous" in sys.argv:
        cibles = [d for d in sorted(glob.glob(f"{RACINE_RB}/*")) if os.path.isdir(d)]
    else:
        cibles = [a.rstrip("/") for a in sys.argv[1:] if not a.startswith("--")]
    if not cibles:
        print("usage : reconstruire_index_roadbook.py <dossier> | --tous")
        return 1
    for d in cibles:
        traiter(d if os.path.isabs(d) else os.path.join(RACINE_RB, d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
