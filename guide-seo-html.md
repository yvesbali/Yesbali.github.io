# Guide SEO HTML — Référence complète

Guide consolidé des bonnes pratiques HTML pour le référencement Google. Organisé par zones de la page, du `<head>` au `<body>`, puis par optimisations techniques et sémantiques.

---

## 1. Fondations du document HTML

Ces balises structurelles garantissent que la page est correctement interprétée par les navigateurs et les robots d'indexation.

- **`<!DOCTYPE html>`** — À placer en toute première ligne. Force le navigateur à interpréter la page en mode standard et évite les erreurs de rendu.
- **`<html lang="fr">`** — L'attribut `lang` indique la langue principale du contenu. Crucial pour l'accessibilité et le SEO international.
- **`<head>`** — Contient toutes les métadonnées invisibles pour l'utilisateur mais essentielles pour Google.
- **`<body>`** — Contient tout le contenu visible de la page.

---

## 2. Les métadonnées du `<head>`

C'est ici que se jouent les directives critiques pour les moteurs de recherche.

### Balise `<title>`
- **Unique pour chaque page** du site.
- Longueur : **50 à 60 caractères** pour éviter la troncature dans les SERP.
- Placer le **mot-clé principal au début** de la balise.
- Constitue l'un des signaux SEO les plus importants.

### Balise `<meta name="description">`
- **Unique pour chaque page**.
- Longueur : **140 à 160 caractères**.
- N'impacte pas directement le classement, mais influence fortement le **taux de clics (CTR)**.
- Doit être incitative, contenir le mot-clé principal et un appel à l'action.

### Balise `<link rel="canonical">`
- **Obligatoire** pour éviter les pénalités pour contenu dupliqué.
- Doit pointer vers l'URL maîtresse de la page.
- Une page unique doit s'auto-référencer via sa propre balise canonical.

### Balise `<meta name="viewport">`
- Indispensable pour le responsive design.
- Configuration recommandée : `<meta name="viewport" content="width=device-width, initial-scale=1.0">`
- Indique à Google que la page est mobile-friendly.

### Balise `<meta charset="UTF-8">`
- Permet d'afficher correctement tous les caractères spéciaux (accents, symboles).

### Balise `<meta name="robots">`
- Donne des instructions précises aux robots d'indexation.
- Directives clés : `index`/`noindex` pour l'indexation, `follow`/`nofollow` pour le suivi des liens.
- Pour exclure une page des résultats : `<meta name="robots" content="noindex, follow">`.

### Balises Hreflang `<link rel="alternate" hreflang="...">`
- À utiliser uniquement pour les sites multilingues ou multi-pays.
- Indique à Google quelle version linguistique afficher selon le contexte de l'utilisateur.

### Balise `<meta name="google-site-verification">`
- Permet de vérifier la propriété du site dans Google Search Console.

### Balises Open Graph (`og:`)
- Contrôlent l'apparence de la page lors du partage sur les réseaux sociaux.
- Permettent de définir un titre, une description et une image spécifiques pour Facebook, LinkedIn, etc.

> ⚠️ **Obsolète** : la balise `<meta name="keywords">` n'est plus utilisée par Google. Inutile de la renseigner.

---

## 3. Structure sémantique du `<body>`

Google utilise les balises HTML5 sémantiques pour comprendre la hiérarchie et les rôles des différentes zones de la page. Il faut toujours privilégier ces balises aux `<div>` génériques.

### Balisage global
- **`<header>`** — En-tête du site ou de la section.
- **`<nav>`** — Menus de navigation.
- **`<main>`** — Contenu principal de la page (unique par page).
- **`<article>`** — Contenu indépendant (article de blog, fiche produit, commentaire).
- **`<section>`** — Regroupement thématique de contenu.
- **`<aside>`** — Contenu secondaire (sidebar, encart latéral).
- **`<footer>`** — Pied de page.

### Balises de titres (`<h1>` à `<h6>`)
- **Un seul `<h1>` par page**. Il doit décrire le sujet principal.
- Hiérarchie stricte : un `<h3>` doit toujours être précédé d'un `<h2>`. Ne jamais sauter de niveau.
- Ne jamais utiliser les titres pour modifier la taille du texte — c'est le rôle du CSS.
- La hiérarchie doit refléter la logique du contenu, pas la mise en page.

### Formatage sémantique du texte
- **`<strong>`** au lieu de `<b>` pour mettre en évidence un concept important (poids sémantique).
- **`<em>`** au lieu de `<i>` pour l'emphase.

---

## 4. Images et médias

L'optimisation des images est cruciale à la fois pour le SEO (Google Images) et pour les Core Web Vitals.

### Attribut `alt`
- **Toutes les balises `<img>` doivent avoir un attribut `alt`**.
- Décrire l'image de manière factuelle et concise.
- Intégrer un mot-clé uniquement si c'est pertinent — pas de bourrage.
- Pour les images purement décoratives : `alt=""`.
- Indispensable pour l'accessibilité (lecteurs d'écran).

### Attributs `width` et `height`
- Toujours définir la largeur et la hauteur dans le HTML.
- Évite le décalage de mise en page (**CLS — Cumulative Layout Shift**), critère clé des Core Web Vitals.

### Chargement différé (`loading="lazy"`)
- À ajouter sur les images situées sous la ligne de flottaison.
- Améliore le temps de chargement principal (LCP).
- **Ne jamais** appliquer cet attribut sur l'image principale du hero ou au-dessus de la ligne de flottaison.

### Balise `<picture>`
- À utiliser pour servir des formats modernes (WebP, AVIF) avec un fallback JPG/PNG pour les anciens navigateurs.

---

## 5. Liens, maillage interne et externe

Les liens permettent à Googlebot de découvrir les pages et de comprendre leurs relations.

