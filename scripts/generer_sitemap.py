#!/usr/bin/env python3
"""
SEO — GÉNÉRATEUR DE SITEMAP (fin du sitemap écrit à la main)

RAISON D'ÊTRE :
  Le sitemap était maintenu à la main → à chaque nouvelle page il se
  désynchronisait, et on retrouvait éternellement « des pages non indexées ».
  Ce script le reconstruit À CHAQUE FOIS à partir du contenu réel du dépôt :
  une page publiée entre automatiquement dans le sitemap, sans intervention.

RÈGLE :
  Est déclarée au sitemap TOUTE page HTML qui
    - n'a pas de balise <meta name="robots" content="...noindex...">
    - n'est pas interdite par robots.txt
    - ne figure pas dans EXCLUS (pages outils, gabarits, gabarits de test)

Usage :
  python3 generer_sitemap.py             # régénère et écrit
  python3 generer_sitemap.py --verifier  # vérifie sans écrire (exit 1 si écart)
"""
import os, re, sys, glob, json
from datetime import datetime

REPO = os.environ.get("LCDMH_REPO", "/home/ubuntu/Yesbali.github.io")
DOM  = "https://lcdmh.com"
SITEMAP = f"{REPO}/sitemap.xml"
RAPPORT = "/home/ubuntu/PROJECTS/LCDMH/SEO/sitemap_rapport.json"

# Pages outils / gabarits : jamais dans le sitemap, jamais indexées
EXCLUS = {
    "nav.html",
    "widget-roadtrip-snippet.html",
    "404.html",
    "recherche.html",          # page outil : 59 mots, aucune valeur de recherche
    "articles/retour-honda-nt-1100-a-26000-kms.html",   # page de fusion → redirige
}

NOINDEX = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', re.I)
TITRE   = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def page_utilise_noindex(txt):
    return bool(NOINDEX.search(txt))


def lire(p):
    try:
        return open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""


def regles_robots():
    """Toutes les interdictions de robots.txt (bloc User-agent: *)."""
    txt = lire(f"{REPO}/robots.txt")
    interdits, dans_general = [], False
    for ligne in txt.splitlines():
        l = ligne.strip()
        if l.lower().startswith("user-agent"):
            dans_general = l.split(":", 1)[1].strip() == "*"
            continue
        if dans_general:
            m = re.match(r"Disallow:\s*(\S+)", l, re.I)
            if m: interdits.append(m.group(1))
    return interdits


def bloque(chemin, interdits):
    for d in interdits:
        if chemin == d or (d.endswith("/") and chemin.startswith(d)):
            return d
    return None


def url_de(rel):
    rel = rel.replace(os.sep, "/")
    if rel == "index.html":
        return DOM + "/"
    if rel.endswith("/index.html"):
        return f"{DOM}/{rel[:-len('index.html')]}"
    return f"{DOM}/{rel}"


def priorite(rel):
    if rel == "index.html":                     return "1.0"
    if rel.count("/") == 0:                     return "0.8"
    if rel.startswith("articles/"):             return "0.7"
    if rel.startswith("roadtrips/"):            return "0.6"
    if "/jours/" in rel:                        return "0.5"   # étapes de roadbook
    return "0.6"


def main(apercu=False):
    interdits = regles_robots()
    pages = sorted(f for f in glob.glob(f"{REPO}/**/*.html", recursive=True)
                   if "/.git/" not in f and "/node_modules/" not in f)

    retenues, exclues = [], []
    for p in pages:
        rel = os.path.relpath(p, REPO).replace(os.sep, "/")
        txt = lire(p)
        raison = None
        if rel in EXCLUS:                        raison = "page outil (liste EXCLUS)"
        elif page_utilise_noindex(txt):          raison = "balise noindex dans la page"
        else:
            b = bloque("/" + rel, interdits)
            if b: raison = f"robots.txt : {b}"
        if raison:
            exclues.append({"fichier": rel, "raison": raison})
        else:
            retenues.append({"fichier": rel, "url": url_de(rel),
                             "lastmod": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d"),
                             "priority": priorite(rel)})

    # dédoublonner par URL
    par_url = {}
    for r in retenues:
        par_url.setdefault(r["url"], r)
    retenues = sorted(par_url.values(), key=lambda x: (x["fichier"].count("/"), x["fichier"]))

    # sitemap actuel
    ancien = set(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", lire(SITEMAP)))
    nouveau = {r["url"] for r in retenues}
    ajouts, retraits = sorted(nouveau - ancien), sorted(ancien - nouveau)

    if apercu:
        print(f"sitemap actuel : {len(ancien)} URLs")
        print(f"sitemap cible  : {len(nouveau)} URLs")
        print(f"  à AJOUTER  : {len(ajouts)}")
        for u in ajouts[:20]: print(f"     + {u}")
        if len(ajouts) > 20: print(f"     … et {len(ajouts)-20} autres")
        print(f"  à RETIRER  : {len(retraits)}")
        for u in retraits[:10]: print(f"     − {u}")
        return 1 if (ajouts or retraits) else 0

    # écriture
    now = datetime.now().strftime("%Y-%m-%d")
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
         f'  <!-- LCDMH.com — sitemap GÉNÉRÉ AUTOMATIQUEMENT le {now} -->',
         f'  <!-- par scripts/generer_sitemap.py — ne pas éditer à la main -->']
    for r in retenues:
        L += ["  <url>", f"    <loc>{r['url']}</loc>",
              f"    <lastmod>{r['lastmod']}</lastmod>",
              f"    <priority>{r['priority']}</priority>", "  </url>"]
    L.append("</urlset>")
    open(SITEMAP, "w", encoding="utf-8").write("\n".join(L) + "\n")

    json.dump({"genere_le": datetime.now().isoformat(timespec="seconds"),
               "urls": len(retenues), "exclues": exclues,
               "ajouts": ajouts, "retraits": retraits},
              open(RAPPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"sitemap régénéré : {len(retenues)} URLs ({len(ajouts)} ajouts, {len(retraits)} retraits)")
    print(f"  {len(exclues)} page(s) volontairement exclue(s)")
    if ajouts:
        print(f"  ajouts : {len(ajouts)}")
        for u in ajouts[:15]: print(f"     + {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main(apercu="--verifier" in sys.argv))
