# Changelog — Enrichissement SEO LCDMH
**Généré le :** 2026-04-12 13:48

---

## Phase A — Inventaire du site (terminé)
- 138 pages HTML scannées
- 196 vignettes vidéo détectées sur le site
- 675 vidéos dans le CSV master
- 560 vidéos orphelines (sur YouTube mais pas sur le site)

## Phase B — Scraping Google Suggest (terminé)
- 262 vidéos scrapées
- 1 476 suggestions brutes collectées
- Script : `scrape_google_suggest.py` (exécuté sur le PC d'Yves)
- Cache : `Automate_YT/data/scraper/cache/google_suggest/`

## Phase C — Enrichissement des pages existantes (terminé)

### Pages hub enrichies (labels SEO + JSON-LD)
| Page | Cartes enrichies | Type principal |
|------|-----------------|----------------|
| cap-nord-moto.html | 13 | road_trip |
| les-alpes-dans-tous-les-sens.html | 7 | serie |
| espagne-2023.html | 6 | road_trip |
| europe-asie-moto.html | 7 | road_trip |
| alpes-aventure-festival-moto.html | 6 | road_trip |
| securite.html | 3 | pratique |
| **Total** | **42 cartes** | |

### Pages articles enrichies (JSON-LD VideoObject)
| Page | JSON-LD ajoutés |
|------|----------------|
| alpes-cols-mythiques.html | ~47 |
| pneus.html | 1 |
| gps.html | 2 |
| intercoms.html | 2 |
| photo-video.html | 4 |
| tests-motos.html | 8 |
| articles/*.html (26 pages) | ~65 |
| **Total** | **~129 blocs JSON-LD** |

## Phase D — Création des 12 pages hub (terminé)

| # | Page hub | Vidéos | Sections |
|---|----------|--------|----------|
| 1 | roadtrips/road-trip-moto-france.html | 21 | Alpes & Cols |
| 2 | roadtrips/road-trip-norvege-cap-nord.html | 18 | Départ, Arctique |
| 3 | roadtrips/road-trip-espagne-solo.html | 6 | Espagne |
| 4 | roadtrips/road-trip-turquie-cappadoce.html | 8 | Turquie |
| 5 | materiel/tests-gps-moto-2026.html | 13 | GPS |
| 6 | materiel/tests-moto-essais-terrain.html | 21 | Honda, Benelli |
| 7 | materiel/test-materiel-conditions-reelles.html | 10 | GPS, Bivouac |
| 8 | materiel/comparatif-gps-moto.html | 7 | Carpuride, Aoocci |
| 9 | materiel/tests-pneus-moto.html | 4 | Michelin, Dunlop |
| 10 | pratique/securite-routiere.html | 14 | Sécurité |
| 11 | pratique/filmer-en-moto-setup.html | 2 | Caméras |
| 12 | pratique/entretien-equipements-moto.html | 3 | Entretien |
| **Total** | | **127 vidéos** | **17 sections** |

---

## Points d'attention pour la revue

1. **Suggestions parasites** : Quelques suggestions Google non filtrées restent (ex: "motorisation", "moto gp"). À nettoyer manuellement dans les JSON-LD keywords.
2. **Sections uniques** : Certains hubs n'ont qu'une seule section (les vidéos sont groupées car le mapping playlist→section est simple). Yves peut réorganiser.
3. **Descriptions courtes** : Conformément à la règle zéro-invention, les paragraphes sont basés uniquement sur les titres vidéo. Yves peut enrichir avec des faits vérifiés.
4. **Pages dynamiques** : Les pages index.html, articles.html et roadtrips.html utilisent du JavaScript pour charger les cartes — elles ne sont pas traitées ici car les cartes sont générées côté client.
