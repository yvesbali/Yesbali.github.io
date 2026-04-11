# CADRAGE LCDMH — Standards techniques & éditoriaux

Document de référence pour toute nouvelle page, article ou roadbook publié sur lcdmh.com.
Dernière mise à jour : 11 avril 2026

Ce fichier sert de source unique de vérité pour :

1. la vision et l'architecture du projet
2. les exigences SEO obligatoires pour chaque page
3. les leçons tirées des audits externes (vraies erreurs vs fausses alertes)
4. les checklists de validation avant publication

---

## 1. Vision et architecture

### Objectif du système

Automatiser la production, la publication et la diffusion de contenu motard : articles SEO, vidéos YouTube, posts réseaux sociaux (via Make.com), roadbooks automatisés. Principe fondateur : **GitHub est la source unique du site en production**.

### Deux environnements distincts

Site de production — `F:\LCDMH_GitHub_Audit\` — contient HTML/CSS/JS, articles, roadtrips, workflows GitHub. Tout push sur la branche principale = publication immédiate via GitHub Pages.

Automatisation locale — `F:\Automate_YT\` — contient Streamlit, scripts de génération de contenu, SEO dashboard, publication auto, fetch YouTube, SEO tracker. C'est le cerveau du système.

### Point critique

Le projet est fortement dépendant de l'automatisation. Toute erreur dans un script se propage au contenu produit et publié. Le contrôle qualité humain reste indispensable tant que la validation automatique n'est pas en place.

---

## 2. Règles absolues (non négociables)

**Règle 1 — Encodage.** Ne jamais utiliser PowerShell pour modifier du HTML. Problèmes récurrents d'encodage UTF-8. Utiliser Python, VS Code, ou les outils dédiés.

**Règle 2 — Aucune invention.** Ne jamais inventer de données, liens, coordonnées GPS, noms de lieux, ou prix. En cas de doute, laisser une formulation neutre ou demander confirmation.

**Règle 3 — Pipeline de publication.** La publication suit toujours cet ordre :

```
git stash
git pull --rebase
copie HTML dans le dossier cible
update articles.html (ajout dans ARTICLES[])
git add [fichiers spécifiques]
git commit
git push
```

**Règle 4 — Tout article doit être référencé dans articles.html.** Un article qui existe physiquement mais n'est pas listé dans `ARTICLES[]` de articles.html est invisible pour Google et pour les visiteurs.

**Règle 5 — Partenaires centralisés.** Jamais de lien d'affiliation en dur dans un article. Toujours passer par `partenaires.json` pour maintenir la cohérence et faciliter la maintenance.

---

## 3. Standards SEO obligatoires pour chaque nouvelle page

Ces standards sont vérifiés lors de chaque audit. Toute nouvelle page doit respecter la totalité de cette checklist avant publication.

### 3.1. Balises techniques obligatoires dans le `<head>`

Déclaration de langue sur la balise html :

```html
<html lang="fr">
```

Meta description comprise entre 120 et 170 caractères, unique, contenant le mot-clé principal et une proposition de valeur :

```html
<meta name="description" content="Test AFERIY Nano 100 : batterie camping moto 99,2 Wh, USB-C 100W, acceptée en cabine avion. Testée sur 5 000 km de road trip en bivouac. Avis terrain honnête.">
```

Title inférieur à 65 caractères, avec marque en suffixe :

```html
<title>Test AFERIY Nano 100 : batterie moto 99 Wh USB-C | LCDMH</title>
```

Canonical URL absolue :

```html
<link rel="canonical" href="https://lcdmh.com/articles/nom-article.html">
```

Balises OpenGraph complètes (og:title, og:description, og:image, og:url, og:type).

### 3.2. Données structurées Schema.org

Tout article doit inclure un bloc JSON-LD de type Article avec headline, description, image, author (Yves), publisher (LCDMH), mainEntityOfPage et inLanguage fr-FR. Les pages de catégorie utilisent CollectionPage. Les pages principales incluent un BreadcrumbList.

Template Article :

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "...",
  "description": "...",
  "image": "https://lcdmh.com/images/...",
  "author": {
    "@type": "Person",
    "name": "Yves",
    "url": "https://lcdmh.com/a-propos.html"
  },
  "publisher": {
    "@type": "Organization",
    "name": "LCDMH — Le Coin Des Motards Heureux",
    "logo": {
      "@type": "ImageObject",
      "url": "https://lcdmh.com/images/og-lcdmh.jpg"
    }
  },
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "https://lcdmh.com/articles/..."
  },
  "inLanguage": "fr-FR"
}
```

