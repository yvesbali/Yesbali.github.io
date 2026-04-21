"""
Télécharge les sous-titres YouTube des 16 vidéos de la région Annecy
et les sauvegarde en JSON dans data/subtitles/ pour alimenter la nouvelle
page /alpes/annecy-et-ses-environs-moto.html.

Usage (depuis la racine du repo LCDMH_GitHub_Audit) :
    pip install youtube-transcript-api
    python scripts/fetch_subtitles_annecy.py
"""
import json
import sys
from pathlib import Path

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("Installe d'abord : pip install youtube-transcript-api")
    sys.exit(1)

# 16 vidéos : 15 Annecy / Bauges / Aravis + Grand Colombier
VIDEOS = [
    ("1JKi34BG_rU", "Vidéo Annecy"),
    ("QPH5CJRbI0E", "Ballade Benelli TRK 502 et Leoncino A2"),
    ("i1YwQsEgCSQ", "Pont de l'Abîme et tours saint Jacques"),
    ("hqDzIM7M2qs", "Les Bauges 2022 (Bellecombe-en-Bauges)"),
    ("VqwvMUWyCO4", "Precherel Bauges 2022 (Trélod)"),
    ("89PnfLu9pGA", "Abbaye de Tamié, Bauges 2022"),
    ("Wxt4pVsC-ZI", "Château de Duingt 4K drone"),
    ("mvEydQ3lpZ4", "Col des Aravis"),
    ("zFJGnSVl4og", "Col de l'Arpettaz"),
    ("jq02gt4YWlo", "Aravis 3 - Château de Menthon"),
    ("3MrTGcwA_-4", "Découverte des Bauges en Savoie"),
    ("XFgsUOnTWgk", "Château de Miolans, Savoie"),
    ("25QDcsN3K18", "Bonne année des Aravis"),
    ("zdkuNEHqCjE", "Aravis - La Clusaz TRK 702 hiver"),
    ("s38cppyYdvo", "Col de l'Arpetaz TRK 702 & Tiger 900"),
    ("v5Ngfsj8X8o", "Col de la Chambotte & Grand Colombier"),
]

OUT_DIR = Path("data/subtitles")
OUT_DIR.mkdir(parents=True, exist_ok=True)

api = YouTubeTranscriptApi()

ok, miss, errs = 0, 0, 0
for vid, label in VIDEOS:
    out = OUT_DIR / f"{vid}_subtitles.json"
    if out.exists():
        print(f"[SKIP] {vid} — déjà présent ({out.stat().st_size} octets)")
        ok += 1
        continue
    try:
        tr = api.fetch(vid, languages=["fr", "fr-FR", "fr-auto", "en"])
        segs = [{"start": s.start, "duration": s.duration, "text": s.text} for s in tr]
        data = {
            "video_id": vid,
            "label": label,
            "language_code": tr.language_code,
            "is_generated": tr.is_generated,
            "segments": segs,
            "full_text": " ".join(s["text"] for s in segs),
        }
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK]   {vid} — {len(segs)} segments, {len(data['full_text'])} car. ({tr.language_code})")
        ok += 1
    except Exception as e:
        err_name = type(e).__name__
        if "NoTranscriptFound" in err_name or "TranscriptsDisabled" in err_name:
            print(f"[MQ]   {vid} — pas de sous-titres disponibles ({label})")
            miss += 1
        else:
            print(f"[ERR]  {vid} — {err_name}: {str(e)[:120]}")
            errs += 1

print(f"\nTerminé : {ok} récupérés, {miss} sans sous-titres, {errs} erreurs.")
print(f"Fichiers dans : {OUT_DIR.resolve()}")
