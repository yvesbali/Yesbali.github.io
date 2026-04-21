# Template description YouTube LCDMH — version v2 (GEO + sous-requêtes)

> Évolution du v1 : on ajoute un **bloc « sous-requêtes en langage naturel »** (question → réponse courte) qui est la mécanique cœur du GEO. Les IA génératives (ChatGPT Search, Perplexity, Gemini, Copilot, Claude) extraient ces paires Q/R comme réponse directe à une requête utilisateur.
>
> Changelog v1 → v2 :
> - AJOUT bloc **« Les questions qu'on nous pose »** (3-5 Q/R factuelles, 1 ligne chacune).
> - AJOUT ligne invisible **`Keywords :`** en bas (lue par crawlers, comprime le cluster sémantique).
> - Le reste est identique à v1 (first line, narrative, liens, chapitres, équipement, qui, hashtags).

---

## Structure v2 (ordre exact)

```
{{FIRST_LINE}}                                                 ← 150 car. max, requête réelle

📍 {{LOCATION}}
🏍️ {{BIKE}} · {{CONTEXT}}
📏 {{KM_DU_JOUR}} km

═══════════════════════════════════════════

{{NARRATIVE_PARAGRAPH}}                                         ← 3-6 phrases, ton LCDMH

═══════════════════════════════════════════

❓ LES QUESTIONS QU'ON NOUS POSE
• {{Q1}} — {{R1}}
• {{Q2}} — {{R2}}
• {{Q3}} — {{R3}}
• {{Q4}} — {{R4}}                                               ← facultatif (3 min.)

═══════════════════════════════════════════

📖 GUIDE / ARTICLE COMPLET :
▶ {{ARTICLE_URL}}

🎬 PLAYLIST :
▶ {{PLAYLIST_URL}}

═══════════════════════════════════════════

⏱️ CHAPITRES                                                    ← YouTube strict : 00:00 + min 3 + 10s
{{CHAPTERS}}

═══════════════════════════════════════════

🧰 ÉQUIPEMENT (liens affiliés, sans surcoût)
{{GEAR}}

═══════════════════════════════════════════

🙋 QUI EST LCDMH ?
LCDMH — La Chaîne du Motard Heureux — est la chaîne de Yves,
motard voyageur basé à Annecy. Road trips moto longue distance
(Cap Nord 2025, Europe, Alpes), bivouac, tests d'équipement.
🌐 Site : https://lcdmh.com
📧 Contact : https://lcdmh.com/a-propos.html

═══════════════════════════════════════════

{{HASHTAGS}}                                                    ← 5-8 hashtags max, ciblés

Keywords : {{CLUSTER_KEYWORDS}}                                 ← 1 ligne, 8-15 mots-clés séparés par virgule
```

## Règles de remplissage spécifiques v2

### `{{Q1..Q4}}` — sous-requêtes
- Format **question naturelle** : telle qu'un humain la poserait à ChatGPT.
- Source prioritaire : requêtes réelles extraites de GSC (colonne `query` de `data/baselines/gsc_queries_*.csv`).
- Choisir des questions où la vidéo apporte une réponse factuelle vérifiable (pas de marketing vague).

Exemples approuvés :
- `Combien coûte un road trip moto au Cap Nord ? — Environ 3 500 € pour 3 semaines sur 10 000 km (ferries, essence, hébergement, bouffe).`
- `Quel Carpuride choisir en 2026 ? — Le W702RS Pro pour la luminosité solaire ; le W501 si budget serré et usage occasionnel.`
- `Est-ce que le Bridgestone T33 vaut mieux que le Michelin Road 6 ? — T33 plus polyvalent piste/route, Road 6 plus endurant sur autoroute. Comparatif dans la vidéo.`

À éviter :
- ❌ « Pourquoi cette vidéo est géniale ? » (auto-promotion)
- ❌ Questions sans réponse (suspense commercial)
- ❌ Réponses > 25 mots (les IA coupent au milieu)

### `{{CLUSTER_KEYWORDS}}` — ligne finale
- 8 à 15 mots-clés séparés par virgule, **triés du plus spécifique au plus générique**.
- Utiliser exclusivement des termes **déjà présents dans GSC** (colonne `query` du CSV baseline).
- Pas de duplication avec les hashtags (les hashtags sont cliquables, les keywords ne le sont pas — ils alimentent juste le signal sémantique).

Exemple pour une vidéo écran moto :
`carpuride w702rs pro, quel carpuride choisir, meilleur carpuride moto, aoocci u6, carplay moto, écran carplay moto, carpuride vs aoocci, comparatif carpuride`

## Critères qualité d'une description v2

| Critère                              | Seuil min. | Mesure                                                   |
|--------------------------------------|-----------:|----------------------------------------------------------|
| Longueur totale                      |  1 500 car | `len(description)` ≥ 1500                                |
| First line contient mot-clé GSC      |       oui  | regex sur colonne `query`                                |
| Bloc Q/R présent                     |       oui  | `❓ LES QUESTIONS QU'ON NOUS POSE`                        |
| Nombre de Q/R                        |        ≥ 3 | count puces `•` dans bloc Q/R                            |
| Chapitres présents                   |       oui  | ligne `00:00` + ≥ 3 timestamps                           |
| Lien lcdmh.com                       |        ≥ 1 | regex `https://lcdmh.com/`                               |
| Bloc « Qui est LCDMH »               |       oui  | chaîne identique à toutes les vidéos (entity locking)    |
| Hashtags                             |      5-8   | count `#`                                                |
| Ligne Keywords                       |       oui  | regex `^Keywords :`                                      |

## Mesure de l'effet

Le script `scripts/geo_snapshot.py --label T30` produit un diff qui mesure :
- Δ `yt_search_pct` par vidéo (objectif : +3 à +8 points sur 30 jours)
- Δ position GSC sur les `related_gsc_queries` de la vidéo
- Δ vues 30j

Le tracker `data/baselines/genai_tracker.xlsx` mesure en parallèle si ChatGPT/Perplexity/Gemini citent lcdmh.com ou youtube.com/@lcdmh en réponse aux questions du bloc Q/R.
