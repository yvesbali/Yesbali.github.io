#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_seo.py - Validation SEO conformément à la section 12.5 du cadrage LCDMH.

Contrats sur le HTML (section 12.5 de LCDMH_Cadrage_Projet.html) :
  1. UTF-8 sans BOM, <meta charset="UTF-8"> en premier dans <head>
  2. <meta name="viewport" content="width=device-width, initial-scale=1">
  3. <html lang="fr">, <title> < 65 c., <meta description> 120-170 c., <link rel="canonical"> absolu
  4. OpenGraph + Twitter Card complets
  5. JSON-LD Article / CollectionPage / VideoObject
  6. Un seul <h1>
  7. <img> : alt non vide + width + height + loading (sauf hero)
  8. Images ≤ 500 KiB (sur disque) + couple WebP+JPG via <picture>
  9. Aucune URL lcdmh.com dans messages sociaux générés en parallèle
 10. Ajout dans articles.html et sitemap.xml

Mode unitaire   : python validate_seo.py path/to/file.html
Mode batch      : python validate_seo.py --batch "articles/*.html"
Mode CSV audit  : python validate_seo.py --audit-site --csv output.csv
Mode Markdown   : python validate_seo.py --audit-site --md output.md

Snippets exclus (pas de meta/title/html attendus) :
  nav.html, widget-roadtrip-snippet.html, header.html, footer.html
