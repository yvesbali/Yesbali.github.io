# 🏗️ ARCHITECTURE DU MAILLAGE LCDMH

**Version** : 1.0 · **Créé le** : 16/09/2026 · **Dernière revue** : 16/09/2026

> **Objectif de ce document** : dans six mois, personne ne doit avoir besoin de réinventer le système.

---

## 1. Le principe en trois phrases

**Il existe UNE source unique** : `data/maillage.json`.
**Elle contient les relations éditoriales** (page source → page cible → ancre → type → justification).
**Un script génère les blocs HTML** depuis cette source — on ne modifie **jamais** un bloc de maillage à la main dans un fichier HTML.

---

## 2. Pourquoi cette architecture

Avant le 16/09/2026, le site comptait **10 systèmes de maillage parallèles** :

| Système | Pages | Liens | Sort |
|---|---|---|---|
| `maillage-section` | 134 | 434 | **conservé** (devient le bloc canonique généré) |
| `.a-lire-aussi` | 26 | 263 | migré |
| `maillage-box` | 13 | 114 | migré |
| `link-grid` / `seo-link-grid` | 7 | 379 | migré |
| `maillage-piliers` | 5 | 51 | migré |
| `guide-related` | 1 | 5 | migré |
| `maillage-lien-pneus` | 4 | 4 | migré |

**Conséquence de cette dispersion** : à chaque audit, on découvrait un nouveau système, des auto-liens invisibles, des pages oubliées. **Les liens existaient en 10 endroits différents, chacun avec ses propres règles.**

**Aujourd'hui** : une source, un générateur, un contrôleur.

---

## 3. La source unique — `data/maillage.json`

### Structure

```json
{
  "$schema": "lcdmh-maillage-v1",
  "relations": [
    {
      "source": "/alpes-cols-mythiques.html",
      "cible": "/bagagerie-moto.html",
      "ancre": "🎒 Bagagerie moto : comment charger sa moto pour voyager",
      "type": "EQUIPMENT",
      "bloc": "maillage_section",
      "justification": "rouler les cols chargé → répartition du poids"
    }
  ]
}
```

### Les 11 types de relation

| Type | Signification | Exemple |
|---|---|---|
| `PARENT` | remonte vers un hub | page → `/voyager-moto.html` |
| `CHILD` | descend vers une sous-page | hub → article |
| `SIBLING` | même niveau thématique | article → article |
| `DESTINATION` | lieu / road trip | → `/cap-nord-moto.html` |
| `PREPARATION` | préparer le voyage | → bivouac, bagagerie |
| `EQUIPMENT` | équipement (moto ou motard) | → `/equipement.html` |
| `NAVIGATION` | GPS, cartes, offline | → `/gps.html` |
| `REGULATION` | papiers, vignettes, péages | → `/voyager-europe-moto.html` |
| `EXPERIENCE` | retour de test, panne, budget | → article vécu |
| `COMPARISON` | comparatif | → article « X vs Y » |
| `NEXT_STEP` | suite commerciale | → `/codes-promo.html` |

---

## 4. ⛔ La règle d'or

> **Une relation doit répondre à : « quelle est la prochaine question logique du lecteur ? »**

**INTERDIT** — le maillage par mots-clés automatique. Il a déjà produit :
- Cap Nord → Alpes ❌
- Annecy → Europe-Asie ❌
- GPS U6 → France ❌

**Le script génère. Il ne décide pas de la pertinence.** La pertinence vit dans `data/maillage.json`, écrite par un humain.

**Aucune exception.** Si tu hésites : ne l'ajoute pas.

---

## 5. Les scripts permanents

Ils vivent **dans le dépôt**, dossier `scripts/`.

### `scripts/build_maillage.py` — le générateur

```bash
cd /home/ubuntu/Yesbali.github.io
python3 scripts/build_maillage.py --dry-run   # montre sans écrire
python3 scripts/build_maillage.py             # écrit
```

**Déterministe et idempotent** : deux exécutions consécutives ne modifient rien.
**Sortie** : bloc `<section class="maillage-section">` entre les marqueurs
`<!-- MAILLAGE_STATIQUE_SEO -->` et `<!-- FIN_MAILLAGE_STATIQUE_SEO -->`.

**Règles internes** :
- **8 relations maximum par page** (la pertinence domine : 3 excellentes valent mieux que 10 moyennes)
- **Aucun auto-lien** : si `source == cible`, la relation est ignorée
- **Cibles commerciales exclues** du bloc éditorial : `codes-promo`, `mentions-legales`, `a-propos`, `articles`, `roadbooks`
- **Ordre imposé** par type (PARENT → CHILD → DESTINATION → … → NEXT_STEP) puis par cible — c'est ce qui garantit le déterminisme

### `scripts/audit_maillage.py` — le contrôleur

```bash
python3 scripts/audit_maillage.py            # rapport
python3 scripts/audit_maillage.py --strict   # code de sortie 1 si ERROR
```

**Sortie** : `PASS` / `WARNING` / `ERROR` + rapport JSON dans `data/audit_maillage_dernier.json`.

### Ce que l'audit détecte

