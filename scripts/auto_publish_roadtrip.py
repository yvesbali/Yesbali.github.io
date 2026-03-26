# -*- coding: utf-8 -*-
"""Auto-publish road trip videos — LCDMH.

Surveille une playlist YouTube et injecte automatiquement les nouvelles
videos dans la page principale et le journal de bord, puis push sur GitHub.

Usage local (test toutes les 5 min) :
    python auto_publish_roadtrip.py --config data/roadtrips/SLUG/auto_publish_config.json --interval 5

Usage unique (GitHub Actions ou cron) :
    python auto_publish_roadtrip.py --config data/roadtrips/SLUG/auto_publish_config.json

Le fichier auto_publish_config.json est genere par page_generateur_roadbook.py
quand on clique "Sauvegarder la config" dans le panneau YouTube.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional


# ===================================================================
#  CONFIGURATION
# ===================================================================

MODULE_DIR = Path(__file__).resolve().parent
MAX_MAIN_CARDS = 3

MOIS_FR = ['', 'JANVIER', 'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN',
           'JUILLET', 'AOUT', 'SEPTEMBRE', 'OCTOBRE', 'NOVEMBRE', 'DECEMBRE']


# ===================================================================
#  YOUTUBE API
# ===================================================================

def _get_youtube_service():
    """Obtient un service YouTube Data API v3.
    
    Tente dans l'ordre :
    1. Credentials depuis variables d'env (GitHub Actions)
    2. Import page_publication_youtube (local Streamlit)
    3. Import page_gestion_playlists (local Streamlit)
    """
    # 1. Variables d'environnement (GitHub Actions)
    token_json = os.environ.get("YT_TOKEN_ANALYTICS", "")
    client_json = os.environ.get("YT_CLIENT_SECRETS", "")
    if token_json and client_json:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            import json as _json
            token_data = _json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_data)
            return build("youtube", "v3", credentials=creds)
        except Exception as exc:
            _log(f"[AUTH] Env vars presentes mais erreur : {exc}")

    # 2. Module local page_publication_youtube
    try:
        sys.path.insert(0, str(MODULE_DIR))
        import page_publication_youtube as _ppy
        if hasattr(_ppy, "_get_service"):
            return _ppy._get_service()
    except Exception:
        pass

    # 3. Module local page_gestion_playlists
    try:
        import page_gestion_playlists as _pgp
        if hasattr(_pgp, "_get_service"):
            return _pgp._get_service()
    except Exception:
        pass

    raise RuntimeError("Impossible d'obtenir un service YouTube API. "
                       "Configurez YT_TOKEN_ANALYTICS/YT_CLIENT_SECRETS ou "
                       "placez page_publication_youtube.py a cote du script.")


def _fetch_playlist_videos(service, playlist_id: str) -> List[Dict[str, Any]]:
    """Recupere toutes les videos d'une playlist YouTube."""
    items = []
    token = None
    while True:
        resp = service.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=token
        ).execute()
        items.extend(resp.get("items", []) or [])
        token = resp.get("nextPageToken")
        if not token:
            break

    # Recuperer les metadonnees detaillees (duree, etc.)
    video_ids = []
    for item in items:
        vid = (item.get("contentDetails") or {}).get("videoId", "")
        if vid:
            video_ids.append(vid)

    videos_meta = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        resp_v = service.videos().list(
            part="snippet,contentDetails,status",
            id=",".join(chunk),
            maxResults=50
        ).execute()
        for v in resp_v.get("items", []) or []:
            videos_meta[v["id"]] = v

    results = []
    for item in items:
        vid = (item.get("contentDetails") or {}).get("videoId", "")
        if not vid:
            continue
        meta = videos_meta.get(vid, {})
        snippet = meta.get("snippet", {})
        content = meta.get("contentDetails", {})
        duration_s = _iso_duration_seconds(content.get("duration", ""))
        published = snippet.get("publishedAt", "")

        results.append({
            "video_id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": snippet.get("title", f"Video {vid}"),
            "description": (snippet.get("description") or "")[:250],
            "thumb": _best_thumb(snippet) or f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
            "published_at": published,
            "date_label": _format_date_fr_from_iso(published),
            "is_short": 0 < duration_s <= 70,
            "duration_s": duration_s,
        })

    return results


def _best_thumb(snippet: dict) -> str:
    thumbs = snippet.get("thumbnails", {})
    for key in ("maxres", "high", "medium", "default"):
        if key in thumbs and thumbs[key].get("url"):
            return thumbs[key]["url"]
    return ""


def _iso_duration_seconds(iso: str) -> int:
    """Convertit PT1M30S en 90 secondes."""
    if not iso:
        return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mins * 60 + s


