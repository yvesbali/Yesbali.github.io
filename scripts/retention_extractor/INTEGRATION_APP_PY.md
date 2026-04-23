# Intégration dans `F:\Automate_YT\app.py`

Ce document explique comment brancher la page Streamlit `page_retention_extractor.py`
dans ton `app.py` existant.

## 1. Installation auto (recommandé)

Depuis le clone Git du repo (`C:\Users\yves\Yesbali.github.io`) :

```powershell
cd C:\Users\yves\Yesbali.github.io
powershell -ExecutionPolicy Bypass -File scripts\retention_extractor\install_to_automate_yt.ps1
```

Le script copie tout ce qu'il faut dans `F:\Automate_YT\`, installe les dépendances
Python et affiche le patch exact à coller dans `app.py`. Aucune modification
automatique d'`app.py` pour ne rien casser.

## 2. Patch manuel dans `app.py`

### Import (en haut du fichier, avec les autres imports de pages)

```python
# Retention Extractor — clips best-of depuis YouTube Analytics
try:
    from page_retention_extractor import page_retention_extractor
    RETENTION_EXTRACTOR_OK = True
except ImportError:
    RETENTION_EXTRACTOR_OK = False
    def page_retention_extractor():
        import streamlit as _st
        _st.error("❌ page_retention_extractor.py introuvable. "
                  "Place-le dans F:\\Automate_YT\\")
```

Ce style `try/except` imite celui que tu as déjà pour `page_content_factory`,
`page_seo_dashboard`, etc. — il évite qu'une page manquante crash toute l'app.

### Routing (dans la section radio button de la sidebar)

Selon le pattern de ton app (je ne l'ai pas sous les yeux, tu l'adaptes) :

**Si tu utilises un dict de pages** :

```python
PAGES = {
    # ... tes entrees existantes ...
    "Retention Extractor (clips best-of)": page_retention_extractor,
}
```

**Si tu utilises des `if/elif` sur `st.session_state["page"]`** :

```python
elif st.session_state["page"] == "Retention Extractor":
    page_retention_extractor()
```

**Si tu as un `st.radio`** :

```python
choice = st.sidebar.radio(
    "Page",
    options=[
        # ... tes pages existantes ...
        "Retention Extractor",
    ],
)
# ...
if choice == "Retention Extractor":
    page_retention_extractor()
```

## 3. Structure finale attendue

```
F:\Automate_YT\
│   app.py                              ← patché pour importer la nouvelle page
│   page_retention_extractor.py         ← copié par install_to_automate_yt.ps1
│   page_content_factory.py             (tes autres pages existantes)
│   page_seo_dashboard.py
│   ...
│   yt_token_analytics.json             (déjà là)
│
├───retention_extractor\                ← copié par install_to_automate_yt.ps1
│       common.py
│       list_candidates.py
│       fetch_retention.py
│       detect_peaks.py
│       extract_clips.py
│       upload_clip.py
│       run_pipeline.py
│       config.json                     (copié depuis config.example.json)
│       config.example.json
│       requirements.txt
│       README.md
│
├───data\retention\                     ← créé au premier run
│       candidates.json
│       plan.json
│       curves\*.json
│       peaks\*.json
│
└───out\clips\                          ← créé au premier run
    └───<video_id>\
            <video_id>_clip01_HH-MM-SS_HH-MM-SS.mp4
            <video_id>_clip01_HH-MM-SS_HH-MM-SS.republish.json
```

## 4. Première utilisation

1. Lance Streamlit : `streamlit run F:\Automate_YT\app.py`
2. Sélectionne "Retention Extractor" dans la sidebar.
3. Le bandeau du haut affiche l'état : token OK, ffmpeg OK, yt-dlp OK, etc.
4. Dans la sidebar, ajuste les paramètres si besoin (durée min, seuils).
5. Clique sur **🚀 Lancer le scenario complet**.
6. Les clips 4K atterrissent dans `F:\Automate_YT\out\clips\<video_id>\`.
7. Chaque clip a son sidecar `.republish.json` avec titre « Souvenir : ... »
   prêt à copier dans YT Studio.
8. Si tu as coché "Uploader automatiquement" : les clips partent en **unlisted**
   sur la chaîne — tu relis dans YT Studio et tu passes en public à la main.

## 5. Mise à jour

Quand je pousse des évolutions sur la branche
`claude/video-retention-extraction-DR6qa` (ou plus tard sur `main` après merge),
il suffit de relancer :

```powershell
cd C:\Users\yves\Yesbali.github.io
git pull
powershell -ExecutionPolicy Bypass -File scripts\retention_extractor\install_to_automate_yt.ps1 -Force
```

Le `-Force` écrase `page_retention_extractor.py` sans demander confirmation.
`config.json` n'est jamais écrasé (tes paramètres perso sont préservés).

## 6. Debug si ça coince

| Symptôme | Cause probable | Fix |
|----------|----------------|-----|
| Bandeau "Token OAuth ❌" | `yt_token_analytics.json` absent de `F:\Automate_YT\` | Lance `python scripts\generate_yt_token.py` depuis le clone Git puis copie le fichier |
| Bandeau "yt-dlp ❌" | pip install pas fait | `pip install yt-dlp requests` |
| Bandeau "ffmpeg ❌" | pas dans le PATH | `winget install Gyan.FFmpeg` + redémarrer PowerShell |
| Rien dans `candidates.json` après "Lister candidats" | Filtres trop stricts (min_views, min_duration) | Baisse les seuils dans la sidebar |
| Beaucoup de `403 Forbidden` au fetch retention | Scope Analytics manquant sur le token | Regénère le token (`generate_yt_token.py`) — le scope `yt-analytics.readonly` est inclus |
| Extraction échoue avec "Requested format not available" | Pas de 2160p sur cette vidéo + `require_4k=true` | Décoche "Exiger 4K" dans la sidebar |
| Upload 401/403 | Token sans scope `youtube.force-ssl` | Regénère (le scope est inclus dans `generate_yt_token.py`) |
