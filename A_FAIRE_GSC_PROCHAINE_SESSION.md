# À faire Google Search Console — prochaine session

**Date de report :** 2026-04-19
**Raison :** quota d'indexation GSC dépassé

## URLs à soumettre pour indexation (dans cet ordre)

1. `https://lcdmh.com/articles/comparatif-carpuride-2026-w702-w702-pro-w702s-pro-et-702rs-pro.html`
   - Cluster Carpuride (zoom technique 4 modèles)
   - Raison : nouveau title + meta description + lien vers pilier + fix JSON-LD @id

2. `https://lcdmh.com/articles/quel-carpuride-moto-choisir.html`
   - Pilier Carpuride (guide décisionnel)
   - Raison : nouveau lien vers cluster (comparatif technique) pour résoudre le cannibalisme

3. `https://lcdmh.com/articles/gps-moto-u6-comment-naviguer-offline.html`
   - Nouvelle URL U6 (slug optimisé SEO)
   - Raison : rename depuis ancien slug tronqué "moto-peti"

4. `https://lcdmh.com/alpes-cols-mythiques.html`
   - Raison : FAQPage réparée (9 questions, JSON valide, plus de duplicate)
   - Erreur GSC à faire disparaître : "Champ FAQPage en double"

5. `https://lcdmh.com/articles/gps-moto-gps-offline-u6-va-t-il-sauver-mes-balades-moto-peti.html`
   - Ancienne URL U6 (redirect stub vers nouvelle)
   - Raison : faire prendre en compte le `noindex, follow` + meta refresh par Google

6. `https://lcdmh.com/alpes/annecy-et-ses-environs-moto.html`
   - Page hub Annecy (15 vidéos)
   - Raison : les 15 vidéos YouTube pointent maintenant vers cette page dans leurs descriptions (depuis 19/04/2026). Il faut que Google recrawl pour capter ce signal de cohérence hub + embed.

## Vérification à faire en parallèle (Rich Results Test — pas de quota)

- https://search.google.com/test/rich-results
- Tester `https://lcdmh.com/alpes-cols-mythiques.html`
- Attendu : 1 FAQ valide (9 questions), 0 erreur, 0 avertissement

## Autres tâches en attente

- [x] ~~Appliquer les 15 titres/descriptions YouTube retravaillés~~ → **FAIT 19/04/2026** via `apply_annecy_seo_batch.py` (15/15 succès, rapport : `F:\Automate_YT\apply_annecy_seo_results.json`)
- [ ] Diagnostic des 5 "Introuvable 404" remontées par GSC (à fournir la liste des URLs)
- [ ] Screenshots SERP baseline pour mesurer J+15 et J+45 sur les requêtes clés :
  - "cols alpes moto" / "road trip moto annecy" / "balade moto aravis" / "col semnoz moto"
  - "carpuride w702" / "gps moto u6" / "moto cap nord"
