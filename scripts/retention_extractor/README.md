# retention_extractor — extraire les meilleurs moments des vidéos LCDMH

Pipeline 4 étapes qui lit les courbes de rétention YouTube Analytics, détecte
les pics, télécharge automatiquement les passages en 4K et prépare des
sidecars de republication avec titre « Souvenir : ... ».

Conçu pour les périodes de panne moto : ré-utilise les contenus existants
sans tourner une seule image.

## Périmètre par défaut : vidéos moto France

La config `config.example.json` exclut Cap Nord, Écosse, Irlande, Norvège et
les vidéos « Jour X » — soit exactement la série France / tests / équipement.
Modifie `exclude_title_keywords` / `exclude_playlists` / `include_title_keywords`
pour changer le périmètre.

## Pré-requis (sur le poste Windows F:\)

1. **Python 3.10+**
2. **yt-dlp** et **ffmpeg** dans le PATH :
   ```powershell
   pip install -r scripts/retention_extractor/requirements.txt
   winget install Gyan.FFmpeg
   ```
3. **Credentials OAuth** déjà en place : le fichier `yt_token_analytics.json`
   à la racine du repo (il l'est déjà — scope `yt-analytics.readonly` inclus).
   Sinon :
   ```powershell
   python scripts/generate_yt_token.py
   ```

## Installation rapide

```powershell
cd F:\Automate_YT\Yesbali.github.io  # ou ton clone du repo
pip install -r scripts/retention_extractor/requirements.txt
copy scripts\retention_extractor\config.example.json scripts\retention_extractor\config.json
```

Édite `config.json` au besoin (seuils, qualité, template de titre).

## Lancer le pipeline complet

```powershell
python scripts/retention_extractor/run_pipeline.py
```

Première exécution : compte ~30 s par vidéo pour Analytics + 1-3 min par clip
à télécharger en 4K (selon la connexion). Tout est idempotent : relancer ne
re-fetch ni re-télécharge que les nouveautés.

### Options utiles

```powershell
# Test à sec : prépare le plan mais sans téléchargement
python scripts/retention_extractor/run_pipeline.py --dry --limit 5

# Ne traite qu'une vidéo précise (debug)
python scripts/retention_extractor/run_pipeline.py --only RaWIvYQ-JiE --debug-peaks

# Refaire uniquement l'extraction (plan déjà généré)
python scripts/retention_extractor/run_pipeline.py --skip-list --skip-fetch --skip-detect
```

## Étapes individuelles

Tu peux aussi lancer chaque étape à la main :

| Étape | Script | Entrée | Sortie |
|-------|--------|--------|--------|
| 1 | `list_candidates.py` | (API YouTube Data) | `data/retention/candidates.json` |
| 2 | `fetch_retention.py` | candidates.json | `data/retention/curves/<vid>.json` |
| 3 | `detect_peaks.py`   | curves/          | `data/retention/peaks/<vid>.json` + `plan.json` |
| 4 | `extract_clips.py`  | plan.json        | `out/clips/<vid>/*.mp4` + `*.republish.json` |

## Qualité 4K

La config `yt_dlp_format` tente dans l'ordre :
`2160p -> 1440p -> 1080p -> meilleure dispo`. Mets `"require_4k": true`
si tu veux skipper les vidéos qui ne sont pas en 2160p natif.

La coupe utilise `--download-sections` + `--force-keyframes-at-cuts` :
la découpe est précise à la frame, et on ne télécharge QUE le passage
demandé (pas la vidéo complète), ce qui divise par 5 à 10 le volume.

## Détection des pics (detect_peaks.py)

Algorithme pur Python, sans scipy :

1. Lissage moving-average (fenêtre `smoothing_window`, défaut 3).
2. Baseline = médiane de la courbe lissée.
3. Zone = suite de points où `audienceWatchRatio > baseline × peak_threshold_ratio`
   (défaut 1.05 = 5 % au-dessus de la médiane).
4. Zones trop courtes filtrées (`min_zone_duration_ratio`, défaut 3 % de la durée).
5. Fenêtre finale : `[zone_start - pad_before, zone_end + pad_after]`
   (défaut ±60 s autour du pic).
6. Contrainte sur la durée finale : `[min_clip_duration_s, max_clip_duration_s]`
   (défaut 3 à 6 minutes).
7. Fusion des fenêtres qui se chevauchent, tri par score, top `max_clips_per_video`
   (défaut 2).
8. Fallback : si aucune zone n'émerge, on prend la meilleure fenêtre glissante
   de `min_clip_duration_s` (moyenne de rétention la plus haute).

## Sidecar de republication

Pour chaque clip, un `*.republish.json` est écrit à côté du .mp4 :

```json
{
  "source_video_id": "RaWIvYQ-JiE",
  "source_url": "https://www.youtube.com/watch?v=RaWIvYQ-JiE",
  "source_title": "Schuberth C5 vs HJC RPHA 91 : Quel casque modulable choisir ?",
  "start_ts": "00:05:42",
  "end_ts": "00:09:55",
  "duration_s": 253.0,
  "suggested_title": "Souvenir : Schuberth C5 vs HJC RPHA 91 : Quel casque modulable choisir ?",
  "suggested_description": "Extrait de la video originale : https://...\nTournage : 2026-04-08\n...",
  "suggested_tags": ["moto", "voyage moto", "roadtrip moto", "lcdmh"]
}
```

Le préfixe `Souvenir :` est voulu : ça signale au viewer (et à l'algorithme)
que c'est un best-of / rétrospective, pas une nouvelle vidéo, ce qui évite
l'effet négatif de republier à l'identique. Tu peux changer le template dans
`config.json` → `republish_title_template` (variables dispo : `{title}`,
`{start_ts}`).

## Structure des fichiers produits

```
data/retention/
  candidates.json          # Liste + stats du filtrage
  curves/<video_id>.json   # Courbe brute (101 points)
  peaks/<video_id>.json    # Zones détectées + fenêtres
  plan.json                # Agrégat de toutes les fenêtres, triées par score
  extract_report.json      # Bilan de la dernière extraction
  fetch_failures.json      # Vidéos pour lesquelles Analytics a refusé

out/clips/<video_id>/
  <video_id>_clip01_00-05-42_00-09-55.mp4
  <video_id>_clip01_00-05-42_00-09-55.republish.json
  <video_id>_clip02_...
```

Les dossiers `data/retention/` et `out/clips/` sont ignorés par Git (voir
`.gitignore`), rien ne finit accidentellement sur GitHub Pages.

## Workflow type quand la moto est en panne

1. `python scripts/retention_extractor/run_pipeline.py --dry --limit 10`
   → on regarde `data/retention/plan.json` pour valider les fenêtres proposées.
2. Si OK : `python scripts/retention_extractor/run_pipeline.py --limit 10`
   → les 10 meilleurs clips sont téléchargés dans `out/clips/`.
3. Pour chaque clip, ouvrir le `.republish.json` à côté, copier le
   `suggested_title` / `suggested_description` dans YouTube Studio, uploader.
4. Option : sauvegarder `out/clips/` sur Google Drive pour conserver les
   rushs décompoupés (ils sont déjà en 4K, on peut les réutiliser pour
   d'autres montages).

## Dépendances et auth en résumé

- `yt_token_analytics.json` → déjà au repo (scope `yt-analytics.readonly`).
- `requests` → déjà utilisé partout dans le repo.
- `yt-dlp` + `ffmpeg` → à installer une fois sur le poste.
- Aucune dépendance scipy/numpy : tout est en Python standard.
