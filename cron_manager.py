# -*- coding: utf-8 -*-
"""cron_manager.py — Gestion des tâches cron GitHub Actions pour LCDMH.

Module séparé et réutilisable : un seul endroit pour créer, lister,
supprimer les workflows auto-publish, quel que soit le nombre de
road trips actifs.

Chaque road trip a son propre workflow .yml et sa propre config JSON.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─── Constantes ───────────────────────────────────────────────

DEFAULT_REPO = Path(r"F:\LCDMH_GitHub_Audit")
LOCAL_SITE   = Path(r"F:\LCDMH_GitHub_Audit")

INTERVALS_HEURES = [1, 2, 3]  # Choix possibles d'intervalle (en heures)

OFFSET_UTC_FRANCE_ETE  = 2   # UTC+2 en été (CEST)
OFFSET_UTC_FRANCE_HIVER = 1  # UTC+1 en hiver (CET)


# ─── Helpers Git ──────────────────────────────────────────────

def _run_git(repo: Path, args: list) -> Tuple[bool, str, str]:
    """Exécute une commande git dans le repo donné."""
    try:
        r = subprocess.run(
            ["git"] + args,
            cwd=str(repo),
            capture_output=True, text=True, timeout=60
        )
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return False, "", str(e)


# ─── Génération du cron ──────────────────────────────────────

def generer_cron_schedule(heure_locale: int, minute_locale: int,
                          intervalle_heures: int,
                          utc_offset: int = OFFSET_UTC_FRANCE_ETE) -> str:
    """Génère le bloc cron pour GitHub Actions.

    Avec heure=18 et intervalle=3 → crons à 18h, 21h, 00h, 03h, 06h, 09h, 12h, 15h
    (en UTC pour GitHub Actions).
    """
    cron_lines = []
    h = heure_locale
    heures_generees = set()

    # Générer les crons sur 24h à partir de l'heure de départ
    while True:
        utc_h = (h - utc_offset) % 24
        if utc_h in heures_generees:
            break
        heures_generees.add(utc_h)
        cron_lines.append(f"    - cron: '{minute_locale} {utc_h} * * *'")
        h = (h + intervalle_heures) % 24

    return "\n".join(cron_lines)


def generer_workflow_yaml(slug: str, cron_block: str) -> str:
    """Génère le contenu complet du fichier workflow .yml."""
    return f"""name: Auto-publish {slug}
on:
  schedule:
{cron_block}
  workflow_dispatch:

permissions:
  contents: write

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install google-api-python-client google-auth reportlab

      - name: Fetch and inject new videos
        env:
          YT_CLIENT_SECRETS: ${{{{ secrets.YT_CLIENT_SECRETS }}}}
          YT_TOKEN_ANALYTICS: ${{{{ secrets.YT_TOKEN_ANALYTICS }}}}
        run: |
          python scripts/auto_publish_roadtrip.py \\
            --config data/roadtrips/{slug}/auto_publish_config.json

      - name: Commit and push changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          git diff --cached --quiet || git commit -m "Auto-publish: nouvelles videos {slug}"
          git push
