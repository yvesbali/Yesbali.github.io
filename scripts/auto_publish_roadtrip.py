# -*- coding: utf-8 -*-
"""Auto-publication des vidéos YouTube sur les pages road trip LCDMH.

Script CLI autonome conçu pour tourner sur GitHub Actions (sans Streamlit,
sans PC allumé). Il lit un fichier de config JSON, interroge l'API YouTube,
et injecte les nouvelles vidéos dans les pages HTML du repo.

Logique :
  1. Lit auto_publish_config.json (slug, playlist_id, max_main_cards, etc.)
  2. Construit le service YouTube API depuis les secrets GitHub
  3. Récupère les vidéos de la playlist
  4. Détecte les vidéos déjà injectées (par video_id dans le HTML)
  5. Injecte les nouvelles vidéos :
     - Page principale : les N meilleures (par vues), max = max_main_cards
     - Page journal : toutes les nouvelles vidéos
  6. Si la page principale a déjà max_main_cards, remplace par celles
     avec le plus de vues (rotation intelligente)

Usage (GitHub Actions) :
  python scripts/auto_publish_roadtrip.py \
    --config data/roadtrips/slug/auto_publish_config.json

Secrets requis (variables d'environnement) :
  YT_CLIENT_SECRETS : JSON des credentials OAuth2
  YT_TOKEN_ANALYTICS : JSON du token OAuth2 rafraîchi
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════
#  YOUTUBE API — construction autonome du service
# ═══════════════════════════════════════════════════════════════════

def _build_youtube_service():
    """Construit le service YouTube Data API v3 depuis les secrets GitHub."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    # Lire les secrets depuis les variables d'environnement
    token_json_str = os.environ.get("YT_TOKEN_ANALYTICS", "")
    client_secrets_str = os.environ.get("YT_CLIENT_SECRETS", "")

    if not token_json_str:
        raise RuntimeError("Secret YT_TOKEN_ANALYTICS manquant (variable d'environnement vide)")
    if not client_secrets_str:
        raise RuntimeError("Secret YT_CLIENT_SECRETS manquant (variable d'environnement vide)")

    token_data = json.loads(token_json_str)
    client_data = json.loads(client_secrets_str)

    # Extraire client_id et client_secret depuis le format Google
    installed = client_data.get("installed") or client_data.get("web") or {}
    client_id = installed.get("client_id") or client_data.get("client_id", "")
    client_secret = installed.get("client_secret") or client_data.get("client_secret", "")

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id") or client_id,
        client_secret=token_data.get("client_secret") or client_secret,
        scopes=token_data.get("scopes") or ["https://www.googleapis.com/auth/youtube.readonly"],
    )

    return build("youtube", "v3", credentials=creds)


# ═══════════════════════════════════════════════════════════════════
#  YOUTUBE HELPERS
# ═══════════════════════════════════════════════════════════════════

