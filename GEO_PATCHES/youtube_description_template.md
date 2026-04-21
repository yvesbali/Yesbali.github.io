# Template de description YouTube LCDMH — version GEO-ready

> Format dual : attractif pour les spectateurs, extractible pour les IA (ChatGPT Search, Perplexity, Google Gemini, Copilot).
>
> Principe : la **première ligne** (≤ 150 caractères) est factuelle et optimisée pour les requêtes réelles. Le corps reste narratif. Les blocs « identité » et « liens » sont **répétés à l'identique** sur toutes les vidéos de la série pour renforcer l'entité LCDMH aux yeux des crawlers.

---

## Gabarit à coller (avec placeholders `{{...}}`)

```
{{FIRST_LINE}}

📍 {{LOCATION_OR_ETAPE}}
🏍️ Honda NT1100 · Road trip solo · Mai–Juin 2025
📏 {{KM_DU_JOUR}} km parcourus cette journée

═══════════════════════════════════════════

{{NARRATIVE_PARAGRAPH}}

═══════════════════════════════════════════

📖 GUIDE COMPLET DU VOYAGE (itinéraire, budget, ferries, bivouac) :
▶ https://lcdmh.com/cap-nord-moto.html

🎬 PLAYLIST COMPLÈTE « Cap Nord 2025 » (14 épisodes) :
▶ https://www.youtube.com/playlist?list={{PLAYLIST_ID}}

═══════════════════════════════════════════

⏱️ CHAPITRES
{{CHAPTERS}}

═══════════════════════════════════════════

🧰 ÉQUIPEMENT UTILISÉ DANS LA SÉRIE
• Moto : Honda NT1100 DCT
• GPS : Aoocci (test sur https://lcdmh.com/gps.html)
• Apps : Entur (ferries norvégiens), FerryPay, Revolut
• Bivouac : tente 3 saisons, duvet grand froid
• Détails : https://lcdmh.com/equipement.html

═══════════════════════════════════════════

🙋 QUI EST LCDMH ?
LCDMH — La Chaîne du Motard Heureux — est la chaîne de Yves,
motard voyageur basé à Annecy. Road trips moto en solo longue
distance (Cap Nord 10 000 km en 2025, Europe-Asie, Alpes),
bivouac moto et tests d'équipement terrain.
🌐 Site : https://lcdmh.com
📧 Contact : via https://lcdmh.com/a-propos.html

═══════════════════════════════════════════

#CapNord #RoadTripMoto #NordkappMoto #HondaNT1100 #BivouacMoto #VoyageMotoNorvège #LCDMH
```

---

## Règles de remplissage

### `{{FIRST_LINE}}` — critique (150 car. max)
Format imposé : **requête réelle + élément factuel distinctif**.

Exemples approuvés :
- `Road trip moto au Cap Nord — épisode 3 : les 5 ferries de Stavanger à Bergen (250 km)`
- `Bivouac moto en Norvège : première nuit sauvage près du Gaularfjellet`
- `Ferry moto Bodø–Lofoten : comment ça se passe, combien ça coûte (21 €)`
- `Comment préparer un road trip moto au Cap Nord : budget, ferries, itinéraire`

À éviter :
- ❌ « La plus belle journée de ma vie »
- ❌ « Cette nuit-là, j'étais à bout »
- ❌ Tout titre émotionnel sans mot-clé géographique ou pratique

### `{{LOCATION_OR_ETAPE}}`
Une ligne géographique précise. Ex : `Stavanger → Bergen, Norvège (côte ouest)`.

### `{{KM_DU_JOUR}}`
Nombre entier, km réels de l'épisode. Si inconnu, mettre la distance approximative d'étape.

### `{{NARRATIVE_PARAGRAPH}}`
3 à 6 phrases, ton LCDMH habituel (je, vécu, ressenti). C'est la partie humaine, qu'on ne sacrifie pas.

### `{{PLAYLIST_ID}}`
ID de la playlist « Cap Nord 2025 » (à récupérer une fois pour toutes, puis réutiliser partout).

### `{{CHAPTERS}}`
Format YouTube **strict** (sinon YouTube ne les reconnaît pas) :
- Premier timestamp = `00:00`
- Minimum 3 chapitres
- Minimum 10 secondes entre chaque
- Format : `00:00 Nom du chapitre` (un par ligne)