### Règles fondamentales
- Les liens doivent être des balises `<a>` avec un attribut `href` pointant vers une URL valide.
- Googlebot ne suit **ni** les `<button>`, **ni** les gestionnaires JavaScript `onclick`, **ni** les liens de type `javascript:goTo(...)`.

### Texte d'ancrage (anchor text)
- Le texte cliquable doit décrire la page cible.
- **Éviter** les « Cliquez ici » ou « En savoir plus ».
- **Préférer** « Découvrez notre comparatif des chaussures de sport ».

### Attributs `rel`
- **`rel="nofollow"`** — Indique à Google de ne pas transmettre de jus SEO. À utiliser pour les liens non de confiance.
- **`rel="sponsored"`** — **Obligatoire** pour les liens affiliés, sponsorisés ou achetés.
- **`rel="ugc"`** — Pour le contenu généré par les utilisateurs (commentaires, forums).

### URLs
- Courtes, lisibles, en minuscules.
- Mots séparés par des tirets (`-`).
- Contenir le mot-clé principal quand c'est pertinent.
- Exemple : `exemple.com/guide/seo-html`.

---

## 6. Performances techniques et Core Web Vitals

Google pénalise les pages lentes. La manière dont le HTML charge les ressources est un facteur de classement majeur.

### Scripts JavaScript
- Placer les balises `<script>` en bas du `<body>`, ou utiliser les attributs **`defer`** ou **`async`** dans le `<head>`.
- Objectif : ne pas bloquer le rendu initial de la page.

### Ressources critiques
- Utiliser `<link rel="preload">` pour forcer le téléchargement prioritaire des ressources critiques : police d'écriture principale, image du hero, CSS critique.

### Core Web Vitals — objectifs à atteindre
- **LCP (Largest Contentful Paint)** — Affichage du contenu principal : **< 2,5 s**.
- **INP (Interaction to Next Paint)** — Réactivité aux interactions : **< 200 ms**.
- **CLS (Cumulative Layout Shift)** — Stabilité visuelle : **< 0,1**.

---

## 7. Données structurées (Schema.org)

Il ne s'agit pas de balises HTML classiques, mais de code contextuel inséré dans la page pour donner à Google une compréhension ultra-précise du contenu.

- **Format recommandé par Google : JSON-LD**.
- S'insère via une balise `<script type="application/ld+json">`.
- Permet d'obtenir les **Rich Snippets** dans les résultats de recherche : étoiles d'avis, prix, temps de cuisson, FAQ, dates d'événements, etc.
- Types les plus utiles : `Article`, `Product`, `Recipe`, `FAQPage`, `BreadcrumbList`, `LocalBusiness`, `VideoObject`.
- Le **fil d'Ariane (Breadcrumb)** via Schema améliore l'affichage du chemin de navigation dans les SERP.

---

## 8. Pratiques à bannir (facteurs bloquants)

- **Contenu caché** — Ne jamais masquer du texte bourré de mots-clés via `display:none` ou `visibility:hidden`. Considéré comme du **cloaking** et sévèrement sanctionné.
- **Iframes pour le contenu principal** — Google a du mal à indexer le contenu dans une `<iframe>`. À réserver aux éléments tiers (YouTube, Google Maps).
- **Texte dans les images** — Google lit mal le texte incrusté. Tout texte important (titres, paragraphes, menus) doit être en HTML natif.
- **Liens non crawlables** — Boutons, événements JavaScript, liens `javascript:`. Googlebot ne les suit pas.
- **Sauts dans la hiérarchie des titres** — Passer d'un `<h2>` directement à un `<h4>` désorganise la structure sémantique.
- **Balise `<title>` ou méta-description identiques** sur plusieurs pages.

---

## 9. Accessibilité et signaux qualité

Un site accessible est mécaniquement un site mieux structuré, ce qui profite au SEO.

- Utiliser les balises sémantiques HTML5.
- Attributs `alt` descriptifs sur toutes les images.
- Contraste de couleurs suffisant (norme WCAG).
- Structure logique des titres.
- Labels explicites sur les formulaires.

Ces bonnes pratiques envoient des signaux positifs à Google tout en améliorant l'expérience utilisateur réelle.

---

## Checklist rapide avant mise en ligne

**Head**
- [ ] `<!DOCTYPE html>` présent
- [ ] `<html lang="...">` renseigné
- [ ] `<meta charset="UTF-8">`
- [ ] `<meta name="viewport">` configuré
- [ ] `<title>` unique, 50-60 caractères, mot-clé en début
- [ ] `<meta name="description">` unique, 140-160 caractères
- [ ] `<link rel="canonical">` pointant vers l'URL maîtresse
- [ ] Balises Open Graph renseignées

**Body**
- [ ] Un seul `<h1>` par page
- [ ] Hiérarchie `<h2>` → `<h3>` → `<h4>` respectée sans saut
- [ ] Balises sémantiques `<header>`, `<main>`, `<article>`, `<footer>` utilisées
- [ ] Toutes les `<img>` ont un `alt` descriptif
- [ ] `width` et `height` définis sur les images
- [ ] `loading="lazy"` sur les images sous la ligne de flottaison
- [ ] Textes d'ancrage descriptifs
- [ ] `rel="sponsored"` sur les liens affiliés
- [ ] `rel="ugc"` sur les commentaires utilisateurs

**Technique**
- [ ] Scripts en `defer`/`async` ou en bas de `<body>`
- [ ] LCP < 2,5 s, INP < 200 ms, CLS < 0,1
- [ ] Données structurées JSON-LD pour les types pertinents
- [ ] URL courte, lisible, avec tirets
- [ ] Aucune iframe pour du contenu principal
- [ ] Aucun texte caché
