#!/usr/bin/env python3
"""
LCDMH — Validateur SEO pré-push
=================================
Lance avant chaque `git push` pour détecter les erreurs SEO courantes.

Usage :
    python validate_seo.py            # contrôle tous les HTML
    python validate_seo.py --fix      # (futur) correctifs automatiques
    python validate_seo.py articles/cap-nord-moto.html  # fichier unique

Codes de sortie :
    0  → tout est OK
    1  → au moins une erreur critique détectée
"""

import re, json, sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
BASE           = Path(__file__).parent
GOOD_GA4       = "G-7GC33KPRMS"
OLD_GA4        = "G-5DP7XR1C7W"
CANONICAL_DOMAIN = "lcdmh.com"
TITLE_MAX      = 60
DESC_MIN       = 70
DESC_MAX       = 160

OG_REQUIRED    = ["og:title", "og:description", "og:image", "og:url"]

SEVERITY_CRIT  = "🔴 CRITIQUE"
SEVERITY_WARN  = "🟡 AVERT."
SEVERITY_OK    = "✅ OK"

# Fichiers HTML présents dans le dépôt mais qui ne sont PAS des pages publiées
# (inclus de navigation, maquettes, documents internes…)
EXCLUDED_FILES = {
    "nav.html",
    "widget-roadtrip-snippet.html",
    "maquette_capnord_complete_v2.html",   # maquette draft
    "LCDMH_Cadrage_Projet.html",           # document interne de gestion de projet
}

# ─────────────────────────────────────────────────────────────────────────────
# Collecte des fichiers HTML
# ─────────────────────────────────────────────────────────────────────────────
def collect_html_files(args):
    if args:
        resolved = []
        for a in args:
            if Path(a).suffix != ".html":
                continue
            p = Path(a)
            if p.is_absolute():
                resolved.append(p)
            elif p.exists():                  # relatif au CWD (Windows : F:\LCDMH_GitHub_Audit)
                resolved.append(p.resolve())
            elif (BASE / p).exists():         # relatif au dossier du script
                resolved.append(BASE / p)
            else:
                print(f"⚠️  Fichier introuvable : {a}")
        if not resolved:
            print("⚠️  Aucun fichier .html valide dans les arguments.")
            sys.exit(1)
        return resolved
    all_files = (
        list(BASE.glob("*.html")) +
        list(BASE.glob("articles/*.html")) +
        list(BASE.glob("roadtrips/*.html"))
    )
    return [f for f in all_files if f.name not in EXCLUDED_FILES]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def extract_text(pattern, html, flags=re.I):
    """Retourne le premier groupe capturé ou None."""
    m = re.search(pattern, html, flags)
    return m.group(1).strip() if m else None

def count_occurrences(pattern, html, flags=re.I):
    return len(re.findall(pattern, html, flags))

def extract_json_ld_blocks(html):
    """Retourne la liste des chaînes JSON trouvées dans les blocs <script type=application/ld+json>."""
    return re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.I | re.DOTALL
    )

# ─────────────────────────────────────────────────────────────────────────────
# Checks individuels — chacun retourne une liste de (sévérité, message)
# ─────────────────────────────────────────────────────────────────────────────

def check_title(html):
    issues = []
    title = extract_text(r'<title[^>]*>(.*?)</title>', html, re.I | re.DOTALL)
    if not title:
        issues.append((SEVERITY_CRIT, "Balise <title> absente"))
    else:
        ln = len(title)
        if ln > TITLE_MAX:
            issues.append((SEVERITY_CRIT, f"Title trop long : {ln} chars (max {TITLE_MAX}) — \"{title[:50]}…\""))
        else:
            issues.append((SEVERITY_OK, f"Title OK ({ln} chars)"))
    return issues


def check_meta_description(html):
    issues = []
    # Gère les deux ordres d'attributs et les deux types de guillemets
    # Important : utiliser [^"] quand délimité par " (permet les apostrophes dans le texte)
    desc = (
        extract_text(r'<meta\s+name=["\']description["\']\s+content="([^"]*)"', html) or
        extract_text(r"<meta\s+name=[\"']description[\"']\s+content='([^']*)'", html) or
        extract_text(r'<meta\s+content="([^"]*)"\s+[^>]*name=["\']description["\']', html) or
        extract_text(r"<meta\s+content='([^']*)'\s+[^>]*name=[\"']description[\"']", html)
    )
    if not desc:
        issues.append((SEVERITY_CRIT, "Meta description absente"))
    else:
        ln = len(desc)
        if ln < DESC_MIN:
            issues.append((SEVERITY_WARN, f"Meta description trop courte : {ln} chars (min {DESC_MIN})"))
        elif ln > DESC_MAX:
            issues.append((SEVERITY_CRIT, f"Meta description trop longue : {ln} chars (max {DESC_MAX}) — \"{desc[:60]}…\""))
        else:
            issues.append((SEVERITY_OK, f"Meta description OK ({ln} chars)"))
    return issues


