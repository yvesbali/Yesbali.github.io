# Synthèse — Audit complet du site LCDMH et évolution des pages

Date : 18 avril 2026
Périmètre : toutes les pages HTML du dépôt `LCDMH_GitHub_Audit` hors
`AUDIT_INGENIEUR_SEO/`, `.git/`, `_archive/`, `node_modules/`, `build/`.
Référentiel : section 12.5 du cadrage projet (`LCDMH_Cadrage_Projet.html`).

Trois outils ont été écrits et exécutés :

1. `AUDIT_INGENIEUR_SEO/scripts/validate_seo.py` — validateur SEO 10 points
2. `AUDIT_INGENIEUR_SEO/scripts/track_page_evolution.py` — historique git par page
3. rapports générés : `AUDIT_SITE_20260418.{csv,md}` + `EVOLUTION_PAGES_20260418.{csv,md}`

---

## 1. Vue d'ensemble

**142 pages HTML analysées**, dont 2 snippets exemptés (`nav.html`, `widget-roadtrip-snippet.html`). 140 pages ont donc été passées au crible des 16 contrôles dérivés de la section 12.5 du cadrage.

**Score moyen : 72/100.** Aucune page n'est stagnante : toutes ont été modifiées dans les 46 derniers jours (premier commit du dépôt : 3 mars 2026). Les scripts existants (fetch_youtube, auto_publish, commit_all) maintiennent un flux de modifications très soutenu — en moyenne 25-55 commits par page majeure.

## 2. Top 10 des violations critiques du site (sur 140 pages)

| # | Obligation | Pages KO | % | Priorité |
|---|---|---:|---:|---|
| 1 | **Twitter Card absent** (`twitter:card`, `:title`, `:description`, `:image`) | 106 | 76 % | P1 |
| 2 | **Images sans `width`+`height`** (CLS dégradé) | 46 | 33 % | P1 |
| 3 | **JSON-LD Schema.org manquant ou non standard** | 37 | 26 % | P1 |
| 4 | **Meta description hors fourchette 120-170 c.** | 35 | 25 % | P2 |
| 5 | **OpenGraph incomplet** (og:locale ou og:site_name souvent manquant) | 20 | 14 % | P2 |
| 6 | **Images sans `loading="lazy"`** sous le premier écran | 12 | 9 % | P2 |
| 7 | **Images > 500 KiB** sur disque | 9 | 6 % | P2 |
| 8 | **Canonical absent ou non absolu** | 8 | 6 % | P1 |
| 9 | **Article manquant dans `articles.html` ou `sitemap.xml`** | 8 | 6 % | P1 |
| 10 | **Meta viewport manquant** | 4 | 3 % | P1 |
| 11 | **Plusieurs `<h1>` détectés** | 2 | 1 % | P1 |
| 12 | **URL lcdmh.com parasite dans le HTML** | 1 | 0,7 % | P2 |

## 3. Pages les plus en retard (à traiter en priorité)

Les scores les plus bas (audit `AUDIT_SITE_20260418.md`) :

| Score | KO | Page |
|---:|---:|---|
| 45 | 6 | `LCDMH_Cadrage_Projet.html` (doc interne, `noindex` — score bas attendu) |
| 50 | 7 | `data/articles/dunlop-mutant-vs-bridgestone-t33_facebook_1080x1920.html` |
| 50 | 5 | `data/articles/la-lampe-frontale-parfaite-pour-moto-bivouac-...html` |
| 50 | 4 | `data/articles/350-km-dans-le-froid-norvegien-...html` |
| 50 | 3 | `data/articles/preparation-road-trip-moto-setup-complet-trk-702-...html` |
| 53 | 7 | `_apercu_design_premium/apercu-premium.html` |
| 55 | 5 | `_review/REPORT.html` |

Observation : la majorité des pires scores sont dans `data/articles/` (anciennes versions historiques / brouillons, non publiées sur le site live) ou dans des dossiers d'aperçu (`_apercu_design_premium/`, `_review/`). Les pages live (articles, hubs) sont généralement entre 70 et 87. **Premier chantier naturel : exclure ces dossiers de publication, ou les déplacer sous `_archive/` pour qu'ils cessent de polluer l'audit.**

## 4. Pages les mieux notées (à prendre comme modèles)

| Score | Page |
|---:|---|
| 93 | `roadtrips/securite-routiere-moto.html` |
| 87 | `aoocci.html`, `carpuride.html`, `photo-video.html`, `securite.html` |

