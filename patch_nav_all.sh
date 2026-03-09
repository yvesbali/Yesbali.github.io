#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-.}"
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Dossier introuvable : $TARGET_DIR" >&2
  exit 1
fi

BACKUP_DIR="$TARGET_DIR/backup_nav_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

export TARGET_DIR BACKUP_DIR

python3 <<'PY'
from pathlib import Path
import os
import re
import shutil

target = Path(os.environ["TARGET_DIR"]).resolve()
backup = Path(os.environ["BACKUP_DIR"]).resolve()

snippet = '''<!-- ======================================== -->
<!-- NAVIGATION UNIQUE LCDMH -->
<!-- ======================================== -->
<div id="lcdmh-nav-container"></div>
<script src="nav-loader.js"></script>
<!-- ======================================== -->'''

pattern_existing_loader = re.compile(
    r'''<div\s+id=["']lcdmh-nav-container["']\s*></div>\s*<script(?:\s+src=["'][^"']*nav-loader\.js[^"']*["'])?[^>]*>.*?</script>''',
    re.IGNORECASE | re.DOTALL,
)

pattern_inline_fetch = re.compile(
    r'''<div\s+id=["']lcdmh-nav-container["']\s*></div>\s*<script>.*?fetch\s*\(.*?nav\.html.*?</script>''',
    re.IGNORECASE | re.DOTALL,
)

patched = []
skipped = []

for path in sorted(target.rglob("*.html")):
    if path.name.lower() == "nav.html":
        skipped.append(str(path.relative_to(target)))
        continue

    original = path.read_text(encoding="utf-8", errors="ignore")
    text = original

    text = pattern_existing_loader.sub(snippet, text, count=1)
    text = pattern_inline_fetch.sub(snippet, text, count=1)

    if 'id="lcdmh-nav-container"' not in text:
        text, count = re.subn(r'(?i)(<body[^>]*>)', r'\1\n\n' + snippet + '\n', text, count=1)
        if count == 0:
            skipped.append(str(path.relative_to(target)))
            continue

    if text != original:
        backup_path = backup / path.relative_to(target)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        path.write_text(text, encoding="utf-8")
        patched.append(str(path.relative_to(target)))
    else:
        skipped.append(str(path.relative_to(target)))

print("PAGES MODIFIÉES :")
for item in patched:
    print(" -", item)

print("\nPAGES NON MODIFIÉES :")
for item in skipped:
    print(" -", item)

print("\nSauvegarde :", backup)
PY

echo
echo "Terminé."
echo "Copie aussi nav.html et nav-loader.js à la racine du site avant de republier."