def check_canonical(html):
    issues = []
    # Gère les deux ordres : rel avant href, ou href avant rel
    canonical = (
        extract_text(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html) or
        extract_text(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', html)
    )
    if not canonical:
        issues.append((SEVERITY_CRIT, "Balise canonical absente"))
    elif CANONICAL_DOMAIN not in canonical:
        issues.append((SEVERITY_CRIT, f"Canonical ne pointe pas vers {CANONICAL_DOMAIN} : {canonical}"))
    else:
        issues.append((SEVERITY_OK, f"Canonical OK → {canonical}"))
    return issues


def check_h1(html):
    issues = []
    count = count_occurrences(r'<h1[\s>]', html)
    if count == 0:
        issues.append((SEVERITY_CRIT, "Aucun <h1> trouvé"))
    elif count > 1:
        issues.append((SEVERITY_CRIT, f"{count} balises <h1> trouvées (1 seule autorisée)"))
    else:
        issues.append((SEVERITY_OK, "H1 unique présent"))
    return issues


def check_lang(html):
    issues = []
    if re.search(r'<html[^>]*\blang=["\']fr["\']', html, re.I):
        issues.append((SEVERITY_OK, 'lang="fr" présent'))
    else:
        issues.append((SEVERITY_CRIT, 'Attribut lang="fr" absent sur <html>'))
    return issues


def check_ga4(html):
    issues = []
    if OLD_GA4 in html:
        issues.append((SEVERITY_CRIT, f"Ancien ID GA4 trouvé : {OLD_GA4} → remplacer par {GOOD_GA4}"))
    if GOOD_GA4 in html:
        issues.append((SEVERITY_OK, f"GA4 {GOOD_GA4} présent"))
    else:
        if OLD_GA4 not in html:
            issues.append((SEVERITY_WARN, f"Aucun tracking GA4 détecté ({GOOD_GA4})"))
    return issues


def check_json_ld(html):
    """Valide la syntaxe JSON de tous les blocs JSON-LD."""
    issues = []
    blocks = extract_json_ld_blocks(html)
    if not blocks:
        return issues  # pas de schéma → pas d'erreur ici

    errors = 0
    for i, blk in enumerate(blocks, 1):
        try:
            json.loads(blk.strip())
        except json.JSONDecodeError as e:
            issues.append((SEVERITY_CRIT, f"JSON-LD bloc #{i} invalide : {e}"))
            errors += 1

    if errors == 0:
        issues.append((SEVERITY_OK, f"{len(blocks)} bloc(s) JSON-LD valide(s)"))
    return issues


def check_video_upload_date(html):
    """Vérifie que chaque VideoObject a uploadDate."""
    issues = []
    blocks = extract_json_ld_blocks(html)
    missing = []
    for blk in blocks:
        try:
            data = json.loads(blk.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get('@type') != 'VideoObject':
                continue
            if not item.get('uploadDate'):
                url = item.get('contentUrl') or item.get('embedUrl') or item.get('name') or '?'
                m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
                vid_id = m.group(1) if m else url[:40]
                missing.append(vid_id)

    if missing:
        for vid in missing:
            issues.append((SEVERITY_CRIT, f"VideoObject sans uploadDate : {vid} — lance fix_video_uploaddate.py"))
    else:
        # Vérifie s'il y a des VideoObject (pour confirmer OK)
        has_video = any(
            any(
                isinstance(item, dict) and item.get('@type') == 'VideoObject'
                for item in (json.loads(b.strip()) if not isinstance(json.loads(b.strip()), list) else json.loads(b.strip()))
                if True
            )
            for b in blocks
            if _safe_parse(b)
        )
        if has_video:
            issues.append((SEVERITY_OK, "Tous les VideoObject ont uploadDate"))
    return issues

def _safe_parse(blk):
    try:
        json.loads(blk.strip())
        return True
    except Exception:
        return False


def check_product_schema(html):
    """
    Vérifie la structure Product :
    - Le type racine doit être Product (pas Review avec itemReviewed)
    - Si Product présent, doit avoir aggregateRating ou review
    """
    issues = []
    blocks = extract_json_ld_blocks(html)
    for i, blk in enumerate(blocks, 1):
        try:
            data = json.loads(blk.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get('@type', '')

            # Erreur classique : Review en racine avec itemReviewed Product
            if t == 'Review' and isinstance(item.get('itemReviewed'), dict):
                reviewed_type = item['itemReviewed'].get('@type', '')
                if reviewed_type == 'Product':
                    issues.append((
                        SEVERITY_CRIT,
                        "Structure Product/Review inversée : racine=Review avec itemReviewed=Product "
                        "→ inverser : racine=Product avec review imbriqué"
                    ))

            # Product présent mais sans aggregateRating ni review
            if t == 'Product':
                has_rating  = 'aggregateRating' in item
                has_review  = 'review' in item
                has_offers  = 'offers' in item
                if not (has_rating or has_review or has_offers):
                    issues.append((
                        SEVERITY_WARN,
                        "Schema Product sans aggregateRating, review ni offers → risque d'inéligibilité aux Rich Results"
                    ))
                else:
                    issues.append((SEVERITY_OK, "Schema Product valide (aggregateRating/review/offers présent)"))

    return issues


def check_og_tags(html):
    """Vérifie la présence des 4 balises Open Graph obligatoires."""
    issues = []
    missing = []
    for prop in OG_REQUIRED:
        if not re.search(rf'property=["\']og:{re.escape(prop.split(":")[1])}\b', html, re.I):
            missing.append(prop)
    if missing:
        for tag in missing:
            issues.append((SEVERITY_WARN, f"OG tag absent : <meta property=\"{tag}\">"))
    else:
        issues.append((SEVERITY_OK, "4 OG tags obligatoires présents (title, description, image, url)"))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Vérification d'un fichier
# ─────────────────────────────────────────────────────────────────────────────
CHECKS = [
    ("Titre",            check_title),
    ("Meta description", check_meta_description),
    ("Canonical",        check_canonical),
    ("H1",               check_h1),
    ("Lang HTML",        check_lang),
    ("Google Analytics", check_ga4),
    ("JSON-LD syntaxe",  check_json_ld),
    ("VideoObject",      check_video_upload_date),
    ("Product/Review",   check_product_schema),
    ("Open Graph",       check_og_tags),
]


def validate_file(fpath):
    try:
        html = fpath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return [("Lecture", SEVERITY_CRIT, f"Impossible de lire le fichier : {e}")]

    all_issues = []
    for label, fn in CHECKS:
        results = fn(html)
        for sev, msg in results:
            all_issues.append((label, sev, msg))
    return all_issues


# ─────────────────────────────────────────────────────────────────────────────
# Rapport
# ─────────────────────────────────────────────────────────────────────────────
def print_report(file_issues):
    """
    file_issues : dict  fpath → list of (label, sev, msg)
    """
    total_crit  = 0
    total_warn  = 0
    total_files_with_errors = 0

    print()
    print("═" * 70)
    print("  LCDMH — Rapport de validation SEO")
    print("═" * 70)

    for fpath, issues in sorted(file_issues.items(), key=lambda x: str(x[0])):
        crits = [(l, s, m) for l, s, m in issues if s == SEVERITY_CRIT]
        warns = [(l, s, m) for l, s, m in issues if s == SEVERITY_WARN]

        if not crits and not warns:
            continue  # tout OK → on n'affiche pas

        total_files_with_errors += 1
        total_crit += len(crits)
        total_warn += len(warns)

        rel = fpath.relative_to(BASE) if fpath.is_relative_to(BASE) else fpath
        print(f"\n📄 {rel}")
        print("─" * 60)
        for label, sev, msg in crits + warns:
            print(f"  {sev}  [{label}] {msg}")

    print()
    print("═" * 70)
    ok_count = len(file_issues) - total_files_with_errors
    print(f"  Fichiers analysés   : {len(file_issues)}")
    print(f"  Fichiers sans erreur: {ok_count}")
    print(f"  Erreurs critiques   : {total_crit}")
    print(f"  Avertissements      : {total_warn}")
    print("═" * 70)

    if total_crit == 0 and total_warn == 0:
        print("\n  ✅  TOUT EST OK — site propre pour git push !\n")
    elif total_crit == 0:
        print(f"\n  🟡  {total_warn} avertissement(s) — push autorisé mais à corriger prochainement.\n")
    else:
        print(f"\n  🔴  {total_crit} erreur(s) critique(s) — CORRIGER AVANT le git push !\n")

    return total_crit


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    files = collect_html_files(args)

    print(f"\n🔍 Analyse de {len(files)} fichier(s) HTML…")

    file_issues = {}
    for fpath in sorted(files):
        file_issues[fpath] = validate_file(fpath)

    critical_count = print_report(file_issues)
    sys.exit(1 if critical_count > 0 else 0)
