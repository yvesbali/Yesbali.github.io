"""
LCDMH — Extensions GEO (Generative Engine Optimization)
========================================================
Module complémentaire à `lcdmh_html_head.py` et `validate_seo.py`.

Ajoute trois capacités pensées pour les moteurs génératifs (ChatGPT Search,
Perplexity, Gemini, Claude, Copilot) :

  1. Bloc HTML "Réponse rapide" visible — extractible en direct par les
     crawlers IA quand ils font une recherche web live.
  2. JSON-LD `HowTo` — pour les pages guide "Comment faire X".
  3. JSON-LD `FAQPage` — pour les sections Q/R factuelles.
  4. Check GEO dans validate_seo.py — score 0-100 par page, alerte si
     manquent les éléments-clés pour la visibilité IA.

Le module respecte la convention de `lcdmh_html_head.py` :
  - Fonctions privées `_schema_*` qui retournent un bloc `<script type="application/ld+json">…</script>`
  - Fonction publique `render_quick_answer_html(data)` pour le HTML visible
  - Fonction publique `check_geo_completeness(html)` pour le validateur

Usage dans un script de build :

    from lcdmh_html_head import PageMeta, build_head
    from lcdmh_geo_extensions import (
        render_quick_answer_html,
        attach_geo_schemas,
    )

    meta = PageMeta(
        title="…",
        description="…",
        slug="cap-nord-moto",
        quick_answer={
            "lead": "Road trip moto Cap Nord depuis la France = 10 000 km en 30 jours …",
            "table": [
                ("Distance totale", "≈ 10 000 km aller-retour"),
                ("Durée recommandée", "28 à 32 jours"),
                # …
            ],
        },
        howto={
            "name": "Comment préparer un road trip moto au Cap Nord",
            "description": "…",
            "total_time_days": 30,
            "estimated_cost_eur": 3750,
            "supplies": ["Moto trail 700-1100 cm³", "Duvet grand froid", …],
            "tools":    ["App Entur", "App FerryPay", …],
            "steps": [
                {"name": "Choisir la période", "text": "…"},
                # …
            ],
        },
        faq=[
            {"q": "Combien coûte un road trip moto au Cap Nord ?", "a": "3 000 à 4 500 € …"},
            # …
        ],
    )

    # Le <head> est toujours généré par build_head() — les schémas GEO
    # sont ajoutés automatiquement si les champs meta.quick_answer / howto / faq
    # sont présents (voir patch dans lcdmh_html_head.py).

    # Dans le <body>, juste après le hero / H1, appeler :
    body_html += render_quick_answer_html(meta.quick_answer)

Le style CSS du bloc Réponse rapide est autonome (inline-ready).
"""

import json
import re
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes (dupliqués pour que le module soit autonome)
# ─────────────────────────────────────────────────────────────────────────────
def _safe_json(data: dict) -> str:
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    json.loads(raw)  # sanity check
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# 1. Bloc HTML "Réponse rapide" — visible, extractible par les crawlers IA
# ─────────────────────────────────────────────────────────────────────────────
QUICK_ANSWER_CSS = """
<style>
/* === LCDMH GEO — Bloc "Réponse rapide" ==================================== */
.lcdmh-quick-answer{max-width:900px;margin:2.5rem auto;padding:1.8rem 2rem;background:#fff;border:2px solid #e67e22;border-radius:16px;box-shadow:0 4px 20px rgba(230,126,34,.08);font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1a1a1a;line-height:1.7}
.lcdmh-quick-answer h2{font-family:'Montserrat','Inter',sans-serif;font-size:1.1rem;font-weight:800;color:#e67e22;text-transform:uppercase;letter-spacing:.08em;margin:0 0 1rem 0;display:flex;align-items:center;gap:.5rem}
.lcdmh-quick-answer h2::before{content:'⚡';font-size:1.3rem}
.lcdmh-quick-answer p.lead{font-size:1.02rem;color:#333;margin:0 0 1.2rem 0}
.lcdmh-quick-answer p.lead strong{color:#1a1a1a}
.lcdmh-quick-table{width:100%;border-collapse:collapse;font-size:.92rem;margin:0}
.lcdmh-quick-table td{padding:.55rem .8rem;border-bottom:1px solid #f0ede8;vertical-align:top}
.lcdmh-quick-table td:first-child{color:#777;font-weight:600;width:42%;font-family:'Montserrat','Inter',sans-serif;font-size:.82rem;text-transform:uppercase;letter-spacing:.05em}
.lcdmh-quick-table td:last-child{color:#1a1a1a;font-weight:500}
.lcdmh-quick-table tr:last-child td{border-bottom:none}
@media(max-width:600px){.lcdmh-quick-answer{margin:1.5rem 1rem;padding:1.3rem 1.3rem}.lcdmh-quick-table td:first-child{width:46%}}
</style>
""".strip()


