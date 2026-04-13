# Cahier des charges — Pages HTML LCDMH
*Référence : codes-promo.html — Dernière mise à jour : avril 2026*

---

## 1. Page de référence

La page **`codes-promo.html`** est la référence visuelle et structurelle pour toutes les pages du site.
Toute nouvelle page doit respecter ses proportions, sa typographie et son système de largeurs.

---

## 2. Largeurs de conteneur

| Élément | max-width | Utilisation |
|---|---|---|
| `.container` principal | `1200px` | Enveloppe générale de la page |
| Blocs de texte / intro SEO | `900px` | Paragraphes, intro, confiance, maillage |
| Blocs spéciaux (choix, produits) | `1000px` | Grilles de cartes |
| Hero content | `950px` | Titre + accroche dans le hero |
| Hero lead (sous-titre) | `780px` | Texte d'accroche sous le H1 |

**Règle :** tous les conteneurs sont centrés avec `margin: 0 auto` et un padding latéral de `5%` sur mobile.

---

## 3. Hero (bandeau haut de page)

### Hauteur
```css
min-height: 45vh;
```
**Valeur fixe pour TOUTES les pages — sans exception.**
Ne jamais utiliser 60vh, 65vh, 70vh ou plus.

### Image de fond
```css
background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.65)),
            url('/images/NOM-DE-LA-PHOTO.jpg') center/cover no-repeat;
```

**Règles impératives :**
- Le chemin commence toujours par `/images/` (absolu depuis la racine)
- Ne jamais écrire `url('photo.jpg')` ou `url('images/photo.jpg')` (chemin relatif = photo absente)
- Quand une photo est ajoutée dans le dossier `images/`, faire immédiatement `git add images/NOM.jpg` avant le push

### Structure HTML du hero
```html
<section class="hero">
  <div class="hero-content">
    <div class="hero-badge">Badge optionnel</div>
    <h1>Titre de la page</h1>
    <p class="hero-lead">Accroche courte et lisible</p>
  </div>
</section>
```

---

## 4. Typographie

| Rôle | Police | Poids |
|---|---|---|
| Titres H1/H2/H3/H4 | `Montserrat` | 700–800 |
| Corps de texte | `Inter` | 400–600 |

```html
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
```

**Tailles de base :**
- `body` : `font-size: 16px`, `line-height: 1.65`
- H1 hero : `clamp(2rem, 5.5vw, 3.6rem)`
- H2 sections : `clamp(1.5rem, 3vw, 2rem)`

---

## 5. Palette de couleurs

```css
:root {
  --orange:      #e67e22;   /* couleur principale, CTA, accents */
  --orange-dark: #d35400;   /* hover sur éléments orange */
  --noir:        #1a1a1a;   /* texte principal, fond footer */
  --bg:          #f7f7f5;   /* fond général de la page */
  --border:      #e5e5e5;   /* bordures des cartes */
  --muted:       #777;      /* textes secondaires */
}
```

---

## 6. Navigation

La navigation est **toujours injectée dynamiquement** via le script dédié.
Ne jamais copier-coller le HTML de nav dans une page.

```html
<div id="lcdmh-nav"></div>
<script src="/js/lcdmh-nav-loader.js" defer></script>
```

Ce bloc se place immédiatement après `<body>`, avant tout contenu.

---

## 7. Blocs achat affiliés (buy-box)

- Fond : `var(--orange)`
- Texte : `color: rgba(255,255,255,.9)` — **toujours blanc, jamais noir**
- Titres dans la buy-box : `color: #fff`
- 3 boutons sur une ligne : `display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem`
- Sur mobile (< 720px) : `grid-template-columns: 1fr`

**Liens affiliés de référence :**
| Marchand | Lien |
|---|---|
| 123pneus.fr | `https://tidd.ly/4b6C1sx` |
| pneus-moto.fr | `https://www.awin1.com/cread.php?awinmid=7403&awinaffid=2753560&ued=https%3A%2F%2Fwww.pneus-moto.fr%2F` |
| pneus.fr | `https://www.pneus.fr/pneus/moto?utm_source=awin&utm_medium=affiliate&ID=aff_tn_fr_awin&sv1=affiliate&sv_campaign_id=2753560&awc=7928_1776085200_56c3768944e51482019b3bbd2b685985` |

---

## 8. SEO — règles de base

