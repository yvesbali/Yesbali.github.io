#!/usr/bin/env python3
"""Genere des liens de partage avec un code de canal, pour /v/<video>.html?c=CODE.

Le code de base identifie la personne (ex. e68aqq). On y ajoute un suffixe de canal
pour savoir OU le lien a ete diffuse : e68aqq-fb, e68aqq-wa, e68aqq-ig...
La page /v/ accepte les tirets et enregistre le code + la plateforme detectee.

Usage:
  python3 scripts/generer_liens_partage.py e68aqq -n2dfOgClTM
  python3 scripts/generer_liens_partage.py e68aqq -n2dfOgClTM --canaux fb,wa
"""
import argparse, sys

BASE = "https://lcdmh.com/v/{video}.html?c={code}"
CANAUX = {
    "fb": "Facebook",
    "wa": "WhatsApp",
    "ig": "Instagram",
    "tt": "TikTok",
    "tg": "Telegram",
    "li": "LinkedIn",
    "x": "X / Twitter",
    "yt": "YouTube (commentaire)",
    "sm": "SMS",
    "em": "e-mail",
    "bl": "blog / site",
}


def lien(video, code):
    return BASE.format(video=video, code=code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code", help="code de base de la personne (ex. e68aqq)")
    ap.add_argument("video", nargs="?", help="identifiant YouTube (ex. -n2dfOgClTM)")
    ap.add_argument("--video", dest="video_opt", help="identifiant YouTube (variante avec tiret initial)")
    ap.add_argument("--canaux", default="fb,wa,ig,tt,tg,x",
                    help="liste separee par des virgules (defaut: fb,wa,ig,tt,tg,x)")
    a = ap.parse_args()
    a.video = a.video_opt or a.video
    if not a.video:
        ap.error("identifiant video manquant (positionnel ou --video)")
    code = a.code.strip().lower()
    if not all(c.isalnum() or c == "-" for c in code):
        sys.exit("code invalide : lettres/chiffres/tirets uniquement")
    print(f"Code de base : {code}\nVideo        : {a.video}\n")
    for c in [x.strip().lower() for x in a.canaux.split(",") if x.strip()]:
        nom = CANAUX.get(c, c)
        print(f"{nom:22s} {lien(a.video, f'{code}-{c}')}")
    print(f"\nLien sans canal      {lien(a.video, code)}")


if __name__ == "__main__":
    main()