"""

from __future__ import annotations

import argparse
import csv
import glob as globmod
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SNIPPET_FILES = {
    "nav.html",
    "widget-roadtrip-snippet.html",
    "header.html",
    "footer.html",
}

# Poids max d'une image en octets (section 12.5 point 8).
MAX_IMAGE_BYTES = 500 * 1024

# Racine du site (ARTICLES[] dans articles.html et urls dans sitemap.xml).
SITE_ROOT_GUESS = Path(__file__).resolve().parents[2]  # AUDIT_INGENIEUR_SEO/scripts/.. -> repo root

# ---------------------------------------------------------------------------
# Structure de résultat
# ---------------------------------------------------------------------------


@dataclass
class Check:
    key: str
    label: str
    status: str  # "OK" | "KO" | "WARN" | "N/A"
    detail: str = ""


@dataclass
class PageReport:
    path: Path
    is_snippet: bool = False
    checks: list[Check] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "OK")

    @property
    def ko_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "KO")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "WARN")

    @property
    def score(self) -> float:
        applicable = [c for c in self.checks if c.status != "N/A"]
        if not applicable:
            return 0.0
        return 100.0 * self.ok_count / len(applicable)


# ---------------------------------------------------------------------------
# Helpers HTML
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> tuple[str, bool]:
    """Retourne (contenu, has_bom)."""
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig", errors="replace")
    return text, has_bom


def _first_match(pattern: str, text: str, flags: int = 0) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1) if m else None


def _count_matches(pattern: str, text: str, flags: int = 0) -> int:
    return len(re.findall(pattern, text, flags))


# ---------------------------------------------------------------------------
# Checks individuels (section 12.5)
# ---------------------------------------------------------------------------


def check_01_utf8(text: str, has_bom: bool) -> Check:
    if has_bom:
        return Check("01_utf8", "UTF-8 sans BOM", "KO", "BOM UTF-8 présent au début du fichier")
    # meta charset doit être présent et idéalement dans les premières lignes du head
    m = re.search(r'<meta[^>]+charset\s*=\s*["\']?utf-?8', text, re.IGNORECASE)
    if not m:
        return Check("01_utf8", "UTF-8 sans BOM", "KO", "meta charset=UTF-8 absent")
    head_start = text.lower().find("<head")
    if head_start < 0 or m.start() - head_start > 400:
        return Check("01_utf8", "UTF-8 sans BOM", "WARN", "meta charset trop loin du début du head")
    return Check("01_utf8", "UTF-8 sans BOM", "OK", "")


def check_02_viewport(text: str) -> Check:
    m = re.search(
        r'<meta[^>]+name\s*=\s*["\']viewport["\'][^>]+content\s*=\s*["\'][^"\']*width=device-width',
        text,
        re.IGNORECASE,
    )
    if m:
        return Check("02_viewport", "Meta viewport responsive", "OK", "")
    return Check("02_viewport", "Meta viewport responsive", "KO", "meta viewport width=device-width absent")


def check_03_lang_title_desc_canonical(text: str) -> list[Check]:
    out: list[Check] = []
    # html lang
    if re.search(r'<html[^>]+lang\s*=\s*["\']fr["\']', text, re.IGNORECASE):
        out.append(Check("03a_lang", "html lang=fr", "OK", ""))
    else:
        out.append(Check("03a_lang", "html lang=fr", "KO", 'Attribut lang="fr" absent sur <html>'))

    # title
    title = _first_match(r"<title>([^<]+)</title>", text, re.IGNORECASE)
    if not title:
        out.append(Check("03b_title", "Title < 65 c.", "KO", "balise <title> absente"))
    else:
        n = len(title.strip())
        if n == 0:
            out.append(Check("03b_title", "Title < 65 c.", "KO", "title vide"))
        elif n >= 65:
            out.append(Check("03b_title", "Title < 65 c.", "WARN", f"{n} caractères (cible < 65)"))
        else:
            out.append(Check("03b_title", "Title < 65 c.", "OK", f"{n} c."))

    # meta description
    desc = _first_match(
        r'<meta[^>]+name\s*=\s*["\']description["\'][^>]+content\s*=\s*["\']([^"\']+)["\']',
        text,
        re.IGNORECASE,
    )
    if not desc:
        out.append(Check("03c_description", "Meta description 120-170 c.", "KO", "meta description absente"))
    else:
        n = len(desc.strip())
        if 120 <= n <= 170:
            out.append(Check("03c_description", "Meta description 120-170 c.", "OK", f"{n} c."))
        else:
            status = "WARN" if 100 <= n <= 200 else "KO"
            out.append(Check("03c_description", "Meta description 120-170 c.", status, f"{n} c. (cible 120-170)"))

    # canonical
    canon = _first_match(
        r'<link[^>]+rel\s*=\s*["\']canonical["\'][^>]+href\s*=\s*["\']([^"\']+)["\']',
        text,
        re.IGNORECASE,
    )
    if not canon:
        out.append(Check("03d_canonical", "Canonical URL absolue", "KO", "link rel=canonical absent"))
    elif not canon.startswith("https://"):
        out.append(Check("03d_canonical", "Canonical URL absolue", "KO", f"URL non absolue : {canon}"))
    elif "lcdmh.com" not in canon:
        out.append(Check("03d_canonical", "Canonical URL absolue", "WARN", f"Domaine inattendu : {canon}"))
    else:
        out.append(Check("03d_canonical", "Canonical URL absolue", "OK", canon))
    return out


def check_04_og_twitter(text: str) -> list[Check]:
    og_keys = ["og:title", "og:description", "og:image", "og:url", "og:type", "og:site_name", "og:locale"]
    twitter_keys = ["twitter:card", "twitter:title", "twitter:description", "twitter:image"]
    present_og = []
    missing_og = []
    for k in og_keys:
        if re.search(
            rf'<meta[^>]+property\s*=\s*["\']{re.escape(k)}["\']', text, re.IGNORECASE
        ):
            present_og.append(k)
        else:
            missing_og.append(k)
    present_tw = []
    missing_tw = []
    for k in twitter_keys:
        if re.search(rf'<meta[^>]+name\s*=\s*["\']{re.escape(k)}["\']', text, re.IGNORECASE):
            present_tw.append(k)
        else:
            missing_tw.append(k)
    og_status = "OK" if not missing_og else ("WARN" if len(present_og) >= 4 else "KO")
    tw_status = "OK" if not missing_tw else ("WARN" if len(present_tw) >= 2 else "KO")
    return [
        Check(
            "04a_opengraph",
            "OpenGraph complet",
            og_status,
            f"présent : {','.join(present_og) or 'rien'} · manquant : {','.join(missing_og) or 'rien'}",
        ),
        Check(
            "04b_twittercard",
            "Twitter Card complet",
            tw_status,
            f"présent : {','.join(present_tw) or 'rien'} · manquant : {','.join(missing_tw) or 'rien'}",
        ),
    ]


def check_05_jsonld(text: str) -> Check:
    scripts = re.findall(
        r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not scripts:
        return Check("05_jsonld", "JSON-LD Schema.org", "KO", "aucun bloc application/ld+json")
    found_types: list[str] = []
    for blk in scripts:
        for m in re.finditer(r'"@type"\s*:\s*"([^"]+)"', blk):
            found_types.append(m.group(1))
    if not found_types:
        return Check("05_jsonld", "JSON-LD Schema.org", "WARN", "bloc JSON-LD présent mais sans @type")
    expected = {"Article", "NewsArticle", "BlogPosting", "CollectionPage", "VideoObject", "WebSite", "Organization", "BreadcrumbList"}
    good = [t for t in found_types if t in expected]
    if good:
        return Check("05_jsonld", "JSON-LD Schema.org", "OK", "types : " + ", ".join(sorted(set(found_types))))
    return Check("05_jsonld", "JSON-LD Schema.org", "WARN", "types : " + ", ".join(sorted(set(found_types))))


def check_06_h1_unique(text: str) -> Check:
    # On ne compte que les H1 dans le body, pas dans les <style> inline.
    # Suppression du contenu des <style> et <script> avant comptage.
    stripped = re.sub(r"<style\b.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    stripped = re.sub(r"<script\b.*?</script>", "", stripped, flags=re.IGNORECASE | re.DOTALL)
    n = len(re.findall(r"<h1\b", stripped, re.IGNORECASE))
    if n == 1:
        return Check("06_h1", "Un seul <h1>", "OK", "")
    if n == 0:
        return Check("06_h1", "Un seul <h1>", "KO", "aucun <h1> trouvé")
    return Check("06_h1", "Un seul <h1>", "KO", f"{n} balises <h1> détectées")


def check_07_images_attrs(text: str) -> list[Check]:
    # On ne scanne que les <img> du body.
    body_start = text.lower().find("<body")
    body = text[body_start:] if body_start > -1 else text
    imgs = re.findall(r"<img\b[^>]*>", body, re.IGNORECASE)
    total = len(imgs)
    if total == 0:
        return [
            Check("07a_alt", "Images avec alt", "N/A", "aucune <img> dans la page"),
            Check("07b_dimensions", "Images avec width/height", "N/A", ""),
            Check("07c_lazy", "Images lazy sous le fold", "N/A", ""),
        ]
    missing_alt = sum(1 for im in imgs if not re.search(r'\balt\s*=\s*["\'][^"\']+', im, re.IGNORECASE))
    # alt="" (vide intentionnel pour déco) n'est pas compté comme manquant si alt= est présent
    no_alt_at_all = sum(1 for im in imgs if not re.search(r"\balt\s*=", im, re.IGNORECASE))
    missing_dims = sum(
        1
        for im in imgs
        if not (re.search(r"\bwidth\s*=", im, re.IGNORECASE) and re.search(r"\bheight\s*=", im, re.IGNORECASE))
    )
    # loading="lazy" : au moins 70% des images devraient l'avoir (les premières sont exemptes)
    lazy = sum(1 for im in imgs if re.search(r'\bloading\s*=\s*["\']lazy', im, re.IGNORECASE))

    out = []
    if no_alt_at_all == 0:
        out.append(Check("07a_alt", "Images avec alt", "OK", f"{total} images, toutes ont un attribut alt"))
    else:
        out.append(
            Check(
                "07a_alt",
                "Images avec alt",
                "KO",
                f"{no_alt_at_all}/{total} images sans attribut alt",
            )
        )
    if missing_dims == 0:
        out.append(Check("07b_dimensions", "Images avec width/height", "OK", f"{total} images"))
    elif missing_dims < total / 2:
        out.append(
            Check("07b_dimensions", "Images avec width/height", "WARN", f"{missing_dims}/{total} sans width+height (CLS)")
        )
    else:
        out.append(
            Check("07b_dimensions", "Images avec width/height", "KO", f"{missing_dims}/{total} sans width+height (CLS)")
        )
    if total >= 3:
        ratio = lazy / total
        if ratio >= 0.6:
            out.append(Check("07c_lazy", "Images lazy sous le fold", "OK", f"{lazy}/{total} en lazy"))
        elif ratio >= 0.3:
            out.append(Check("07c_lazy", "Images lazy sous le fold", "WARN", f"{lazy}/{total} en lazy"))
        else:
            out.append(Check("07c_lazy", "Images lazy sous le fold", "KO", f"{lazy}/{total} en lazy"))
    else:
        out.append(Check("07c_lazy", "Images lazy sous le fold", "N/A", f"seulement {total} image(s)"))
    return out


def check_08_image_weights(text: str, html_path: Path) -> Check:
    """Vérifie la taille sur disque des images référencées dans la page."""
    srcs = re.findall(r'<img\b[^>]+src\s*=\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
    srcs += re.findall(r'<source\b[^>]+srcset\s*=\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
    if not srcs:
        return Check("08_imgweight", "Images ≤ 500 KiB", "N/A", "aucune image référencée")

    heavy: list[tuple[str, int]] = []
    not_found = 0
    checked = 0
    for src in srcs:
        src = src.strip().split(",")[0].strip().split(" ")[0]
        if src.startswith(("http://", "https://", "data:")):
            continue
        # Résoudre le chemin relatif
        if src.startswith("/"):
            candidate = SITE_ROOT_GUESS / src.lstrip("/")
        else:
            candidate = (html_path.parent / src).resolve()
        if not candidate.exists():
            not_found += 1
            continue
        checked += 1
        size = candidate.stat().st_size
        if size > MAX_IMAGE_BYTES:
            heavy.append((src, size))
    if checked == 0:
        return Check("08_imgweight", "Images ≤ 500 KiB", "N/A", f"aucun fichier image local résolu ({not_found} introuvables)")
    if not heavy:
        return Check("08_imgweight", "Images ≤ 500 KiB", "OK", f"{checked} images contrôlées")
    top = sorted(heavy, key=lambda x: -x[1])[:3]
    samples = ", ".join(f"{Path(s).name} ({sz // 1024} KiB)" for s, sz in top)
    return Check("08_imgweight", "Images ≤ 500 KiB", "KO", f"{len(heavy)}/{checked} trop lourdes : {samples}")


def check_09_social_parasite(text: str) -> Check:
    """La page elle-même n'a pas de message social, mais on détecte les fragments 'lcdmh.com' suspects hors du head."""
    # Skip : ici on check juste qu'il n'y a pas de lien social généré avec URL parasite.
    # Patterns surveillés (extraits de fix_facebook_messages.py) :
    parasites = [
        r"🔗\s*https?://lcdmh\.com",
        r"👉\s*Mon test.*lcdmh\.com",
    ]
    hits = []
    for pat in parasites:
        if re.search(pat, text, re.IGNORECASE):
            hits.append(pat)
    if hits:
        return Check("09_social", "Pas d'URL lcdmh.com parasite", "KO", f"{len(hits)} pattern(s) parasite(s) détecté(s)")
    return Check("09_social", "Pas d'URL lcdmh.com parasite", "OK", "")


