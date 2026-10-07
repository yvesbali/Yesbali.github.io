#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AUDIT DE COHÉRENCE D'UN ARTICLE — attraper les contradictions internes.

Pourquoi ce script existe (07/10/2026, question d'Yves : « comment tu publies une phrase
où tu dis qu'on n'a pas les prix et plus loin tu annonces les prix ? ») :

  06/10 00:13 -> l'article est écrit : « je n'ai pas de tarif vérifié, donc je ne l'invente pas »
                 C'est VRAI à cette seconde : les prix n'ont pas encore été cherchés.
  06/10 00:21 -> 8 minutes plus tard, une section « Les prix » est ajoutée : 499,90 €, 474,90 €,
                 revendeurs, relevé daté.
                 MAIS la phrase de 00:13 n'est pas retirée.
  06/10 10:40 -> l'article est publié. Les contrôles vérifient robots/sitemap/menu : tous verts.
                 Aucun ne regarde si l'article se contredit lui-même.
  07/10 20:30 -> la contradiction est découverte puis corrigée.

Cause racine : je modifie un article morceau par morceau, et chaque morceau est vérifié
isolément. Personne ne relit l'ensemble. Ce script comble ce trou : il cherche les
affirmations d'un article qui en contredisent une autre du même article.

Usage : python3 audit_coherence_article.py <fichier.html> [<fichier.html> ...]
Sortie : les contradictions trouvées ; code de retour 1 si au moins une.
"""
import re
import sys


def texte_lignes(chemin):
    """Le texte visible, ligne par ligne (les balises retirées, le JSON-LD ignoré)."""
    html = open(chemin, encoding="utf-8").read()
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    lignes = []
    for i, l in enumerate(html.split("\n"), 1):
        t = re.sub(r"<[^>]+>", " ", l)
        t = t.replace("&nbsp;", " ").replace("&euro;", "€").replace("&#8364;", "€")
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            lignes.append((i, t))
    return html, lignes


# Ce qu'on cherche : une phrase qui NIE une information, en face de chiffres qui l'AFFIRMENT.
NEGATIONS = {
    "prix": [
        r"je n'ai pas de tarif", r"pas de tarif", r"aucun tarif", r"pas de prix",
        r"sans prix", r"je n'ai pas de prix", r"pas de tarif v[ée]rifi[ée]",
        r"je ne l'invente pas", r"je n'invente pas", r"prix non communiqu[ée]",
        r"on ne conna[îi]t pas (le|les) prix",
    ],
    "kilometrage": [
        r"pas de kilom[èe]trage", r"je n'ai pas de kilom[èe]trage",
        r"aucun kilom[èe]trage", r"pas de distance", r"je n'ai pas (de|la) distance",
    ],
}

# Un mot du thème doit être présent dans la MÊME phrase que la négation, sinon on attrape des
# tournures innocentes. Vécu le 07/10/2026 : « Pas de poids en hauteur » (une règle de rangement
# des sacoches) a été signalé comme un démenti sur le poids — faux positif. Un détecteur qui
# crie à tort ne sert à rien : on exige le contexte.
CONTEXTE = {
    "prix": r"prix|tarif|€|euro|co[ûu]te|revient|budget|pay[ée]|achet[ée]|facture",
    "kilometrage": r"km\b|kilom[èe]tre|distance|parcouru|roul[ée]",
}

# Ce qui, présent ailleurs dans la page, contredit la négation.
AFFIRMATIONS = {
    "prix": [r"\d[\d\s\u202f]*[,.]\d{2}\s*(?:€|EUR)", r"\d+\s*(?:€|EUR)\b", r"prix (?:public )?conseill[ée]"],
    "kilometrage": [r"\d[\d\s\u202f]*\s*km\b"],
    "poids": [r"\d[\d\s\u202f]*\s*(?:g|grammes|kg)\b"],
    "date": [r"\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{4}"],
}


def audit(chemin):
    """Retourne la liste des contradictions trouvées dans le fichier."""
    html, lignes = texte_lignes(chemin)
    bas = html.lower()
    trouves = []
    for theme, motifs_neg in NEGATIONS.items():
        # les négations, avec leur ligne
        negatives = []
        for i, t in lignes:
            tl = t.lower()
            if not re.search(CONTEXTE[theme], tl):
                continue          # négation sans le vocabulaire du thème → tournure innocente
            for m in motifs_neg:
                if re.search(m, tl):
                    negatives.append((i, t))
                    break
        if not negatives:
            continue
        # les affirmations du même thème, ailleurs dans la page
        affirmations = []
        for i, t in lignes:
            for m in AFFIRMATIONS[theme]:
                if re.search(m, t, re.I):
                    affirmations.append((i, t))
                    break
        if affirmations:
            trouves.append({"theme": theme, "negations": negatives, "affirmations": affirmations})
    return trouves


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    total = 0
    for chemin in argv:
        res = audit(chemin)
        print("═══ %s ═══" % chemin)
        if not res:
            print("  ✅ aucune contradiction interne détectée")
            continue
        total += len(res)
        for r in res:
            print("\n  🔴 CONTRADICTION — thème « %s »" % r["theme"])
            print("     la page NIE :")
            for i, t in r["negations"]:
                print("       ligne %-4d « %s »" % (i, t[:118]))
            print("     et AFFIRME ailleurs :")
            for i, t in r["affirmations"][:4]:
                print("       ligne %-4d « %s »" % (i, t[:118]))
            print("     → un lecteur qui tombe sur la première phrase doutera de tout l'article.")
    if total:
        print("\n  RÉSULTAT : %d contradiction(s) — à corriger avant publication." % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
