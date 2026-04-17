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

import re, json, subprocess, sys
from pathlib import Path

BASE = Path(__file__).parent

# ── 1. Collecter tous les IDs YouTube présents dans les JSON-LD ──────────────
print("=== Étape 1 : Scan des fichiers HTML ===")

html_files = (
    list(BASE.glob("*.html")) +
    list(BASE.glob("articles/*.html")) +
    list(BASE.glob("roadtrips/*.html"))
)

# vid_id → liste de chemins de fichiers qui le contiennent
video_map = {}

for fpath in sorted(html_files):
    try:
        content = fpath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    scripts = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.I | re.DOTALL
    )
    for s in scripts:
        try:
            data = json.loads(s.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get('@type') == 'VideoObject' and not item.get('uploadDate'):
                url = item.get('contentUrl') or item.get('embedUrl') or ''
                m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
                if m:
                    vid_id = m.group(1)
                    video_map.setdefault(vid_id, set()).add(str(fpath))

unique_ids = list(video_map.keys())
total_occurrences = sum(len(v) for v in video_map.values())
print(f"  {len(unique_ids)} IDs YouTube uniques à corriger")
print(f"  {total_occurrences} fichiers HTML concernés")

if not unique_ids:
    print("\n  Rien à corriger — tous les VideoObject ont déjà uploadDate.")
    sys.exit(0)

# ── 2. Vérifier yt-dlp ───────────────────────────────────────────────────────
print("\n=== Étape 2 : Vérification yt-dlp ===")
try:
    r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, check=True)
    print(f"  yt-dlp {r.stdout.strip()} — OK")
    ytdlp_cmd = "yt-dlp"
except FileNotFoundError:
    print("  ERREUR : yt-dlp introuvable.")
    print("  Installe-le avec :  pip install yt-dlp")
    sys.exit(1)

# ── 3. Récupérer les métadonnées YouTube ─────────────────────────────────────
print("\n=== Étape 3 : Récupération YouTube ===")

# Charger le cache existant si présent
cache_file = BASE / "data" / "video_metadata_cache.json"
meta_cache = {}
if cache_file.exists():
    try:
        meta_cache = json.loads(cache_file.read_text(encoding="utf-8"))
        already_cached = [vid for vid in unique_ids if vid in meta_cache and meta_cache[vid].get('uploadDate')]
        if already_cached:
            print(f"  Cache existant : {len(already_cached)} vidéos déjà connues, ignorées")
    except Exception:
        pass

errors = []

for vid_id in unique_ids:
    # Déjà dans le cache avec une date valide → on passe
    if meta_cache.get(vid_id, {}).get('uploadDate'):
        print(f"  ↩  {vid_id} — depuis cache")
        continue

    url = f"https://www.youtube.com/watch?v={vid_id}"
    print(f"  📡 {vid_id}...", end=" ", flush=True)
    try:
        r = subprocess.run(
            [ytdlp_cmd, "--dump-json", "--no-download", "--quiet", "--no-warnings", url],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout)
            upload_raw = d.get('upload_date', '')          # format YYYYMMDD
            duration_s = int(d.get('duration') or 0)

            # Convertir YYYYMMDD → YYYY-MM-DD
            if len(upload_raw) == 8 and upload_raw.isdigit():
                iso_date = f"{upload_raw[:4]}-{upload_raw[4:6]}-{upload_raw[6:]}"
            else:
                iso_date = None

            # Convertir secondes → ISO 8601 duration (PTxHxMxS)
            h, rem = divmod(duration_s, 3600)
            m2, s2 = divmod(rem, 60)
            iso_dur = (f"PT{h}H{m2}M{s2}S" if h else f"PT{m2}M{s2}S") if duration_s else None

            meta_cache[vid_id] = {'uploadDate': iso_date, 'duration': iso_dur}
            print(f"✅  {iso_date}  {iso_dur}")
        else:
            errmsg = (r.stderr or "erreur inconnue").strip()[:80]
            print(f"❌  {errmsg}")
            meta_cache[vid_id] = {'uploadDate': None, 'duration': None}
            errors.append(vid_id)
    except Exception as e:
        print(f"❌  {e}")
        meta_cache[vid_id] = {'uploadDate': None, 'duration': None}
        errors.append(vid_id)