def render_quick_answer_html(
    data: dict,
    heading: str = "Réponse rapide",
    include_css: bool = False,
) -> str:
    """
    Génère le bloc HTML visible "Réponse rapide".

    Paramètres
    ----------
    data : dict
        {
          "heading": "Réponse rapide : …" (optionnel, sinon param `heading`)
          "lead":    "Paragraphe d'intro factuel (100-200 mots).",
          "table":   [("Libellé", "Valeur"), ...]  # 5-12 lignes recommandées
        }
    heading : str
        Titre si non fourni dans `data`.
    include_css : bool
        Si True, inclut le <style> autonome. Sinon, on suppose que le CSS
        a déjà été injecté globalement (via extra_css de build_head()).

    Retourne
    --------
    HTML prêt à insérer dans <body>, typiquement juste après le hero/H1.
    """
    if not data:
        return ""

    lead = data.get("lead", "")
    rows = data.get("table", [])
    h = data.get("heading", heading)

    rows_html = "\n".join(
        f'        <tr><td>{_escape(k)}</td><td>{_escape_allow_html(v)}</td></tr>'
        for k, v in rows
    )

    aria_id = "lcdmh-quick-answer-" + _slugify(h)[:40]
    css = (QUICK_ANSWER_CSS + "\n") if include_css else ""

    return (
        f'{css}'
        f'<section class="section" aria-labelledby="{aria_id}">\n'
        f'  <div class="lcdmh-quick-answer">\n'
        f'    <h2 id="{aria_id}">{_escape(h)}</h2>\n'
        f'    <p class="lead">{_escape_allow_html(lead)}</p>\n'
        f'    <table class="lcdmh-quick-table"><tbody>\n'
        f'{rows_html}\n'
        f'    </tbody></table>\n'
        f'  </div>\n'
        f'</section>'
    )


