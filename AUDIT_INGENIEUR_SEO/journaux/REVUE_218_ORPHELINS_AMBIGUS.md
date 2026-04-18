# Revue catégorisée des 218 orphelins ambigus

Date : 2026-04-18
Source : `dedup_ambiguous_orphans.txt` (218 chemins, ~88 MiB total sur disque)
Objectif : décider en lot plutôt qu'image par image ce qu'on supprime, ce qu'on insère, ce qu'on archive.

Rappel : un orphelin « ambigu » est un fichier image présent sur disque mais non référencé par aucune page HTML, ET sans équivalent référencé ailleurs (contrairement aux 75 `safe_orphans` déjà supprimés au commit `d5d0c84`).

## Répartition par catégorie

| Catégorie | Nb fichiers | Poids | Décision recommandée |
|---|---:|---:|---|
| orphan_article (articles sans image locale) | 100 | 32 MiB | INSÉRER ou SUPPRIMER |
| normal (candidats légitimes) | 55 | 37 MiB | REVUE MANUELLE |
| special_chars (noms avec accents/espaces/+) | 28 | 15 MiB | SUPPRIMER |
| blog_generated (fichiers CDN auto) | 26 | 2 MiB | SUPPRIMER |
| shopify_variants (tailles inutilisées) | 9 | 0,3 MiB | SUPPRIMER |
| **Total** | **218** | **≈88 MiB** | |

## Catégorie 1 — orphan_article (100 fichiers, 32 MiB)

Les articles `retour-honda-nt-1100-a-26000-kms.html` (331 lignes) et `cols-mythiques-des-alpes-a-moto-trk-502-ep-1.html` (439 lignes) contiennent une vidéo YouTube chacun mais **aucune image locale** (0 `<img src>` dans leur HTML).

Leurs dossiers `/articles/images/` contiennent respectivement 76 et 76 fichiers (photos authentiques + variantes WebP). Un duo JPG+WEBP par photo = ~38 photos distinctes par article, jamais insérées.

### Option A — Les insérer dans l'article (recommandé SEO)
Un article de voyage sans image, c'est faible pour le SEO (Discover, temps de lecture, partage). Le patch `patch_picture_tags.py` prendra ensuite en charge l'emballage `<picture>`.

### Option B — Les supprimer si tu as décidé de laisser ces deux articles en "vidéo only"
Économise ~32 MiB repo + bande passante.

**À décider par toi** : tu veux enrichir ces deux articles avec 5–8 photos chacun, ou tu les laisses en format vidéo ?

## Catégorie 2 — normal (55 fichiers, 37 MiB)

Concentration : `radar-moto-comment-ca-marche/` (16 fichiers) et `bivouac-moto-comment-bien-dormir-en-tente-test-nemo-sonic-0/` (6 fichiers dont le plus gros du lot).

### Top poids inspectés

- `bivouac/NEMO_Camping-DSC_0386.jpg` : **22 MiB** — photo promotionnelle NEMO brute, jamais insérée. À compresser + insérer OU supprimer (22 MiB pour une image, c'est un scandale perf).
- `radar-moto/Plan-de-travail-1.png` : 1,4 MiB — schéma.
- `radar-moto/v2.png` : 1,3 MiB — schéma.
- `radar-moto/2026-03-23_*.jpg` : 3 captures d'écran (~3 MiB total).

### Recommandation

Parcourir les 16 du dossier `radar-moto` — ce sont potentiellement des illustrations intéressantes (schémas, captures) que l'article mérite. Les 6 du dossier `bivouac` contiennent la photo NEMO 22 MiB à décider impérativement (insérer compressé OU dégager).

## Catégorie 3 — special_chars (28 fichiers, 15 MiB)

Noms contenant espaces, accents, ou suffixe `+` / `++` :

- `Lampe Olight +.webp`, `Lampe frontale +.webp`, `Lampre éclairage rouge +.webp` (typo "Lampre")
- `Pub évolution de la marque sur 18 ans +.jpg` et son clone sans accent
- `Visuel lampe avec echelle de grandeur.webp` et son clone `echaelle` (typo)
- `Système-d'élevage-pour-approvisionner-en-nourriture.*`

Analyse : ce sont des uploads manuels avec typos/doublons accent-sans-accent. Aucune référence HTML (les pages utilisent des noms sans accent).

**Décision recommandée : SUPPRIMER les 28.** Zéro risque, gain 15 MiB.

## Catégorie 4 — blog_generated (26 fichiers, 2 MiB)

Noms auto-générés par des CDN de blog (Adobe AEM, Shopify auto, etc.) :

- `cq5dam.web.800.800_*.jpg` (Adobe AEM DAM — 8 variantes × 3 = 24)
- `ben-homepage-mobil-promo-trk702-fr.*` (Benelli)
- `maxresdefault_4.jpg` (YouTube thumbnail)

Ce sont des captures automatiques téléchargées depuis les CDN constructeurs, jamais référencées chez nous. **Décision recommandée : SUPPRIMER les 26.** Gain 2 MiB.

## Catégorie 5 — shopify_variants (9 fichiers, 0,3 MiB)

Variantes de taille Shopify inutilisées après la conversion WebP :

- `AFERIY_AF-SL30_Panneau_Solaire_Portable_30W_3_1170x.{jpg,webp}`
- `05_S22_Sonic_0_34-Head-GillsClosed_900x.webp`
- `roussanou980x613.webp`

Ces noms proviennent du CDN Shopify (format `_XXXXx`). La conversion WebP a créé des variantes, mais seul un format est utilisé dans l'HTML. **Décision recommandée : SUPPRIMER les 9.**

## Plan d'action proposé

1. **SUPPRIMER immédiatement (63 fichiers, ~17 MiB)** : categ 3 + 4 + 5. Zéro risque, gain net.
2. **STATUER sur la photo NEMO 22 MiB** : insérer compressée (≤ 500 Ko) dans l'article bivouac, ou supprimer.
3. **DÉCIDER sur les 2 articles sans image** (Honda NT 1100 retour + Cols des Alpes ep.1) :
   - Si enrichir : sélectionner 5–8 photos par article, insérer via `<picture>`, supprimer les autres.
   - Si laisser vidéo-only : supprimer les 100 fichiers.
4. **REVUE MANUELLE des 55 « normal »** : parcourir dossier par dossier (surtout `radar-moto/` 16 fichiers).

Si tu me valides la catégorie 3+4+5 (63 fichiers, 17 MiB de gain sans risque), je peux écrire le script de suppression + commit dédié, de la même façon que pour les 75 safe orphans (commit `d5d0c84`).

## Annexe — Fichiers de référence

- `dedup_categorized.json` : catégorisation brute pour scripts futurs
- `dedup_ambiguous_orphans.txt` : liste source (218 chemins)
- `dedup_safe_orphans.txt` : 75 orphelins déjà supprimés (pour mémoire)
