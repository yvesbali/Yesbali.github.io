#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Installe le GARDE-FOU LOCAL du site lcdmh.com.
#
# Ce garde-fou exécute au moment du commit les MÊMES 5 contrôles que le robot
# GitHub (.github/workflows/audit-maillage.yml) :
#     1. source unique data/maillage.json présente
#     2. build du maillage IDEMPOTENT  (le build ne doit modifier aucune page)
#     3. index de recherche du site à jour
#     4. sitemap à jour
#     5. audit du maillage sans ERREUR
#
# POURQUOI : le 21/09/2026 le robot GitHub a échoué 7 fois en 28 minutes, ce qui
# a envoyé 7 mails « Run failed: Contrôle maillage LCDMH » dans la boîte d'Yves.
# Cause : le hook local ne vérifiait que 2 contrôles sur 5, donc le n°2 échouait
# à chaque push sans qu'on le sache avant. Désormais l'échec est bloqué sur le
# VPS — plus jamais par mail.
#
# ⚠️ .git/hooks n'est PAS versionné : relancer ce script après tout clone.
#
# Usage :  bash scripts/installer_garde_fou_sitemap.sh
#           bash scripts/installer_garde_fou_sitemap.sh --verifier
# ══════════════════════════════════════════════════════════════════════════════

set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$REPO/scripts/hooks/pre-commit"
HOOK="$REPO/.git/hooks/pre-commit"

if [ ! -d "$REPO/.git" ]; then
    echo "❌ pas un dépôt git : $REPO"; exit 1
fi

if [ ! -f "$SOURCE" ]; then
    echo "❌ source du garde-fou absente : $SOURCE"; exit 1
fi

# ── mode vérification : le hook installé est-il à jour ? ─────────────────────
if [ "$1" = "--verifier" ]; then
    if [ ! -f "$HOOK" ]; then
        echo "🔴 garde-fou NON INSTALLÉ — lancer : bash scripts/installer_garde_fou_sitemap.sh"; exit 1
    fi
    if ! diff -q "$SOURCE" "$HOOK" >/dev/null 2>&1; then
        echo "🔴 garde-fou PÉRIMÉ (versionné ≠ installé) — relancer l'installeur"; exit 1
    fi
    echo "✅ garde-fou à jour ($(grep -c '^# ── ' "$HOOK") contrôles)"
    exit 0
fi

cp "$SOURCE" "$HOOK"
chmod +x "$HOOK"
echo "✅ garde-fou installé : $HOOK"
echo ""
echo "   Contrôles exécutés à chaque commit :"
grep -E '^# ── [0-9]' "$HOOK" | sed 's/^# ── /     /; s/ ─*$//'
echo ""
echo "   Vérifier à tout moment : bash scripts/installer_garde_fou_sitemap.sh --verifier"