Ces pages peuvent servir de template pour normaliser les autres.

## 5. Évolution et maturité

- **0 page stagnante** (seuil 90 jours).
- La page la plus ancienne du dépôt date du 3 mars 2026 (46 jours).
- Le dépôt est dans une phase de construction / consolidation active : les scripts GitHub Actions et d'automatisation touchent régulièrement toutes les pages.
- Conséquence : toute régression SEO non détectée serait très vite diffusée à tout le site. D'où l'intérêt du validateur pré-commit (voir §6).

## 6. Recommandations par ordre de priorité

**P1 — À corriger dans la semaine**

1. **Installer un pre-commit hook** qui appelle `validate_seo.py` sur tout fichier HTML modifié. Bloquer le commit si un point P1 est KO. Côté Windows, un hook `.git/hooks/pre-commit` court, ou l'intégrer dans `commit_all.ps1`.
2. **Twitter Card manquant sur 106 pages** — écrire un patch `add_twitter_cards.py` qui dérive les balises `twitter:*` à partir des `og:*` déjà présents (quand ils le sont). Idempotent.
3. **8 pages sans canonical** — script `add_canonical.py` qui ajoute `<link rel="canonical">` absolu sur chaque page manquante.
4. **H1 multiples (2 pages)** — correction manuelle ciblée.

**P2 — À planifier sur 2-3 semaines**

5. **Images sans `width`/`height`** (46 pages) — script qui parcourt les pages, lit les dimensions réelles des fichiers image via Pillow et injecte les attributs. Améliore directement le CLS.
6. **Meta descriptions 120-170 c.** (35 pages) — passe LLM contrôlée (prompt court, longueur forcée, contrôle idempotent via mesure de la longueur actuelle).
7. **JSON-LD manquant** (37 pages) — majoritairement des pages annexes (hubs, roadbooks). Ajouter `CollectionPage` sur les hubs et `Article` sur les articles restants.
8. **Images > 500 KiB** (9 pages) — passer par `convert_images_webp.py` déjà présent dans le dépôt (cf. Action 07 du journal du 18 avril).

**P3 — Chantiers structurels**

9. Exclure les dossiers `data/articles/`, `_apercu_design_premium/`, `_review/` du pipeline de publication ou les archiver sous `_archive/`.
10. Normaliser tous les générateurs d'`Automate_YT` via un wrapper unique qui appelle `validate_seo.py` avant écriture (cf. audit du 18 avril).

## 7. Commandes utiles

```bash
# Audit unitaire d'une page
python AUDIT_INGENIEUR_SEO/scripts/validate_seo.py articles/aferiy-nano-100-autonomie-electrique-en-road-trip.html

# Audit complet du site (CSV + Markdown)
python AUDIT_INGENIEUR_SEO/scripts/validate_seo.py --audit-site \
  --csv AUDIT_INGENIEUR_SEO/journaux/AUDIT_SITE_YYYYMMDD.csv \
  --md  AUDIT_INGENIEUR_SEO/journaux/AUDIT_SITE_YYYYMMDD.md --quiet

# Historique git de toutes les pages
python AUDIT_INGENIEUR_SEO/scripts/track_page_evolution.py \
  --csv AUDIT_INGENIEUR_SEO/journaux/EVOLUTION_PAGES_YYYYMMDD.csv \
  --md  AUDIT_INGENIEUR_SEO/journaux/EVOLUTION_PAGES_YYYYMMDD.md
```

## 8. Livrables générés ce jour

- `LCDMH_Cadrage_Projet.html` — règles 6, 7, 8 + sections 12 et 13 ajoutées
- `AUDIT_INGENIEUR_SEO/scripts/validate_seo.py` — validateur 10 points
- `AUDIT_INGENIEUR_SEO/scripts/track_page_evolution.py` — tracker git
- `AUDIT_INGENIEUR_SEO/journaux/AUDIT_SITE_20260418.{csv,md}` — 142 pages
- `AUDIT_INGENIEUR_SEO/journaux/EVOLUTION_PAGES_20260418.{csv,md}` — historique
- `AUDIT_INGENIEUR_SEO/journaux/JOURNAL_CHANGEMENTS.md` — entrées 07, 08, 09 ajoutées
- `AUDIT_INGENIEUR_SEO/journaux/SYNTHESE_AUDIT_SITE_20260418.md` — ce document