def _extract_youtube_id(url_or_id: str) -> str:
    text = (url_or_id or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    for pattern in [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
        r"(?:live/)([A-Za-z0-9_-]{11})",
    ]:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return text


def _youtube_watch_url(video_id: str) -> str:
    if not video_id or len(video_id) != 11:
        return ""
    return f"https://www.youtube.com/watch?v={video_id}"


def _youtube_thumb(video_id: str) -> str:
    if not video_id:
        return ""
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def _iso8601_duration_seconds(duration: str) -> int:
    """Parse ISO 8601 duration (PT1M30S) en secondes."""
    if not duration:
        return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not m:
        return 0
    h, mn, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mn * 60 + s


def _thumbnail_from_snippet(snippet: dict) -> str:
    thumbs = snippet.get("thumbnails", {})
    for key in ("maxres", "high", "medium", "default"):
        if key in thumbs and thumbs[key].get("url"):
            return thumbs[key]["url"]
    return ""


def _format_date_fr(dt: datetime = None) -> str:
    mois_fr = ['', 'JANVIER', 'FÉVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN',
               'JUILLET', 'AOÛT', 'SEPTEMBRE', 'OCTOBRE', 'NOVEMBRE', 'DÉCEMBRE']
    if dt is None:
        dt = datetime.now()
    return f"{dt.day} {mois_fr[dt.month]} {dt.year}"


def _date_label_from_value(date_str: str) -> str:
    text = (date_str or "").strip()[:10]
    if not text:
        return _format_date_fr()
    try:
        dt = datetime.strptime(text, "%Y-%m-%d")
        return _format_date_fr(dt)
    except ValueError:
        return _format_date_fr()


# ═══════════════════════════════════════════════════════════════════
#  FETCH PLAYLIST VIDEOS (avec viewCount)
# ═══════════════════════════════════════════════════════════════════

def _fetch_playlist_videos(service, playlist_id: str) -> List[Dict[str, Any]]:
    """Récupère toutes les vidéos d'une playlist avec leurs stats (vues)."""
    # 1. Lister les items de la playlist
    items = []
    token = None
    while True:
        resp = service.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=token,
        ).execute()
        items.extend(resp.get("items", []) or [])
        token = resp.get("nextPageToken")
        if not token:
            break

    video_ids = [
        item.get("contentDetails", {}).get("videoId", "")
        for item in items
        if item.get("contentDetails", {}).get("videoId")
    ]
    if not video_ids:
        return []

    item_map = {
        item.get("contentDetails", {}).get("videoId", ""): item
        for item in items
    }

    # 2. Récupérer les métadonnées + statistiques (viewCount)
    videos_meta = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        resp = service.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(chunk),
            maxResults=50,
        ).execute()
        for v in resp.get("items", []) or []:
            videos_meta[v.get("id", "")] = v

    # 3. Construire la liste de sortie
    out = []
    for vid in video_ids:
        item = item_map.get(vid, {})
        meta = videos_meta.get(vid, {})
        snippet = meta.get("snippet", {})
        content = meta.get("contentDetails", {})
        stats = meta.get("statistics", {})
        position = int(item.get("snippet", {}).get("position", 0) or 0)
        duration_s = _iso8601_duration_seconds(content.get("duration", ""))

        out.append({
            "video_id": vid,
            "url": _youtube_watch_url(vid),
            "title": snippet.get("title", "") or f"Vidéo {position + 1}",
            "description": snippet.get("description", "") or "",
            "date_label": _date_label_from_value(snippet.get("publishedAt", "")),
            "thumb": _thumbnail_from_snippet(snippet) or _youtube_thumb(vid),
            "is_short": 0 < duration_s <= 70,
            "position": position,
            "view_count": int(stats.get("viewCount", 0) or 0),
            "published_at": snippet.get("publishedAt", ""),
        })

    out.sort(key=lambda e: e.get("position", 0))
    return out


# ═══════════════════════════════════════════════════════════════════
#  DÉTECTION DES VIDÉOS DÉJÀ INJECTÉES
# ═══════════════════════════════════════════════════════════════════

def _extract_injected_video_ids(html_content: str) -> set:
    """Extrait tous les video_id YouTube déjà présents dans le HTML."""
    ids = set()
    # Chercher dans les URLs YouTube (watch, shorts, embed)
    for pattern in [
        r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"img\.youtube\.com/vi/([A-Za-z0-9_-]{11})",
    ]:
        ids.update(re.findall(pattern, html_content))
    return ids


def _count_cards(html_content: str) -> int:
    """Compte le nombre de cards vidéo sur une page."""
    return (
        html_content.count('class="short-card"')
        + html_content.count('class="journal-card"')
        + html_content.count('class="ecosse-jcard"')
        + html_content.count('class="jnl-card"')
        + html_content.count('class="coming-soon-card"')
    )


# ═══════════════════════════════════════════════════════════════════
#  GÉNÉRATION HTML
# ═══════════════════════════════════════════════════════════════════

def _generate_main_page_card_html(
    video_info: Dict[str, Any],
    date_label: str = "",
    journal_href: str = "",
) -> str:
    """Carte vidéo pour la section aperçu de la page principale."""
    video_url = video_info.get("url", "")
    title = video_info.get("title", "Video YouTube")
    thumb = video_info.get("thumb", "")
    description = (video_info.get("description", "") or "")[:120]
    if len(description) == 120:
        description += "..."

    card_href = journal_href if journal_href else video_url
    card_target = "" if journal_href else ' target="_blank"'

    return f'''
        <!-- Video auto-publiee le {datetime.now().strftime('%Y-%m-%d %H:%M')} | views={video_info.get('view_count', 0)} -->
        <div class="short-card">
            <div class="short-thumb">
                <span class="short-badge">{escape(date_label) if date_label else ""}</span>
                <a href="{escape(card_href)}"{card_target}>
                    <img src="{escape(thumb)}" alt="{escape(title)}" loading="lazy">
                </a>
            </div>
            <div class="short-body">
                <h3>{escape(title)}</h3>
                <p>{escape(description) if description else "Nouvelle video du voyage."}</p>
                <a href="{escape(card_href)}"{card_target} class="btn btn-dark">Voir le short</a>
            </div>
        </div>
'''


