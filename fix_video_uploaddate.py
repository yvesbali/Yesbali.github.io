#!/usr/bin/env python3
"""
LCDMH — Fix VideoObject uploadDate + duration
Lance ce script une fois depuis F:\LCDMH_GitHub_Audit\
Il récupère les dates YouTube et corrige tous les JSON-LD.

Prérequis :
    pip install yt-dlp

Usage :
    python fix_video_uploaddate.py
"""

import re, json, glob, os, subprocess, sys
from pathlib import Path

BASE = Path(__file__).parent

# ── 1. Collecter tous les IDs YouTube présents dans les JSON-LD ──────────────
print("=== Étape 1 : Scan des fichiers HTML ===")

html_files = list(BASE.glob("*.html")) + list(BASE.glob("articles/*.html")) + list(BASE.glob("roadtrips/*.html"))

video_map = {}   # {vid_id: [(filepath, block_index), ...]}

for fpath in sorted(html_files):
    with open(fpath, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.I | re.DOTALL
    )
    for i, s in enumerate(scripts):
        try:
            data = json.loads(s.strip())
        except:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get('@type') == 'VideoObject' and not item.get('uploadDate'):
                url = item.get('contentUrl') or item.get('embedUrl') or ''
                m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
                if m:
                    vid_id = m.group(1)
                    video_map.setdefault(vid_id, []).append(str(fpath))

unique_ids = list(video_map.keys())
print(f"  {len(unique_ids)} IDs uniques à corriger dans {sum(len(v) for v in video_map.values())} occurrences")

# ── 2. Récupérer les métadonnées depuis YouTube via yt-dlp ───────────────────
print("\n=== Étape 2 : Récupération YouTube (yt-dlp) ===")

# Check yt-dlp
try:
    subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
    ytdlp_cmd = "yt-dlp"
except:
    print("ERREUR : yt-dlp non trouvé. Installe-le avec : pip install yt-dlp")
    sys.exit(1)

meta_cache = {}
errors = []

for vid_id in unique_ids:
    url = f"https://www.youtube.com/watch?v={vid_id}"
    print(f"  Récupération {vid_id}...", end=" ", flush=True)
    try:
        r = subprocess.run(
            [ytdlp_cmd, "--dump-json", "--no-download", "--quiet", "--no-warnings", url],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout)
            upload_date = d.get('upload_date', '')
            duration_s = d.get('duration', 0)
            iso_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}" if len(upload_date)==8 else None
            h, rem = divmod(int(duration_s or 0), 3600)
            m2, s2 = divmod(rem, 60)
            iso_dur = f"PT{h}H{m2}M{s2}S" if h else f"PT{m2}M{s2}S"
            meta_cache[vid_id] = {'uploadDate': iso_date, 'duration': iso_dur}
            print(f"✅ {iso_date} / {iso_dur}")
        else:
            print(f"❌ yt-dlp error")
            errors.append(vid_id)
            meta_cache[vid_id] = {'uploadDate': None, 'duration': None}
    except Exception as e:
        print(f"❌ {e}")
        errors.append(vid_id)
        meta_cache[vid_id] = {'uploadDate': None, 'duration': None}

# Sauvegarder le cache
cache_file = BASE / "data" / "video_metadata_cache.json"
with open(cache_file, "w", encoding="utf-8") as f:
    json.dump(meta_cache, f, indent=2, ensure_ascii=False)
print(f"\n  Cache sauvegardé : {cache_file}")

# ── 3. Appliquer les corrections dans les HTML ───────────────────────────────
print("\n=== Étape 3 : Correction des fichiers HTML ===")

fixed_count = 0
skipped_count = 0

for fpath_str in sorted(set(p for paths in video_map.values() for p in paths)):
    fpath = Path(fpath_str)
    with open(fpath, encoding="utf-8") as f:
        content = f.read()
    new_content = content

    def fix_jsonld_script(m):
        global fixed_count
        script_open = m.group(1)
        block = m.group(2)
        script_close = m.group(3)
        try:
            data = json.loads(block.strip())
        except:
            return m.group(0)
        items = data if isinstance(data, list) else [data]
        changed = False
        for item in items:
            if item.get('@type') == 'VideoObject':
                url = item.get('contentUrl') or item.get('embedUrl') or ''
                vid_m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
                if vid_m:
                    vid_id = vid_m.group(1)
                    meta = meta_cache.get(vid_id, {})
                    if meta.get('uploadDate') and not item.get('uploadDate'):
                        item['uploadDate'] = meta['uploadDate']
                        changed = True
                    if meta.get('duration') and not item.get('duration'):
                        item['duration'] = meta['duration']
                        changed = True
        if changed:
            fixed_count += 1
            new_json = json.dumps(data if isinstance(data, list) else items[0],
                                  indent=2, ensure_ascii=False)
            return f"{script_open}\n{new_json}\n{script_close}"
        return m.group(0)

    new_content = re.sub(
        r'(<script[^>]+type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)',
        fix_jsonld_script,
        new_content,
        flags=re.I | re.DOTALL
    )
    if new_content != content:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  ✅ Corrigé : {fpath.name}")
    else:
        skipped_count += 1

# ── 4. Résumé ────────────────────────────────────────────────────────────────
print(f"""
=== RÉSUMÉ ===
  Vidéos traitées  : {len(unique_ids)}
  Fichiers HTML modifiés : {fixed_count}
  Fichiers sans changement : {skipped_count}
  Erreurs YouTube : {len(errors)}
""")
if errors:
    print("  IDs avec erreurs (à traiter manuellement) :")
    for e in errors:
        print(f"    {e}")

print("""
=== PROCHAINE ÉTAPE ===
  git add -A
  git commit -m "SEO : VideoObject uploadDate + duration sur toutes les vidéos"
  git push origin main

  Puis tester sur : https://search.google.com/test/rich-results
""")