# Sauvegarder le cache
try:
    cache_file.write_text(json.dumps(meta_cache, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Cache sauvegardé : {cache_file.name}")
except Exception as e:
    print(f"\n  ⚠️  Cache non sauvegardé : {e}")

# ── 4. Appliquer les corrections dans les HTML ───────────────────────────────
print("\n=== Étape 4 : Correction des fichiers HTML ===")

files_modified = 0
files_unchanged = 0
schemas_fixed = 0

# Parcourir chaque fichier HTML concerné
all_files = sorted(set(p for paths in video_map.values() for p in paths))

for fpath_str in all_files:
    fpath = Path(fpath_str)
    try:
        original = fpath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️  Lecture impossible : {fpath.name} — {e}")
        continue

    modified = original
    file_changed = False

    # Traiter chaque bloc JSON-LD individuellement
    def process_block(m):
        global schemas_fixed, file_changed
        open_tag  = m.group(1)
        json_body = m.group(2)
        close_tag = m.group(3)

        try:
            data = json.loads(json_body.strip())
        except Exception:
            return m.group(0)   # bloc non parsable → on ne touche pas

        items = data if isinstance(data, list) else [data]
        block_changed = False

        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get('@type') != 'VideoObject':
                continue
            url = item.get('contentUrl') or item.get('embedUrl') or ''
            vid_m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
            if not vid_m:
                continue
            vid_id = vid_m.group(1)
            meta = meta_cache.get(vid_id, {})

            if meta.get('uploadDate') and not item.get('uploadDate'):
                item['uploadDate'] = meta['uploadDate']
                block_changed = True
            if meta.get('duration') and not item.get('duration'):
                item['duration'] = meta['duration']
                block_changed = True

        if not block_changed:
            return m.group(0)

        # Valider le JSON avant de l'écrire
        try:
            new_json = json.dumps(data, indent=2, ensure_ascii=False)
            json.loads(new_json)   # double vérification
        except Exception as e:
            print(f"  ⚠️  JSON invalide après modification ({vid_id}) : {e}")
            return m.group(0)      # on n'écrit pas si invalide

        schemas_fixed += 1
        return f"{open_tag}\n{new_json}\n{close_tag}"

    modified = re.sub(
        r'(<script[^>]*type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)',
        process_block,
        modified,
        flags=re.I | re.DOTALL
    )

    if modified != original:
        # Vérification finale : les JSON-LD sont-ils tous valides ?
        all_blocks = re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            modified, re.I | re.DOTALL
        )
        all_valid = True
        for blk in all_blocks:
            try:
                json.loads(blk.strip())
            except Exception as e:
                print(f"  ❌ JSON invalide après écriture dans {fpath.name} : {e}")
                all_valid = False
                break

        if all_valid:
            fpath.write_text(modified, encoding="utf-8")
            print(f"  ✅  {fpath.name}")
            files_modified += 1
        else:
            print(f"  ⛔  {fpath.name} NON modifié (validation échouée — fichier original conservé)")
    else:
        files_unchanged += 1

# ── 5. Résumé final ──────────────────────────────────────────────────────────
print(f"""
{'='*50}
RÉSUMÉ
{'='*50}
  Vidéos YouTube traitées  : {len(unique_ids)}
  Schémas VideoObject fixés : {schemas_fixed}
  Fichiers HTML modifiés   : {files_modified}
  Fichiers inchangés       : {files_unchanged}
  Erreurs YouTube          : {len(errors)}
""")

if errors:
    print("  IDs non récupérés (à vérifier manuellement) :")
    for e in errors:
        print(f"    https://www.youtube.com/watch?v={e}")

print("""
PROCHAINE ÉTAPE :
  git add -A
  git commit -m "SEO : VideoObject uploadDate + duration sur toutes les vidéos"
  git push origin main

  Puis tester : https://search.google.com/test/rich-results
""")
