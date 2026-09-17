#!/usr/bin/env python3
"""
audit_maillage.py — CONTRÔLEUR PERMANENT DU MAILLAGE LCDMH
===========================================================
Scanne tout le site et sort PASS / WARNING / ERROR.

ERROR (bloquant) : auto-lien éditorial · lien interne cassé · cible inexistante ·
                   doublon dans un même bloc · HTML gravement invalide.
WARNING          : page orpheline · profondeur excessive · page sans recommandation ·
                   cible noindex · cul-de-sac.

Usage :
    python scripts/audit_maillage.py
    python scripts/audit_maillage.py --strict   # exit 1 si ERROR
"""
import os, re, json, sys, collections, html

# RACINE auto-détectée : le dépôt est le parent du dossier scripts/
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "data", "maillage.json")

# navigation globale : à NE PAS compter comme maillage éditorial
NAV_FICHIERS = {"nav.html", "footer.html"}
NAV_CLASSES = ["lcdmh-dropdown", "breadcrumb", "hero-crumbs", "lcdmh-nav",
               "site-footer", "lcdh-footer", "lcdmh-footer", "menu-"]
# exceptions légitimes d'auto-lien
AUTOLIEN_OK = {"/mentions-legales.html"}
# cibles commerciales : linkage éditorial non requis
CIBLES_COMMERCIALES = {"/codes-promo.html"}

erreurs, warnings, infos = [], [], []


def charge_pages():
    pages = {}
    for root_, dirs, files in os.walk(RACINE):
        dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "ARCHIVES_SITE_2026"}]
        for f in files:
            if f.endswith(".html"):
                p = os.path.join(root_, f)
                u = "/" + os.path.relpath(p, RACINE).replace(os.sep, "/")
                pages[u] = {"path": p, "html": open(p, encoding="utf-8", errors="ignore").read()}
    return pages


def liens_editoriaux(t):
    """Liens du bloc canonique uniquement (maillage éditorial)."""
    out = []
    m = re.search(r"<!-- MAILLAGE_STATIQUE_SEO -->.*?<!-- FIN_MAILLAGE_STATIQUE_SEO -->", t, re.S)
    if not m:
        return out
    for a in re.finditer(r'<a[^>]+href="(/[^"#?]*?\.html)"[^>]*>(.*?)</a>', m.group(0), re.S):
        ancre = html.unescape(re.sub(r"<[^>]+>", "", a.group(2))).strip()
        out.append((a.group(1), ancre))
    return out


def liens_tous(t):
    return re.findall(r'href="(/[^"#?]*?\.html)"', t)


