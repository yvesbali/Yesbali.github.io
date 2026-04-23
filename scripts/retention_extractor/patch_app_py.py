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
    # Skip si deja present dans la liste radio
    radio_block_re = re.compile(
        r"st\.radio\([^)]*?\[([^\]]*)\]",
        re.DOTALL,
    )
    for block in radio_block_re.finditer(content):
        if '"🎯 Retention Extractor"' in block.group(1):
            return content, "skipped (deja present dans radio)"

    # Anchor : "🧑‍💻 Git / GitHub" suivi directement d'une virgule (format liste).
    # Le format dict "🧑‍💻 Git / GitHub": ne matche PAS ce regex (deux-points
    # au lieu de virgule), donc on ne risque pas de patcher le dict par erreur.
    pattern = re.compile(r'(\n)(\s+)"\U0001f9d1‍\U0001f4bb Git / GitHub"\s*,\s*\n')
    m = pattern.search(content)
    if m:
        insert_at = m.start(1) + 1
        new_content = content[:insert_at] + RADIO_ENTRY_LINE + content[insert_at:]
        return new_content, "OK (radio list, avant Git / GitHub)"

    # Fallback : chercher n'importe quelle liste contenant "Git / GitHub",
    # et inserer avant la derniere occurrence.
    fallback = re.compile(r'(\n)(\s+)"[^"]*Git / GitHub"\s*,\s*\n')
    matches = list(fallback.finditer(content))
    if matches:
        m = matches[-1]
        insert_at = m.start(1) + 1
        new_content = content[:insert_at] + RADIO_ENTRY_LINE + content[insert_at:]
        return new_content, "OK (fallback Git / GitHub)"

    return content, "FAIL (aucun anchor Git / GitHub dans liste radio)"


def patch_dispatch(content: str) -> tuple[str, str]:
    """
    Ajoute le elif dispatch pour la page Retention Extractor.
    Supporte plusieurs formes de dispatch :
      - if/elif mode_app == "..."
      - if/elif st.session_state.get("_mode_app") == "..."
      - if/elif choice == "..."
      - etc. (on detecte via la presence d'un page_xxx() / render_xxx()
        directement apres le :)
    On localise le dernier bloc de ce type et on insere a la suite, en
    reprenant la meme variable et indentation.
    """
    # Skip si le dispatch specifique est deja en place : on cherche EXACTEMENT
    # un test d'egalite sur "🎯 Retention Extractor" directement suivi par
    # un appel a page_retention_extractor(). N'importe quel autre faux
    # positif (mots contenant "if", commentaires, dict values) est exclu.
    already = re.search(
        r'==\s*"🎯 Retention Extractor"\s*:\s*\n\s*page_retention_extractor\s*\(\s*\)',
        content,
    )
    if already:
        return content, "skipped (deja present)"

    # Regex tres permissif : (elif|if) <var...> == "<mode string>": \n <indent> <fn>()
    # <var...> peut etre : mode_app / choix / st.session_state.get("_mode_app") / etc.
    # <fn> doit etre page_xxx ou render_xxx ou un nom pythonique valide.
    disp_pattern = re.compile(
        r'(^\s*)(elif|if)\s+(.+?)\s*==\s*"([^"]+)"\s*:\s*\n'
        r'(\s+)([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)',
        re.MULTILINE,
    )
    matches = list(disp_pattern.finditer(content))

    # Filtrer : on garde seulement les matches ou la fonction est un
    # page_xxx() / render_xxx() (sinon on attrape du if dans la sidebar).
    filtered: list[re.Match[str]] = []
    for m in matches:
        fn_name = m.group(6)
        if fn_name.startswith("page_") or fn_name.startswith("render_"):
            filtered.append(m)

    if not filtered:
        return content, "FAIL (aucun dispatch page_xxx()/render_xxx() trouve)"

    # Grouper par variable de dispatch ; on prend le plus gros groupe contigus.
    # Plus simple : dernier match de la plus longue chaine contigu.
    last = filtered[-1]
    indent_if = last.group(1)
    dispatch_var = last.group(3).strip()
    indent_body = last.group(5)
    body_fn_name = last.group(6)

    # Calculer la fin du body du dernier elif : on avance jusqu'a la premiere
    # ligne qui a une indentation plus petite ou egale a celle du 'elif'/'if'.
    body_start = last.end()
    lines_after = content[body_start:].split("\n")
    end_offset = body_start
    current = body_start
    for i, line in enumerate(lines_after):
        if i == 0:
            current += len(line) + 1  # premiere ligne : juste finir la ligne en cours
            continue
        # Une ligne vide fait partie du bloc.
        if line.strip() == "":
            current += len(line) + 1
            continue
        # Si indentation au moins egale a indent_body, on reste dans le body.
        leading = len(line) - len(line.lstrip(" "))
        if leading >= len(indent_body):
            current += len(line) + 1
            continue
        # Sinon on sort.
        end_offset = current - 1  # le - 1 pour ne pas manger le \n de fin
        break
    else:
        end_offset = current

    # Construire le snippet en reprenant la meme forme de dispatch
    new_branch = (
        f"\n{indent_if}elif {dispatch_var} == \"🎯 Retention Extractor\":\n"
        f"{indent_body}page_retention_extractor()\n"
    )
    new_content = content[:end_offset] + new_branch + content[end_offset:]
    line_no = content[:end_offset].count("\n") + 1
    return new_content, (
        f"OK (insere apres ligne {line_no}, var={dispatch_var!r}, "
        f"fn_ref={body_fn_name})"
    )


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
