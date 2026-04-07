# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
import json
import re


class GitPublishError(RuntimeError):
    pass


@dataclass
class CoherenceReport:
    ok: bool
    message: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    infos: List[str] = field(default_factory=list)


def _run_git(repo_path: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise GitPublishError(
            f"Commande git échouée : git {' '.join(args)}\n\n"
            f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        )
    return result


def _is_git_repo(repo_path: Path) -> bool:
    return (repo_path / ".git").exists()


def _remote_exists(repo_path: Path, remote_name: str) -> bool:
    result = _run_git(repo_path, ["remote"], check=False)
    remotes = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return remote_name in remotes


def _current_branch(repo_path: Path) -> str:
    result = _run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip()


def _has_changes(repo_path: Path) -> bool:
    result = _run_git(repo_path, ["status", "--porcelain"], check=False)
    return bool(result.stdout.strip())


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _contains_reference(page_path: Path, needle: str) -> bool:
    if not page_path.exists():
        return False
    content = _read_text_safe(page_path)
    return needle.replace("\\", "/") in content.replace("\\", "/")


def _normalize_rel(rel_value: str) -> str:
    return rel_value.replace("\\", "/").lstrip("./")


def verify_publish_tree(
    publish_root: str | Path,
    slug: str,
    main_page_name: Optional[str] = None,
    journal_page_name: Optional[str] = None,
    require_cname: bool = False,
) -> CoherenceReport:
    """
    Vérifie la cohérence minimale du site local avant publication GitHub.
    """
    root = Path(publish_root).expanduser().resolve()
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []

    if not root.exists():
        return CoherenceReport(
            ok=False,
            message=f"Dossier de publication introuvable : {root}",
            errors=[f"Dossier de publication introuvable : {root}"],
        )

    if not _is_git_repo(root):
        errors.append("Le dossier de publication n'est pas un dépôt Git (.git absent).")

    roadtrips_dir = root / "roadtrips"
    images_dir = root / "images" / "roadtrips" / slug
    data_dir = root / "data" / "roadtrips" / slug

    if not roadtrips_dir.exists():
        errors.append(f"Dossier roadtrips absent : {roadtrips_dir}")
    if not images_dir.exists():
        errors.append(f"Dossier images du voyage absent : {images_dir}")
    if not data_dir.exists():
        errors.append(f"Dossier data du voyage absent : {data_dir}")

    if require_cname and not (root / "CNAME").exists():
        errors.append("Le fichier CNAME est absent à la racine du dépôt.")

    if main_page_name is None:
        main_page_name = f"{slug}.html"
    if journal_page_name is None:
        journal_page_name = f"{slug}-journal.html"

    main_page = roadtrips_dir / main_page_name
    journal_page = roadtrips_dir / journal_page_name

    if not main_page.exists():
        errors.append(f"Page principale absente : {main_page}")
    else:
        infos.append(f"Page principale trouvée : {main_page.name}")

    if not journal_page.exists():
        errors.append(f"Sous-page journal absente : {journal_page}")
    else:
        infos.append(f"Sous-page journal trouvée : {journal_page.name}")

    project_json = data_dir / "project.json"
    journal_entries_json = data_dir / "journal_entries.json"

    if not project_json.exists():
        errors.append(f"project.json absent : {project_json}")
    else:
        infos.append("project.json trouvé.")

    if not journal_entries_json.exists():
        warnings.append(f"journal_entries.json absent : {journal_entries_json}")

    hero_path = None
    qr_path = None
    roadbook_pdf_path = None
    kurviger_path = None

    if project_json.exists():
        try:
            payload = json.loads(_read_text_safe(project_json))
            paths = payload.get("paths", {}) if isinstance(payload, dict) else {}
            publication_layout = payload.get("publication_layout", {}) if isinstance(payload, dict) else {}

            hero_raw = str(paths.get("hero") or "")
            qr_raw = str(paths.get("qr") or "")
            pdf_raw = str(paths.get("roadbook_pdf") or "")
            kurviger_raw = str(paths.get("kurviger") or "")

            if hero_raw:
                hero_path = Path(hero_raw)
            if qr_raw:
                qr_path = Path(qr_raw)
            if pdf_raw:
                roadbook_pdf_path = Path(pdf_raw)
            if kurviger_raw:
                kurviger_path = Path(kurviger_raw)

            expected_main = publication_layout.get("main_page")
            expected_journal = publication_layout.get("journal_page")
            if expected_main and expected_main != main_page_name:
                warnings.append(
                    f"Nom de page principale dans project.json différent : {expected_main} au lieu de {main_page_name}"
                )
            if expected_journal and expected_journal != journal_page_name:
                warnings.append(
                    f"Nom de page journal dans project.json différent : {expected_journal} au lieu de {journal_page_name}"
                )

        except Exception as exc:
            errors.append(f"Lecture impossible de project.json : {exc}")

    # Fallback par scan si besoin
    if hero_path is None and images_dir.exists():
        heroes = [p for p in images_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".webp"}]
        if heroes:
            hero_path = heroes[0]

    if qr_path is None and images_dir.exists():
        pngs = [p for p in images_dir.iterdir() if p.suffix.lower() == ".png"]
        if pngs:
            qr_path = pngs[0]

    if hero_path is None or not Path(hero_path).exists():
        errors.append("Image hero JPG/JPEG/WEBP absente.")
    else:
        if Path(hero_path).suffix.lower() not in {".jpg", ".jpeg", ".webp"}:
            errors.append(f"Le hero n'a pas une extension valide : {hero_path.name}")
        else:
            infos.append(f"Hero trouvé : {Path(hero_path).name}")

    if qr_path is None or not Path(qr_path).exists():
        errors.append("QR code PNG absent.")
    else:
        if Path(qr_path).suffix.lower() != ".png":
            errors.append(f"Le QR code n'est pas en PNG : {Path(qr_path).name}")
        else:
            infos.append(f"QR trouvé : {Path(qr_path).name}")

    if roadbook_pdf_path is None or not Path(roadbook_pdf_path).exists():
        warnings.append("Roadbook PDF absent.")
    else:
        infos.append(f"Roadbook PDF trouvé : {Path(roadbook_pdf_path).name}")

    if kurviger_path is None or not Path(kurviger_path).exists():
        warnings.append("Trace Kurviger absente.")
    else:
        infos.append(f"Trace Kurviger trouvée : {Path(kurviger_path).name}")

    # Contrôle simple des liens dans les pages
    if main_page.exists():
        main_html = _read_text_safe(main_page)

        if journal_page.exists() and journal_page.name not in main_html:
            warnings.append("La page principale ne semble pas référencer la sous-page journal.")

        if hero_path and Path(hero_path).name not in main_html:
            warnings.append("La page principale ne semble pas contenir le nom du hero.")

        if qr_path and Path(qr_path).name not in main_html:
            warnings.append("La page principale ne semble pas contenir le nom du QR code.")

    if journal_page.exists():
        journal_html = _read_text_safe(journal_page)
        if main_page.exists() and main_page.name not in journal_html:
            warnings.append("La page journal ne semble pas contenir de lien retour vers la page principale.")

    ok = len(errors) == 0
    message = "Vérification cohérente." if ok else "Vérification bloquante : corriger avant publication."

    return CoherenceReport(
        ok=ok,
        message=message,
        errors=errors,
        warnings=warnings,
        infos=infos,
    )


