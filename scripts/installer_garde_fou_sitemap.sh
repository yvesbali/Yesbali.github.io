#!/bin/bash
# Installe un garde-fou git : refuse un commit si le sitemap ne correspond
# plus au contenu réel du site.
#
# POURQUOI : la cause racine du problème d'indexation de lcdmh.com était un
# sitemap ÉCRIT À LA MAIN, qui se désynchronisait à chaque nouvelle page.
# Des pages publiées n'entraient jamais dans le sitemap → Google ne les
# découvrait pas → « des pages non indexées, toujours les mêmes ».
#
# Le sitemap est désormais GÉNÉRÉ (scripts/generer_sitemap.py). Ce garde-fou
# garantit qu'on ne peut plus commiter un sitemap périmé.
#
# ⚠️ .git/hooks n'est PAS versionné : relancer ce script après tout clone.
#
# Usage :  bash scripts/installer_garde_fou_sitemap.sh

set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$REPO/.git/hooks/pre-commit"

if [ ! -d "$REPO/.git" ]; then
    echo "❌ pas un dépôt git : $REPO"; exit 1
fi

cat > "$HOOK" <<'HOOK'
#!/bin/bash
# Garde-fou : refuse un commit si le sitemap ne correspond plus au contenu réel.
REPO="$(git rev-parse --show-toplevel)"
if [ ! -f "$REPO/scripts/generer_sitemap.py" ]; then exit 0; fi
SORTIE=$(cd "$REPO" && python3 scripts/generer_sitemap.py --verifier 2>&1)
if [ $? -ne 0 ]; then
  echo ""
  echo "🔴 SITEMAP DÉSYNCHRONISÉ — commit refusé."
  echo "$SORTIE"
  echo ""
  echo "   → lancer : python3 scripts/generer_sitemap.py  puis re-commiter"
  echo "   → ou forcer : git commit --no-verify"
  echo ""
  exit 1
fi
exit 0
HOOK
chmod +x "$HOOK"
echo "✅ garde-fou installé : $HOOK"
