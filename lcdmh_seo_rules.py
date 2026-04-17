"""
LCDMH — Règles SEO post-génération
====================================
Module à importer dans page_article_generator.py et tout futur générateur.

Usage dans _build_final_html(), juste après markdown_to_html() :

    html = markdown_to_html(...)
    html = seo_postprocess(html, title=title, slug=slug, sel_vids=sel_vids)

Toutes les corrections sont non-destructives : si un élément est déjà correct,
il n'est pas touché. Si une correction échoue, le HTML original est conservé.
"""

import re
import json
from datetime import date

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────
SITE_DOMAIN   = "https://lcdmh.com"
GA4_ID        = "G-7GC33KPRMS"
GA4_SCRIPT    = (
    '<!-- Google tag (gtag.js) - GA4 LCDMH -->\n'
    f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>\n'
    f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag(\'js\',new Date());gtag(\'config\',\'{GA4_ID}\');</script>\n'
)
TITLE_MAX     = 60
DESC_MIN      = 70
DESC_MAX      = 160
TODAY         = date.today().isoformat()   # ex. "2026-04-17"


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLE 1 — Schema Product/Review : corriger la structure inversée
# ─────────────────────────────────────────────────────────────────────────────
def _fix_product_review_schema(html: str) -> str:
    """
    Détecte les blocs JSON-LD avec @type:Review en racine ayant itemReviewed:Product
    et les transforme en structure correcte : Product en racine, review imbriqué.

    Avant (INVALIDE pour Google Rich Results) :
        { "@type": "Review",
          "itemReviewed": { "@type": "Product", ... },
          "reviewRating": ... }

    Après (VALIDE) :
        { "@type": "Product",
          "aggregateRating": { ... },
          "review": { "@type": "Review", ... } }
    """
    def _fix_block(m):
        open_tag  = m.group(1)
        json_body = m.group(2)
        close_tag = m.group(3)

        try:
            data = json.loads(json_body.strip())
        except Exception:
            return m.group(0)   # JSON illisible → ne pas toucher

        items = data if isinstance(data, list) else [data]
        changed = False

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            if item.get("@type") != "Review":
                continue
            reviewed = item.get("itemReviewed")
            if not isinstance(reviewed, dict) or reviewed.get("@type") != "Product":
                continue

            # ── Construire le nouveau schema Product ──
            rating_val   = item.get("reviewRating", {}).get("ratingValue", "4")
            review_body  = item.get("reviewBody", "")
            author       = item.get("author", {"@type": "Person", "name": "Yves"})
            review_name  = item.get("name", "")
            publisher    = item.get("publisher")
            review_date  = item.get("datePublished", TODAY)

            new_item = {
                "@context": item.get("@context", "https://schema.org"),
                "@type": "Product",
                "name": reviewed.get("name", ""),
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "ratingValue": str(rating_val),
                    "bestRating":  "5",
                    "worstRating": "1",
                    "reviewCount": "1"
                },
                "review": {
                    "@type": "Review",
                    "reviewBody": review_body,
                    "author": author,
                    "reviewRating": {
                        "@type": "Rating",
                        "ratingValue": str(rating_val),
                        "bestRating": "5"
                    },
                    "datePublished": review_date
                }
            }

            # Copier les champs optionnels du Product d'origine
            for field in ("brand", "description", "category", "image"):
                if field in reviewed:
                    new_item[field] = reviewed[field]

            # Ajouter les champs optionnels du Review d'origine
            if review_name:
                new_item["review"]["name"] = review_name
            if publisher:
                new_item["review"]["publisher"] = publisher

            # Retirer @context des niveaux imbriqués
            new_item["review"].pop("@context", None)

            items[idx] = new_item
            changed = True

        if not changed:
            return m.group(0)

        new_data = items if isinstance(data, list) else items[0]
        try:
            new_json = json.dumps(new_data, indent=2, ensure_ascii=False)
            json.loads(new_json)  # vérification
        except Exception:
            return m.group(0)   # si erreur → conserver l'original

        return f"{open_tag}\n{new_json}\n{close_tag}"

    return re.sub(
        r'(<script[^>]*type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)',
        _fix_block,
        html,
        flags=re.I | re.DOTALL
    )


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLE 2 — VideoObject : ajouter un bloc JSON-LD pour chaque iframe YouTube
# ─────────────────────────────────────────────────────────────────────────────
def _ensure_video_jsonld(html: str, sel_vids: list = None) -> str:
    """
    Pour chaque video YouTube dans sel_vids (liste de dicts {id, title, ...}),
    vérifie qu'un VideoObject JSON-LD existe. Si absent → l'ajoute.

    ⚠️  uploadDate est mis à TODAY comme date par défaut.
        Lance fix_video_uploaddate.py après publication pour corriger avec la
        vraie date YouTube via yt-dlp.
    """
    if not sel_vids:
        return html

    # Identifier les video_ids déjà présents dans les JSON-LD
    existing_ids = set(re.findall(
        r'(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})',
        "\n".join(
            b for b in re.findall(
                r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',
                html, re.I | re.DOTALL
            )
        )
    ))

    new_blocks = []
    for vid in sel_vids:
        vid_id    = vid.get("id") or vid.get("video_id", "")
        vid_title = vid.get("title", "")
        if not vid_id or vid_id in existing_ids:
            continue

        upload_date = vid.get("uploadDate") or vid.get("upload_date") or TODAY
        duration    = vid.get("duration", "")    # ISO 8601, ex. PT12M34S
        thumb       = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"

        schema = {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": vid_title,
            "description": vid_title,
            "thumbnailUrl": thumb,
            "embedUrl": f"https://www.youtube.com/embed/{vid_id}",
            "contentUrl": f"https://www.youtube.com/watch?v={vid_id}",
            "uploadDate": upload_date,
        }
        if duration:
            schema["duration"] = duration

        block = (
            '<script type="application/ld+json">\n'
            + json.dumps(schema, indent=2, ensure_ascii=False)
            + '\n</script>'
        )
        new_blocks.append(block)
        existing_ids.add(vid_id)

    if new_blocks:
        html = html.replace("</head>", "\n".join(new_blocks) + "\n</head>", 1)

    return html


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLE 3 — Canonical : s'assurer qu'il est présent
# ─────────────────────────────────────────────────────────────────────────────
def _ensure_canonical(html: str, slug: str, subfolder: str = "articles") -> str:
    """
    Ajoute/corrige la balise canonical si absente.
    slug : ex. "test-benelli-trk-702-avis-15000-km-road-trip"
    subfolder : "articles", "roadtrips", "" pour la racine
    """
    # Vérifier si une canonical existe déjà (les deux ordres d'attributs)
    has_canonical = bool(
        re.search(r'<link[^>]*rel=["\']canonical["\']', html, re.I) or
        re.search(r'<link[^>]*href=[^>]*rel=["\']canonical["\']', html, re.I)
    )
    if has_canonical:
        return html

    if subfolder:
        url = f"{SITE_DOMAIN}/{subfolder}/{slug}.html"
    else:
        url = f"{SITE_DOMAIN}/{slug}.html"

    canonical_tag = f'<link rel="canonical" href="{url}"/>\n'
    return html.replace("</head>", canonical_tag + "</head>", 1)


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLE 4 — Open Graph : vérifier les 4 balises obligatoires
# ─────────────────────────────────────────────────────────────────────────────
def _ensure_og_tags(html: str, slug: str, title: str, description: str,
                    og_image: str = "", subfolder: str = "articles") -> str:
    """
    Ajoute les balises OG manquantes parmi : og:title, og:description, og:url, og:image.
    Ne remplace pas celles déjà présentes.
    """
    if subfolder:
        page_url = f"{SITE_DOMAIN}/{subfolder}/{slug}.html"
    else:
        page_url  = f"{SITE_DOMAIN}/{slug}.html"

    fallback_image = og_image or f"{SITE_DOMAIN}/img/og-lcdmh.jpg"

    needed = {
        "og:type":        '<meta property="og:type" content="article"/>',
        "og:title":       f'<meta property="og:title" content="{title[:TITLE_MAX]}"/>',
        "og:description": f'<meta property="og:description" content="{description[:DESC_MAX]}"/>',
        "og:url":         f'<meta property="og:url" content="{page_url}"/>',
        "og:image":       f'<meta property="og:image" content="{fallback_image}"/>',
    }

    tags_to_add = []
    for prop, tag_html in needed.items():
        if f'property="{prop}"' not in html and f"property='{prop}'" not in html:
            tags_to_add.append(tag_html)

    if tags_to_add:
        html = html.replace("</head>", "\n".join(tags_to_add) + "\n</head>", 1)

    return html


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLE 5 — JSON-LD : éliminer les sauts de ligne dans les chaînes
# ─────────────────────────────────────────────────────────────────────────────
def _fix_jsonld_newlines(html: str) -> str:
    """
    Reparse et redumpe chaque bloc JSON-LD pour éliminer les sauts de ligne
    littéraux dans les valeurs de chaînes (erreur fréquente lors de génération
    automatique avec Claude).
    """
    def _clean_block(m):
        open_tag  = m.group(1)
        json_body = m.group(2)
        close_tag = m.group(3)
        try:
            data = json.loads(json_body.strip())
            clean = json.dumps(data, indent=2, ensure_ascii=False)
            json.loads(clean)  # vérification
            return f"{open_tag}\n{clean}\n{close_tag}"
        except Exception:
            return m.group(0)

    return re.sub(
        r'(<script[^>]*type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)',
        _clean_block,
        html,
        flags=re.I | re.DOTALL
    )


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLE 6 — Titre : vérifier la longueur (alerte uniquement, pas de troncature)
# ─────────────────────────────────────────────────────────────────────────────
def check_title_length(title: str) -> str | None:
    """
    Retourne un message d'avertissement si le titre est trop long, None sinon.
    """
    ln = len(title.strip())
    if ln > TITLE_MAX:
        return f"⚠️  TITRE TROP LONG : {ln} chars (max {TITLE_MAX}) → raccourcir avant de publier"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLE 7 — Meta description : vérifier la plage (alerte uniquement)