def _generate_journal_entry_html(
    video_info: Dict[str, Any],
    date_label: str = "",
) -> str:
    """Entrée vidéo pour la page journal de bord."""
    if not date_label:
        date_label = _format_date_fr()

    video_url = video_info.get("url", "")
    title = video_info.get("title", "Video YouTube")
    description = (video_info.get("description", "") or "")[:250]
    if len(description) == 250:
        description += "..."
    thumb = video_info.get("thumb", "")

    return f'''
        <!-- Entree auto-publiee le {datetime.now().strftime('%Y-%m-%d %H:%M')} -->
        <div class="journal-card">
            <div class="journal-thumb">
                <span class="journal-badge">{escape(date_label)}</span>
                <a href="{escape(video_url)}" target="_blank">
                    <img src="{escape(thumb)}" alt="{escape(title)}" loading="lazy">
                </a>
            </div>
            <div class="journal-body">
                <h3>{escape(title)}</h3>
                <p>{escape(description) if description else "Nouvelle video du voyage."}</p>
                <a href="{escape(video_url)}" target="_blank" style="display:inline-block;width:auto;max-width:fit-content;padding:.55rem 1.2rem;background:#1a1a1a;color:#fff;border-radius:8px;font-size:.85rem;font-weight:600;text-decoration:none;">Voir la video</a>
            </div>
        </div>
'''


# ═══════════════════════════════════════════════════════════════════
#  INJECTION DANS LES PAGES HTML
# ═══════════════════════════════════════════════════════════════════

