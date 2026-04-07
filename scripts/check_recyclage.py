#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificateur Recyclage Social LCDMH
=====================================
Verifie que tout est en place pour l'automatisation.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ERRORS = []
WARNINGS = []
OK = []


def check(label, condition, error_msg="", warn=False):
    if condition:
        OK.append(f"  OK  {label}")
    elif warn:
        WARNINGS.append(f"  ??  {label} - {error_msg}")
    else:
        ERRORS.append(f"  XX  {label} - {error_msg}")


def main():
    print("=" * 60)
    print("  VERIFICATION RECYCLAGE SOCIAL LCDMH")
    print("=" * 60)
    print()

    # ── 1. FICHIERS SCRIPTS ──
    print("1. SCRIPTS")
    print("-" * 40)

    cron_script = REPO_ROOT / "scripts" / "cron_recyclage_social.py"
    check("cron_recyclage_social.py", cron_script.exists(), "MANQUANT dans scripts/")

    workflow = REPO_ROOT / ".github" / "workflows" / "recyclage-social.yml"
    check("recyclage-social.yml", workflow.exists(), "MANQUANT dans .github/workflows/")

    if workflow.exists():
        content = workflow.read_text(encoding="utf-8")
        check("Workflow contient cron", "cron:" in content, "Pas de cron dans le workflow")
        check("Workflow contient yt-dlp", "yt-dlp" in content, "yt-dlp pas dans les dependances")
        check("Workflow contient requests", "requests" in content, "requests pas dans les dependances")

    for item in OK + WARNINGS + ERRORS:
        print(item)
    print()

    # ── 2. FICHIERS DATA ──
    print("2. DONNEES")
    print("-" * 40)
    prev_counts = (len(OK), len(WARNINGS), len(ERRORS))

    data_dir = REPO_ROOT / "data" / "social_recyclage"
    check("Dossier data/social_recyclage/", data_dir.exists(), "MANQUANT - creer le dossier")

    planning_file = data_dir / "planning_v8.json"
    check("planning_v8.json", planning_file.exists(), "MANQUANT - uploader depuis le PC")

    historique_file = data_dir / "historique_publications.json"
    check("historique_publications.json", historique_file.exists(), "MANQUANT - uploader depuis le PC", warn=True)

    for item in (OK + WARNINGS + ERRORS)[sum(prev_counts):]:
        print(item)
    print()

    # ── 3. PLANNING ──
    print("3. PLANNING")
    print("-" * 40)
    prev_counts2 = (len(OK), len(WARNINGS), len(ERRORS))

    if planning_file.exists():
        try:
            planning = json.loads(planning_file.read_text(encoding="utf-8"))
            check(f"Planning lisible ({len(planning)} entrees)", True)

            # Publications par type
            pubs = [p for p in planning if p.get("type_contenu") == "pub"]
            souvenirs = [p for p in planning if p.get("type_contenu") == "souvenir"]
            check(f"Pubs: {len(pubs)}, Souvenirs: {len(souvenirs)}", len(planning) > 0, "Planning vide")

            # Publications a venir
            today = date.today()
            futures = [p for p in planning if p.get("date", "") >= str(today)]
            check(f"Publications a venir: {len(futures)}", len(futures) > 0, "Aucune publication future - regenerer le planning")

            # Prochaine publication
            if futures:
                futures.sort(key=lambda x: x.get("date", ""))
                prochaine = futures[0]
                check(
                    f"Prochaine: {prochaine.get('date')} {prochaine.get('plateforme')} - {prochaine.get('titre', '')[:40]}",
                    True
                )

            # Publications aujourd'hui
            aujourdhui = [p for p in planning if p.get("date") == str(today)]
            if aujourdhui:
                check(f"Aujourd'hui: {len(aujourdhui)} publication(s)", True)
            else:
                check("Aujourd'hui: aucune publication prevue", True)

            # Verifier que chaque entree a les champs requis
            champs_requis = ["date", "plateforme", "video_id", "titre", "url"]
            incomplets = 0
            for p in planning:
                if not all(p.get(c) for c in champs_requis):
                    incomplets += 1
            check(f"Entrees completes", incomplets == 0, f"{incomplets} entree(s) avec champs manquants", warn=True)

            # Plateformes
            fb = len([p for p in planning if p.get("plateforme") == "Facebook"])
            ig = len([p for p in planning if p.get("plateforme") == "Instagram"])
            check(f"Facebook: {fb}, Instagram: {ig}", True)

        except Exception as e:
            check("Lecture planning", False, f"Erreur: {e}")
    else:
        check("Planning", False, "Fichier manquant, impossible de verifier")

    for item in (OK + WARNINGS + ERRORS)[sum(prev_counts2):]:
        print(item)
    print()

    # ── 4. HISTORIQUE ──
    print("4. HISTORIQUE")
    print("-" * 40)
    prev_counts3 = (len(OK), len(WARNINGS), len(ERRORS))

    if historique_file.exists():
        try:
            historique = json.loads(historique_file.read_text(encoding="utf-8"))
            check(f"Historique lisible ({len(historique)} entrees)", True)
        except Exception as e:
            check("Lecture historique", False, f"Erreur: {e}")
    else:
        check("Historique absent", True)
        print("  >>  Sera cree automatiquement au premier run")

    for item in (OK + WARNINGS + ERRORS)[sum(prev_counts3):]:
        print(item)
    print()

    # ── 5. CONFIG WEBHOOK ──
    print("5. CONFIG WEBHOOK / CLOUDINARY")
    print("-" * 40)
    prev_counts4 = (len(OK), len(WARNINGS), len(ERRORS))

    if cron_script.exists():
        script_content = cron_script.read_text(encoding="utf-8")
        check("Webhook Make configure", "hook.eu1.make.com" in script_content, "URL webhook manquante")
        check("Cloudinary configure", "dwls7akrc" in script_content, "Cloud Cloudinary manquant")
        check("PIN configure", "0172" in script_content, "PIN manquant")
        check("Envoie platform (pas publish_fb)", '"platform"' in script_content, "Utilise publish_fb au lieu de platform")

    for item in (OK + WARNINGS + ERRORS)[sum(prev_counts4):]:
        print(item)
    print()

    # ── RESUME ──
    print("=" * 60)
    print(f"  RESULTAT: {len(OK)} OK / {len(WARNINGS)} avertissements / {len(ERRORS)} erreurs")
    print("=" * 60)

    if ERRORS:
        print()
        print("  ERREURS A CORRIGER:")
        for e in ERRORS:
            print(f"    {e}")
        print()
        sys.exit(1)
    elif WARNINGS:
        print()
        print("  AVERTISSEMENTS (non bloquants):")
        for w in WARNINGS:
            print(f"    {w}")
        print()
        print("  >> Le cron devrait fonctionner malgre les avertissements")
        sys.exit(0)
    else:
        print()
        print("  TOUT EST BON ! Le cron va publier automatiquement.")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