**🔴 ERROR (bloquant)**
- auto-lien éditorial
- lien interne cassé
- doublon dans un même bloc
- ancre vide ou trop courte (< 3 caractères)
- système résiduel (`a-lire-aussi`, `maillage-box`, `link-grid`…)

**🟡 WARNING (non bloquant)**
- page sans recommandation
- page orpheline
- cul-de-sac
- profondeur excessive (hub > 2, page > 3)
- cible noindex très liée

---

## 6. Comment ajouter une relation

1. Ouvrir `data/maillage.json`
2. Ajouter dans `"relations"` :
```json
{
  "source": "/la-page-qui-recommande.html",
  "cible": "/la-page-recommandee.html",
  "ancre": "Le libellé qui donne envie de cliquer",
  "type": "EQUIPMENT",
  "bloc": "manuel",
  "justification": "pourquoi c'est LA prochaine question du lecteur"
}
```
3. Lancer `python3 scripts/build_maillage.py`
4. Lancer `python3 scripts/audit_maillage.py`
5. Commit

**⚠️ L'ancre doit décrire la CIBLE**, jamais la page source.
- ✅ `🗺️ GPS moto : CarPlay, Android Auto ou offline`
- ❌ `Cols mythiques — épisode 1`

---

## 7. Comment supprimer une relation

1. Retirer l'entrée de `data/maillage.json`
2. `python3 scripts/build_maillage.py`
3. `python3 scripts/audit_maillage.py`
4. Commit

**Ne jamais supprimer un lien dans le HTML à la main** : le prochain build le remettrait.

**Exception documentée** : `/mentions-legales.html` garde un lien vers lui-même dans le **footer global** — c'est de la navigation, pas du maillage éditorial. Whitelisté dans l'audit.

---

## 8. Workflow d'un nouvel article

```
ARTICLE CRÉÉ
    ↓
1. Intention ajoutée à MASTER_SEMANTIC_MAP.json
    ↓
2. Relation(s) ajoutée(s) dans data/maillage.json
    ↓
3. python3 scripts/build_maillage.py
    ↓
4. python3 scripts/audit_maillage.py   (doit être 0 ERROR)
    ↓
5. git commit && git push
    ↓
6. Baseline GSC
```

**Exemple — article COLIGHT Apex :**
```json
{"source": "/equipement.html", "cible": "/feux-additionnels-moto.html",
 "ancre": "🔦 Feux additionnels moto : mon test longue durée des COLIGHT Apex",
 "type": "EQUIPMENT", "bloc": "manuel",
 "justification": "le hub équipement → l'éclairage, la question suivante du lecteur"}
```

**➜ Plus jamais d'injection manuelle dispersée dans 10 fichiers HTML.**

---

## 9. Contrôle automatique (CI)

`.github/workflows/audit-maillage.yml` tourne **à chaque push** et **bloque** sur :
- `data/maillage.json` absent
- le build modifie des fichiers (= dépôt pas à jour)
- une **ERROR** d'audit

Les **WARNING ne bloquent pas** (critères éditoriaux subjectifs).

**Après un push, vérifier l'onglet Actions du dépôt GitHub.**

---

## 10. Navigation ≠ maillage éditorial

| Catégorie | Emplacement | Compte dans les métriques éditoriales |
|---|---|---|
| Navigation globale | `nav.html` (chargé en JS) | ❌ non |
| Breadcrumb | dans chaque page | ❌ non |
| Footer | `footer-loader.js` | ❌ non |
| **Maillage éditorial** | **bloc `maillage-section` généré** | ✅ **oui** |

**Pourquoi c'est important** : quand on dira « France a X liens éditoriaux entrants », ce X **exclut** le lien de menu présent sur 140 pages. Les deux mesures ne se mélangent pas.

---

## 11. Rollback

| Sauvegarde | Contenu |
|---|---|
| Tag `maillage-avant-finalisation` | état avant le chantier |
| `SEO_CHANTIER/FINALISATION_MAILLAGE/BACKUP_AVANT/pages/` | snapshot des 141 pages |
| `BACKUP_AVANT/maillage.js` | le JS d'origine |
| `BACKUP_RESIDUELS/` + `BACKUP_RESIDUELS2/` | pages avant suppression des blocs |
| `BACKUP_HTML_TRONQUE/` | pages avant correction du HTML |
| `data/maillage.json` | source complète — **rien n'est perdu** |

**Restaurer** : `git checkout maillage-avant-finalisation -- .`

---

## 12. Résumé à retenir

| Question | Réponse |
|---|---|
| Où sont les relations ? | `data/maillage.json` |
| Comment les modifier ? | éditer ce fichier, puis build |
| Comment voir le résultat ? | `python3 scripts/build_maillage.py` |
| Comment vérifier ? | `python3 scripts/audit_maillage.py` |
| Qui décide de la pertinence ? | **un humain**, jamais le script |
| Que faire d'un doute ? | ne pas ajouter la relation |
| Où est le bloc généré ? | entre `MAILLAGE_STATIQUE_SEO` et `FIN_MAILLAGE_STATIQUE_SEO` |
| Combien de liens par page ? | **8 maximum**, la pertinence domine |
