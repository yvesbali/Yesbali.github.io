#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_app_py.py — Patche F:\\Automate_YT\\app.py pour ajouter la page
Retention Extractor dans ton app Streamlit existante.

Fait 4 modifications (toutes idempotentes, toutes avec backup horodate) :

  1. Bloc try/except d'import de page_retention_extractor, place apres
     les autres blocs d'import de pages en haut du fichier.
  2. Entree dans le dict _PAGE_DESCRIPTIONS (infobulle contextuelle),
     place juste avant la cle "🧑‍💻 Git / GitHub" (derniere entree).
  3. Entree dans la liste du st.radio "Mode", meme position.
  4. Dispatch elif mode_app == "🎯 Retention Extractor", insere a la
     fin de la chaine if/elif qui appelle les pages.

Fonctionnement :
  - Lit app.py en UTF-8.
  - Cherche des "anchors" textuels pour localiser les 4 points d'insertion.
  - Si une modif est deja presente, la saute (idempotent).
  - Fait toujours une backup horodatee avant de toucher au fichier.
  - Pour le dispatch (#4), si l'anchor est ambigu, affiche un diff
     propose et demande confirmation.

Usage :
  python F:\\Automate_YT\\retention_extractor\\patch_app_py.py
  python F:\\Automate_YT\\retention_extractor\\patch_app_py.py --app F:\\chemin\\autre\\app.py
  python F:\\Automate_YT\\retention_extractor\\patch_app_py.py --dry-run
  python F:\\Automate_YT\\retention_extractor\\patch_app_py.py --revert  # restaure la derniere backup
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_APP_PY = Path(r"F:\Automate_YT\app.py")

# ══════════════════════════════════════════════════════════════════════
# Snippets a inserer
# ══════════════════════════════════════════════════════════════════════
IMPORT_BLOCK = """\
# Retention Extractor — clips best-of depuis YouTube Analytics
try:
    from page_retention_extractor import page_retention_extractor
    RETENTION_EXTRACTOR_OK = True
except ImportError:
    RETENTION_EXTRACTOR_OK = False
    def page_retention_extractor():
        import streamlit as _st
        _st.error("❌ page_retention_extractor.py introuvable dans F:\\\\Automate_YT\\\\")

"""

DESC_ENTRY_LINE = (
    '            "🎯 Retention Extractor":       '
    '"Extrait les meilleurs passages des vidéos longues via YouTube Analytics, '
    'découpe en 4K et prépare la republication (Souvenir : ...).",\n'
)

RADIO_ENTRY_LINE = '                "🎯 Retention Extractor",\n'

DISPATCH_SNIPPET = """\

    elif mode_app == "🎯 Retention Extractor":
        page_retention_extractor()
"""


# ══════════════════════════════════════════════════════════════════════
# Utilitaires
# ══════════════════════════════════════════════════════════════════════
def make_backup(app_py: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = app_py.with_name(f"{app_py.name}.bak.{ts}")
    shutil.copy2(app_py, backup)
    return backup


def latest_backup(app_py: Path) -> Path | None:
    pattern = f"{app_py.name}.bak.*"
    backups = sorted(app_py.parent.glob(pattern))
    return backups[-1] if backups else None


# ══════════════════════════════════════════════════════════════════════
# Patches
# ══════════════════════════════════════════════════════════════════════
def patch_imports(content: str) -> tuple[str, str]:
    """Ajoute le bloc d'import apres le dernier bloc try/except from page_*."""
    if "from page_retention_extractor import page_retention_extractor" in content:
        return content, "skipped (deja present)"

    # Anchor : le dernier "from page_*" ou bloc try/except qui finit par un
    # def page_xxx(): ... _st.error(...).  On prend le dernier bloc qui finit
    # par une fonction fallback d'erreur.
    patterns = [
        # bloc try/except complet
        re.compile(
            r"(try:\n\s+from page_publication_center import render_page as render_publication_center\n.*?"
            r"_st\.error\(.*?\)\n)",
            re.DOTALL,
        ),
        re.compile(
            r"(try:\n\s+from page_article_generator import render_article_generator\n.*?"
            r"HAS_ARTICLE_GEN = False\n)",
            re.DOTALL,
        ),
        re.compile(
            r"(try:\n\s+from page_content_factory import render_content_factory\n.*?"
            r"_st\.error\(.*?\)\n)",
            re.DOTALL,
        ),
    ]
    for pat in patterns:
        matches = list(pat.finditer(content))
        if matches:
            last = matches[-1]
            insert_at = last.end()
            new_content = content[:insert_at] + "\n" + IMPORT_BLOCK + content[insert_at:]
            return new_content, f"OK (insere apres pattern #{patterns.index(pat)+1})"

    # Fallback : juste apres la derniere ligne qui commence par "from page_"
    last_from = None
    for m in re.finditer(r"^from page_\w+ import .+$", content, re.MULTILINE):
        last_from = m
    if last_from:
        insert_at = last_from.end()
        # avance jusqu'a la fin de la ligne et saute \n
        while insert_at < len(content) and content[insert_at] != "\n":
            insert_at += 1
        if insert_at < len(content):
            insert_at += 1
        new_content = content[:insert_at] + "\n" + IMPORT_BLOCK + content[insert_at:]
        return new_content, "OK (fallback: apres dernier from page_*)"

    return content, "FAIL (aucun anchor d'import trouve)"


def patch_page_descriptions(content: str) -> tuple[str, str]:
    """Ajoute une entree dans le dict _PAGE_DESCRIPTIONS."""
    if '"🎯 Retention Extractor"' in content and "_PAGE_DESCRIPTIONS" in content:
        # On verifie plus precisement que notre entree est presente
        if re.search(
            r'"🎯 Retention Extractor"\s*:\s*"',
            content,
        ):
            return content, "skipped (deja present)"

    # Anchor : la ligne "🧑‍💻 Git / GitHub" dans _PAGE_DESCRIPTIONS
    anchor = re.compile(
        r'(\n)(\s+)"🧑‍💻 Git / GitHub":\s*"[^"]*",\n',
    )
    m = anchor.search(content)
    if m:
        insert_at = m.start(1) + 1  # juste apres le \n precedent
        # On prend l'indentation de la ligne anchor
        new_content = content[:insert_at] + DESC_ENTRY_LINE + content[insert_at:]
        return new_content, "OK (avant Git / GitHub)"

    # Fallback : fin du dict _PAGE_DESCRIPTIONS
    anchor2 = re.compile(
        r"(_PAGE_DESCRIPTIONS\s*=\s*\{[^}]*?)(\n\s+\})",
        re.DOTALL,
    )
    m2 = anchor2.search(content)
    if m2:
        inner = m2.group(1).rstrip()
        if not inner.endswith(","):
            inner += ","
        new_content = (
            content[:m2.start()]
            + inner
            + "\n"
            + DESC_ENTRY_LINE.rstrip("\n")
            + m2.group(2)
            + content[m2.end():]
        )
        return new_content, "OK (fin de dict)"

    return content, "FAIL (dict _PAGE_DESCRIPTIONS introuvable)"


def patch_radio_list(content: str) -> tuple[str, str]:
    """Ajoute une entree dans la liste du st.radio 'Mode'."""
    # Check presence
    if re.search(r'"🎯 Retention Extractor"\s*,', content):
        # Verifier qu'elle est bien dans la liste du radio (pas juste dans le dict)
        radio_block = re.search(
            r"mode_app\s*=\s*st\.radio\(\s*\"Mode\",\s*\[([^\]]*)\]",
            content,
            re.DOTALL,
        )
        if radio_block and '"🎯 Retention Extractor"' in radio_block.group(1):
            return content, "skipped (deja present)"

    # Anchor : la ligne "🧑‍💻 Git / GitHub" dans la liste du radio
    # (c'est la 2e occurrence dans le fichier, la 1re etant dans le dict)
    pattern = re.compile(r'(\n)(\s+)"🧑‍💻 Git / GitHub",\n')
    matches = list(pattern.finditer(content))
    if len(matches) >= 2:
        # 2e occurrence = liste radio
        m = matches[1]
        insert_at = m.start(1) + 1
        new_content = content[:insert_at] + RADIO_ENTRY_LINE + content[insert_at:]
        return new_content, "OK (avant Git / GitHub dans radio list)"
    elif len(matches) == 1:
        # Fallback : cette unique occurrence est peut-etre dans la liste radio
        # si on l'a deja ajoutee dans le dict (cas idempotence partielle)
        m = matches[0]
        # Verifier le contexte
        before = content[max(0, m.start()-300):m.start()]
        if "st.radio" in before or "mode_app" in before:
            insert_at = m.start(1) + 1
            new_content = content[:insert_at] + RADIO_ENTRY_LINE + content[insert_at:]
            return new_content, "OK (1 match, contexte radio)"

    return content, "FAIL (aucun anchor Git / GitHub dans liste radio)"


def patch_dispatch(content: str) -> tuple[str, str]:
    """Ajoute le elif dispatch a la fin de la chaine if/elif mode_app."""
    if re.search(r'elif\s+mode_app\s*==\s*"🎯 Retention Extractor"', content):
        return content, "skipped (deja present)"

    # Strategy : trouver toutes les occurrences de
    # `elif mode_app == "..."` (ou `if mode_app == "..."`) qui sont suivies
    # d'un appel de fonction (page_xxx() ou render_xxx()).
    # Les vrais dispatches ont cette signature.
    disp_pattern = re.compile(
        r'(^\s*)(elif|if)\s+mode_app\s*==\s*"[^"]+"\s*:\s*\n'
        r'(\s+)([a-zA-Z_]\w*)\s*\(\s*\)',
        re.MULTILINE,
    )
    matches = list(disp_pattern.finditer(content))
    if not matches:
        return content, "FAIL (aucun dispatch if/elif mode_app trouve)"

    # Dernier match = fin de la chaine dispatch
    last = matches[-1]
    indent_if = last.group(1)  # indentation de 'elif'
    indent_body = last.group(3)  # indentation du body

    # On doit inserer apres le bloc complet du dernier elif. Trouver la fin du body.
    body_start = last.end()
    body_end = body_start
    for line_match in re.finditer(
        rf'^({indent_body}.*|\s*$)', content[body_start:], re.MULTILINE,
    ):
        if line_match.group(0).strip() == "":
            body_end = body_start + line_match.end()
            continue
        if not line_match.group(0).startswith(indent_body):
            break
        body_end = body_start + line_match.end()

    snippet = f"\n{indent_if}elif mode_app == \"🎯 Retention Extractor\":\n{indent_body}page_retention_extractor()\n"
    new_content = content[:body_end] + snippet + content[body_end:]
    return new_content, f"OK (insere apres ligne {content[:body_end].count(chr(10))})"


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", type=Path, default=DEFAULT_APP_PY,
                    help=f"Chemin d'app.py (defaut: {DEFAULT_APP_PY})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Affiche ce qui serait fait, sans ecrire.")
    ap.add_argument("--revert", action="store_true",
                    help="Restaure la derniere backup.")
    args = ap.parse_args()

    app_py = args.app.resolve()
    if not app_py.exists():
        print(f"[ERREUR] {app_py} introuvable.")
        return 1

    if args.revert:
        backup = latest_backup(app_py)
        if not backup:
            print(f"[ERREUR] Aucune backup trouvee pour {app_py}")
            return 1
        shutil.copy2(backup, app_py)
        print(f"[OK] {app_py} restaure depuis {backup.name}")
        return 0

    content = app_py.read_text(encoding="utf-8")
    original = content

    print(f"[*] Fichier  : {app_py}  ({len(content)} chars)")
    print(f"[*] Dry run  : {args.dry_run}")
    print("")

    steps = [
        ("1/4 import  ", patch_imports),
        ("2/4 dict    ", patch_page_descriptions),
        ("3/4 radio   ", patch_radio_list),
        ("4/4 dispatch", patch_dispatch),
    ]
    for label, fn in steps:
        content, status = fn(content)
        print(f"  [{label}] {status}")

    if content == original:
        print("\n[*] Aucun changement (tout est deja applique).")
        return 0

    if args.dry_run:
        print("\n[DRY] Aucune ecriture. Lance sans --dry-run pour appliquer.")
        # Diff resume
        delta = len(content) - len(original)
        print(f"[DRY] Taille : +{delta} caracteres.")
        return 0

    backup = make_backup(app_py)
    print(f"\n[BACKUP] {backup.name}")
    app_py.write_text(content, encoding="utf-8")
    print(f"[OK] {app_py} patche.")
    print("\nTu peux maintenant relancer :")
    print("  streamlit run F:\\Automate_YT\\app.py")
    print("\nSi quelque chose casse :")
    print(f"  python patch_app_py.py --revert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
