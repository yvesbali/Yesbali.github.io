#!/usr/bin/env python3
"""
GÉNÉRATEUR DE L'INDEX DE RECHERCHE DU SITE (data/site-index.json)

RAISON D'ÊTRE :
  `data/site-index.json` alimente la recherche du site (page recherche.html).
  Il était maintenu À LA MAIN : aucun script ne le régénérait. Conséquence
  constatée le 22/09/2026 : la recherche du site ne trouvait pas des pages
  publiées depuis des semaines (page Colight, article pneus, bagagerie,
  voyager-moto, 21 pages de roadbook...). Même cause racine que le sitemap.

RÈGLE :
  Entre dans la recherche TOUTE page HTML qui
    - n'a pas de <meta name="robots" content="...noindex...">
    - n'est pas interdite par robots.txt
    - ne figure pas dans EXCLUS (pages outils / gabarits)

Usage :
  python3 scripts/generer_index_recherche.py             # régénère et écrit
  python3 scripts/generer_index_recherche.py --verifier  # contrôle, n'écrit rien
                                                         # (exit 1 si écart)
"""
import os, re, sys, glob, json
from datetime import datetime
from html import unescape
from html.parser import HTMLParser

REPO = os.environ.get("LCDMH_REPO", "/home/ubuntu/Yesbali.github.io")
SORTIE = f"{REPO}/data/site-index.json"

# Pages outils / gabarits / techniques : jamais dans la recherche du visiteur
EXCLUS = {
    "nav.html",
    "404.html",
    "widget-roadtrip-snippet.html",
    "sitemap.html",          # plan du site : déjà un index, pas un contenu
    "recherche.html",        # la page de recherche elle-même
    "articles/retour-honda-nt-1100-a-26000-kms.html",   # page de fusion
}

NOINDEX = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', re.I)
TITRE   = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
DESC    = re.compile(r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
H1      = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
H2      = re.compile(r"<h2[^>]*>(.*?)</h2>", re.I | re.S)
P       = re.compile(r"<p[^>]*>(.*?)</p>", re.I | re.S)


def lire(p):
    try:
        return open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""


def texte(html):
    """HTML → texte propre (sans balises, sans entités, sans espaces doubles)."""
    t = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def regles_robots():
    txt = lire(f"{REPO}/robots.txt")
    interdits, general = [], False
    for ligne in txt.splitlines():
        l = ligne.strip()
        if l.lower().startswith("user-agent"):
            general = l.split(":", 1)[1].strip() == "*"
            continue
        if general:
            m = re.match(r"Disallow:\s*(\S+)", l, re.I)
            if m:
                interdits.append(m.group(1))
    return interdits


def bloque(chemin, interdits):
    for d in interdits:
        if chemin == d or (d.endswith("/") and chemin.startswith(d)):
            return d
    return None


def url_de(rel):
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


class MetaExtracteur(HTMLParser):
    """Récupère le contenu des balises <meta name=... content=...>.

    POURQUOI UN VRAI ANALYSEUR : une expression régulière sur `content="..."` se
    casse dès que la valeur contient une apostrophe (`content="J'ai roulé…"`) —
    la regex s'arrête au premier `'` et ne renvoie qu'un « J ». Vécu le 22/09/2026 :
    27 descriptions sur 100 étaient tronquées à 1-2 caractères.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        d = {k.lower(): (v or "") for k, v in attrs}
        nom = (d.get("name") or d.get("property") or "").lower()
        if nom in ("description", "og:description", "twitter:description") and "description" not in self.metas:
            self.metas["description"] = d.get("content", "")
        if nom == "og:title" and "og:title" not in self.metas:
            self.metas["og:title"] = d.get("content", "")


def meta_description(html):
    p = MetaExtracteur()
    try:
        p.feed(html)
    except Exception:
        pass
    return re.sub(r"\s+", " ", p.metas.get("description", "")).strip()


def entree(p, rel):
    html = lire(p)
    titre = texte(TITRE.search(html).group(1)) if TITRE.search(html) else ""
    desc = meta_description(html)
    h1 = H1.search(html)
    sections = [texte(x) for x in H2.findall(html)]
    sections = [s for s in sections if s][:14]

    # extrait : premier <p> substantiel du corps
    extrait = ""
    for m in P.finditer(html):
        t = texte(m.group(1))
        if len(t) >= 90:
            extrait = t[:400]
            break
    if not extrait:
        extrait = texte(html)[:400]

    # filet de sécurité : si la page n'a pas de meta description, on en fabrique
    # une à partir du premier paragraphe — sinon la recherche n'affiche rien.
    if len(desc) < 40:
        desc = extrait[:300]

    return {
        "url": url_de(rel),
        "titre": titre,
        "description": desc,
        "h1": texte(h1.group(1)) if h1 else "",
        "extrait": extrait,
        "sections": sections,
    }


def main(apercu=False):
    interdits = regles_robots()
    pages = sorted(f for f in glob.glob(f"{REPO}/**/*.html", recursive=True)
                   if "/.git/" not in f and "/node_modules/" not in f)

    retenues, exclues = [], []
    for p in pages:
        rel = os.path.relpath(p, REPO).replace(os.sep, "/")
        html = lire(p)
        raison = None
        if rel in EXCLUS:
            raison = "page outil (EXCLUS)"
        elif NOINDEX.search(html):
            raison = "balise noindex"
        else:
            b = bloque("/" + rel, interdits)
            if b:
                raison = f"robots.txt : {b}"
        if raison:
            exclues.append({"fichier": rel, "raison": raison})
        else:
            retenues.append(entree(p, rel))

    par_url = {}
    for r in retenues:
        par_url.setdefault(r["url"], r)
    retenues = sorted(par_url.values(), key=lambda x: x["url"])

    ancien = []
    if os.path.exists(SORTIE):
        try:
            ancien = json.load(open(SORTIE, encoding="utf-8"))
        except Exception:
            ancien = []
    vus_ancien = {e.get("url") for e in ancien}
    vus_nouveau = {e["url"] for e in retenues}
    ajouts = sorted(vus_nouveau - vus_ancien)
    retraits = sorted(vus_ancien - vus_nouveau)

    if apercu:
        print(f"index actuel : {len(ancien)} pages")
        print(f"index cible  : {len(retenues)} pages")
        print(f"  à AJOUTER : {len(ajouts)}   (donc introuvables par la recherche)")
        for u in ajouts[:25]:
            print(f"     + {u}")
        if len(ajouts) > 25:
            print(f"     … et {len(ajouts) - 25} autres")
        print(f"  à RETIRER : {len(retraits)}")
        for u in retraits[:10]:
            print(f"     − {u}")
        return 1 if (ajouts or retraits) else 0

    json.dump(retenues, open(SORTIE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"index de recherche régénéré : {len(retenues)} pages "
          f"({len(ajouts)} ajouts, {len(retraits)} retraits)")
    print(f"  {len(exclues)} page(s) volontairement exclue(s)")
    for u in ajouts[:20]:
        print(f"     + {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main(apercu="--verifier" in sys.argv))
