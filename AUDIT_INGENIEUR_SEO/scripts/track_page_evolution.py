#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
track_page_evolution.py - Historique git de chaque page HTML du site LCDMH.

Pour chaque fichier .html hors AUDIT_INGENIEUR_SEO / .git / _archive :
  - date de création (premier commit)
  - date de dernière modification (dernier commit)
  - nombre de commits
  - jours depuis création
  - jours depuis dernière modification
  - indicateur "stagnant" si > 90 jours sans modification

Usage :
  python track_page_evolution.py --csv rapport.csv --md rapport.md
  python track_page_evolution.py --quiet
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_DIRS = {"AUDIT_INGENIEUR_SEO", ".git", "_archive", "node_modules", "build"}
STAGNANT_DAYS = 90


@dataclass
class PageHistory:
    path: Path
    commits: int = 0
    first_date: date | None = None
    last_date: date | None = None
    last_subject: str = ""

    @property
    def age_days(self) -> int | None:
        if self.first_date is None:
            return None
        return (date.today() - self.first_date).days

    @property
    def since_last_days(self) -> int | None:
        if self.last_date is None:
            return None
        return (date.today() - self.last_date).days

    @property
    def is_stagnant(self) -> bool:
        d = self.since_last_days
        return d is not None and d > STAGNANT_DAYS


def collect_html_pages(root: Path) -> list[Path]:
    pages = []
    for p in root.rglob("*.html"):
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        pages.append(p)
    return sorted(pages)


def git_history(path: Path, repo_root: Path) -> PageHistory:
    hist = PageHistory(path=path)
    rel = path.relative_to(repo_root)
    # --follow pour suivre les renommages
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "log",
        "--follow",
        "--format=%ad|%s",
        "--date=short",
        "--",
        str(rel).replace("\\", "/"),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return hist
    if r.returncode != 0 or not r.stdout.strip():
        return hist
    lines = [l for l in r.stdout.strip().splitlines() if "|" in l]
    hist.commits = len(lines)
    if lines:
        # git log est du plus récent au plus ancien
        last_line = lines[0]
        first_line = lines[-1]
        try:
            hist.last_date = datetime.strptime(last_line.split("|", 1)[0], "%Y-%m-%d").date()
            hist.first_date = datetime.strptime(first_line.split("|", 1)[0], "%Y-%m-%d").date()
            hist.last_subject = last_line.split("|", 1)[1].strip()[:80]
        except ValueError:
            pass
    return hist


def write_csv(histories: list[PageHistory], csv_path: Path, repo_root: Path) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "page",
                "commits",
                "first_date",
                "last_date",
                "age_days",
                "since_last_days",
                "stagnant",
                "last_subject",
            ]
        )
        for h in histories:
            rel = h.path.relative_to(repo_root)
            w.writerow(
                [
                    str(rel).replace("\\", "/"),
                    h.commits,
                    h.first_date.isoformat() if h.first_date else "",
                    h.last_date.isoformat() if h.last_date else "",
                    h.age_days if h.age_days is not None else "",
                    h.since_last_days if h.since_last_days is not None else "",
                    "yes" if h.is_stagnant else "no",
                    h.last_subject,
                ]
            )


def write_markdown(histories: list[PageHistory], md_path: Path, repo_root: Path) -> None:
    lines = [
        "# Évolution des pages HTML du site LCDMH",
        "",
        f"Généré le : {date.today().isoformat()}",
        f"Pages analysées : **{len(histories)}**",
        f"Seuil de stagnation : **{STAGNANT_DAYS} jours sans modification**",
        "",
    ]

    tracked = [h for h in histories if h.first_date is not None]
    untracked = [h for h in histories if h.first_date is None]
    stagnant = [h for h in tracked if h.is_stagnant]
    fresh = [h for h in tracked if not h.is_stagnant]
    recent = sorted(tracked, key=lambda h: h.last_date or date(1970, 1, 1), reverse=True)[:10]

    lines += [
        "## Synthèse",
        "",
        f"- Pages suivies par git : **{len(tracked)}**",
        f"- Pages non suivies (probablement non committées) : **{len(untracked)}**",
        f"- Pages stagnantes (> {STAGNANT_DAYS} jours) : **{len(stagnant)}**",
        f"- Pages fraîches : **{len(fresh)}**",
        "",
        "## 10 pages les plus récemment modifiées",
        "",
        "| Page | Dernière modif | Commits | Sujet dernier commit |",
        "|---|---|---:|---|",
    ]
    for h in recent:
        rel = h.path.relative_to(repo_root)
        lines.append(
            f"| `{rel}` | {h.last_date} | {h.commits} | {h.last_subject.replace('|', '/')} |"
        )

    lines += [
        "",
        f"## Pages stagnantes (> {STAGNANT_DAYS} jours sans modification)",
        "",
        "| Page | Dernière modif | Jours sans modif | Commits totaux |",
        "|---|---|---:|---:|",
    ]
    for h in sorted(stagnant, key=lambda x: x.since_last_days or 0, reverse=True):
        rel = h.path.relative_to(repo_root)
        lines.append(f"| `{rel}` | {h.last_date} | {h.since_last_days} | {h.commits} |")

    lines += [
        "",
        "## Pages les plus anciennes (par date de création)",
        "",
        "| Page | Créée le | Âge (jours) | Commits |",
        "|---|---|---:|---:|",
    ]
    oldest = sorted(tracked, key=lambda x: x.first_date or date(9999, 1, 1))[:15]
    for h in oldest:
        rel = h.path.relative_to(repo_root)
        lines.append(f"| `{rel}` | {h.first_date} | {h.age_days} | {h.commits} |")

    if untracked:
        lines += [
            "",
            "## Pages non suivies par git",
            "",
        ]
        for h in untracked:
            rel = h.path.relative_to(repo_root)
            lines.append(f"- `{rel}`")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Historique git des pages HTML LCDMH")
    parser.add_argument("--csv", metavar="FILE", help="Export CSV")
    parser.add_argument("--md", metavar="FILE", help="Export Markdown")
    parser.add_argument("--root", default=str(SITE_ROOT), help="Racine du dépôt")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    pages = collect_html_pages(root)
    histories = [git_history(p, root) for p in pages]

    if args.csv:
        write_csv(histories, Path(args.csv), root)
        print(f"CSV écrit : {args.csv}")
    if args.md:
        write_markdown(histories, Path(args.md), root)
        print(f"Markdown écrit : {args.md}")

    if not args.quiet and not args.csv and not args.md:
        tracked = [h for h in histories if h.first_date is not None]
        stagnant = [h for h in tracked if h.is_stagnant]
        print(f"{len(pages)} pages, {len(tracked)} suivies par git, {len(stagnant)} stagnantes (> {STAGNANT_DAYS} j)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
