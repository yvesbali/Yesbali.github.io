#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_articles.py — Générateur statique pour articles.html
Source de vérité : data/articles-data.json
Utilisation : python build_articles.py
"""

import json
import re
import math
from datetime import date, datetime
from pathlib import Path

# ── Chemins ────────────────────────────────────────────────────────────────
BASE   = Path(__file__).parent
JSON   = BASE / "data" / "articles-data.json"
HTML   = BASE / "articles.html"

# ── Utilitaires ──────────────────────────────────────────────────────────────
def escape(s):
    """Échappe les caractères HTML dangereux (identique à escapeHtml JS)."""
    return (str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;"))

# ── Templates HTML (identiques aux fonctions JS dans articles.html) ──────────
def tpl_article_card(a):
    return (
        f'<a href="{a["href"]}" class="article-card">'
        f'<div class="article-thumb">'
        f'<img src="{a["img"]}" alt="{escape(a["alt"])}" loading="lazy">'
        f'</div>'
        f'<div class="article-body">'
        f'<span class="article-tag">{escape(a["tag"])}</span>'
        f'<h3>{escape(a["title"])}</h3>'
        f'<p>{escape(a["excerpt"])}</p>'
        f'<span class="article-btn">Lire l\'article →</span>'
        f'</div>'
        f'</a>'
    )

def tpl_featured_main(a):
    return (
        f'<div class="featured-image">'
        f'<img src="{a["img"]}" alt="{escape(a["alt"])}" loading="eager">'
        f'</div>'
        f'<div class="featured-body">'
        f'<div class="meta-line">{escape(a["tag"])} • Article à la une</div>'
        f'<h3>{escape(a["title"])}</h3>'
        f'<p>{escape(a["excerpt"])}</p>'
        f'<div class="featured-actions">'
        f'<a class="featured-btn featured-btn-primary" href="{a["href"]}">Lire l\'article</a>'
        f'<a class="featured-btn featured-btn-secondary" href="#road-trips">Voir les catégories</a>'
        f'</div>'
        f'</div>'
    )

def tpl_featured_mini(a):
    return (
        f'<a href="{a["href"]}" class="featured-mini">'
        f'<div class="featured-mini-image">'
        f'<img src="{a["img"]}" alt="{escape(a["alt"])}" loading="lazy">'
        f'</div>'
        f'<div class="featured-mini-body">'
        f'<div class="meta-line">{escape(a["tag"])}</div>'
        f'<h3>{escape(a["title"])}</h3>'
        f'<p>{escape(a["excerpt"])}</p>'
        f'</div>'
        f'</a>'
    )

def tpl_popular_item(a, index):
    return (
        f'<a href="{a["href"]}" class="popular-item">'
        f'<div class="popular-rank">{index + 1}</div>'
        f'<div>'
        f'<strong>{escape(a["title"])}</strong>'
        f'<span>{escape(a["tag"])}</span>'
        f'</div>'
        f'</a>'
    )

# ── Logique de rotation ──────────────────────────────────────────────────────
def get_featured_slug(cfg):
    """Calcule quel article est à la une aujourd'hui (rotation 56 jours)."""
    ref  = date.fromisoformat(cfg["featured_rotation_ref"])
    days = (date.today() - ref).days
    idx  = math.floor(max(0, days) / cfg["featured_rotation_days"]) % len(cfg["featured_rotation_slugs"])
    return cfg["featured_rotation_slugs"][idx]

