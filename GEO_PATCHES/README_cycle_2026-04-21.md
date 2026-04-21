# Cycle GEO LCDMH — Livrables du 21/04/2026

## Ce qui a été livré

### Contenu
- `GEO_PATCHES/youtube_description_template_v2.md` — Template v2 (ajout bloc Q/R + ligne Keywords)
- `GEO_PATCHES/youtube_descriptions_batch_01.md` — 5 descriptions prêtes à coller

### Tracking
- `data/baselines/baseline_T0_2026-04-21.json` — snapshot figé (référence immuable)
- `data/baselines/gsc_queries_2026-04-21.csv` — export GSC (100 requêtes)
- `data/baselines/targets_batch_01.json` — métadonnées des 5 vidéos du cycle
- `data/baselines/genai_tracker.xlsx` — tracker manuel citations ChatGPT/Perplexity/Gemini (42 formules)
- `data/baselines/daily_stats_log.xlsx` — dashboard quotidien (45 formules, 1re ligne déjà écrite)

### Scripts
- `scripts/geo_baseline.py` — génère une baseline T0 depuis les fichiers locaux
- `scripts/geo_snapshot.py` — snapshots T+7/T+14/T+30 + diff automatique vs T0
- `scripts/append_daily_log.py` — ajoute 1 ligne/jour au dashboard quotidien
- `scripts/daily_stats.ps1` — orchestrateur PowerShell (fetch → log → commit → veille)
- `scripts/daily_stats_task.xml` — tâche planifiée Windows avec `WakeToRun=true`

---

## Action #1 — côté toi, sur ton poste Windows

### A. Ajouter les 3 vidéos AFMA au tracking YouTube
Les 3 épisodes Alpes Aventure Moto Festival ne sont pas dans `seo_stats.json` :
- `eNVD7c6g3wM` (EP1 Barcelonnette)
- `dOjvRtEitX4` (EP2 Chute)
- `xQSpEY5EsEc` (EP3 Valcavera)

**Commande à lancer une fois**, après que ta variable `YT_TOKEN_ANALYTICS` est en place :

```powershell
cd F:\LCDMH_GitHub_Audit
python fetch_youtube.py
```

Cela pull les 47 vidéos du canal. Si les 3 AFMA sont publiques, elles apparaîtront automatiquement dans `seo_stats.json` au prochain run. Vérifie ensuite :

```powershell
python -c "import json; d=json.load(open('seo_stats.json',encoding='utf-8')); print([k for k in ('eNVD7c6g3wM','dOjvRtEitX4','xQSpEY5EsEc') if k in d])"
```

### B. Publier les 5 descriptions sur YouTube — **via API, automatisé**

Les descriptions sont prêtes sans placeholder (chapitres retirés — YouTube génère les chapitres auto dès 10 min, ou tu les ajoutes à la main plus tard dans Studio, 2 min par vidéo).

**Si ta variable `YT_TOKEN_ANALYTICS` existe déjà au niveau User** (elle est utilisée par les workflows GitHub et sans doute présente localement) :

```powershell
cd F:\LCDMH_GitHub_Audit
# charge la variable User dans la session en cours
$env:YT_TOKEN_ANALYTICS = [Environment]::GetEnvironmentVariable("YT_TOKEN_ANALYTICS", "User")
# vérifie qu'elle est bien chargée
if ($env:YT_TOKEN_ANALYTICS) { "OK taille=$($env:YT_TOKEN_ANALYTICS.Length)" } else { "ABSENTE" }

# dry-run (lit sans écrire, fait le backup des descriptions actuelles)
python scripts/apply_descriptions_batch_01.py --dry

# publication réelle — écrit via API videos.update
python scripts/apply_descriptions_batch_01.py
```

**Si la variable n'est pas présente** (output "ABSENTE"), lance une fois le bootstrap OAuth :

```powershell
cd F:\LCDMH_GitHub_Audit
python scripts/generate_yt_token.py
```

