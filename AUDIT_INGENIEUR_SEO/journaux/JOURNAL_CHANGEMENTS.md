# JOURNAL DES CHANGEMENTS — AUDIT_INGENIEUR_SEO

Ce journal trace TOUTES les modifications apportees au repo dans le cadre
de l'audit ingenieur & SEO. Chaque bloc decrit : date, action, fichiers
touches, justification, commande de commit suggeree.

Tout est **commit local uniquement** (pas de push automatise), l'utilisateur
valide avant de pousser.

---

## 2026-04-18 (apres-midi) — Action 04 : Enrichissement pages zombies

**Contexte**
- 6 pages zombies recevaient des impressions GSC sans clic. L'utilisateur
  a fourni les VRAIES URLs YouTube de ses tests terrain (pas d'invention).
- Objectif : convertir les impressions en clics grace a des embeds video
  statiques (signal fort pour Google : VideoObject + contenu terrain).

**komobi.html**
- Ajout de 2 iframes YouTube statiques AVANT le feed dynamique :
  - `uI7B5kLR95M` (YouTube Short, ratio 9:16 avec `padding-bottom:177.77%`)
  - `qO7YMCBp-28` (test complet 16:9)
- Nouveau h2 "Test terrain Komobi — videos"
- Feed dynamique `product-feed.js` conserve comme "fallback + nouveautes"

**gps.html**
- Ajout d'une section hero video (fond noir) avec iframe
  `pinxDxAs9jw` (test Aoocci U6 / BX / C6 PRO — GPS offline et autonome)
- Position : juste apres l'intro, avant le comparatif 3 types de GPS
- Ratio 16:9 avec box-shadow pour lisibilite premium

**aferiy.html**
- Remplacement des 2 iframes placeholders (`TMEUulIwbCQ`, `f8tI6Lm0TKs`)
  par les vraies videos de test :
  - `D1eLA6LRkLU` (test terrain bivouac moto)
  - `d-s-wOZKjWI` (presentation / test bureau)
- Titres et captions mis a jour pour refleter le contenu reel

**olight.html**
- Ajout de 2 iframes YouTube statiques AVANT le feed dynamique :
  - `eJtSU-JAdB0` (test lampe frontale Perun 3)
  - `1jWjwR2dMKs` (utilisation bivouac + fixation magnetique)
- Nouveau h2 "Test terrain — Olight Perun 3"
- Feed dynamique conserve comme "Autres videos Olight sur ma chaine"

**intercoms.html**
- **AUCUNE modification** — verification effectuee : la page contient
  deja les bons iframes statiques :
  - Sena 50S : `sZDUr0ewee0`
  - Sena 60S : `PNlKbmWrKjY`
- Title, meta description, comparatif, FAQ deja complets et coherents.

**equipement.html**
- Ajout d'un second bloc JSON-LD `ItemList` (3 items : bagagerie, Olight,
  casque) en plus de l'Article schema existant. Signal "liste curee" pour
  Google, meilleur eligibility au Top Pick SERP.
- Ajout d'ancres `id="bagagerie"` et `id="casque"` sur les product-cards
  pour que les URLs du ItemList pointent vers les bonnes sections.
- `dateModified` mis a jour : 2026-04-18.
- **PAS d'ajout de videos statiques** : l'utilisateur n'a pas fourni
  d'IDs specifiques pour equipement.html ("a toi de voir le mieux"). Je
  n'ai rien invente. Le feed dynamique continue de tirer les bonnes
  videos via keywords : casque, equipement, veste, lampe, bivouac.

**Fichiers touches (5 modifies + 1 verifie)**
- komobi.html, gps.html, aferiy.html, olight.html, equipement.html
- (intercoms.html verifie, inchange)