# ─────────────────────────────────────────────────────────────────────────────
def check_desc_length(desc: str) -> str | None:
    """
    Retourne un message d'avertissement si la meta description est hors plage.
    """
    ln = len(desc.strip())
    if ln < DESC_MIN:
        return f"⚠️  META DESCRIPTION TROP COURTE : {ln} chars (min {DESC_MIN})"
    if ln > DESC_MAX:
        return f"⚠️  META DESCRIPTION TROP LONGUE : {ln} chars (max {DESC_MAX}) → tronquer"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL — à appeler depuis _build_final_html()
# ─────────────────────────────────────────────────────────────────────────────
def seo_postprocess(
    html: str,
    title: str = "",
    description: str = "",
    slug: str = "",
    subfolder: str = "articles",
    sel_vids: list = None,
    og_image: str = "",
) -> tuple[str, list[str]]:
    """
    Applique toutes les règles SEO en post-traitement et retourne (html_corrigé, warnings).

    Intégration dans page_article_generator.py :

        from lcdmh_seo_rules import seo_postprocess, check_title_length, check_desc_length

        # Dans _build_final_html(), après markdown_to_html() :
        html, seo_warnings = seo_postprocess(
            html,
            title=title,
            description=meta_desc,
            slug=slug,
            subfolder="articles",
            sel_vids=sel_vids,
            og_image=og_image,
        )
        # Afficher les avertissements dans Streamlit :
        for w in seo_warnings:
            st.warning(w)

    Retourne :
        html         : HTML corrigé (Product/Review, VideoObject, canonical, OG tags, JSON-LD clean)
        seo_warnings : Liste de messages d'alerte à afficher à l'utilisateur
    """
    warnings = []

    # ── R1 : Product/Review ──
    html = _fix_product_review_schema(html)

    # ── R2 : VideoObject JSON-LD ──
    html = _ensure_video_jsonld(html, sel_vids=sel_vids)

    # ── R3 : Canonical ──
    if slug:
        html = _ensure_canonical(html, slug=slug, subfolder=subfolder)

    # ── R4 : OG tags ──
    if slug:
        html = _ensure_og_tags(
            html,
            slug=slug,
            title=title,
            description=description,
            og_image=og_image,
            subfolder=subfolder,
        )

    # ── R5 : JSON-LD newlines ──
    html = _fix_jsonld_newlines(html)

    # ── R6 : Alerte titre ──
    if title:
        w = check_title_length(title)
        if w:
            warnings.append(w)

    # ── R7 : Alerte meta description ──
    if description:
        w = check_desc_length(description)
        if w:
            warnings.append(w)

    return html, warnings


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT SEO CORRIGÉ — remplace le prompt dans _optimize_seo()
# ─────────────────────────────────────────────────────────────────────────────
SEO_OPTIMIZE_PROMPT_RULES = """
RÈGLES SEO STRICTES (à respecter impérativement) :
- title_suggestion     : MAXIMUM 60 caractères (pas 65). Mot-clé en premier.
- meta_description     : Entre 70 et 160 caractères. Commence par le mot-clé.
- Pas de | pipe dans le titre — utiliser un tiret — ou deux points :
- Pas de majuscules inutiles dans le titre
- Pas de bourrage de mots-clés (densité naturelle)
"""