### 3.3. Structure Hn

Un seul H1 par page. Pas de deuxième H1, même dans un bloc secondaire. Hiérarchie respectée H1 → H2 → H3 sans saut. Le H1 doit correspondre au sujet principal et contenir le mot-clé.

### 3.4. Images

Toute image doit avoir un attribut alt descriptif. Pour les miniatures YouTube, un alt générique du type `Miniature vidéo [sujet] - LCDMH` est acceptable. Pour les photos, décrire le contenu réel. Ajouter `loading="lazy"` sur les images sous le premier écran pour améliorer le LCP.

### 3.5. Maillage interne

Chaque article doit contenir au moins trois liens internes vers d'autres pages pertinentes du site. Les pages hub (articles.html, gps.html, pneus.html, etc.) doivent linker vers leurs articles de détail.

### 3.6. Contenu minimum

Aucune page publiée ne doit être vide ou quasi vide. Minimum recommandé : 200 mots pour une page hub, 500 mots pour un article, 100 mots de récit en plus des données techniques pour une page roadbook journalière.

---

## 4. Pages spécifiques : templates et contraintes

### 4.1. Page roadbook journalière

Toute page `/roadbooks-html/.../jour-XX.html` doit contenir en plus des données techniques (distance, temps, coordonnées GPS, prix) :

- un paragraphe narratif d'au moins 100 mots (météo, état d'esprit, difficulté rencontrée, souvenir marquant)
- une photo avec alt descriptif
- un lien vers la page principale du road trip
- un lien vers le jour précédent et le jour suivant
- meta description unique adaptée au jour

Le bloc `Micro non supporté par ce navigateur` est une fallback JavaScript légitime affichée quand l'API Web Speech Recognition n'est pas disponible. Ce n'est pas une erreur technique. Cependant, pour éviter que Googlebot l'indexe comme contenu principal, il est recommandé d'envelopper ce message dans une balise `<noscript>` ou de l'afficher uniquement côté client via `display:none` par défaut.

### 4.2. Page hub (articles.html, gps.html, pneus.html, etc.)

Doit contenir une introduction éditoriale de 150 à 300 mots qui explique le thème, le contexte d'expérience (par exemple après combien de km testé), et ce que le lecteur va trouver dans la liste. Ensuite seulement vient le listing ou la grille d'articles.

### 4.3. Article test produit

Structure recommandée : introduction (contexte, qui je suis, pourquoi ce test) → présentation du produit → retour terrain après X km → points positifs → points négatifs → tableau comparatif si pertinent → verdict → FAQ → avis communauté → maillage interne.

---

## 5. Checklist de validation avant publication

Avant tout push vers GitHub Pages, vérifier ces dix points sur la nouvelle page :

1. balise `<html lang="fr">` présente
2. `<title>` inférieur à 65 caractères
3. `<meta name="description">` entre 120 et 170 caractères, unique
4. `<link rel="canonical">` absolu et correct
5. un seul `<h1>` contenant le mot-clé principal
6. toutes les images ont un attribut alt non vide
7. Schema.org Article (ou CollectionPage) présent en JSON-LD
8. minimum 3 liens internes vers d'autres pages du site
9. l'article est ajouté dans `ARTICLES[]` de articles.html
10. l'article est ajouté dans le sitemap.xml avec une date récente