def main():
    strict = "--strict" in sys.argv
    pages = charge_pages()
    data = json.load(open(SOURCE, encoding="utf-8"))
    rel = {(r["source"], r["cible"]) for r in data["relations"]}

    indexables = {u: p for u, p in pages.items() if "noindex" not in p["html"].lower()}

    # ── A. AUTO-LIENS (bloc éditorial uniquement)
    for u, p in pages.items():
        if u in AUTOLIEN_OK:
            continue
        for cible, _ in liens_editoriaux(p["html"]):
            if cible == u:
                erreurs.append(f"AUTO-LIEN éditorial : {u} se recommande lui-même")

    # ── B. LIENS CASSÉS (tout le site)
    for u, p in pages.items():
        for l in set(liens_tous(p["html"])):
            c = l.lstrip("/")
            if not (os.path.exists(os.path.join(RACINE, c)) or
                    os.path.exists(os.path.join(RACINE, c, "index.html"))):
                erreurs.append(f"LIEN CASSÉ : {u} → {l}")

    # ── C. DOUBLONS dans un même bloc
    for u, p in pages.items():
        lk = [c for c, _ in liens_editoriaux(p["html"])]
        dup = [k for k, v in collections.Counter(lk).items() if v > 1]
        for d in dup:
            erreurs.append(f"DOUBLON dans le bloc : {u} → {d} ({lk.count(d)}×)")

    # ── D. ANCRES VIDES / TROP COURTES
    for u, p in pages.items():
        for cible, ancre in liens_editoriaux(p["html"]):
            if len(ancre) < 3:
                erreurs.append(f"ANCRE VIDE/TROP COURTE : {u} → {cible} (« {ancre} »)")

    # ── E. BLOCS RÉSIDUELS
    RESID = {"a_lire_aussi": r'class="[^"]*a-lire-aussi',
             "maillage_box": r'class="maillage-box"',
             "link_grid": r'class="[^"]*link-grid',
             "maillage_piliers": r'class="[^"]*maillage-piliers',
             "guide_related": r'class="[^"]*guide-related'}
    for u, p in pages.items():
        for nom, motif in RESID.items():
            if re.search(motif, p["html"]):
                erreurs.append(f"SYSTÈME RÉSIDUEL : {u} contient encore {nom}")

    # ── F. PAGES SANS BLOC
    for u, p in pages.items():
        if u in ("/nav.html", "/footer.html") or "noindex" in p["html"].lower():
            continue
        if "MAILLAGE_STATIQUE_SEO" not in p["html"]:
            warnings.append(f"SANS BLOC : {u} (aucune recommandation éditoriale)")

    # ── G. PAGES ORPHELINES (aucun lien entrant éditorial ni navigation)
    entrants = collections.defaultdict(set)
    for u, p in pages.items():
        for l in set(liens_tous(p["html"])):
            entrants[l].add(u)
    for u in indexables:
        if u in ("/", "/index.html"):
            continue
        if not entrants.get(u):
            warnings.append(f"ORPHELINE : {u} (aucun lien entrant)")

    # ── H. CULS-DE-SAC (aucune sortie contextuelle)
    for u, p in indexables.items():
        if u in ("/", "/index.html"):
            continue
        if not liens_editoriaux(p["html"]) and not liens_tous(p["html"]):
            warnings.append(f"CUL-DE-SAC : {u}")

    # ── I. CIBLES NOINDEX recevant beaucoup de liens éditoriaux
    cnt = collections.Counter(c for r in data["relations"] for c in [r["cible"]])
    for cible, n in cnt.items():
        if n >= 10 and cible in pages and "noindex" in pages[cible]["html"].lower():
            warnings.append(f"CIBLE NOINDEX très liée : {cible} ({n} liens éditoriaux)")

    # ── J. PROFONDEUR depuis l'accueil (BFS)
    graphe = collections.defaultdict(set)
    for u, p in pages.items():
        for l in set(liens_tous(p["html"])):
            if l != u:
                graphe[u].add(l)
    prof = {"/": 0, "/index.html": 0}
    frontiere = ["/", "/index.html"]
    niveau = 0
    while frontiere and niveau < 8:
        suivant = []
        for u in frontiere:
            for v in graphe.get(u, ()): 
                if v not in prof:
                    prof[v] = niveau + 1
                    suivant.append(v)
        frontiere = suivant
        niveau += 1

    HUBS = ["/voyager-moto.html", "/roadtrips.html", "/roadtrips/road-trip-moto-france.html",
            "/alpes-cols-mythiques.html", "/cap-nord-moto.html", "/gps.html",
            "/bagagerie-moto.html", "/voyager-europe-moto.html", "/equipement.html"]
    for h in HUBS:
        d = prof.get(h)
        if d is None:
            warnings.append(f"PROFONDEUR : hub {h} NON ATTEIGNABLE depuis l'accueil")
        elif d > 2:
            warnings.append(f"PROFONDEUR : hub {h} à {d} clics (objectif ≤ 2)")
    for u in indexables:
        d = prof.get(u)
        if d is not None and d > 3:
            warnings.append(f"PROFONDEUR : {u} à {d} clics (objectif ≤ 3)")

    # ── VIGNETTES YOUTUBE : format 16:9 garanti
    # Ajouté le 17/09/2026 après un défaut constaté sur les cartes d'accueil :
    # hqdefault.jpg (480x360, 4:3) dans un cadre 16:9 avec object-fit:cover
    # rognait le haut de l'image — donc les titres incrustés des vignettes.
    # Règle : src = maxresdefault.jpg (16:9 natif), repli onerror = hqdefault.jpg,
    # et css/vignettes.css chargé pour neutraliser les hauteurs fixes.
    for u, pg in pages.items():
        t = pg["html"]
        nb_yt = len(re.findall(r"i\.ytimg\.com", t))
        if not nb_yt:
            continue
        # a) une vignette 4:3 appelée directement en src (hors repli onerror)
        srcs_4_3 = re.findall(r'src="[^"]*hqdefault\.jpg"', t)
        if srcs_4_3:
            erreurs.append(
                f"VIGNETTE 4:3 : {u} appelle hqdefault.jpg ({len(srcs_4_3)}×) en src — "
                f"480x360 rogné, utiliser maxresdefault.jpg"
            )
        # b) le CSS de sécurité des vignettes doit être chargé
        if "vignettes.css" not in t:
            erreurs.append(
                f"VIGNETTE SANS CSS : {u} affiche {nb_yt} vignette(s) YouTube "
                f"sans charger css/vignettes.css (hauteurs fixes non neutralisées)"
            )
        # c) hauteur fixe posée sur une vignette YouTube (écrase aspect-ratio)
        for m in re.finditer(r'<img[^>]*i\.ytimg\.com[^>]*>', t):
            if re.search(r'style="[^"]*height\s*:\s*(?!auto)[0-9]', m.group(0)):
                erreurs.append(
                    f"VIGNETTE HAUTEUR FIXE : {u} impose un height inline sur une "
                    f"vignette YouTube — écrase aspect-ratio, rognage variable"
                )
                break

    # ── RÉSULTAT
    print("=" * 100)
    print("AUDIT MAILLAGE LCDMH")
    print("=" * 100)
    print(f"   pages        : {len(pages)}")
    print(f"   indexables   : {len(indexables)}")
    print(f"   relations    : {len(data['relations'])} (source unique)")
    print(f"   hubs suivis  : {len(HUBS)}")
    print()
    print(f"   🔴 ERROR   : {len(erreurs)}")
    print(f"   🟡 WARNING : {len(warnings)}")
    print()

    if erreurs:
        print("─" * 100)
        print("ERROR")
        print("─" * 100)
        for e in erreurs[:40]:
            print(f"   🔴 {e}")
        if len(erreurs) > 40:
            print(f"   ... et {len(erreurs)-40} autres")

    if warnings:
        print("─" * 100)
        print("WARNING")
        print("─" * 100)
        for w in warnings[:30]:
            print(f"   🟡 {w}")
        if len(warnings) > 30:
            print(f"   ... et {len(warnings)-30} autres")

    # hubs
    print("─" * 100)
    print("HUBS")
    print("─" * 100)
    print(f"   {'hub':48s} {'sortants':>9s} {'entrants':>9s} {'prof':>5s} {'auto':>5s}")
    print("   " + "-" * 80)
    for h in HUBS:
        if h not in pages:
            print(f"   {h:48s} {'ABSENT':>9s}")
            continue
        so = len(liens_editoriaux(pages[h]["html"]))
        en = len(entrants.get(h, ()))
        d = prof.get(h, "—")
        au = sum(1 for c, _ in liens_editoriaux(pages[h]["html"]) if c == h)
        print(f"   {h:48s} {so:9d} {en:9d} {str(d):>5s} {au:5d}")

    print()
    verdict = "ERROR" if erreurs else ("WARNING" if warnings else "PASS")
    print("=" * 100)
    print(f"   VERDICT : {verdict}")
    print("=" * 100)

    rapport = {"erreurs": erreurs, "warnings": warnings, "pages": len(pages),
               "relations": len(data["relations"]), "profondeur": prof}
    json.dump(rapport, open(os.path.join(RACINE, "data", "audit_maillage_dernier.json"), "w"),
              ensure_ascii=False, indent=1)

    if strict and erreurs:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