def check_10_articles_sitemap(html_path: Path) -> Check:
    """Vérifie que le slug de la page est listé dans articles.html (ARTICLES[]) et sitemap.xml."""
    # Ne concerne que les pages /articles/xxx.html
    if html_path.parent.name != "articles":
        return Check("10_indexed", "Listé dans articles.html + sitemap.xml", "N/A", "page hors /articles/")
    slug = html_path.stem
    root = SITE_ROOT_GUESS
    articles_html = root / "articles.html"
    sitemap_xml = root / "sitemap.xml"
    if not articles_html.exists() or not sitemap_xml.exists():
        return Check(
            "10_indexed",
            "Listé dans articles.html + sitemap.xml",
            "WARN",
            "articles.html ou sitemap.xml introuvables",
        )
    art = articles_html.read_text(encoding="utf-8", errors="replace")
    smp = sitemap_xml.read_text(encoding="utf-8", errors="replace")
    in_art = slug in art
    in_smp = slug in smp
    if in_art and in_smp:
        return Check("10_indexed", "Listé dans articles.html + sitemap.xml", "OK", "")
    missing = []
    if not in_art:
        missing.append("articles.html")
    if not in_smp:
        missing.append("sitemap.xml")
    return Check("10_indexed", "Listé dans articles.html + sitemap.xml", "KO", "absent de : " + ", ".join(missing))