| Élément | Règle |
|---|---|
| `<title>` | Descriptif, 60 caractères max, inclure "LCDMH" |
| `meta description` | 150 caractères max, lisible, pas une liste de marques |
| `meta keywords` | **À supprimer** — Google ne l'utilise plus |
| `canonical` | Toujours présent, URL absolue |
| Open Graph | `og:title`, `og:description`, `og:url`, `og:image` obligatoires |
| H1 | Un seul par page, cohérent avec le `<title>` |
| Structure Hn | H1 → H2 → H3, jamais sauter de niveau |

---

## 9. Images

- Toutes les images dans `/images/`
- Toujours référencées avec chemin absolu : `/images/nom.jpg`
- Quand une nouvelle image est ajoutée : `git add images/nom.jpg` **avant** le push
- Format recommandé : `.jpg` ou `.webp` (préférer webp pour la performance)
- Ajouter `loading="lazy"` sur toutes les images hors hero

---

## 10. Commentaires communauté

- 4 commentaires visibles par défaut
- Les autres masqués dans `<div class="comments-hidden" id="extra-comments">`
- Bouton toggle : `▼ Voir les X autres avis`
- Badge total : `<span class="comments-count">X avis</span>`
- Quand de nouveaux commentaires YouTube sont ajoutés : mettre à jour badge + bouton

---

## 11. Footer

Le footer de référence est celui de `olight.html`. Il est **sobre, lisible, identitaire** — à appliquer sur toutes les pages du site.

### CSS (à inclure dans le `<style>` de chaque page)
```css
footer{background:var(--noir);color:rgba(255,255,255,.65);padding:2.8rem 6%;margin-top:4rem;text-align:center}
.f-logo{font-family:'Montserrat',sans-serif;font-size:1.6rem;font-weight:800;color:#fff}
.f-logo em{font-style:normal;color:var(--orange)}
.f-nav{list-style:none;display:flex;flex-wrap:wrap;justify-content:center;gap:.5rem 1.5rem;margin:.8rem 0}
.f-nav a{font-size:.8rem;color:rgba(255,255,255,.55)}
.f-nav a:hover{color:var(--orange)}
.f-legal{font-size:.76rem;color:rgba(255,255,255,.3);margin-top:1.1rem;line-height:1.7}
```

### HTML (identique sur toutes les pages racine)
```html
<footer>
    <div class="f-logo">LC<em>D</em>MH</div>
    <p style="font-size:.83rem;margin:.4rem 0 0;color:rgba(255,255,255,.45)">La Chaîne du Motard Heureux · Annecy, France</p>
    <ul class="f-nav">
        <li><a href="codes-promo.html">Codes promo</a></li>
        <li><a href="carpuride.html">Carpuride</a></li>
        <li><a href="aferiy.html">AFERIY</a></li>
        <li><a href="komobi.html">Komobi</a></li>
        <li><a href="https://www.youtube.com/@LCDMH">YouTube</a></li>
        <li><a href="mentions-legales.html">Mentions légales</a></li>
        <li><a href="a-propos.html">À propos</a></li>
    </ul>
    <p class="f-legal">Ce site contient des liens d'affiliation. Leur utilisation me permet de continuer à produire du contenu gratuit sur YouTube.<br>LCDMH © 2026 – Yves · Annecy, France</p>
</footer>
```

### Pour les pages dans `/articles/`
Mêmes règles, mais les liens utilisent des chemins absolus :
```html
<li><a href="/codes-promo.html">Codes promo</a></li>
```

### Règles
- Fond : `var(--noir)` (#1a1a1a)
- Logo `<em>D</em>` : `var(--orange)`
- Texte baseline : `rgba(255,255,255,.45)`
- Liens nav : `rgba(255,255,255,.55)` — hover `var(--orange)`
- Mention légale : `rgba(255,255,255,.3)`
- **Ne jamais copier un footer d'une autre page sans vérifier qu'il est complet et non tronqué**

---

## 12. Push Git — procédure

Le script `push-lcdmh.bat` utilise `git add -u` qui **ne prend que les fichiers déjà trackés**.

Pour tout nouveau fichier (image, nouvelle page) :
```bash
git -C "F:\LCDMH_GitHub_Audit" add images\NOUVELLE-PHOTO.jpg
git -C "F:\LCDMH_GitHub_Audit" add NOUVELLE-PAGE.html
```
Puis lancer `push-lcdmh.bat` normalement.

**Si le `index.lock` bloque :** fermer VS Code ou tout programme qui a le dossier 