def _inject_into_main_page(
    main_path: Path,
    videos: List[Dict[str, Any]],
    max_cards: int,
    journal_href: str,
) -> Dict[str, Any]:
    """
    Gère l'injection sur la page principale avec rotation par vues.

    Stratégie :
    - Compte les cards déjà présentes
    - Si < max_cards : ajoute les nouvelles (les plus vues d'abord)
    - Si >= max_cards : remplace les cards existantes par celles avec le
      plus de vues parmi TOUTES les vidéos de la playlist
    """
    result = {"ok": False, "injected": 0, "replaced": False, "trace": []}

    if not main_path.exists():
        result["trace"].append(f"[MAIN] Page introuvable : {main_path}")
        return result

    content = main_path.read_text(encoding="utf-8")
    existing_ids = _extract_injected_video_ids(content)
    current_count = _count_cards(content)
    result["trace"].append(f"[MAIN] Cards existantes : {current_count}/{max_cards}")
    result["trace"].append(f"[MAIN] IDs déjà présents : {len(existing_ids)}")

    # Trier par vues décroissantes
    videos_by_views = sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)
    top_videos = videos_by_views[:max_cards]

    if current_count >= max_cards:
        # ── ROTATION : remplacer toute la section par les top vidéos ──
        result["trace"].append(f"[MAIN] Mode ROTATION — top {max_cards} par vues")

        # Vérifier si les top vidéos sont déjà celles affichées
        top_ids = {v["video_id"] for v in top_videos}
        if top_ids == existing_ids & top_ids and len(top_ids) == max_cards:
            result["trace"].append("[MAIN] Top vidéos déjà affichées, rien à changer")
            result["ok"] = True
            return result

        # Construire le HTML des top vidéos
        new_cards_html = ""
        for v in top_videos:
            new_cards_html += _generate_main_page_card_html(
                v, date_label=v.get("date_label", ""), journal_href=journal_href
            )

        # Remplacer le contenu entre les marqueurs de la grille
        # On cherche la grille et on remplace son contenu
        grid_patterns = [
            r'(<div[^>]*class="[^"]*journal-preview[^"]*"[^>]*>)(.*?)(</div>\s*(?:</div>|</section>))',
            r'(<div[^>]*class="[^"]*jnl-grid[^"]*"[^>]*>)(.*?)(</div>\s*(?:</div>|</section>))',
            r'(<div[^>]*class="[^"]*coming-soon-grid[^"]*"[^>]*>)(.*?)(</div>\s*(?:</div>|</section>))',
            r'(<div[^>]*class="[^"]*shorts-grid[^"]*"[^>]*>)(.*?)(</div>\s*(?:</div>|</section>))',
            r'(<div[^>]*class="[^"]*short-cards[^"]*"[^>]*>)(.*?)(</div>\s*(?:</div>|</section>))',
        ]

        replaced = False
        for pattern in grid_patterns:
            m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if m:
                content = content[:m.start(2)] + "\n" + new_cards_html + "\n        " + content[m.end(2):]
                result["trace"].append(f"[MAIN] ✅ Grille remplacée (pattern: {pattern[:40]}...)")
                replaced = True
                break

        if not replaced:
            result["trace"].append("[MAIN] ⚠️ Impossible de trouver la grille pour rotation")
            result["ok"] = True  # Pas une erreur fatale
            return result

        result["replaced"] = True
        result["injected"] = len(top_videos)

    else:
        # ── AJOUT : injecter les nouvelles vidéos manquantes ──
        new_videos = [v for v in videos_by_views if v["video_id"] not in existing_ids]
        slots_available = max_cards - current_count
        to_inject = new_videos[:slots_available]

        if not to_inject:
            result["trace"].append("[MAIN] Aucune nouvelle vidéo à ajouter")
            result["ok"] = True
            return result

        result["trace"].append(f"[MAIN] Mode AJOUT — {len(to_inject)} vidéo(s) à injecter")

        for v in to_inject:
            entry_html = _generate_main_page_card_html(
                v, date_label=v.get("date_label", ""), journal_href=journal_href
            )

            # Points d'insertion (même logique que l'original)
            insertion_patterns = [
                ("journal-preview", r'(<div[^>]*class="[^"]*journal-preview[^"]*"[^>]*>)'),
                ("jnl-grid", r'(<div[^>]*class="[^"]*jnl-grid[^"]*"[^>]*>)'),
                ("coming-soon-grid", r'(<div[^>]*class="[^"]*coming-soon-grid[^"]*"[^>]*>)'),
                ("shorts-grid", r'(<div[^>]*class="[^"]*shorts-grid[^"]*"[^>]*>)'),
                ("short-cards", r'(<div[^>]*class="[^"]*short-cards[^"]*"[^>]*>)'),
                ("video-grid", r'(<div[^>]*class="[^"]*video-grid[^"]*"[^>]*>)'),
            ]

            inserted = False
            for label, pattern in insertion_patterns:
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    content = content[:m.end()] + "\n" + entry_html + content[m.end():]
                    result["trace"].append(f"[MAIN] ✅ Injecté via '{label}' : {v['title'][:50]}")
                    inserted = True
                    break

            if not inserted:
                # Fallback : avant la première card existante
                for marker in ['class="short-card"', 'class="coming-soon-card"', 'class="jnl-card"']:
                    if marker in content:
                        idx = content.index(marker)
                        tag_start = content.rfind('<', 0, idx)
                        if tag_start >= 0:
                            content = content[:tag_start] + entry_html + "\n        " + content[tag_start:]
                            result["trace"].append(f"[MAIN] ✅ Injecté via fallback '{marker}'")
                            inserted = True
                            break

            if not inserted:
                result["trace"].append(f"[MAIN] ❌ Point d'insertion introuvable pour : {v['title'][:50]}")

            result["injected"] += 1 if inserted else 0

    # Sauvegarder
    backup_path = main_path.with_suffix(".html.backup")
    try:
        shutil.copy2(main_path, backup_path)
    except Exception:
        pass

    main_path.write_text(content, encoding="utf-8")
    result["ok"] = True
    result["trace"].append(f"[MAIN] ✅ Page sauvegardée ({len(content)} car.)")
    return result