def publish_site_to_github(
    repo_path: str | Path,
    slug: str,
    main_page_name: Optional[str] = None,
    journal_page_name: Optional[str] = None,
    commit_message: Optional[str] = None,
    remote_name: str = "origin",
    branch: Optional[str] = None,
    pull_before_push: bool = False,
    require_clean_check: bool = True,
    require_cname: bool = False,
) -> dict:
    """
    Vérifie la cohérence puis pousse sur GitHub.
    """
    repo = Path(repo_path).expanduser().resolve()

    report = verify_publish_tree(
        publish_root=repo,
        slug=slug,
        main_page_name=main_page_name,
        journal_page_name=journal_page_name,
        require_cname=require_cname,
    )

    if require_clean_check and not report.ok:
        return {
            "ok": False,
            "message": "Publication refusée : la cohérence du site n'est pas valide.",
            "report": report,
        }

    if not repo.exists():
        return {"ok": False, "message": f"Dépôt introuvable : {repo}"}

    if not _is_git_repo(repo):
        return {"ok": False, "message": f"Le dossier n'est pas un dépôt Git : {repo}"}

    if not _remote_exists(repo, remote_name):
        return {"ok": False, "message": f"Remote Git introuvable : {remote_name}"}

    if branch is None:
        branch = _current_branch(repo)

    _run_git(repo, ["add", "-A"])

    if not _has_changes(repo):
        return {
            "ok": True,
            "message": "Aucun changement à publier.",
            "report": report,
            "branch": branch,
            "remote": remote_name,
        }

    if not commit_message:
        horodatage = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        commit_message = f"Mise à jour automatique du site - {slug} - {horodatage}"

    _run_git(repo, ["commit", "-m", commit_message])

    if pull_before_push:
        _run_git(repo, ["pull", "--rebase", remote_name, branch])

    _run_git(repo, ["push", remote_name, branch])

    return {
        "ok": True,
        "message": "Publication GitHub terminée.",
        "report": report,
        "branch": branch,
        "remote": remote_name,
        "commit_message": commit_message,
    }


if __name__ == "__main__":
    repo = r"F:\LCDMH_GitHub_Audit"
    slug = "road-trip-moto-ecosse-2026"

    rep = verify_publish_tree(
        publish_root=repo,
        slug=slug,
        main_page_name=f"{slug}.html",
        journal_page_name=f"{slug}-journal.html",
        require_cname=False,
    )
    print(rep.message)
    for line in rep.infos:
        print("INFO   :", line)
    for line in rep.warnings:
        print("WARNING:", line)
    for line in rep.errors:
        print("ERROR  :", line)