---

## 6. Leçons apprises — fausses alertes récurrentes des audits externes

Les audits externes (cinq reçus pendant cette session) se sont révélés peu fiables pour plusieurs raisons. Les fausses alertes suivantes reviennent systématiquement :

**Fausse alerte 1 — Meta-description ABSENTE.** Ce diagnostic a été posé sur quasiment toutes les pages auditées. Après vérification dans le code, la très grande majorité avait bien une meta description valide de 120 à 170 caractères. Cause probable : l'auditeur regarde le HTML rendu après JavaScript dans un navigateur, ce qui peut ne pas inclure le `<head>`. Toujours vérifier dans le code source brut.

**Fausse alerte 2 — Page 404.** `contact.html` a été signalée comme inexistante. Vérification directe dans le filesystem : elle existe, taille normale, meta description 155 caractères. Cause probable : erreur ponctuelle de cache CDN.

**Fausse alerte 3 — lang="fr" non déclaré.** Vérification : seuls `nav.html` et `widget-roadtrip-snippet.html` n'ont pas la balise, mais ce sont des snippets inclus dans d'autres pages et ils ne doivent PAS l'avoir. Toutes les pages principales déclarent bien `lang="fr"`.

**Fausse alerte 4 — Tableau comparatif inversé.** Il faut **toujours** vérifier les chiffres contre le texte de l'article. Un audit externe a bien identifié un tableau Dunlop Mutant vs T33 où la longévité était inversée, mais d'autres signalements de ce type se sont révélés faux.

**Fausse alerte 5 — Aucune balise alt.** Vérification globale : 87 % des images ont un alt. Les 13 % manquants étaient concentrés sur 3 pages (alpes-aventure-festival-moto, espagne-2023, gps.html) pour les miniatures YouTube. Tous corrigés.

**Fausse alerte 6 — Micro non supporté = erreur.** Ce message est une fallback JavaScript légitime qui ne s'affiche qu'aux navigateurs sans Web Speech API.

**Fausse alerte 7 — Vouvoiement incohérent.** Les audits ont parfois reproché un mélange tu/vous. Vérification : le site tutoie systématiquement. C'est la ligne éditoriale, pas une incohérence.

---

## 7. Vraies erreurs récurrentes détectées par les audits

Les audits externes restent utiles pour identifier ces problèmes réels :

**Transcriptions orales non relues.** Les articles générés à partir des sous-titres YouTube contiennent parfois des erreurs phonétiques sur les noms propres et applications. Exemples corrigés : « Magic Hort » au lieu de Magic Earth, « Golard Gels Vegan » au lieu de Gamle Strynefjellsvegen, « bibouquer » au lieu de bivouaquer.

**Noms de produits incohérents.** Le même produit apparaît sous plusieurs noms dans le même article. Exemples corrigés : Blackview X1 / Blackview Xplore X1 / Blackview BV8800 Pro / Blackview XLOR X1 mélangés sur une même page. Règle : un produit, un nom unique, cohérent dans titre, H1, meta, OG et texte.

**Titres et H1 cut-off.** Exemple : « Quel téléphone pour road trip ? Blackview X1 renforcé (pluie, chocs, froid)**Blackview X1 :**» — clairement un copier-coller non terminé. À vérifier systématiquement.

**Backticks Markdown résiduels.** Les articles générés par LLM peuvent conserver des fences ` ```html ` et ` ``` ` visibles dans le texte final. À supprimer.

**Accents manquants dans les titres éditoriaux.** « Budget Cap Nord a moto seul : 10 000 km, couts » au lieu de « à moto seul, coûts ». Fréquent quand le titre provient d'un slug URL non accentué.

**Tableaux de comparaison avec données contradictoires avec le texte.** Toujours relire le texte et le tableau ensemble avant publication.