Il te demande client_id + client_secret (Google Cloud Console → Credentials), ouvre ton navigateur, tu valides, tu colles le code affiché → il génère `yt_token_analytics.json` à la racine du repo (et l'ajoute à `.gitignore`). Les scripts suivants liront ce fichier en fallback automatiquement.

**Sauvegardes automatiques** : avant écriture, `apply_descriptions_batch_01.py` sauvegarde chaque snippet entier dans `logs/yt_backup_<video_id>_<date>.json`. Rollback possible en rejouant manuellement.

**Après la publication** : ouvre `data/baselines/genai_tracker.xlsx` (feuille Tests), saisis la date de publication dans la colonne Notes pour chaque vidéo.

### C. Activer le tracking quotidien automatique
Ouvre une **invite de commandes en administrateur** :

```cmd
schtasks /Create /XML "F:\LCDMH_GitHub_Audit\scripts\daily_stats_task.xml" /TN "LCDMH\DailyStats"
```

Prérequis :
- Dans Panneau de config > Alimentation > Modifier les paramètres avancés > Veille > « Autoriser les minuteries de réveil » = **Activé**.
- Dans BIOS (facultatif, si hibernation S4) : activer « Wake on Scheduled Time » ou équivalent.
- La variable d'environnement `YT_TOKEN_ANALYTICS` doit être définie niveau utilisateur.

Test à la main :
```powershell
pwsh -ExecutionPolicy Bypass -File scripts\daily_stats.ps1 -Dry
```
Si OK, test complet :
```powershell
pwsh -ExecutionPolicy Bypass -File scripts\daily_stats.ps1
```

---

## Action #2 — plan de commits git

On peut pousser tout ça en 4 commits logiques (ou 1 seul si tu préfères). Depuis `F:\LCDMH_GitHub_Audit` :

```powershell
# --- 1. Baselines + targets + GSC export ---
git add data/baselines/baseline_T0_2026-04-21.json `
        data/baselines/gsc_queries_2026-04-21.csv `
        data/baselines/targets_batch_01.json `
        data/baselines/genai_tracker.xlsx `
        data/baselines/daily_stats_log.xlsx
git commit -m "feat(geo): baseline T0 2026-04-21 + trackers GenAI/daily"

# --- 2. Scripts GEO (baseline + snapshot + daily) ---
git add scripts/geo_baseline.py `
        scripts/geo_snapshot.py `
        scripts/append_daily_log.py `
        scripts/daily_stats.ps1 `
        scripts/daily_stats_task.xml
git commit -m "feat(geo): scripts tracking (baseline, snapshot, daily_stats)"

# --- 3. Template v2 + descriptions batch_01 ---
git add GEO_PATCHES/youtube_description_template_v2.md `
        GEO_PATCHES/youtube_descriptions_batch_01.md `
        GEO_PATCHES/README_cycle_2026-04-21.md
git commit -m "feat(yt): template description v2 + batch_01 (5 videos)"

# --- 4. Push ---
git push
```

Si tu préfères un commit unique :
```powershell
git add -A
git commit -m "feat(geo): cycle 2026-04-21 complet — baseline T0, trackers, scripts, descriptions v2"
git push
```

---

## Action #3 — calendrier de suivi

| Date         | Action                                                         | Attendu                                         |
|--------------|----------------------------------------------------------------|-------------------------------------------------|
| **J+0**      | Publier les 5 descriptions v2 sur YouTube                      |                                                 |
| **J+0**      | Faire les 15 tests GenAI (seed queries × 3 outils)             | Baseline genai_tracker remplie                  |
| **J+7**      | `python scripts/geo_snapshot.py --label T7`                    | Premiers signaux YT_SEARCH sur Blackview + Cap Nord |
| **J+14**     | Re-export GSC + `geo_snapshot.py --label T14`                  | Remontée des 3 AFMA en page 2 GSC               |
| **J+30**     | Re-export GSC + `geo_snapshot.py --label T30` + 15 tests GenAI | Cible : +3 à +8 pts YT_SEARCH sur batch_01      |
| **J+60**     | `geo_snapshot.py --label T60`                                  | Effet de compoundage (autres vidéos tirées)     |
| **J+90**     | Bilan cycle — décision batch_02                                | Cibles rapport Word : 150 clics GSC/mois, 50 req top10 |

---

## Limites connues (honnêteté)

- **Timestamps vidéo** : je n'ai pas accès aux vraies timelines des 5 vidéos, donc les chapitres dans les descriptions contiennent des `XX:XX` à remplacer.
- **Liens affiliés** : `[LIEN AMAZON AFFILIÉ]` à remplacer par tes tags réels (`tag=lcdmh-21` ou équivalent).
- **Tracking AFMA** : les 3 épisodes AFMA ne sont pas encore dans `seo_stats.json`. Le premier run de `fetch_youtube.py` règle ça.
- **Wake-on-LAN** : la tâche `WakeToRun=true` fonctionne en veille S3 (par défaut Windows). Si ton PC hiberne en S4, il faut activer le BIOS `Wake from S4/S5` OU changer le mode d'alimentation pour privilégier S3. À vérifier sur ton matériel.
- **Tests GenAI** : le remplissage du `genai_tracker.xlsx` reste **manuel** (pas d'API ChatGPT/Perplexity stable pour l'auto-citation). 5 minutes par outil par cycle.