# ---------------------------------------------------------------------------
# Pipeline complet
# ---------------------------------------------------------------------------


def validate_page(path: Path) -> PageReport:
    report = PageReport(path=path)
    if path.name in SNIPPET_FILES:
        report.is_snippet = True
        report.checks.append(Check("snippet", "Fichier snippet (exempté)", "N/A", "inclus partiel, pas de meta/title"))
        return report
    try:
        text, has_bom = _read_text(path)
    except Exception as exc:
        report.checks.append(Check("read", "Lecture fichier", "KO", f"erreur : {exc}"))
        return report

    report.checks.append(check_01_utf8(text, has_bom))
    report.checks.append(check_02_viewport(text))
    report.checks.extend(check_03_lang_title_desc_canonical(text))
    report.checks.extend(check_04_og_twitter(text))
    report.checks.append(check_05_jsonld(text))
    report.checks.append(check_06_h1_unique(text))
    report.checks.extend(check_07_images_attrs(text))
    report.checks.append(check_08_image_weights(text, path))
    report.checks.append(check_09_social_parasite(text))
    report.checks.append(check_10_articles_sitemap(path))
    return report


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------


def print_single(report: PageReport) -> int:
    rel = report.path.relative_to(SITE_ROOT_GUESS) if report.path.is_absolute() else report.path
    print(f"=== {rel} ===")
    if report.is_snippet:
        print("(snippet : validation non applicable)")
        return 0
    for c in report.checks:
        mark = {"OK": "[OK]  ", "KO": "[KO]  ", "WARN": "[WARN]", "N/A": "[N/A] "}[c.status]
        line = f"{mark} {c.key:18s} {c.label}"
        if c.detail:
            line += f"  — {c.detail}"
        print(line)
    print(f"Score : {report.score:.0f}/100  ({report.ok_count} OK, {report.ko_count} KO, {report.warn_count} WARN)")
    return 1 if report.ko_count > 0 else 0