**Duplication de contenu.** Deux pages racontent le même road trip (les-alpes-dans-tous-les-sens.html et alpes-aventure-festival-moto.html). À consolider avec un canonical ou à différencier éditorialement.

---

## 8. Faiblesses structurelles identifiées

**SEO non automatisé.** Pas de validation automatique à la génération de l'article. Un pre-commit hook ou un workflow GitHub Action qui vérifie la checklist section 5 serait une priorité.

**fetch_youtube.py cassé.** Perte de données vidéo et mise à jour de contenu. À corriger en priorité.

**Dépendance nav-loader.js.** Toute page qui n'intègre pas nav-loader.js affiche une navigation cassée. À vérifier systématiquement.

**Risque Git.** Des fichiers ont déjà été non trackés par git après génération, rendant les articles invisibles en ligne. La fonction `publish_to_github()` doit explicitement vérifier que les fichiers ajoutés apparaissent bien dans le push.

**Pas de contrôle qualité automatique.** C'est la couche manquante la plus critique. Un script qui parcourt tous les fichiers HTML avant push et vérifie les points de la checklist section 5 sécuriserait l'ensemble du pipeline.

---

## 9. Recommandations d'amélioration priorisées

### Priorité 1 — Urgente

Créer un script `validate_seo.py` qui parcourt tous les HTML modifiés avant commit et vérifie les dix points de la checklist section 5. Le script doit bloquer le push si un point critique manque.

Corriger `fetch_youtube.py` pour restaurer la mise à jour automatique des données vidéo.

Sécuriser `publish_to_github()` en vérifiant explicitement que les fichiers modifiés sont bien trackés par git avant le push.

### Priorité 2 — Importante

Ajouter un générateur automatique de meta-description à partir du contenu de l'article (premier paragraphe tronqué à 155 caractères, ou génération via LLM avec prompt contrôlé).

Ajouter un générateur automatique d'alt pour les images, basé sur le nom du fichier et le contexte du paragraphe.

Mettre en place un sitemap.xml auto-généré à chaque push, avec les dates réelles de modification des fichiers.

Enrichir les pages roadbook journalières avec un bloc narratif (min. 100 mots) et envelopper le message « Micro non supporté » dans une balise `<noscript>`.

### Priorité 3 — Optimisation

Consolider la duplication Alpes 2022 (canonical ou différenciation éditoriale).

Enrichir les pages hubs (articles.html, gps.html, photo-video.html) avec des introductions éditoriales de 200 à 300 mots.

Ajouter un flux RSS pour la découverte des nouveaux articles.

Uniformiser les noms de produits dans tout le site via un dictionnaire central (partenaires.json étendu).

---

## 10. Historique de la session d'audit

Cette session a traité cinq audits externes successifs couvrant environ 50 pages du site. Bilan :

Environ 30 corrections réelles appliquées sur 40+ fichiers HTML : meta descriptions ajoutées, titres raccourcis, descriptions raccourcies, H1 multiples corrigés, Schema.org Article ajouté à 21 articles, CollectionPage sur articles.html, orthographe (sacoche, emporter, à moto, coûts, imprévus, Magic Earth, Gamle Strynefjellsvegen, Xplore X1), tableau Mutant/T33 corrigé, accents gps.html, H1 Perun 3, backticks parasites, alt sur 28 images YouTube.

Environ 25 fausses alertes rejetées après vérification directe dans le code (meta descriptions absentes, contact 404, lang="fr" absent, Micro non supporté, vouvoiement, titres déjà corrigés).

Leçon principale : **toujours vérifier les audits externes dans le code source brut** avant d'appliquer une correction. Un audit externe est utile comme filet de détection mais ne doit jamais être appliqué aveuglément.

---

## 11. Règles d'infographie et proportions visuelles

Ces règles s'appliquent à toutes les pages utilisant des grilles de cartes produit (photo-video.html, gps.html, pneus.html, intercoms.html, équipement, hubs partenaires, etc.).

