# Projet "Optimisation SEO site" — lcdmh.com
> Audit réalisé le 17 avril 2026
> Document Word complet : LCDMH_Optimisation_SEO_Site.docx (à la racine du dépôt)

## Chiffres clés (état au 17/04/2026 — mis à jour)
- ~70 pages HTML publiées (32 racine + 28 articles + 8 roadtrips)
- articles/images/ : ~14.7 Mo (après compression WebP, avant : 104 Mo)
- 8 workflows GitHub Actions actifs
- 8 articles sur 27 encore avec thumbnails YouTube
- 0 page sans og:image (corrigé)

## Actions URGENTES (Semaine 1) ✅ TERMINÉES
- [x] Supprimer .bak, .backup, payloads test → commit ca17578
- [x] Ajouter og:image sur budget-cap-nord → commit ca17578
- [ ] Supprimer les ~60 URLs orphelines du sitemap.xml (roadbooks-html/) ← À VÉRIFIER (sitemap OK mais à reconfirmer)
- [ ] Archiver dossier _review/ → _archive/

## Actions IMPORTANTES (Semaine 2-3)
- [x] Compresser/convertir JPG → WebP (104 Mo → 14.7 Mo, -86%) → commit 8026900
- [x] Remplacer 4 thumbnails YouTube par vraies photos (GPS, Cols Alpes, Honda, Radar) → commit 7e21ce3
- [ ] Remplacer les 8 thumbnails YouTube restants (nécessite photos de Yves)
- [x] Auditer URLs orphelines comparaison_liste_vs_dossier.csv → supprimé du tracking
- [x] Rationaliser workflows GitHub Actions → commit f5cd35d (auto-publish 24x→1x/jour, update_videos/sync_journal/recyclage-social quotidien→3x/semaine)
- [x] Consolider doublons : _review/articles/ (26 fichiers) + data/articles/ (87 fichiers) supprimés → commit 2bb8dcd
- [ ] Vérifier les 476 liens affiliés (pertinence, redirections, ref codes)

## Actions MOYEN TERME (Mois 2-3)
- [ ] Renforcer maillage interne (2-3 liens par article)
- [ ] Schema JSON-LD Article sur les 27 articles
- [ ] Fusionner 9 CSS → 3-4 fichiers max
- [x] Supprimer/archiver scripts PS1, logs, fichiers obsolètes racine (13 fichiers) → commit f5cd35d
- [ ] README.md par dossier principal

## Indicateurs cibles
| Métrique | Avant | Actuel | Cible |
|----------|-------|--------|-------|
| Taille dépôt | 672 Mo | ~550 Mo | < 450 Mo |
| URLs orphelines sitemap | ~60 | 0 (à confirmer) | 0 |
| Articles avec vraies photos | 15/27 | 19/27 | 27/27 |
| Pages sans og:image | 1 | 0 | 0 |
| Poids articles/images/ | 138 Mo | ~14.7 Mo | < 90 Mo ✅ |
| Fichiers tracking doublons | 113 | 0 | 0 ✅ |
| Crons GitHub Actions/semaine | 185+ | ~22 | <30 ✅ |

## Thumbnails YouTube restants (8 articles — photos nécessaires)
Haute priorité :
1. le-cap-nord-ca-va-mal-finir-cercle-arctique-polaire-road-tri.html
2. dunlop-mutant-vs-bridgestone-t33-le-combat-quel-pneu-choisir.html
3. voyager-en-norvege-ferries-budget-conseils-guide-de-voyage-n.html

Moyenne priorité :
4. 350-km-dans-le-froid-norvegien-le-vent-du-groenland-ma-brise.html
5. geirangerfjord-a-moto-le-plus-beau-fjord-de-norvege-road-tri.html
6. alpes-en-moto-barcelonnette-cuneo-benelli-trk-502-ep3.html

Basse priorité :
7. guide-nettoyage-bulle-moto.html
8. t33-vs-road-6.html

## Commits préparés — en attente de git push par Yves
- aa3e49e — fix: restauration renderPage() articles.html (fichier tronqué, grille articles disparue)
- 2bb8dcd — refactor: suppression _review/articles/ (26) + data/articles/ (87 fichiers orphelins)
- f5cd35d — perf: workflows rationalisés + 13 fichiers racine supprimés
> `git push` à lancer depuis F:\LCDMH_GitHub_Audit quand possible

## Publications nouvelles (session 17/04/2026)
- bivouac-moto-quel-equipement.html — design magazine premium, 20 chapitres, 15 photos → commit 3481b3d
  - CSS guide-pratique.css v2 (variables --gp-*, typographie Playfair/Crimson Pro)
  - "Le conseil d'Yves" renommé en "Le conseil LCDMH" (13 occurrences) → commit 4d7e044
  - Hero réduit à 50vh max → commit 69d9ac0