"""


# ─── CRUD tâches ─────────────────────────────────────────────

def deployer_cron(
    slug: str,
    playlist_id: str,
    playlist_name: str,
    heure_depart: str,           # "18:00"
    intervalle_heures: int,      # 1, 2 ou 3
    repo_path: Path = DEFAULT_REPO,
    publish_root: Optional[Path] = None,
    auto_script_src: Optional[Path] = None,
) -> Dict[str, Any]:
    """Déploie un workflow cron pour un road trip.

    Supprime automatiquement l'ancien workflow du même slug avant
    d'en créer un nouveau.

    Returns:
        {"ok": bool, "message": str, "workflow_file": str, "crons_count": int}
    """
    result = {"ok": False, "message": "", "workflow_file": "", "crons_count": 0}

    repo = repo_path.expanduser().resolve()
    if not repo.exists():
        result["message"] = f"Dépôt GitHub introuvable : {repo}"
        return result

    # Parse heure
    parts = heure_depart.split(":")
    hour_local = int(parts[0])
    minute_local = int(parts[1]) if len(parts) > 1 else 0

    # 0. Supprimer l'ancien workflow du même slug
    supprimer_cron(slug, repo_path=repo)

    # 1. Sauvegarder la config
    auto_config = {
        "slug": slug,
        "playlist_id": playlist_id,
        "playlist_name": playlist_name,
        "start_time": heure_depart,
        "interval_hours": intervalle_heures,
        "journal_page": f"roadtrips/{slug}-journal.html",
        "main_page": f"roadtrips/{slug}.html",
        "max_main_cards": 3,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    for root in [repo, publish_root]:
        if root and Path(root).exists():
            config_dest = Path(root) / "data" / "roadtrips" / slug / "auto_publish_config.json"
            config_dest.parent.mkdir(parents=True, exist_ok=True)
            config_dest.write_text(
                json.dumps(auto_config, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

    # 2. Générer le cron
    cron_block = generer_cron_schedule(hour_local, minute_local, intervalle_heures)
    nb_crons = cron_block.count("- cron:")

    # 3. Générer le workflow YAML
    workflow_yaml = generer_workflow_yaml(slug, cron_block)

    # 4. Écrire le workflow
    workflow_dir = repo / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    workflow_path = workflow_dir / f"auto-publish-{slug}.yml"
    workflow_path.write_text(workflow_yaml, encoding="utf-8")

    # 5. Copier le script auto_publish_roadtrip.py
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    if auto_script_src and auto_script_src.exists():
        shutil.copy2(auto_script_src, scripts_dir / "auto_publish_roadtrip.py")

    # 6. Git push
    _run_git(repo, ["add", "-A"])
    ok_c, _, err_c = _run_git(repo, [
        "commit", "-m",
        f"Deploy auto-publish {slug} (toutes les {intervalle_heures}h a partir de {heure_depart})"
    ])
    if ok_c:
        _run_git(repo, ["pull", "--rebase", "origin", "main"])
        ok_p, _, err_p = _run_git(repo, ["push", "origin", "main"])
        if ok_p:
            result["ok"] = True
            result["message"] = f"Workflow déployé : {workflow_path.name}"
            result["workflow_file"] = workflow_path.name
            result["crons_count"] = nb_crons
        else:
            result["message"] = f"Push échoué : {err_p}"
    else:
        result["message"] = f"Commit échoué (rien à commiter ?) : {err_c}"
        # Peut arriver si rien n'a changé
        if "nothing to commit" in err_c.lower():
            result["ok"] = True
            result["message"] = "Workflow déjà à jour, rien à commiter."
            result["workflow_file"] = f"auto-publish-{slug}.yml"
            result["crons_count"] = nb_crons

    return result


def supprimer_cron(slug: str, repo_path: Path = DEFAULT_REPO) -> Dict[str, Any]:
    """Supprime le workflow cron d'un road trip."""
    result = {"ok": False, "message": "", "deleted": []}
    repo = repo_path.expanduser().resolve()
    workflow_dir = repo / ".github" / "workflows"

    if not workflow_dir.exists():
        result["message"] = "Aucun dossier workflows trouvé."
        return result

    existing = list(workflow_dir.glob(f"auto-publish-{slug}*.yml"))
    if not existing:
        result["ok"] = True
        result["message"] = f"Aucun workflow pour {slug}."
        return result

    for wf in existing:
        rel = str(wf.relative_to(repo)).replace("\\", "/")
        _run_git(repo, ["rm", "-f", rel])
        result["deleted"].append(wf.name)

    _run_git(repo, ["commit", "-m", f"Suppression workflow {slug}"])
    _run_git(repo, ["push", "origin", "main"])

    result["ok"] = True
    result["message"] = f"{len(existing)} workflow(s) supprimé(s)."
    return result


def lister_crons(repo_path: Path = DEFAULT_REPO) -> List[Dict[str, Any]]:
    """Liste tous les workflows auto-publish actifs dans le repo.

    Returns:
        Liste de dicts : {"slug", "file", "crons_count", "config"}
    """
    repo = repo_path.expanduser().resolve()
    workflow_dir = repo / ".github" / "workflows"
    results = []

    if not workflow_dir.exists():
        return results

    for wf in sorted(workflow_dir.glob("auto-publish-*.yml")):
        # Extraire le slug du nom de fichier
        slug = wf.stem.replace("auto-publish-", "")

        # Compter les crons
        content = wf.read_text(encoding="utf-8", errors="ignore")
        crons_count = content.count("- cron:")

        # Chercher la config associée
        config = {}
        config_path = repo / "data" / "roadtrips" / slug / "auto_publish_config.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        results.append({
            "slug": slug,
            "file": wf.name,
            "crons_count": crons_count,
            "config": config,
        })

    return results


def recapitulatif_cron(slug: str, heure_depart: str, intervalle_heures: int) -> str:
    """Génère un texte récapitulatif lisible des horaires de cron."""
    parts = heure_depart.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0

    heures = []
    heures_set = set()
    current = h
    while True:
        if current in heures_set:
            break
        heures_set.add(current)
        heures.append(f"{current:02d}:{m:02d}")
        current = (current + intervalle_heures) % 24

    return ", ".join(heures)
