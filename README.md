# LCDMH — YouTube Feed automatique

## Structure
- fetch_youtube.py     : script principal (lance via GitHub Actions)
- trips.json           : config des voyages (tu edites ca manuellement)
- js/youtube-feed.js   : affichage flux general sur le site
- js/trip-feed.js      : affichage page voyage dédiée
- data/videos.json     : généré automatiquement (ne pas editer)
- data/trips/*.json    : générés automatiquement (ne pas editer)

## Secrets GitHub requis
- YOUTUBE_CLIENT_ID
- YOUTUBE_CLIENT_SECRET
- YOUTUBE_REFRESH_TOKEN

## Ajouter un voyage
1. Créer la playlist sur YouTube
2. Copier son Playlist ID (PLxxxxxxxxx)
3. Ajouter une entrée dans trips.json
4. Committer → le prochain run génère le JSON automatiquement

## Intégration HTML flux général
    <div id="lcdmh-videos"></div>
    <div id="lcdmh-shorts"></div>
    <script src="js/youtube-feed.js"></script>

## Intégration HTML page voyage
    <div id="trip-videos"></div>
    <div id="trip-shorts"></div>
    <script>const TRIP_SLUG = "ecosse-irlande-2025";</script>
    <script src="js/trip-feed.js"></script>
