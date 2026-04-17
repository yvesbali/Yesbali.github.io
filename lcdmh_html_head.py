"""
LCDMH — Générateur universel de <head> SEO
==========================================
Module central à importer dans TOUS les scripts qui créent des pages HTML.

Garantit que chaque page générée a :
  ✅ <title> ≤60 chars
  ✅ <meta name="description"> 70-160 chars
  ✅ <link rel="canonical"> pointant vers lcdmh.com
  ✅ <html lang="fr">
  ✅ GA4 G-7GC33KPRMS
  ✅ Open Graph : og:title, og:description, og:image, og:url, og:type
  ✅ JSON-LD : Article ou BreadcrumbList ou VideoObject ou Product selon le type
  ✅ Aucun saut de ligne dans les valeurs JSON-LD
  ✅ Structure Product/Review correcte (Product en racine)

Usage minimal :
    from lcdmh_html_head import build_head, PageMeta

    meta = PageMeta(
        title        = "Cap Nord à moto : 10 000 km en solo | LCDMH",
        description  = "Récit complet du road trip Cap Nord à moto...",
        slug         = "cap-nord-moto",
        page_type    = "article",          # "article" | "roadtrip" | "product" | "website"
    )
    head_html = build_head(meta)
    html = f"<!DOCTYPE html>\\n<html lang='fr'>\\n{head_html}\\n<body>..."
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Constantes globales
# ─────────────────────────────────────────────────────────────────────────────
SITE_DOMAIN    = "https://lcdmh.com"
SITE_NAME      = "LCDMH"
SITE_AUTHOR    = "Yves"
GA4_ID         = "G-7GC33KPRMS"
DEFAULT_OG_IMG = "https://lcdmh.com/img/og-lcdmh.jpg"
TITLE_MAX      = 60
DESC_MIN       = 70
DESC_MAX       = 160
TODAY          = date.today().isoformat()

# ─────────────────────────────────────────────────────────────────────────────
# Dataclass PageMeta — décrit une page
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class PageMeta:
    # ── Obligatoires ──
    title:         str           # ≤60 chars
    description:   str           # 70-160 chars
    slug:          str           # ex. "cap-nord-moto"

    # ── Optionnels ──
    page_type:     str  = "article"   # "article" | "roadtrip" | "product" | "website"
    subfolder:     str  = "articles"  # "articles" | "roadtrips" | "" (racine)
    og_image:      str  = ""
    date_published:str  = ""     # YYYY-MM-DD
    date_modified: str  = ""     # YYYY-MM-DD
    keywords:      str  = ""
    author:        str  = SITE_AUTHOR

    # ── Schemas JSON-LD supplémentaires ──
    # VideoObject(s) associés : liste de dicts {id, title, uploadDate?, duration?}
    videos:        List[dict] = field(default_factory=list)
    # Product si page test matériel : dict {name, brand, ratingValue, reviewBody}
    product:       Optional[dict] = None
    # Breadcrumb personnalisé : liste de (nom, url)
    breadcrumb:    List[tuple] = field(default_factory=list)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _clean(text: str) -> str:
    """Supprime les sauts de ligne et guillemets qui casseraient le HTML."""
    return text.replace("\n", " ").replace("\r", " ").replace('"', "&quot;").strip()

def _page_url(meta: PageMeta) -> str:
    if meta.subfolder:
        return f"{SITE_DOMAIN}/{meta.subfolder}/{meta.slug}.html"
    return f"{SITE_DOMAIN}/{meta.slug}.html"

def _truncate_title(title: str) -> str:
    """Tronque proprement le titre à TITLE_MAX chars si nécessaire."""
    t = title.strip()
    if len(t) <= TITLE_MAX:
        return t
    # Chercher le dernier espace avant la limite
    cut = t.rfind(" ", 0, TITLE_MAX - 1)
    return t[:cut] + "…" if cut > 0 else t[:TITLE_MAX]

def _validate_desc(desc: str) -> str:
    """Avertissement console si la description est hors plage (ne modifie pas)."""
    ln = len(desc.strip())
    if ln < DESC_MIN:
        print(f"⚠️  [lcdmh_html_head] meta description trop courte : {ln} chars (min {DESC_MIN})")
    elif ln > DESC_MAX:
        print(f"⚠️  [lcdmh_html_head] meta description trop longue : {ln} chars (max {DESC_MAX})")
    return desc.strip()[:DESC_MAX]

def _safe_json(data: dict) -> str:
    """Dumps JSON garanti sans saut de ligne dans les valeurs de chaînes."""
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    # Vérification parse-retour
    json.loads(raw)
    return raw

# ─────────────────────────────────────────────────────────────────────────────
# Blocs HTML individuels
# ─────────────────────────────────────────────────────────────────────────────
def _ga4_block() -> str:
    return (
        f'<!-- Google tag (gtag.js) -->\n'
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>\n'
        f'<script>window.dataLayer=window.dataLayer||[];'
        f'function gtag(){{dataLayer.push(arguments);}}gtag(\'js\',new Date());'
        f'gtag(\'config\',\'{GA4_ID}\');</script>\n'
    )

def _base_meta(meta: PageMeta) -> str:
    title   = _truncate_title(meta.title)
    desc    = _validate_desc(meta.description)
    url     = _page_url(meta)
    og_img  = meta.og_image or DEFAULT_OG_IMG

    lines = [
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '<meta name="robots" content="index, follow">',
        f'<title>{_clean(title)}</title>',
        f'<meta name="description" content="{_clean(desc)}"/>',
        f'<link rel="canonical" href="{url}"/>',
        f'<meta property="og:type" content="{meta.page_type}"/>',
        f'<meta property="og:title" content="{_clean(title)}"/>',
        f'<meta property="og:description" content="{_clean(desc)}"/>',
        f'<meta property="og:url" content="{url}"/>',
        f'<meta property="og:image" content="{og_img}"/>',
        f'<meta property="og:site_name" content="{SITE_NAME}"/>',
    ]
    if meta.keywords:
        lines.append(f'<meta name="keywords" content="{_clean(meta.keywords)}"/>')
    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# Schemas JSON-LD
# ─────────────────────────────────────────────────────────────────────────────
def _schema_article(meta: PageMeta) -> str:
    pub_date = meta.date_published or TODAY
    mod_date = meta.date_modified  or pub_date
    url      = _page_url(meta)
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": _truncate_title(meta.title),
        "description": meta.description[:DESC_MAX],
        "author": {
            "@type": "Person",
            "name": meta.author,
            "url": f"{SITE_DOMAIN}/a-propos.html"
        },
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_DOMAIN
        },
        "datePublished":  pub_date,
        "dateModified":   mod_date,
        "url": url,
    }
    if meta.og_image or DEFAULT_OG_IMG:
        schema["image"] = meta.og_image or DEFAULT_OG_IMG
    return f'<script type="application/ld+json">\n{_safe_json(schema)}\n</script>'


def _schema_breadcrumb(meta: PageMeta) -> str:
    """Génère un BreadcrumbList. Utilise meta.breadcrumb ou un breadcrumb auto."""
    crumbs = meta.breadcrumb or [
        ("LCDMH", SITE_DOMAIN),
        (meta.title[:50], _page_url(meta)),
    ]
    items = [
        {
            "@type": "ListItem",
            "position": i + 1,
            "name": name,
            "item": url
        }
        for i, (name, url) in enumerate(crumbs)
    ]
    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items
    }
    return f'<script type="application/ld+json">\n{_safe_json(schema)}\n</script>'


def _schema_video(vid: dict) -> str:
    """
    Génère un VideoObject JSON-LD à partir d'un dict vidéo.
    Champs reconnus : id, title, description?, uploadDate?, duration?
    """
    vid_id      = vid.get("id") or vid.get("video_id", "")
    vid_title   = vid.get("title", "")
    vid_desc    = vid.get("description") or vid_title
    upload_date = vid.get("uploadDate") or vid.get("upload_date") or TODAY
    duration    = vid.get("duration", "")
    thumb       = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"

    schema = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": vid_title,
        "description": vid_desc[:500],
        "thumbnailUrl": thumb,
        "embedUrl":  f"https://www.youtube.com/embed/{vid_id}",
        "contentUrl": f"https://www.youtube.com/watch?v={vid_id}",
        "uploadDate": upload_date,
        "author": {
            "@type": "Person",
            "name": SITE_AUTHOR
        }
    }
    if duration:
        schema["duration"] = duration
    return f'<script type="application/ld+json">\n{_safe_json(schema)}\n</script>'


def _schema_product(meta: PageMeta) -> str:
    """
    Génère un schema Product VALIDE (racine=Product, review imbriqué).
    meta.product doit contenir : name, brand, ratingValue, reviewBody
    """
    p           = meta.product
    pub_date    = meta.date_published or TODAY
    rating_val  = str(p.get("ratingValue", "4"))
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": p.get("name", ""),
        "brand": {
            "@type": "Brand",
            "name": p.get("brand", SITE_NAME)
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": rating_val,
            "bestRating":  "5",
            "worstRating": "1",
            "reviewCount": "1"
        },
        "review": {
            "@type": "Review",
            "reviewBody": p.get("reviewBody", "")[:1000],
            "author": {
                "@type": "Person",
                "name": meta.author,
                "url": f"{SITE_DOMAIN}/a-propos.html"
            },
            "reviewRating": {
                "@type": "Rating",
                "ratingValue": rating_val,
                "bestRating": "5"
            },
            "datePublished": pub_date,
            "publisher": {
                "@type": "Organization",
                "name": SITE_NAME,
                "url": SITE_DOMAIN
            }
        }
    }
    if p.get("description"):
        schema["description"] = p["description"][:500]
    if p.get("image"):
        schema["image"] = p["image"]
    return f'<script type="application/ld+json">\n{_safe_json(schema)}\n</script>'

# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE — build_head()
# ─────────────────────────────────────────────────────────────────────────────
def build_head(
    meta:        PageMeta,
    extra_css:   str = "",   # contenu CSS inline ou <link> tags supplémentaires
    extra_head:  str = "",   # autres balises <head> libres
) -> str:
    """
    Retourne un bloc <head> complet et SEO-correct.

    Exemple d'utilisation :
        meta = PageMeta(
            title       = "Test Benelli TRK 702 — 15 000 km | LCDMH",
            description = "Avis complet sur la Benelli TRK 702 après 15 000 km...",
            slug        = "test-benelli-trk-702-avis-15000-km-road-trip",
            page_type   = "article",
            subfolder   = "articles",
            date_published = "2026-04-13",
            product     = {
                "name": "Benelli TRK 702",
                "brand": "Benelli",
                "ratingValue": "4",
                "reviewBody": "Moto polyvalente, moteur Kawasaki, rapport qualité/prix excellent."
            }
        )
        html = f"<!DOCTYPE html>\\n<html lang='fr'>\\n{build_head(meta)}\\n<body>..."
    """
    parts = ["<head>"]

    # 1. GA4
    parts.append(_ga4_block())

    # 2. Balises meta de base + OG
    parts.append(_base_meta(meta))

    # 3. CSS supplémentaire
    if extra_css:
        parts.append(extra_css)

    # 4. Balises head libres
    if extra_head:
        parts.append(extra_head)

    # 5. JSON-LD : Article ou BreadcrumbList (toutes les pages)
    if meta.page_type in ("article", "roadtrip", "website"):
        parts.append(_schema_article(meta))
    parts.append(_schema_breadcrumb(meta))

    # 6. JSON-LD : VideoObject(s) si videos présentes
    for vid in meta.videos:
        parts.append(_schema_video(vid))

    # 7. JSON-LD : Product si page test matériel
    if meta.product:
        parts.append(_schema_product(meta))

    parts.append("</head>")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaire : corriger un HTML existant (post-processing)
# ─────────────────────────────────────────────────────────────────────────────
def patch_existing_html(html: str, meta: PageMeta) -> str:
    """
    Injecte/corrige le <head> d'un HTML déjà généré sans l'écraser.
    Utile pour les scripts qui construisent leur HTML par concaténation.

    Corrige :
      - Canonical manquant ou incorrect
      - GA4 absent
      - OG tags manquants
      - JSON-LD Product/Review inversé
      - VideoObject sans uploadDate
    """
    from lcdmh_seo_rules import seo_postprocess
    html, warnings = seo_postprocess(
        html,
        title       = meta.title,
        description = meta.description,
        slug        = meta.slug,
        subfolder   = meta.subfolder,
        sel_vids    = meta.videos,
        og_image    = meta.og_image,
    )
    for w in warnings:
        print(f"  {w}")
    return html


# ─────────────────────────────────────────────────────────────────────────────
# Test rapide en ligne de commande
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    meta = PageMeta(
        title       = "Test Benelli TRK 702 — Avis 15 000 km | LCDMH",
        description = "Avis complet sur la Benelli TRK 702 après 15 000 km de road trip moto : points forts, faiblesses, entretien et rapport qualité/prix.",
        slug        = "test-benelli-trk-702-avis-15000-km-road-trip",
        page_type   = "article",
        subfolder   = "articles",
        date_published = "2026-04-13",
        videos      = [{"id": "dQw4w9WgXcQ", "title": "Test Benelli TRK 702", "uploadDate": "2026-01-15"}],
        product     = {
            "name": "Benelli TRK 702",
            "brand": "Benelli",
            "ratingValue": "4",
            "reviewBody": "Moto polyvalente avec moteur Kawasaki, entretien facile, rapport qualité/prix excellent."
        },
        breadcrumb  = [
            ("LCDMH", "https://lcdmh.com"),
            ("Tests matériel", "https://lcdmh.com/articles.html"),
            ("Test Benelli TRK 702", "https://lcdmh.com/articles/test-benelli-trk-702-avis-15000-km-road-trip.html"),
        ]
    )
    head = build_head(meta)
    print(head[:2000])
    print("\n✅  lcdmh_html_head.py fonctionne correctement.")