def collect_site_pages(root: Path) -> list[Path]:
    excluded_dirs = {"AUDIT_INGENIEUR_SEO", ".git", "_archive", "node_modules", "facebook", "kurviger", "build"}
    pages = []
    for p in root.rglob("*.html"):
        if any(part in excluded_dirs for part in p.parts):
            continue
        pages.append(p)
    return sorted(pages)


def write_csv(reports: list[PageReport], csv_path: Path) -> None:
    if not reports:
        return
    all_keys = []
    seen = set()
    for r in reports:
        for c in r.checks:
            if c.key not in seen:
                seen.add(c.key)
                all_keys.append((c.key, c.label))
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        header = ["page", "snippet", "score", "ok", "ko", "warn"] + [k for k, _ in all_keys]
        w.writerow(header)
        for r in reports:
            rel = r.path.relative_to(SITE_ROOT_GUESS) if r.path.is_absolute() else r.path
            by_key = {c.key: c for c in r.checks}
            row = [
                str(rel).replace("\\", "/"),
                "yes" if r.is_snippet else "no",
                f"{r.score:.0f}",
                r.ok_count,
                r.ko_count,
                r.warn_count,
            ]
            for k, _ in all_keys:
                c = by_key.get(k)
                row.append(c.status if c else "")
            w.writerow(row)


