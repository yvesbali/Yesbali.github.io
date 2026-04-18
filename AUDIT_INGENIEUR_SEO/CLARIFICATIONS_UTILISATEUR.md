# CLARIFICATIONS NECESSAIRES AVANT POURSUITE DES TRAVAUX

Document a completer par l'utilisateur pour que je puisse poursuivre
les actions qui NECESSITENT des donnees factuelles. Je n'inventerai
aucune metadonnee produit, aucun taux, aucune URL.

---

## 1. Reconstruction `/carpuride.html` (action prioritaire)

La page Carpuride est ton **page la plus proche du chiffre** (393
impressions GSC). Pour la reconstruire proprement j'ai besoin de :

### 1.1. Video YouTube principale a mettre en tete
- [x] Deux videos deja integrees dans la page actuelle :
  `Q2OlIRiTFgc` et `Z658n_oLejg`
- [ ] **Confirmer** : laquelle mettre en position **hero** (au-dessus
  du pli, lancement automatique mute) ? Ou autre video ?

### 1.2. AggregateRating (Product Schema)
Google ne laisse plus afficher d'etoiles dans les SERPs si le
AggregateRating n'est pas legitime. Donne-moi les VRAIES valeurs :
- [ ] Note moyenne (ex: 4.6 / 5)
- [ ] Nombre de votes / avis agreges
- [ ] Source des avis (tes propres tests repetes, retours lecteurs,
  avis agreges Amazon+Carpuride ? — il faut pouvoir documenter)

Si tu n'as pas de chiffres documentes, on **retire** simplement le
AggregateRating. Ne jamais le bricoler : penalite Google possible.

### 1.3. Images de la page
- Actuellement 0 image dans le corps de la page (uniquement bg hero).
- [ ] Tu as deja des photos terrain du Carpuride ? Si oui, chemin
  exact (ex: `/images/carpuride-ecran-route.jpg`).
- [ ] Sinon, je te prepare la structure pour `<picture>` + `srcset` ou
  tu colleras les images plus tard.

---

## 2. Pages zombies a reconstruire

6 pages recoivent des impressions GSC sans generer de clic. Je peux
les reconstruire, mais j'ai besoin de savoir sur CHACUNE :

| Page | Situation |
|------|-----------|
| komobi.html | Traceur GPS — as-tu un test perso, ou uniquement avis constructeur ? |
| gps.html | Guide general — quelles requetes cibles ? je pensais "GPS moto 2026 comparatif" |
| aferiy.html | Station energie — garde-t-on ou fusionne dans un guide bivouac ? |
| olight.html | Lampe — idem, garder solo ou fusionner ? |
| intercoms.html | Guide intercoms — liste des produits testes reels ? |
| equipement.html | Page generale — a-t-elle vocation a etre pillier ? |

Pour chacune, je peux soit :
- **Reconstruire avec + de contenu** si tu me donnes les details
- **Rediriger 301** vers la page pillier la plus proche si tu preferes

---

## 3. Pages pilliers francophonie a creer

Je te propose de creer ces 4 nouvelles pages optimisees longue traine :

| Page | Slug propose | Cible SEO |
|------|--------------|-----------|
| Norvege | /road-trip-moto-norvege.html | "road trip moto norvege", "cap nord a moto" |
| Dolomites | /road-trip-moto-dolomites.html | "road trip moto dolomites", "passo stelvio moto" |
| Alpes | /road-trip-moto-alpes.html | "road trip moto alpes", "cols alpes moto" (existe partiellement) |
| Espagne | /road-trip-moto-espagne.html | "road trip moto espagne", "pyrenees moto" |

- [ ] Confirmes-tu les 4 slugs ?
- [ ] Pour chaque pillier, 3-5 road trips / articles existants a citer
  en maillage interne ? (je peux te proposer un mapping si tu valides
  la structure)

---

## 4. Suivi SEO continu

Proposition :
- **Workflow GitHub Actions hebdomadaire** qui exporte le JSON GSC
  (via API, tu as deja OAuth) et compare aux 7 jours precedents.
- Alerte automatique (mail ou Slack) si une page passe en position
  5-15 ET CTR < 2% (sweet spot a optimiser).

- [ ] OK pour commencer par le workflow Actions mensuel CrUX + GSC ?
- [ ] Email / Webhook ou je dois envoyer l'alerte ? (Make.com ?)

---

## 5. API YouTube (pour VideoObject schema)

Tu as deja une cle API YouTube Data v3 dans ton automation. Je peux
enrichir toutes les pages avec VideoObject schema si tu lances ce
script en local (il ne marchera pas depuis la VM Cowork) :

```powershell
cd F:\LCDMH_GitHub_Audit
$env:YT_API_KEY = "TA_CLE_AIza..."
pip install google-api-python-client
python AUDIT_INGENIEUR_SEO\scripts\add_video_object_schema.py
```

- [ ] OK pour lancer ce script localement une fois que tu as 5 minutes ?
