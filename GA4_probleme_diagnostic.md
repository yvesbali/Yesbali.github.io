# Problème GA4 — lcdmh.com — Compte rendu pour consultation externe

## Contexte

- **Site** : lcdmh.com (blog moto / road trip)
- **Hébergement** : GitHub Pages depuis le repo `yvesbali/Yesbali.github.io` (CNAME → lcdmh.com)
- **Architecture** : HTML plats à la racine (`securite.html`, `pneus.html`, etc.), pas de framework, pas de Hugo en production
- **GA4** :
  - Propriété GA4 : `486269672`
  - Measurement ID : `G-5DP7XR1C7W`
  - Compte Analytics : LCDMH
- **Réseau utilisateur** : Freebox Pop (FAI Free), connexion fibre France
- **Navigateurs testés** : Chrome et Edge sur Windows

## Objectif

Faire apparaître des données dans GA4 → Rapports → Temps réel quand l'utilisateur visite `https://lcdmh.com/securite.html` depuis chez lui. Avant modification, GA4 affichait systématiquement "Aucune donnée reçue" / 0 utilisateur actif.

## Ce qui a été fait (et vérifié commité + pushé sur GitHub)

Dans le fichier `securite.html`, juste après `<meta name="viewport">`, ajout du snippet gtag.js standard :

```html
<!-- Google tag (gtag.js) - GA4 LCDMH -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-5DP7XR1C7W"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-5DP7XR1C7W');
</script>
```

Le commit a été poussé (`git push origin main`), GitHub Pages a rebuildé le site, la page est bien à jour en ligne (vérifié visuellement : un autre changement visuel du même commit — un encart témoignage avec classe `.testimonial-pro` — est visible sur la page).

## Ce qui fonctionne (confirmé)

1. **Le script gtag.js est bien chargé par le navigateur.**
   - Dans la console DevTools, `typeof gtag` renvoie `'function'` → la fonction gtag est définie.
2. **Le dataLayer est correctement rempli.**
   - `dataLayer` renvoie un `Array(4)` avec :
     - `['js', Date 16:40:31]`
     - `['config', 'G-5DP7XR1C7W']`
     - `['js', Date 16:40:32]` (1 seconde plus tard)
     - `['config', 'G-5DP7XR1C7W']`
   - → **Le snippet est exécuté DEUX FOIS** à 1 seconde d'écart. Probablement parce qu'un autre script (`lcdmh-nav-loader.js`, un loader dynamique de navigation utilisé sur le site) injecte aussi gtag. Pas bloquant en théorie, mais c'est une anomalie notable.

## Ce qui ne fonctionne pas

1. **Aucune requête `g/collect` n'est visible dans l'onglet Network des DevTools.**
   - Test fait sur Chrome puis sur Edge, avec filtre Network sur `collect`, `Preserve log` coché, Ctrl+F5 pour recharger.
   - Aucune requête vers `www.google-analytics.com` ou `region1.google-analytics.com` n'apparaît.
   - Aucune requête vers `googletagmanager.com` non plus n'est visible avec filtre large `google` (point à re-vérifier — peut-être cached).
2. **GA4 Temps Réel affiche toujours "Aucune donnée disponible" / 0 utilisateur.**

## Observation suspecte (interprétation incertaine)

En filtrant Network par `collect` sur Edge, une requête inattendue est apparue :
- URL : `https://assistance.free.fr/compte/contact.php?id=11523652&idt=c3b3013611c8724d404...`
- Type : document
- Statut : 404
- Initiateur : inconnu / non identifié sur la capture

**Pourquoi cette requête a matché le filtre `collect` alors que l'URL ne contient pas ce mot n'est pas clair.** Le mot "contact" ≠ "collect". Soit le filtre matche ailleurs (headers ?), soit c'est une coïncidence, soit c'est un widget Free indépendant.

`assistance.free.fr` appartient à Free (le FAI). Hypothèse initiale : la Freebox Pop intercepterait les requêtes vers google-analytics.com au niveau DNS et les redirigerait vers une page de blocage Free. **Non confirmé.** Aucun paramétrage explicite de blocage tracker n'a été trouvé dans les réglages Free (les pages vérifiées — reverse DNS, blocage SMTP sortant — ne sont pas pertinentes).

## Ce qui reste à tester / à diagnostiquer

### Tests non encore effectués
1. **Test depuis 4G sur téléphone** (critique) : charger `lcdmh.com/securite.html` depuis le téléphone avec Wi-Fi désactivé, puis vérifier GA4 Realtime. Résultat attendu : soit ça fonctionne → confirme que c'est un blocage local à la maison (réseau ou browser), soit ça ne fonctionne pas → problème côté site/script.
2. **Incognito mode confirmé** : test dans une fenêtre InPrivate/Incognito pour éliminer l'hypothèse d'une extension browser. Pas clairement effectué jusqu'ici.
3. **Inspection de `lcdmh-nav-loader.js`** : ce script injecte-t-il gtag une deuxième fois ? Le snippet du loader pourrait utiliser une version alternative (ex: `gtag('config', ..., { send_page_view: false })`) qui cancelerait le page_view.
4. **Vérifier l'onglet Network sans filtre** avec `Preserve log`, puis Ctrl+F5, puis taper `google-analytics` dans le filtre. Si même le chargement initial de `gtag/js` n'apparaît pas, c'est très anormal (alors que `typeof gtag === 'function'` marche).

### Questions ouvertes
- **Comment `typeof gtag === 'function'` peut-il être vrai si la requête `gtag/js?id=G-5DP7XR1C7W` n'apparaît pas dans Network ?** Soit elle apparaît mais on n'a pas regardé au bon moment (cache), soit elle utilise un service worker, soit elle est chargée différemment par `lcdmh-nav-loader.js`.
- **La double initialisation (2 x config) peut-elle empêcher l'envoi du collect ping ?** À vérifier : GA4 déduplique-t-il les events si deux `config` avec le même ID sont envoyés ? Ou au contraire, chaque `config` devrait générer 1 page_view → on devrait voir 2 collect.
- **Si Free bloque, comment le confirmer formellement ?** Commande `nslookup www.google-analytics.com` depuis le PC de l'utilisateur pour voir si le DNS renvoie une IP légitime (142.251.x.x) ou une IP de blocage Free.

## Demande

Si une autre IA ou un autre humain peut suggérer une piste de diagnostic fraîche, voici les angles les plus prometteurs :
- **Pourquoi gtag est défini (`typeof gtag === 'function'`) sans que la requête vers `googletagmanager.com/gtag/js` soit visible dans Network** — cette contradiction apparente est peut-être la clé.
- **Le rôle de `lcdmh-nav-loader.js`** (script custom présent sur le site) dans la double initialisation de GA4, et s'il pourrait annuler le page_view envoyé par le snippet inline.
- **Un test DNS direct** (`nslookup google-analytics.com` / `ping googletagmanager.com`) qui pourrait trancher en 10 secondes si le blocage est au niveau Freebox/DNS.

## État du repo

- Tous les commits légitimes poussés sur `origin/main`.
- Le commit toxique `fad30df "Hugo rebuild après édition"` (qui supprimait tous les roadbooks, kurviger, scripts, images) a été explicitement droppé via `git rebase -i`.
- Branche `main` propre, 0 commit en avance, arbre propre.