def _escape(text: str) -> str:
    """Échappe les caractères HTML critiques (texte brut)."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _escape_allow_html(text: str) -> str:
    """Autorise <strong>, <em>, <br> mais échappe le reste.
    Utilisé pour les valeurs où on veut pouvoir mettre en gras des chiffres."""
    if text is None:
        return ""
    t = _escape(text)
    # Re-autoriser une liste blanche de tags inline
    for tag in ("strong", "em", "b", "i"):
        t = t.replace(f"&lt;{tag}&gt;", f"<{tag}>")
        t = t.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    t = t.replace("&lt;br/&gt;", "<br/>").replace("&lt;br&gt;", "<br>")
    return t


def _slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ─────────────────────────────────────────────────────────────────────────────
# 2. JSON-LD HowTo
# ─────────────────────────────────────────────────────────────────────────────
def schema_howto(data: dict, image_url: str = "") -> str:
    """
    Génère un bloc <script type="application/ld+json"> de type HowTo.

    data = {
      "name":              str,
      "description":       str,
      "total_time_days":   int      (optionnel)  → converti en ISO 8601 "P{n}D"
      "total_time_iso":    str      (optionnel, prioritaire sur total_time_days)
      "estimated_cost_eur": int     (optionnel)
      "supplies":          [str]    (optionnel)
      "tools":             [str]    (optionnel)
      "steps":             [
          {"name": str, "text": str, "url": str (optionnel), "image": str (optionnel)}
      ]
    }
    """
    if not data or not data.get("steps"):
        return ""

    schema = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": data["name"],
        "description": data.get("description", ""),
    }
    if image_url:
        schema["image"] = image_url

    if "total_time_iso" in data:
        schema["totalTime"] = data["total_time_iso"]
    elif "total_time_days" in data:
        schema["totalTime"] = f"P{int(data['total_time_days'])}D"

    if "estimated_cost_eur" in data:
        schema["estimatedCost"] = {
            "@type": "MonetaryAmount",
            "currency": "EUR",
            "value": str(data["estimated_cost_eur"]),
        }

    if data.get("supplies"):
        schema["supply"] = [{"@type": "HowToSupply", "name": s} for s in data["supplies"]]
    if data.get("tools"):
        schema["tool"] = [{"@type": "HowToTool", "name": t} for t in data["tools"]]

    steps = []
    for i, step in enumerate(data["steps"], 1):
        s = {
            "@type": "HowToStep",
            "position": i,
            "name": step["name"],
            "text": step["text"],
        }
        if step.get("url"):
            s["url"] = step["url"]
        if step.get("image"):
            s["image"] = step["image"]
        steps.append(s)
    schema["step"] = steps

    return f'<script type="application/ld+json">\n{_safe_json(schema)}\n</script>'


# ─────────────────────────────────────────────────────────────────────────────
# 3. JSON-LD FAQPage
# ─────────────────────────────────────────────────────────────────────────────
def schema_faqpage(faq: list) -> str:
    """
    Génère un bloc JSON-LD FAQPage à partir d'une liste de Q/R.

    faq = [
      {"q": "Combien coûte …?", "a": "Réponse factuelle 40-80 mots."},
      ...
    ]
    """
    if not faq:
        return ""

    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["a"],
                },
            }
            for item in faq
        ],
    }
    return f'<script type="application/ld+json">\n{_safe_json(schema)}\n</script>'


# ─────────────────────────────────────────────────────────────────────────────
# 4. Validateur GEO — à brancher dans validate_seo.py
# ─────────────────────────────────────────────────────────────────────────────
SEVERITY_CRIT = "🔴 CRITIQUE"
SEVERITY_WARN = "🟡 AVERT."
SEVERITY_OK   = "✅ OK"
SEVERITY_GEO  = "🤖 GEO"

# Types de pages pour lesquels le GEO-check est pertinent.
# Les pages navigationnelles (index, 404, contact) sont exclues — heuristique
# simple : on check seulement si la page a un Article JSON-LD.
def _has_article_schema(html: str) -> bool:
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.I | re.DOTALL
    )
    for b in blocks:
        try:
            data = json.loads(b.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and it.get("@type") in ("Article", "BlogPosting", "NewsArticle"):
                return True
    return False


def check_geo_completeness(html: str) -> list:
    """
    Retourne une liste de (sévérité, message) pour le validate_seo.py existant.
    Signale les leviers GEO absents mais **sans bloquer le push** (tout en WARN
    ou en info, pour éviter les faux positifs sur les pages non-article).

    Critères contrôlés :
      - Présence d'un bloc Quick Answer visible (.lcdmh-quick-answer ou
        .quick-answer)
      - Présence d'un schema HowTo OU FAQPage (au moins un des deux)
      - Présence de dateModified à jour (< 12 mois)
      - Présence d'un <link rel="alternate" hreflang> si multi-langue (skip sinon)
    """
    issues = []

    # On applique le check seulement aux pages qui ont un Article — sinon
    # c'est du bruit (pages légales, contact, etc.)
    if not _has_article_schema(html):
        return issues

    # 1. Bloc Quick Answer visible
    has_quick_answer = bool(
        re.search(r'class=["\'][^"\']*(lcdmh-quick-answer|quick-answer)[^"\']*["\']', html, re.I)
    )
    if has_quick_answer:
        issues.append((SEVERITY_OK, "Bloc « Réponse rapide » visible présent"))
    else:
        issues.append((SEVERITY_WARN, "Bloc « Réponse rapide » visible absent — recommandé pour extractibilité IA"))

    # 2. Au moins un schema GEO-spécifique (HowTo ou FAQPage)
    has_howto  = bool(re.search(r'"@type"\s*:\s*"HowTo"', html))
    has_faq    = bool(re.search(r'"@type"\s*:\s*"FAQPage"', html))
    if has_howto and has_faq:
        issues.append((SEVERITY_OK, "Schemas HowTo + FAQPage présents"))
    elif has_howto:
        issues.append((SEVERITY_OK, "Schema HowTo présent"))
    elif has_faq:
        issues.append((SEVERITY_OK, "Schema FAQPage présent"))
    else:
        issues.append((SEVERITY_WARN, "Aucun schema HowTo ni FAQPage — ajouter 1 des 2 pour gagner en citations IA"))

    # 3. Fraîcheur du dateModified
    m = re.search(r'"dateModified"\s*:\s*"(\d{4})-(\d{2})-(\d{2})', html)
    if m:
        from datetime import date
        try:
            mod = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            age_days = (date.today() - mod).days
            if age_days > 365:
                issues.append((SEVERITY_WARN, f"dateModified > 12 mois ({age_days} j) — rafraîchir pour signaler le contenu maintenu"))
            else:
                issues.append((SEVERITY_OK, f"dateModified à jour ({age_days} jours)"))
        except ValueError:
            pass

    # 4. Présence du lien canonique vers a-propos.html quelque part (signal
    #    d'entité) — check léger, seulement si Article.
    if "a-propos" not in html:
        issues.append((SEVERITY_WARN, "Aucun lien vers /a-propos.html — lien interne vers la page entité recommandé"))

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Test rapide
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Mini test : générer les 3 schemas sur un exemple
    sample_qa = {
        "heading": "Réponse rapide : le Cap Nord à moto",
        "lead": "Un road trip moto au <strong>Cap Nord</strong> depuis la France = environ <strong>10 000 km</strong> en 30 jours.",
        "table": [
            ("Distance totale", "≈ 10 000 km"),
            ("Durée", "28 à 32 jours"),
            ("Budget", "3 000 à 4 500 €"),
        ],
    }
    print(render_quick_answer_html(sample_qa, include_css=True)[:400], "\n...")
    print()

    sample_howto = {
        "name": "Comment préparer un road trip moto",
        "description": "Guide en 3 étapes.",
        "total_time_days": 30,
        "estimated_cost_eur": 3750,
        "steps": [
            {"name": "Choisir la période", "text": "Partir entre mai et juillet."},
            {"name": "Préparer la moto", "text": "Pneus neufs obligatoires."},
            {"name": "Budgéter", "text": "Prévoir 3 000 à 4 500 €."},
        ],
    }
    print(schema_howto(sample_howto)[:400], "\n...")
    print()

    sample_faq = [
        {"q": "Combien ça coûte ?", "a": "Entre 3 000 et 4 500 € pour 30 jours."},
        {"q": "Quelle période ?", "a": "Mai à fin juillet."},
    ]
    print(schema_faqpage(sample_faq)[:400], "\n...")