Exemple :
```
00:00 Introduction et contexte
01:45 Départ de Stavanger
05:30 Premier ferry
12:10 Route côtière vers Haugesund
18:40 Arrivée à Bergen
23:15 Bilan de la journée
```

---

## Exemple concret — épisode 3

```
Road trip moto au Cap Nord — épisode 3 : les 5 ferries de Stavanger à Bergen (250 km)

📍 Stavanger → Bergen, Norvège (côte ouest)
🏍️ Honda NT1100 · Road trip solo · Mai–Juin 2025
📏 250 km parcourus cette journée

═══════════════════════════════════════════

La Norvège a cette façon très particulière de te séduire. Cette côte magique,
envoûtante, sinueuse, comme créée pour mieux nous surprendre. Cinq ferries en
une journée pour longer cette côte impossible. La mer n'est jamais bien loin,
même en montagne. Premier vrai contact avec le rythme scandinave : embarquer,
rouler, embarquer, rouler. Une journée qui change la perception de la distance.

═══════════════════════════════════════════

📖 GUIDE COMPLET DU VOYAGE (itinéraire, budget, ferries, bivouac) :
▶ https://lcdmh.com/cap-nord-moto.html

🎬 PLAYLIST COMPLÈTE « Cap Nord 2025 » (14 épisodes) :
▶ https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx

═══════════════════════════════════════════

⏱️ CHAPITRES
00:00 Introduction et contexte
01:45 Départ de Stavanger
05:30 Premier ferry de la journée
12:10 Route côtière
18:40 Arrivée Bergen
23:15 Bilan

═══════════════════════════════════════════

🧰 ÉQUIPEMENT UTILISÉ DANS LA SÉRIE
• Moto : Honda NT1100 DCT
• GPS : Aoocci (test sur https://lcdmh.com/gps.html)
• Apps : Entur (ferries norvégiens), FerryPay, Revolut
• Bivouac : tente 3 saisons, duvet grand froid
• Détails : https://lcdmh.com/equipement.html

═══════════════════════════════════════════

🙋 QUI EST LCDMH ?
LCDMH — La Chaîne du Motard Heureux — est la chaîne de Yves,
motard voyageur basé à Annecy. Road trips moto en solo longue
distance (Cap Nord 10 000 km en 2025, Europe-Asie, Alpes),
bivouac moto et tests d'équipement terrain.
🌐 Site : https://lcdmh.com
📧 Contact : via https://lcdmh.com/a-propos.html

═══════════════════════════════════════════

#CapNord #RoadTripMoto #NordkappMoto #HondaNT1100 #BivouacMoto #VoyageMotoNorvège #LCDMH
```

---

## Pourquoi ce format marche pour les IA

1. **Première ligne factuelle** : c'est ce que les crawlers indexent en priorité. Elle contient le mot-clé géographique + un élément pratique chiffré, donc elle matche les requêtes « road trip moto Cap Nord », « ferry moto Bergen », « bivouac Norvège moto ».
2. **Lien canonique vers l'article pilier** répété sur les 14 épisodes → 14 backlinks internes cohérents, signal fort d'autorité.
3. **Bloc « Qui est LCDMH » identique partout** → répétition de l'entité nommée, ce qui renforce la reconnaissance par les modèles (ChatGPT, Claude, Gemini apprennent à associer « LCDMH » + « Cap Nord » + « Honda NT1100 » comme un triplet stable).
4. **Chapitres structurés** : YouTube génère les Key Moments, Google les indexe, et les IA extraient les segments pertinents en réponse à des requêtes précises (« comment passer le ferry Bodø-Lofoten »).
5. **Hashtags ciblés** : alimentent les requêtes YouTube et les signaux thématiques.

## À NE JAMAIS mettre dans la description

- ❌ Tartine de 30 hashtags sans lien avec le sujet
- ❌ Texte copié-collé d'un autre épisode sans adaptation de la première ligne
- ❌ « Merci de liker et de vous abonner » en première ligne (gâche la position prime d'extractibilité)
- ❌ URLs YouTube brutes sans lien cliquable (utiliser `▶ https://...`)
- ❌ Emojis en début de première ligne (les crawlers les traitent comme du bruit)