def _format_date_fr(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    return f"{dt.day} {MOIS_FR[dt.month]} {dt.year}"


def _format_date_fr_from_iso(iso_str: str) -> str:
    if not iso_str:
        return _format_date_fr()
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return _format_date_fr(dt)
    except Exception:
        return _format_date_fr()


# ===================================================================
#  DETECTION DES VIDEOS DEJA INJECTEES
# ===================================================================

def _extract_injected_video_ids(html_path: Path) -> set:
    """Extrait les video_id YouTube deja presents dans un fichier HTML."""
    if not html_path.exists():
        return set()
    content = html_path.read_text(encoding="utf-8", errors="ignore")
    # Cherche les patterns youtube.com/watch?v=XXXX et youtube.com/shorts/XXXX et img.youtube.com/vi/XXXX
    ids = set()
    for m in re.finditer(r'youtube\.com/(?:watch\?v=|shorts/|vi/)([a-zA-Z0-9_-]{11})', content):
        ids.add(m.group(1))
    return ids


def _count_main_cards(html_path: Path) -> int:
    """Compte les vignettes video deja presentes sur la page principale."""
    if not html_path.exists():
        return 0
    content = html_path.read_text(encoding="utf-8", errors="ignore")
    return (content.count('class="short-card"') +
            content.count('class="journal-card"') +
            content.count('class="ecosse-jcard"'))


# ===================================================================
#  GENERATION HTML
# ===================================================================

def _generate_main_card_html(video: Dict[str, Any], date_label: str, journal_href: str = "") -> str:
    """Genere une carte short-card pour la page principale."""
    url = video["url"]
    title = video["title"]
    thumb = video["thumb"]
    desc = video.get("description", "")[:120]
    if len(desc) == 120:
        desc += "..."
    card_href = journal_href if journal_href else url
    card_target = "" if journal_href else ' target="_blank"'
    return f'''
        <!-- Video importee le {datetime.now().strftime('%Y-%m-%d %H:%M')} -->
        <div class="short-card">
            <div class="short-thumb">
                <span class="short-badge">{escape(date_label)}</span>
                <a href="{escape(card_href)}"{card_target}>
                    <img src="{escape(thumb)}" alt="{escape(title)}" loading="lazy">
                </a>
            </div>
            <div class="short-body">
                <h3>{escape(title)}</h3>
                <p>{escape(desc) if desc else "Nouvelle video du voyage."}</p>
                <a href="{escape(card_href)}"{card_target} class="btn btn-dark">Voir le short</a>
            </div>
        </div>
'''


def _generate_journal_card_html(video: Dict[str, Any], date_label: str) -> str:
    """Genere une entree journal-card pour le journal de bord."""
    url = video["url"]
    title = video["title"]
    thumb = video["thumb"]
    desc = video.get("description", "")[:250]
    if len(desc) == 250:
        desc += "..."
    return f'''
        <!-- Entree importee le {datetime.now().strftime('%Y-%m-%d %H:%M')} -->
        <div class="journal-card">
            <div class="journal-thumb">
                <span class="journal-badge">{escape(date_label)}</span>
                <a href="{escape(url)}" target="_blank">
                    <img src="{escape(thumb)}" alt="{escape(title)}" loading="lazy">
                </a>
            </div>
            <div class="journal-body">
                <h3>{escape(title)}</h3>
                <p>{escape(desc) if desc else "Nouvelle video du voyage."}</p>
                <a href="{escape(url)}" target="_blank" style="display:inline-block;width:auto;max-width:fit-content;padding:.55rem 1.2rem;background:#1a1a1a;color:#fff;border-radius:8px;font-size:.85rem;font-weight:600;text-decoration:none;">Voir la video</a>
            </div>
        </div>
'''


# ===================================================================
#  INJECTION HTML
# ===================================================================

def _inject_into_main(main_path: Path, card_html: str) -> bool:
    """Injecte une carte dans la page principale."""
    content = main_path.read_text(encoding="utf-8")
    
    patterns = [
        (r'(<div[^>]*class="[^"]*journal-preview[^"]*"[^>]*>)', r'\1\n' + card_html),
        (r'(<div[^>]*class="[^"]*jnl-grid[^"]*"[^>]*>)', r'\1\n' + card_html),
        (r'(<div[^>]*class="[^"]*shorts-grid[^"]*"[^>]*>)', r'\1\n' + card_html),
    ]
    
    for pattern, replacement in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
            # Backup
            shutil.copy2(main_path, main_path.with_suffix(".html.backup"))
            main_path.write_text(content, encoding="utf-8")
            return True
    
    _log(f"  [WARN] Aucun point d'insertion trouve dans {main_path.name}")
    return False


def _inject_into_journal(journal_path: Path, card_html: str) -> bool:
    """Injecte une entree dans le journal de bord."""
    content = journal_path.read_text(encoding="utf-8")
    
    patterns = [
        (r'(<div[^>]*class="[^"]*section-kicker[^"]*"[^>]*>[^<]*</div>\s*)', r'\1\n' + card_html),
        (r'(<section[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)', r'\1\n' + card_html),
        (r'(<div[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)', r'\1\n' + card_html),
        (r'(ENTR.ES DU JOURNAL</[^>]+>\s*)', r'\1\n' + card_html),
        (r'(<div[^>]*id="journal-content"[^>]*>)', r'\1\n' + card_html),
    ]
    
    for pattern, replacement in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
            shutil.copy2(journal_path, journal_path.with_suffix(".html.backup"))
            journal_path.write_text(content, encoding="utf-8")
            return True
    
    # Fallback : chercher journal-card ou journal-empty
    for marker in ['class="journal-card"', 'class="journal-entry"', 'class="journal-empty"']:
        if marker in content:
            idx = content.index(marker)
            tag_start = content.rfind('<', 0, idx)
            if tag_start >= 0:
                content = content[:tag_start] + card_html + '\n' + content[tag_start:]
                shutil.copy2(journal_path, journal_path.with_suffix(".html.backup"))
                journal_path.write_text(content, encoding="utf-8")
                return True
    
    _log(f"  [WARN] Aucun point d'insertion trouve dans {journal_path.name}")
    return False


# ===================================================================
#  GIT
# ===================================================================

def _run_git(repo: Path, args: list) -> tuple:
    """Execute une commande git et retourne (ok, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return False, "", str(exc)


def _git_push(repo_path: Path, files: List[Path], commit_msg: str) -> bool:
    """Add, commit, push des fichiers modifies."""
    _log(f"[GIT] Push depuis {repo_path}")
    
    # Pull avant push
    ok, _, err = _run_git(repo_path, ["pull", "--rebase", "origin", "main"])
    if not ok:
        _log(f"[GIT] pull --rebase : {err}")
    
    # Add les fichiers
    for f in files:
        try:
            rel = str(f.relative_to(repo_path)).replace("\\", "/")
        except ValueError:
            # Le fichier n'est pas dans le repo, il faut le copier
            _log(f"[GIT] Fichier hors repo, skip : {f}")
            continue
        ok, _, err = _run_git(repo_path, ["add", rel])
        if ok:
            _log(f"[GIT] add {rel}")
        else:
            _log(f"[GIT] add ERREUR {rel} : {err}")
    
    # Commit
    ok, out, err = _run_git(repo_path, ["commit", "-m", commit_msg])
    if not ok:
        if "nothing to commit" in (err + out):
            _log("[GIT] Rien a committer")
            return True
        _log(f"[GIT] commit ERREUR : {err}")
        return False
    
    # Push
    ok, _, err = _run_git(repo_path, ["push", "origin", "main"])
    if ok:
        _log("[GIT] Push OK")
        return True
    else:
        _log(f"[GIT] push ERREUR : {err}")
        return False


def _sync_file_to_repo(source: Path, publish_root: Path, repo_path: Path) -> Optional[Path]:
    """Copie un fichier du publish_root vers le repo GitHub et retourne le chemin destination."""
    try:
        rel = source.relative_to(publish_root)
    except ValueError:
        return None
    dest = repo_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return dest


# ===================================================================
#  LOGGING
# ===================================================================

_LOG_LINES: List[str] = []

def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    _LOG_LINES.append(line)


def _save_log(project_dir: Path, slug: str):
    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"auto_publish_{slug}_{datetime.now().strftime('%Y%m%d')}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n".join(_LOG_LINES) + "\n\n")
    _LOG_LINES.clear()


# ===================================================================
#  BOUCLE PRINCIPALE
# ===================================================================

def run_once(config: Dict[str, Any]) -> int:
    """Execute un cycle de verification + injection. Retourne le nombre de videos injectees."""
    slug = config["slug"]
    playlist_id = config["playlist_id"]
    publish_root = Path(config.get("publish_root", r"F:\LCDMH")).resolve()
    repo_path = Path(config.get("repo_path", r"F:\LCDMH_GitHub_Audit")).resolve()
    max_main = int(config.get("max_main_cards", MAX_MAIN_CARDS))

    main_page = publish_root / config.get("main_page", f"roadtrips/{slug}.html")
    journal_page = publish_root / config.get("journal_page", f"roadtrips/{slug}-journal.html")

    _log(f"{'='*60}")
    _log(f"[RUN] Verification playlist pour : {slug}")
    _log(f"[RUN] Playlist ID : {playlist_id}")
    _log(f"[RUN] Page principale : {main_page}")
    _log(f"[RUN] Journal : {journal_page}")

    if not main_page.exists():
        _log(f"[ERR] Page principale introuvable : {main_page}")
        return 0
    if not journal_page.exists():
        _log(f"[ERR] Journal introuvable : {journal_page}")
        return 0

    # 1. Recuperer les videos de la playlist
    _log("[API] Connexion YouTube API...")
    try:
        service = _get_youtube_service()
        videos = _fetch_playlist_videos(service, playlist_id)
    except Exception as exc:
        _log(f"[ERR] API YouTube : {exc}")
        return 0

    _log(f"[API] {len(videos)} video(s) dans la playlist")

    # 2. Detecter les videos deja injectees
    known_main = _extract_injected_video_ids(main_page)
    known_journal = _extract_injected_video_ids(journal_page)
    known_all = known_main | known_journal
    _log(f"[DETECT] Videos deja presentes : {len(known_main)} (principale) / {len(known_journal)} (journal)")

    new_videos = [v for v in videos if v["video_id"] not in known_all]
    if not new_videos:
        _log("[DETECT] Aucune nouvelle video a injecter")
        return 0

    _log(f"[DETECT] {len(new_videos)} nouvelle(s) video(s) a injecter")

    # 3. Injecter
    main_card_count = _count_main_cards(main_page)
    injected = 0
    modified_files: List[Path] = []

    for video in new_videos:
        date_label = video.get("date_label") or _format_date_fr()
        _log(f"[INJECT] {video['title']} ({video['video_id']})")

        # Journal de bord : toujours
        journal_html = _generate_journal_card_html(video, date_label)
        if _inject_into_journal(journal_page, journal_html):
            _log(f"  [OK] Journal de bord")
            if journal_page not in modified_files:
                modified_files.append(journal_page)
        else:
            _log(f"  [FAIL] Journal de bord")

        # Page principale : si < max
        if main_card_count < max_main:
            main_html = _generate_main_card_html(
                video, date_label,
                journal_href=f"/roadtrips/{slug}-journal.html"
            )
            if _inject_into_main(main_page, main_html):
                main_card_count += 1
                _log(f"  [OK] Page principale ({main_card_count}/{max_main})")
                if main_page not in modified_files:
                    modified_files.append(main_page)
            else:
                _log(f"  [FAIL] Page principale")
        else:
            _log(f"  [SKIP] Page principale pleine ({main_card_count}/{max_main})")

        injected += 1

    # 4. Sync vers repo Git + push
    if modified_files and repo_path.exists():
        git_files = []
        for f in modified_files:
            dest = _sync_file_to_repo(f, publish_root, repo_path)
            if dest:
                git_files.append(dest)
                _log(f"[SYNC] {f.name} -> {dest}")

        if git_files:
            commit_msg = f"Auto-publish: {injected} video(s) {slug}"
            _git_push(repo_path, git_files, commit_msg)
    else:
        _log("[GIT] Pas de fichiers modifies ou repo absent")

    _log(f"[DONE] {injected} video(s) injectee(s)")
    return injected


def main():
    parser = argparse.ArgumentParser(description="Auto-publish road trip videos LCDMH")
    parser.add_argument("--config", required=True, help="Chemin vers auto_publish_config.json")
    parser.add_argument("--interval", type=int, default=0,
                        help="Intervalle en minutes entre chaque verification (0 = une seule fois)")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"ERREUR : fichier config introuvable : {config_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    _log(f"[INIT] Config chargee : {config_path}")
    _log(f"[INIT] Slug : {config.get('slug')}")
    _log(f"[INIT] Playlist : {config.get('playlist_name')} ({config.get('playlist_id')})")

    if args.interval > 0:
        _log(f"[INIT] Mode boucle : verification toutes les {args.interval} min")
        _log(f"[INIT] Ctrl+C pour arreter")
        try:
            while True:
                run_once(config)
                project_dir = Path(config.get("publish_root", MODULE_DIR))
                _save_log(project_dir, config.get("slug", "unknown"))
                _log(f"[WAIT] Prochaine verification dans {args.interval} min...")
                time.sleep(args.interval * 60)
        except KeyboardInterrupt:
            _log("[STOP] Arret demande par l'utilisateur")
    else:
        count = run_once(config)
        project_dir = Path(config.get("publish_root", MODULE_DIR))
        _save_log(project_dir, config.get("slug", "unknown"))
        sys.exit(0 if count >= 0 else 1)


if __name__ == "__main__":
    main()