# ── Remplacement dans le HTML ────────────────────────────────────────────────
def replace_inner(html, element_id, new_content):
    """
    Remplace le contenu (innerHTML) d'un élément identifié par son id.
    Gère correctement les imbrications en comptant les niveaux d'ouverture/fermeture.
    """
    TAGS = r'(?:div|article|aside|section|ul|ol|main)'

    # Trouver le tag ouvrant avec l'id demandé
    open_pat = re.compile(
        r'<(' + TAGS + r')\b[^>]*\bid="' + re.escape(element_id) + r'"[^>]*>',
        re.IGNORECASE
    )
    m_open = open_pat.search(html)
    if not m_open:
        print(f"  ⚠ id='{element_id}' non trouvé — ignoré")
        return html

    tag_name = m_open.group(1).lower()
    inner_start = m_open.end()

    # Suivre la profondeur pour trouver le tag fermant correspondant
    depth = 1
    pos   = inner_start
    open_re  = re.compile(r'<'  + tag_name + r'\b', re.IGNORECASE)
    close_re = re.compile(r'</' + tag_name + r'\s*>', re.IGNORECASE)

    while depth > 0 and pos < len(html):
        mo = open_re.search(html, pos)
        mc = close_re.search(html, pos)
        if mc is None:
            print(f"  ⚠ tag fermant introuvable pour id='{element_id}'")
            return html
        if mo is not None and mo.start() < mc.start():
            depth += 1
            pos = mo.end()
        else:
            depth -= 1
            if depth == 0:
                inner_end  = mc.start()
                close_tag  = mc.group(0)
                close_end  = mc.end()
                replacement = (html[:m_open.start()] +
                               m_open.group(0) + "\n" +
                               new_content + "\n" +
                               close_tag +
                               html[close_end:])
                return replacement
            pos = mc.end()

    print(f"  ⚠ fermeture non trouvée pour id='{element_id}'")
    return html

# ── Point d'entrée ────────────────────────────────────────────────────────────
def main():
    print("⚙  build_articles.py — génération statique")

    # 1. Charger le JSON
    data     = json.loads(JSON.read_text(encoding="utf-8"))
    cfg      = data["config"]
    articles = data["articles"]
    by_slug  = {a["slug"]: a for a in articles}

    # 2. Calculer l'article à la une
    featured_slug = get_featured_slug(cfg)
    featured      = by_slug.get(featured_slug, articles[0])
    print(f"   À la une : {featured_slug}")

    # 3. Articles secondaires et populaires
    secondary_slugs  = cfg["featured_secondary_slugs"]
    secondaries = [by_slug[s] for s in secondary_slugs if s in by_slug and s != featured_slug][:2]

    popular_slugs = cfg["popular_slugs"]
    populars      = [by_slug[s] for s in popular_slugs if s in by_slug][:4]

    # 4. Grilles par catégorie
    categories = ["road-trips", "tests-materiel", "guides-pratiques", "tests-motos", "photo-video"]
    grids = {cat: [a for a in articles if a["category"] == cat] for cat in categories}

    # 5. Lire le HTML actuel
    html = HTML.read_text(encoding="utf-8")

    # 6. Remplacer chaque zone
    html = replace_inner(html, "featured-main",          tpl_featured_main(featured))
    html = replace_inner(html, "featured-side",          "".join(tpl_featured_mini(a) for a in secondaries))
    html = replace_inner(html, "grid-road-trips",        "".join(tpl_article_card(a) for a in grids["road-trips"]))
    html = replace_inner(html, "grid-tests-materiel",    "".join(tpl_article_card(a) for a in grids["tests-materiel"]))
    html = replace_inner(html, "grid-guides-pratiques",  "".join(tpl_article_card(a) for a in grids["guides-pratiques"]))
    html = replace_inner(html, "grid-tests-motos",       "".join(tpl_article_card(a) for a in grids["tests-motos"]))
    html = replace_inner(html, "grid-photo-video",       "".join(tpl_article_card(a) for a in grids["photo-video"]))
    html = replace_inner(html, "popular-list",           "".join(tpl_popular_item(a, i) for i, a in enumerate(populars)))

    # 7. Mettre à jour les compteurs textuels
    total = len(articles)
    # stat-total-articles (span ou tout élément avec cet id)
    html = re.sub(
        r'(<[^>]+\bid="stat-total-articles"[^>]*>)\d+(<)',
        rf'\g<1>{total}\2',
        html
    )
    # footer-count
    html = re.sub(
        r'(<[^>]+\bid="footer-count"[^>]*>)[^<]*(</)',
        rf'\g<1>📖 {total} articles publiés — Page articles mise à jour\2',
        html
    )

    # 8. Écrire le résultat
    HTML.write_text(html, encoding="utf-8")
    print(f"   {total} articles — articles.html mis à jour ✓")
    print(f"   Rotation : {featured_slug} (idx calculé depuis {cfg['featured_rotation_ref']}, {cfg['featured_rotation_days']}j)")

if __name__ == "__main__":
    main()