### 11.1. Hauteur fixe obligatoire pour les vignettes produit

Toutes les vignettes (`.card-header` ou équivalent) d'une même grille doivent avoir une hauteur **fixe et identique**. Jamais de `min-height` exprimé en `vh`, qui produit des vignettes de 500 à 700 pixels avec d'immenses vides autour d'une photo ou d'un emoji.

Règle : `height: 260px;` recommandé, ou toute valeur en `px` cohérente dans la grille. Ne pas utiliser `min-height` sur un conteneur de vignette produit.

```css
.card-header {
  height: 260px;          /* hauteur fixe, jamais vh */
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
}
.card-header img {
  width: 100%;
  height: 100%;
  object-fit: cover;      /* l'image remplit le cadre sans déformation */
  display: block;
}
```

### 11.2. Variante emoji-only pour les cartes sans visuel réel

Quand une carte produit n'a pas encore de photo réelle (on affiche uniquement un emoji 🚁 📸 🏔️), utiliser une classe supplémentaire `emoji-only` pour :

1. afficher un fond plus contrasté (gradient orange clair)
2. agrandir l'emoji (`font-size: 8rem`) pour qu'il remplisse visuellement l'espace
3. ajouter un badge « Visuel à venir » en bas de la carte, pour signaler qu'il s'agit d'un placeholder et non d'un choix design

```css
.card-header.emoji-only {
  background: linear-gradient(135deg, #fff4e6 0%, #ffe0b2 100%);
  font-size: 8rem;
}
.card-header.emoji-only::after {
  content: "Visuel à venir";
  position: absolute;
  bottom: 12px; left: 0; right: 0;
  text-align: center;
  font-size: .72rem;
  color: #b37400;
  letter-spacing: .05em;
  text-transform: uppercase;
  font-weight: 600;
}
```

### 11.3. Alignement vertical de tous les headers d'une même grille

Dans une grille CSS, toutes les cartes d'une même ligne s'étirent automatiquement à la hauteur de la carte la plus haute. Cela provoque des décalages visibles si les `.card-body` ont des longueurs de texte très différentes. Pour garder une grille propre :

- hauteur du header : `height: 260px;` fixe pour toutes
- corps de carte : `display: flex; flex-direction: column;` sur `.camera-card` pour que le bouton en bas reste aligné même si le texte est plus court
- bouton : `margin-top: auto;` pour le coller au bas de la carte

### 11.4. Interdiction des grands vides autour des images

Tout cadre qui contient une image doit obéir à une de ces trois règles :

1. l'image remplit tout le cadre avec `object-fit: cover`, pas de vide visible
2. l'image est centrée avec un padding uniforme (max 20 % de la hauteur totale)
3. le cadre est d'une taille proche de la taille native de l'image (±10 %)

Une vignette qui montre 200 pixels d'image au milieu de 500 pixels vides est interdite. C'est systématiquement une erreur de CSS (`min-height: Nvh` en général) qui doit être corrigée.

### 11.5. Checklist infographie avant publication

Avant tout push d'une page contenant une grille de cartes produit :

1. ouvrir la page dans le navigateur, passer en mode responsive (375 px, 768 px, 1280 px)
2. vérifier que toutes les cartes d'une même ligne ont la **même hauteur** sur les trois largeurs
3. vérifier qu'aucune image n'est entourée de plus de 40 pixels de vide au-dessus ou en-dessous
4. vérifier que les emoji-only ont bien le fond contrasté + badge « Visuel à venir »
5. vérifier que les boutons d'action sont alignés sur la même ligne horizontale dans chaque ligne de la grille

Cette règle a été ajoutée suite à un bug photo-video.html où `.card-header { min-height: 65vh; }` produisait 700+ pixels de vide autour de photos de 260 pixels. Ne pas reproduire.
