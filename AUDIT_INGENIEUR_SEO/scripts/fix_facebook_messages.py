#!/usr/bin/env python3
"""
Corrige les messages Facebook dans la bibliothèque `facebook/facebook_payload_test.json`
pour éliminer les mentions URL parasites qui font que Facebook scrape la HOME lcdmh.com
au lieu de générer la preview YouTube.

Bug observé le 15/04/2026 sur le post w05-aferiy-nano100 :
  Card affichée : "LCDMH - La Chaîne du Motard Heureux" + lcdmh.com + pas d'image
  Attendu      : thumbnail YouTube + titre vidéo + description

Cause : le message contient "🔗 https://lcdmh.com" → Facebook détecte cette URL dans le
texte AVANT le champ link=YouTube, et scrape la home lcdmh.com qui a un og:image trop
générique.

Stratégie : supprimer la mention "🔗 https://lcdmh.com" et remplacer
"👉 Mon test : lcdmh.com" par "👉 Mon test complet sur la chaîne" (sans URL).

Résultat : Facebook scrape uniquement le link YouTube → preview thumbnail + titre propre
→ clic → trafic YouTube (monétisation).

Mode --dry-run pour audit avant.
Idempotent : ne modifie que les posts non encore publiés.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "facebook" / "facebook_payload_test.json"

# Patterns parasites à retirer/remplacer
# Ordre IMPORTANT : du plus spécifique au plus général
PATTERNS = [
    # 1. Ligne entière "🔗 https://lcdmh.com[/...]"  (URL complète sur sa propre ligne)
    (re.compile(r"\n*🔗 https?://lcdmh\.com[^\s\n]*\n*"), "\n"),
    # 2. "👉 Mon test [complet] : lcdmh.com[/...]" → "👉 Mon test complet en vidéo"
    (re.compile(r"👉 Mon test( complet)? : lcdmh\.com[^\s\n]*"),
     "👉 Mon test complet en vidéo"),
    # 3. "👉 Mon test sur lcdmh.com[/...]" → idem
    (re.compile(r"👉 Mon test sur lcdmh\.com[^\s\n]*"),
     "👉 Mon test complet en vidéo"),
    # 4. "est sur lcdmh.com avec" / "sur lcdmh.com avec mes vidéos" → "sur la chaîne avec"
    (re.compile(r"sur lcdmh\.com avec"), "sur la chaîne avec"),
    # 5. URL nue lcdmh.com/xxx.html dans texte → "(lien en bio)"
    (re.compile(r"lcdmh\.com/[\w\-/]+\.html"), "(lien en description)"),
    # 6. Mentions "lcdmh.com" seules (pas dans URL https://, pas suivies de /)
    (re.compile(r"(?<![/:])\blcdmh\.com\b(?![\w/])"), "la chaîne"),
]

def clean_message(msg: str) -> str:
    original = msg
    for pat, repl in PATTERNS:
        msg = pat.sub(repl, msg)
    # Nettoyer les doubles sauts de ligne générés par la suppression
    msg = re.sub(r"\n{3,}", "\n\n", msg)
    return msg.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    posts = data["posts"]

    modified = 0
    skipped_published = 0
    examples = []

    for p in posts:
        if p.get("published"):
            skipped_published += 1
            continue
        original = p.get("message", "")
        cleaned = clean_message(original)
        if cleaned != original:
            modified += 1
            if len(examples) < 2:
                examples.append((p["id"], original, cleaned))
            if not args.dry_run:
                p["message"] = cleaned

    print(f"Posts analysés : {len(posts)}")
    print(f"Posts déjà publiés (skip) : {skipped_published}")
    print(f"Posts {'à modifier' if args.dry_run else 'modifiés'} : {modified}")
    print()

    if examples:
        print("=== EXEMPLES (2 premiers) ===")
        for pid, orig, clean in examples:
            print(f"\n--- {pid} ---")
            print("AVANT:")
            for line in orig.split("\n"):
                print(f"  {line}")
            print("APRÈS:")
            for line in clean.split("\n"):
                print(f"  {line}")

    if not args.dry_run and modified:
        PAYLOAD.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
        print(f"\n✅ Fichier mis à jour : {PAYLOAD.relative_to(ROOT)}")
    elif args.dry_run:
        print("\n[DRY-RUN] Aucune modification écrite.")

if __name__ == "__main__":
    main()