**Verification post-deploiement**
- Passer chaque page sur https://search.google.com/test/rich-results
  et verifier : Article + ItemList (equipement) OK, VideoObject pas
  encore attendu (il faudra lancer `add_video_object_schema.py` en local
  pour l'ajouter — necessite YT_API_KEY).
- Mesurer sur 30j en GSC : evolution CTR de ces pages. Sweet spot vise :
  0% -> 1-2% CTR sur les memes impressions.

**Commit suggere**

```bash
cd F:\LCDMH_GitHub_Audit
git add komobi.html gps.html aferiy.html olight.html equipement.html
git commit -m "seo(contenu): enrichit pages zombies avec iframes YouTube terrain + ItemList schema equipement"
```

---

## 2026-04-18 — Action 03 : Installation Google Tag Manager

**Contexte**
- L'utilisateur a fourni le conteneur GTM `GTM-MVJK8VFG` (compte LCDMH).
- Objectif : unifier le tracking dans GTM (fini le snippet gtag dupli-
  que / bricole). GA4 (`G-7GC33KPRMS`) sera ensuite configure COMME TAG
  dans GTM, puis on pourra retirer le snippet gtag direct.

**Script**
- `AUDIT_INGENIEUR_SEO/scripts/install_gtm.py` (idempotent, UTF-8, dry-run)

**Ce qui a ete fait**
1. Insertion du snippet **GTM head** (async, non bloquant) juste apres
   `<head>` sur chaque page HTML de la racine et du dossier `articles/`.
2. Insertion du snippet **GTM body** (`<noscript>` fallback) juste apres
   `<body>`.
3. Le snippet gtag `G-7GC33KPRMS` existant est **laisse en place** pour
   que le tracking GA4 reste fonctionnel pendant que tu configures le
   tag GA4 dans GTM. Une fois verifie, on retirera le snippet gtag.

**Fichiers touches (56)**
Racine (25) : `index.html`, `a-propos.html`, `aferiy.html`,
`alpes-aventure-festival-moto.html`, `alpes-cols-mythiques-episode-01.html`,
`alpes-cols-mythiques.html`, `aoocci.html`, `articles.html`, `blackview.html`,
`cap-nord-moto.html`, `carpuride.html`, `codes-promo.html`, `contact.html`,
`dunlop-mutant.html`, `equipement.html`, `espagne-2023.html`,
`europe-asie-moto.html`, `gps.html`, `intercoms.html`, `komobi.html`,
`les-alpes-dans-tous-les-sens.html`, `mentions-legales.html`, `olight.html`,
`photo-video.html`, `pneus.html`, `roadtrips.html`, `securite.html`,
`sitemap.html`, `tests-motos.html`.

Dossier `articles/` (30) : tous les articles *.html ont ete patches (voir
log complet de `install_gtm.py`).

**Ignore (1)**
- `widget-roadtrip-snippet.html` : fragment, pas de balise head/body propre
  → pas de GTM, comportement attendu.

**Verification**
- Apres deploiement, ouvrir la **Tag Assistant Chrome** sur lcdmh.com et
  verifier que le conteneur `GTM-MVJK8VFG` se charge bien.
- Apres config GA4 dans GTM, un event `page_view` doit apparaitre dans
  GA4 Realtime.
- Quand GA4 via GTM est confirme fonctionnel, supprimer le snippet
  `gtag G-7GC33KPRMS` des 56 pages (prochain script).

**Commit suggere**

```bash
cd F:\LCDMH_GitHub_Audit
git add AUDIT_INGENIEUR_SEO/
git add index.html a-propos.html aferiy.html alpes-aventure-festival-moto.html
git add alpes-cols-mythiques-episode-01.html alpes-cols-mythiques.html
git add aoocci.html articles.html blackview.html cap-nord-moto.html
git add carpuride.html codes-promo.html contact.html dunlop-mutant.html
git add equipement.html espagne-2023.html europe-asie-moto.html gps.html
git add intercoms.html komobi.html les-alpes-dans-tous-les-sens.html
git add mentions-legales.html olight.html photo-video.html pneus.html
git add roadtrips.html securite.html sitemap.html tests-motos.html
git add articles/*.html
git commit -m "seo(tracking): installe GTM-MVJK8VFG sur toutes les pages (gtag conserve en transition)"
```

Ou plus simplement, le script `AUDIT_INGENIEUR_SEO/scripts/commit_all.ps1`
(cree a la fin de l'audit) fera tout d'un coup.

---

## 2026-04-18 — Action 02 : rel="sponsored nofollow noopener" + target="_blank"

**Contexte**
- Exigence Google depuis septembre 2020 : tout lien monetise DOIT porter
  `rel="sponsored"`. Nofollow seul n'est plus suffisant aux yeux du
  crawler.

**Script**
- `AUDIT_INGENIEUR_SEO/scripts/add_rel_sponsored.py` (idempotent)

**Domaines cibles** (extraits de `data/partenaires.json` + classiques)
carpuride.com, aoocci.fr, aoocci.com, amazon.fr/dp, amazon.fr/gp,
amazon.com/dp, amzn.to, amzn.eu, olightstore, olightworld, olight-world,
komobi.com, blackview.hk, blackview.com, innovv.com, tidd.ly,
aliexpress.com, s.click.aliexpress, banggood.com, awin1.com, sjv.io.

**Resultat**
- **35 liens affilies** marques sur **10 fichiers** :
  - `codes-promo.html` : 9 liens
  - `pneus.html` : 9 liens
  - `articles/comparatif-carpuride-2026-w702-*.html` : 5
  - `articles/t33-vs-road-6.html` : 4
  - `articles/quel-carpuride-moto-choisir.html` : 3
  - autres : 1 lien chacun

**Note**
- Les pages produit `aoocci.html`, `carpuride.html`, `komobi.html`,
  `olight.html` avaient deja rel="sponsored noopener" (heritage des
  scripts existants).

---

## 2026-04-18 — Action 08 : Organization schema (homepage)

**Contexte**
- Pour activer un Knowledge Panel LCDMH dans Google, il faut declarer
  explicitement l'`Organization` avec logo et `sameAs` (profils verifies).

**Fichier touche**
- `index.html` uniquement (Organization declaree UNE fois, referencee
  par `@id` partout ailleurs via `publisher`).

**sameAs ajoutes**
- https://www.youtube.com/@LCDMH
- https://www.facebook.com/profile.php?id=61582712395640
- https://www.tiktok.com/@lcdmh74
- https://fr.tipeee.com/lcdmh

Logo : `/apple-touch-icon.png` (512x512)
areaServed : FR, BE, CH, CA, LU
knowsLanguage : fr-FR
founder : Yves → /a-propos.html

**Verification recommandee**
- https://validator.schema.org/ apres deploiement
- Resultat attendu : Organization + WebSite, aucun warning sur sameAs

---

## 2026-04-18 — Action 05 : sitemap + noindex pages test/maquette

**Probleme detecte**
- Le commentaire en tete du `sitemap.xml` indiquait que les pages
  `road-trip-moto-test-2026-3*.html` etaient supprimees, mais elles
  etaient en realite toujours presentes dans le sitemap.
- `LCDMH_Cadrage_Projet.html` et `maquette_capnord_complete_v2.html`
  etaient dans `robots.txt Disallow:` SANS meta noindex (Google peut
  indexer malgre Disallow si backlinks externes).

**Fichiers modifies**
- `sitemap.xml` : retrait des 2 URLs test
- `roadtrips/road-trip-moto-test-2026-3.html` : meta noindex
- `roadtrips/road-trip-moto-test-2026-3-journal.html` : meta noindex
- `roadtrips/maquette_capnord_complete_v2.html` : meta noindex
- `LCDMH_Cadrage_Projet.html` : meta noindex

**Script**
- `AUDIT_INGENIEUR_SEO/scripts/add_noindex_tests.py` (idempotent)

---

## 2026-04-18 — Livrables prepares (execution differee)

### Action 06 : VideoObject schema

- Script pret : `AUDIT_INGENIEUR_SEO/scripts/add_video_object_schema.py`
- Inventaire : **39 pages** avec embed YouTube, dont **34 sans VideoObject**
- ~55 videos uniques a enrichir
- Execution differee (necessite YT_API_KEY, voir CLARIFICATIONS)

### Action 07 : Conversion WebP

- Script pret : `AUDIT_INGENIEUR_SEO/scripts/convert_images_webp.py`
- Requiert : `pip install Pillow`
- Non destructif : WebP cree a cote des originaux
- Genere CSV `AUDIT_INGENIEUR_SEO/journaux/conversions_webp.csv`

### Actions bloquees sur donnees utilisateur

- Action 01 : rebuild `/carpuride.html` → video hero + AggregateRating
  + images terrain (voir CLARIFICATIONS_UTILISATEUR.md §1)
- Action 04 : pages zombies → reconstruire OU rediriger 301 (§2)
- Action 09 : 4 pages pilliers francophonie (§3)
- Action 10 : workflow SEO continu → choix webhook alerte (§4)

---

## Etat global du repo (fin de session 2026-04-18 matin)

- **Fichiers HTML modifies** : 56 (GTM) + 10 (rel=sponsored) + 1
  (Organization sur index.html) + 4 (noindex) + 1 (sitemap.xml)
- **Scripts crees** : 4 Python + 1 PowerShell
- **Documents crees** : JOURNAL_CHANGEMENTS.md, CLARIFICATIONS_UTILISATEUR.md
- **Commits attendus** : 5 commits granulaires (via commit_all.ps1)
- **Push** : NON (pas de push, sur demande)

**Prochaines etapes utilisateur**
1. Relire ce journal
2. Lancer `powershell -ExecutionPolicy Bypass -File AUDIT_INGENIEUR_SEO\commit_all.ps1`
3. Repondre a CLARIFICATIONS_UTILISATEUR.md
4. Configurer GA4 dans GTM (Google Tag, Measurement ID G-7GC33KPRMS)
5. Verifier Tag Assistant Chrome sur lcdmh.com