def _inject_into_journal_page(
    journal_path: Path,
    videos: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Injecte toutes les nouvelles vidéos dans la page journal."""
    result = {"ok": False, "injected": 0, "trace": []}

    if not journal_path.exists():
        result["trace"].append(f"[JOURNAL] Page introuvable : {journal_path}")
        return result

    content = journal_path.read_text(encoding="utf-8")
    existing_ids = _extract_injected_video_ids(content)
    result["trace"].append(f"[JOURNAL] IDs déjà présents : {len(existing_ids)}")

    new_videos = [v for v in videos if v["video_id"] not in existing_ids]
    # Trier par date de publication (plus récent en haut)
    new_videos.sort(key=lambda v: v.get("published_at", ""), reverse=True)

    if not new_videos:
        result["trace"].append("[JOURNAL] Aucune nouvelle vidéo à ajouter")
        result["ok"] = True
        return result

    result["trace"].append(f"[JOURNAL] {len(new_videos)} vidéo(s) à injecter")

    for v in new_videos:
        entry_html = _generate_journal_entry_html(v, date_label=v.get("date_label", ""))

        insertion_patterns = [
            ("section-kicker", r'(<div[^>]*class="[^"]*section-kicker[^"]*"[^>]*>[^<]*</div>\s*)'),
            ("section.journal-entries", r'(<section[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)'),
            ("div.journal-entries", r'(<div[^>]*class="[^"]*journal-entries[^"]*"[^>]*>)'),
            ("ENTREES DU JOURNAL", r'(ENTR.ES DU JOURNAL</[^>]+>\s*)'),
            ("div#journal-content", r'(<div[^>]*id="journal-content"[^>]*>)'),
        ]

        inserted = False
        for label, pattern in insertion_patterns:
            m = re.search(pattern, content, re.IGNORECASE)
            if m:
                content = content[:m.end()] + "\n" + entry_html + content[m.end():]
                result["trace"].append(f"[JOURNAL] ✅ Injecté via '{label}' : {v['title'][:50]}")
                inserted = True
                break

        if not inserted:
            for marker in ['class="journal-card"', 'class="journal-entry"']:
                if marker in content:
                    idx = content.index(marker)
                    tag_start = content.rfind('<', 0, idx)
                    if tag_start >= 0:
                        content = content[:tag_start] + entry_html + "\n        " + content[tag_start:]
                        result["trace"].append(f"[JOURNAL] ✅ Injecté via fallback '{marker}'")
                        inserted = True
                        break

        if not inserted:
            if 'class="journal-empty"' in content:
                idx = content.index('class="journal-empty"')
                tag_start = content.rfind('<', 0, idx)
                if tag_start >= 0:
                    content = content[:tag_start] + entry_html + "\n        " + content[tag_start:]
                    result["trace"].append("[JOURNAL] ✅ Injecté via fallback 'journal-empty'")
                    inserted = True

        if not inserted:
            result["trace"].append(f"[JOURNAL] ❌ Point d'insertion introuvable pour : {v['title'][:50]}")

        result["injected"] += 1 if inserted else 0

    # Sauvegarder
    backup_path = journal_path.with_suffix(".html.backup")
    try:
        shutil.copy2(journal_path, backup_path)
    except Exception:
        pass

    journal_path.write_text(content, encoding="utf-8")
    result["ok"] = True
    result["trace"].append(f"[JOURNAL] ✅ Page sauvegardée ({len(content)} car.)")
    return result


# ═══════════════════════════════════════════════════════════════════
#  FIND PAGES
# ═══════════════════════════════════════════════════════════════════

def _find_page(repo_root: Path, rel_path: str) -> Optional[Path]:
    """Trouve une page HTML dans le repo."""
    p = repo_root / rel_path
    if p.exists():
        return p
    # Essayer en minuscules
    p_lower = repo_root / rel_path.lower()
    if p_lower.exists():
        return p_lower
    return None


# ═══════════════════════════════════════════════════════════════════
#  MAIN — POINT D'ENTRÉE CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Auto-publication vidéos YouTube LCDMH")
    parser.add_argument("--config", required=True, help="Chemin vers auto_publish_config.json")
    args = parser.parse_args()

    # ── 1. Lire la config ──
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ Config introuvable : {config_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    slug = config.get("slug", "")
    playlist_id = config.get("playlist_id", "")
    max_main_cards = int(config.get("max_main_cards", 3))
    main_page_rel = config.get("main_page", f"roadtrips/{slug}.html")
    journal_page_rel = config.get("journal_page", f"roadtrips/{slug}-journal.html")

    print(f"═══ AUTO-PUBLISH LCDMH ═══")
    print(f"  Slug           : {slug}")
    print(f"  Playlist       : {playlist_id}")
    print(f"  Max main cards : {max_main_cards}")
    print(f"  Main page      : {main_page_rel}")
    print(f"  Journal page   : {journal_page_rel}")

    if not slug or not playlist_id:
        print("❌ slug ou playlist_id manquant dans la config")
        sys.exit(1)

    # ── 2. Déterminer la racine du repo ──
    # Sur GitHub Actions, le repo est checké out dans le working directory
    repo_root = Path.cwd()
    # Si le script est appelé depuis un sous-dossier, remonter
    if not (repo_root / main_page_rel).exists():
        # Essayer depuis le parent du dossier config
        repo_root = config_path.resolve().parent.parent.parent
    if not (repo_root / main_page_rel).exists():
        # Dernier essai : GITHUB_WORKSPACE
        workspace = os.environ.get("GITHUB_WORKSPACE", "")
        if workspace:
            repo_root = Path(workspace)

    print(f"  Repo root      : {repo_root}")

    # ── 3. Trouver les pages HTML ──
    main_path = _find_page(repo_root, main_page_rel)
    journal_path = _find_page(repo_root, journal_page_rel)

    if not main_path:
        print(f"❌ Page principale introuvable : {repo_root / main_page_rel}")
        sys.exit(1)
    if not journal_path:
        print(f"⚠️ Page journal introuvable : {repo_root / journal_page_rel}")
        # Pas fatal — on continue avec la page principale seule

    print(f"  Main path      : {main_path}")
    print(f"  Journal path   : {journal_path}")

    # ── 4. Construire le service YouTube ──
    print("\n── Connexion YouTube API ──")
    try:
        service = _build_youtube_service()
        print("  ✅ Service YouTube construit")
    except Exception as exc:
        print(f"  ❌ Erreur YouTube API : {exc}")
        sys.exit(1)

    # ── 5. Récupérer les vidéos de la playlist ──
    print("\n── Récupération playlist ──")
    try:
        videos = _fetch_playlist_videos(service, playlist_id)
        print(f"  ✅ {len(videos)} vidéo(s) trouvée(s)")
        for v in videos[:5]:
            print(f"     #{v['position']} | {v['view_count']:>6} vues | {'SHORT' if v['is_short'] else 'LONG '} | {v['title'][:60]}")
        if len(videos) > 5:
            print(f"     ... et {len(videos) - 5} autres")
    except Exception as exc:
        print(f"  ❌ Erreur récupération playlist : {exc}")
        sys.exit(1)

    if not videos:
        print("  ℹ️ Playlist vide — rien à faire")
        sys.exit(0)

    # ── 6. Injecter dans la page principale ──
    print(f"\n── Injection page principale (max {max_main_cards}) ──")
    journal_href_for_main = f"/{journal_page_rel}" if journal_path else ""
    main_result = _inject_into_main_page(main_path, videos, max_main_cards, journal_href_for_main)
    for line in main_result.get("trace", []):
        print(f"  {line}")
    if main_result.get("injected", 0) > 0:
        mode = "remplacé" if main_result.get("replaced") else "ajouté"
        print(f"  → {main_result['injected']} vidéo(s) {mode}(es)")
    else:
        print("  → Aucun changement")

    # ── 7. Injecter dans la page journal ──
    if journal_path:
        print(f"\n── Injection page journal ──")
        journal_result = _inject_into_journal_page(journal_path, videos)
        for line in journal_result.get("trace", []):
            print(f"  {line}")
        if journal_result.get("injected", 0) > 0:
            print(f"  → {journal_result['injected']} vidéo(s) ajoutée(s)")
        else:
            print("  → Aucun changement")

    # ── 8. Mettre à jour la config ──
    config["updated_at"] = datetime.now().isoformat(timespec="seconds")
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Config mise à jour : {config_path}")

    # ── Résumé ──
    total_changes = main_result.get("injected", 0) + (
        journal_result.get("injected", 0) if journal_path else 0
    )
    if total_changes > 0:
        print(f"\n🎬 Total : {total_changes} modification(s) — le commit sera fait par GitHub Actions")
    else:
        print(f"\n✅ Aucune nouvelle vidéo à publier — tout est à jour")


if __name__ == "__main__":
    main()
