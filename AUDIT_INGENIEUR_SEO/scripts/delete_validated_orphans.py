#!/usr/bin/env python3
"""
Suppression des orphelins validés par l'utilisateur le 2026-04-18.
Trois lots :
  1. quick-wins (special_chars + blog_generated + shopify_variants) = 63 fichiers
  2. dossiers vidéo-only doublons (retour-honda + cols-alpes) = 152 fichiers (76 + 76)
  3. surnuméraires radar-moto = 16 fichiers

Idempotent : ne supprime que ce qui existe encore.
Mode --dry-run pour audit avant exécution.
"""
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOURNAL_DIR = ROOT / "AUDIT_INGENIEUR_SEO" / "journaux"

# Dossiers complets à virer (videos-only avec contenu fourre-tout dupliqué)
FOLDERS_TO_DELETE = [
    "articles/images/retour-honda-nt-1100-a-26000-kms",
    "articles/images/cols-mythiques-des-alpes-a-moto-trk-502-ep-1",
]

def load_categorized():
    src = JOURNAL_DIR / "dedup_categorized.json"
    return json.loads(src.read_text())

def collect_quick_wins(data):
    """63 fichiers : special_chars + blog_generated + shopify_variants."""
    paths = []
    for cat in ("special_chars", "blog_generated", "shopify_variants"):
        paths.extend(data.get(cat, []))
    return paths

def collect_radar_normal(data):
    """16 fichiers de radar-moto dans la catégorie 'normal'."""
    return [p for p in data.get("normal", []) if "radar-moto-comment-ca-marche" in p]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Lister sans supprimer")
    args = ap.parse_args()

    data = load_categorized()
    quick = collect_quick_wins(data)
    radar = collect_radar_normal(data)

    print(f"Quick-wins (3 catégs)     : {len(quick)} fichiers à supprimer")
    print(f"Radar-moto surnuméraires  : {len(radar)} fichiers à supprimer")
    print(f"Dossiers vidéo-only doubl : {len(FOLDERS_TO_DELETE)} dossiers entiers")
    print(f"Mode : {'DRY-RUN' if args.dry_run else 'EXÉCUTION'}")
    print()

    deleted_files = 0
    deleted_bytes = 0
    skipped = 0

    # 1. Fichiers individuels
    for rel in quick + radar:
        fp = ROOT / rel
        if not fp.exists():
            skipped += 1
            continue
        size = fp.stat().st_size
        if args.dry_run:
            print(f"  [DRY] {rel}")
        else:
            fp.unlink()
        deleted_files += 1
        deleted_bytes += size

    # 2. Dossiers complets
    folder_files = 0
    folder_bytes = 0
    for rel in FOLDERS_TO_DELETE:
        fd = ROOT / rel
        if not fd.exists():
            print(f"  [SKIP] dossier déjà absent : {rel}")
            continue
        # Compter avant suppression
        for fp in fd.rglob("*"):
            if fp.is_file():
                folder_files += 1
                folder_bytes += fp.stat().st_size
        if args.dry_run:
            print(f"  [DRY-DIR] {rel} ({sum(1 for _ in fd.rglob('*') if _.is_file())} fichiers)")
        else:
            shutil.rmtree(fd)
            print(f"  [RMDIR] {rel}")

    print()
    print("=== RÉSUMÉ ===")
    print(f"Fichiers individuels {'supprimés' if not args.dry_run else 'à supprimer'} : {deleted_files} ({deleted_bytes//1024} KiB)")
    print(f"Fichiers dans dossiers {'supprimés' if not args.dry_run else 'à supprimer'} : {folder_files} ({folder_bytes//1024//1024} MiB)")
    print(f"Total libéré : {(deleted_bytes + folder_bytes)//1024//1024} MiB")
    print(f"Déjà absents (skip) : {skipped}")

if __name__ == "__main__":
    main()
