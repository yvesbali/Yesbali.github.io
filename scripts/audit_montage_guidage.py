#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GARDE-FOU — le moteur de guidage doit rester MONTÉ sur ses 8 pages.

POURQUOI CE CONTRÔLE EXISTE (vécu 13/10/2026) :
Le commit de migration maillage 17fde98c (16/09/2026) a supprimé, sur pneus.html,
gps.html et carpuride.html, le bloc de fin de page (conteneur #lcdmh-guidage + son
script + le conteneur partenaires + le chargement du footer). Personne ne l'a vu
pendant 27 jours : le contrôle mesurait le trafic, pas la présence du dispositif.
Résultat : 3 des 8 pages « équipées » n'ont produit AUCUN clic de guidage pendant
toute la fenêtre de mesure T0+28.

Ce script vérifie l'ÉTAT DU MONTAGE, pas le comportement :
  1. la section #lcdmh-guidage existe
  2. le script /js/lcdmh-guidage.js est appelé
  3. le fichier data/pages/<page>.json existe et contient un bloc « guidage »

Usage :  python3 scripts/audit_montage_guidage.py [--silencieux]
Sortie :  0 = montage complet, 1 = au moins une page démontée.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAGES = {
    "index.html": "index",
    "roadtrips.html": "roadtrips",
    "intercoms.html": "intercoms",
    "equipement.html": "equipement",
    "codes-promo.html": "codes-promo",
    "pneus.html": "pneus",
    "gps.html": "gps",
    "carpuride.html": "carpuride",
}


def controler(silencieux=False):
    problemes = []
    for page, cle in PAGES.items():
        p = ROOT / page
        if not p.exists():
            problemes.append(f"{page} : fichier absent")
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if 'id="lcdmh-guidage"' not in t:
            problemes.append(f"{page} : section #lcdmh-guidage ABSENTE (le guidage ne s'affichera pas)")
        if "lcdmh-guidage.js" not in t:
            problemes.append(f"{page} : script /js/lcdmh-guidage.js NON appelé")
        j = ROOT / "data" / "pages" / f"{cle}.json"
        if not j.exists():
            problemes.append(f"{page} : data/pages/{cle}.json absent")
        else:
            try:
                d = json.loads(j.read_text(encoding="utf-8"))
                if not d.get("guidage"):
                    problemes.append(f"data/pages/{cle}.json : bloc « guidage » vide")
            except Exception as e:
                problemes.append(f"data/pages/{cle}.json : illisible ({e})")

    if problemes:
        if not silencieux:
            print(f"🔴 MONTAGE DU GUIDAGE INCOMPLET — {len(problemes)} problème(s) :")
            for x in problemes:
                print(f"   · {x}")
            print("   → restaurer le bloc de fin de page (voir TOOLS/restaure_guidage_3pages.py)")
        return 1
    if not silencieux:
        print("✅ guidage : les 8 pages sont montées (section + script + JSON)")
    return 0


if __name__ == "__main__":
    sys.exit(controler("--silencieux" in sys.argv))