def write_markdown(reports: list[PageReport], md_path: Path) -> None:
    lines = [
        "# Audit SEO du site LCDMH — conformité section 12.5",
        "",
        f"Pages analysées : **{len(reports)}**",
        "",
        "## Synthèse par score",
        "",
        "| Page | Score | OK | KO | WARN |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in sorted(reports, key=lambda x: x.score):
        rel = r.path.relative_to(SITE_ROOT_GUESS) if r.path.is_absolute() else r.path
        if r.is_snippet:
            lines.append(f"| `{rel}` | — | — | — | — |")
        else:
            lines.append(
                f"| `{rel}` | {r.score:.0f}/100 | {r.ok_count} | {r.ko_count} | {r.warn_count} |"
            )
    lines += ["", "## Violations critiques les plus fréquentes", ""]
    tally: dict[str, int] = {}
    for r in reports:
        for c in r.checks:
            if c.status == "KO":
                tally[f"{c.key} — {c.label}"] = tally.get(f"{c.key} — {c.label}", 0) + 1
    for k, n in sorted(tally.items(), key=lambda x: -x[1]):
        lines.append(f"- **{n}** page(s) : {k}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    global SITE_ROOT_GUESS  # noqa: PLW0603
    parser = argparse.ArgumentParser(description="Validation SEO LCDMH selon section 12.5 du cadrage.")
    parser.add_argument("path", nargs="?", help="Fichier HTML à valider (mode unitaire)")
    parser.add_argument("--batch", metavar="GLOB", help='Glob (ex: "articles/*.html")')
    parser.add_argument("--audit-site", action="store_true", help="Audit de toutes les pages du site")
    parser.add_argument("--csv", metavar="FILE", help="Exporter en CSV")
    parser.add_argument("--md", metavar="FILE", help="Exporter en Markdown")
    parser.add_argument("--root", default=str(SITE_ROOT_GUESS), help="Racine du site")
    parser.add_argument("--quiet", action="store_true", help="Ne pas afficher les rapports individuels")
    args = parser.parse_args()

    SITE_ROOT_GUESS = Path(args.root).resolve()

    pages: list[Path] = []
    if args.path:
        pages.append(Path(args.path).resolve())
    if args.batch:
        for p in globmod.glob(args.batch, recursive=True):
            pages.append(Path(p).resolve())
    if args.audit_site:
        pages.extend(collect_site_pages(SITE_ROOT_GUESS))

    if not pages:
        parser.print_help()
        return 2

    # Dédup
    seen = set()
    unique_pages: list[Path] = []
    for p in pages:
        if p not in seen:
            seen.add(p)
            unique_pages.append(p)

    reports = [validate_page(p) for p in unique_pages]

    if not args.quiet and len(reports) <= 5:
        for r in reports:
            print_single(r)

    if args.csv:
        write_csv(reports, Path(args.csv))
        print(f"CSV écrit : {args.csv}")
    if args.md:
        write_markdown(reports, Path(args.md))
        print(f"Markdown écrit : {args.md}")

    if not args.csv and not args.md and args.audit_site:
        # Synthèse console
        avg = sum(r.score for r in reports if not r.is_snippet) / max(1, sum(1 for r in reports if not r.is_snippet))
        print(f"\n{len(reports)} pages, score moyen : {avg:.0f}/100")

    # Code retour : 0 si toutes les pages KO == 0
    total_ko = sum(r.ko_count for r in reports)
    return 0 if total_ko == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
