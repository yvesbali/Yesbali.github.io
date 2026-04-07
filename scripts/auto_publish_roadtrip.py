# -*- coding: utf-8 -*-
"""
LCDMH — Auto-publish Road Trip CLI v3.1
=======================================
Script CLI pour GitHub Actions qui surveille une playlist YouTube
et injecte automatiquement les nouvelles vidéos dans les pages road trip.

v3.1 (07/04/2026):
- FILTRE STRICT : seules les vidéos PUBLIQUES sont importées
- Ignore "Deleted video", "Private video" (titre YouTube)
- Ignore status.privacyStatus != "public" (private, unlisted)
- Ignore les vidéos sans métadonnées (pas accessible)

v3.0: 
- Top 3 shorts par NOMBRE DE VUES sur la page principale
- Journal : toutes les vidéos en ordre chronologique
- Formatage corrigé pour correspondre au CSS
- Ignore les "Deleted video" et "Private video"

Usage:
    python auto_publish_roadtrip.py --config data/roadtrips/xxx/auto_publish_config.json
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Set

# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parent.parent  # Racine du repo GitHub


# ═══════════════════════════════════════════════════════════════════
#  YOUTUBE API (via secrets GitHub)
# ═══════════════════════════════════════════════════════════════════

def get_youtube_service():
    """Crée un service YouTube API à partir des secrets GitHub."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    
    # Lire les credentials depuis les variables d'environnement
    client_secrets_json = os.environ.get("YT_CLIENT_SECRETS", "")
    token_json = os.environ.get("YT_TOKEN_ANALYTICS", "")
    
    if not client_secrets_json or not token_json:
        raise RuntimeError(
            "Variables d'environnement manquantes: YT_CLIENT_SECRETS et/ou YT_TOKEN_ANALYTICS. "
            "Vérifiez les secrets GitHub."
        )
    
    try:
        token_data = json.loads(token_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"YT_TOKEN_ANALYTICS n'est pas un JSON valide: {e}")
    
    # Créer les credentials
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes", ["https://www.googleapis.com/auth/youtube.readonly"]),
    )
    
    return build("youtube", "v3", credentials=creds)


def fetch_playlist_videos_with_stats(playlist_id: str) -> List[Dict[str, Any]]:
    """Récupère toutes les vidéos d'une playlist YouTube AVEC les statistiques (vues)."""
    service = get_youtube_service()
    
    items: List[Dict[str, Any]] = []
    token = None
    
    # Récupérer les items de la playlist
    while True:
        response = service.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=token
        ).execute()
        
        items.extend(response.get("items", []))
        token = response.get("nextPageToken")
        if not token:
            break
    
    # Récupérer les IDs des vidéos
    video_ids = [item.get("contentDetails", {}).get("videoId", "") for item in items]
    video_ids = [v for v in video_ids if v]
    
    # Récupérer les métadonnées ET statistiques des vidéos
    videos_meta: Dict[str, Dict] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        if not chunk:
            continue
        # IMPORTANT: On ajoute "statistics" pour avoir viewCount
        resp = service.videos().list(
            part="snippet,contentDetails,status,statistics",
            id=",".join(chunk),
            maxResults=50
        ).execute()
        for v in resp.get("items", []):
            videos_meta[v.get("id", "")] = v
    
    # Construire la liste des vidéos
    result: List[Dict[str, Any]] = []
    for item in items:
        video_id = item.get("contentDetails", {}).get("videoId", "")
        if not video_id:
            continue
        
        meta = videos_meta.get(video_id, {})
        snippet = meta.get("snippet", item.get("snippet", {}))
        content = meta.get("contentDetails", {})
        statistics = meta.get("statistics", {})
        status = meta.get("status", {})
        position = item.get("snippet", {}).get("position", 0)
        
        # ═══ FILTRE DE VISIBILITÉ ═══
        # Vérifier le statut de confidentialité de la vidéo
        privacy_status = status.get("privacyStatus", "")
        
        # Vérifier si la vidéo est disponible via son titre
        title = snippet.get("title", "")
        
        # ═══ RÈGLES DE FILTRAGE ═══
        # 1. Ignorer les vidéos supprimées ou privées (titre générique YouTube)
        if "Deleted video" in title or "Private video" in title:
            print(f"   ⚠️ Vidéo ignorée (supprimée/privée - titre): {video_id}")
            continue
        
        # 2. Ignorer les vidéos non publiques (private, unlisted)
        if privacy_status and privacy_status != "public":
            print(f"   ⚠️ Vidéo ignorée (statut {privacy_status}): {title[:40]}... [{video_id}]")
            continue
        
        # 3. Ignorer les vidéos sans métadonnées (vidéo pas accessible)
        if not meta:
            print(f"   ⚠️ Vidéo ignorée (pas de métadonnées): {video_id}")
            continue
        
        # Calculer la durée
        duration_s = parse_iso8601_duration(content.get("duration", ""))
        
        # Extraire la date de publication
        published = snippet.get("publishedAt", "")
        date_label = format_date_label(published) if published else ""
        
        # Récupérer le nombre de vues
        view_count = int(statistics.get("viewCount", 0))
        like_count = int(statistics.get("likeCount", 0))
        
        # Thumbnail
        thumbs = snippet.get("thumbnails", {})
        thumb = (
            thumbs.get("maxres", {}).get("url") or
            thumbs.get("high", {}).get("url") or
            thumbs.get("medium", {}).get("url") or
            thumbs.get("default", {}).get("url") or
            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        )
        
        result.append({
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": title,
            "description": snippet.get("description", ""),
            "thumb": thumb,
            "date_label": date_label,
            "published_at": published,
            "position": position,
            "is_short": 0 < duration_s <= 70,
            "view_count": view_count,
            "like_count": like_count,
        })
    
    return result


def parse_iso8601_duration(duration: str) -> int:
    """Parse une durée ISO 8601 (ex: PT1M30S) en secondes."""
    if not duration:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def format_date_label(iso_date: str) -> str:
    """Convertit une date ISO en label français (ex: 25 MARS 2026)."""
    if not iso_date:
        return ""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        months_fr = [
            "", "JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN",
            "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"
        ]
        return f"{dt.day} {months_fr[dt.month]} {dt.year}"
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════
#  DÉTECTION VIDÉOS DÉJÀ INJECTÉES
# ═══════════════════════════════════════════════════════════════════

def get_injected_video_ids(html_path: Path) -> Set[str]:
    """Extrait les IDs des vidéos déjà injectées dans une page HTML."""
    if not html_path.exists():
        return set()
    
    content = html_path.read_text(encoding="utf-8", errors="replace")
    
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'data-video-id="([a-zA-Z0-9_-]{11})"',
        r'img\.youtube\.com/vi/([a-zA-Z0-9_-]{11})/',
    ]
    
    video_ids = set()
    for pattern in patterns:
        matches = re.findall(pattern, content)
        video_ids.update(matches)
    
    return video_ids


# ═══════════════════════════════════════════════════════════════════
#  GÉNÉRATION HTML - JOURNAL (format horizontal)
# ═══════════════════════════════════════════════════════════════════

def generate_journal_entry_html(video: Dict[str, Any]) -> str:
    """Génère le HTML d'une entrée journal (format carte horizontale)."""
    title = escape(video.get("title", ""))
    desc_raw = video.get("description", "")
    # Nettoyer la description (enlever les liens, limiter la longueur)
    desc_clean = re.sub(r'http\S+', '', desc_raw)
    desc_clean = re.sub(r'---.*', '', desc_clean, flags=re.DOTALL)
    desc = escape(desc_clean.strip()[:180])
    
    thumb = video.get("thumb", "")
    url = video.get("url", "")
    date_label = video.get("date_label", "")
    video_id = video.get("video_id", "")
    view_count = video.get("view_count", 0)
    
    return f'''<article class="journal-card" data-video-id="{video_id}">
<div class="journal-thumb" style="background-image:url('{thumb}')">
<img src="{thumb}" alt="{title}" loading="lazy">
<span class="journal-badge">{date_label}</span>
</div>
<div class="journal-body">
<h2>{title}</h2>
<p>{desc}{'...' if len(desc) >= 180 else ''}</p>
<p style="font-size:.8rem;color:#999;margin-top:.5rem">👁️ {view_count:,} vues</p>
<a class="btn-sm" href="{url}" target="_blank" rel="noopener">Voir la vidéo ▶</a>
</div>
</article>'''


# ═══════════════════════════════════════════════════════════════════
#  GÉNÉRATION HTML - PAGE PRINCIPALE (grille 3 colonnes)
# ═══════════════════════════════════════════════════════════════════

def generate_main_card_html(video: Dict[str, Any], entry_num: int = 1) -> str:
    """Génère le HTML d'une carte pour la page principale (format grille)."""
    title = escape(video.get("title", ""))
    desc_raw = video.get("description", "")
    desc_clean = re.sub(r'http\S+', '', desc_raw)
    desc_clean = re.sub(r'---.*', '', desc_clean, flags=re.DOTALL)
    desc = escape(desc_clean.strip()[:100])
    
    thumb = video.get("thumb", "")
    url = video.get("url", "")
    video_id = video.get("video_id", "")
    view_count = video.get("view_count", 0)
    date_label = video.get("date_label", "")
    
    return f'''<article class="jc" data-video-id="{video_id}">
<img src="{thumb}" alt="{title}">
<div class="jb">
<div class="jm">{date_label} • 👁️ {view_count:,} vues</div>
<h3>{title[:50]}{'...' if len(title) > 50 else ''}</h3>
<p>{desc}{'...' if len(desc) >= 100 else ''}</p>
<div class="ja"><a class="btn btn-d" href="{url}" target="_blank" rel="noopener">Voir le short</a></div>
</div>
</article>'''


# ═══════════════════════════════════════════════════════════════════
#  INJECTION HTML - JOURNAL
# ═══════════════════════════════════════════════════════════════════

def rebuild_journal(journal_path: Path, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Reconstruit entièrement la section journal avec toutes les vidéos.
    Trie par date de publication (plus récent en premier).
    """
    result = {"ok": False, "message": "", "trace": [], "count": 0}
    
    if not journal_path.exists():
        result["message"] = f"Journal introuvable: {journal_path}"
        return result
    
    content = journal_path.read_text(encoding="utf-8")
    
    # Trier les vidéos par date de publication (plus récent en premier)
    videos_sorted = sorted(
        videos,
        key=lambda v: v.get("published_at", ""),
        reverse=True
    )
    
    # Générer le HTML pour toutes les vidéos
    entries_html = []
    for video in videos_sorted:
        entry = generate_journal_entry_html(video)
        entries_html.append(entry)
    
    # Chercher le point d'insertion
    # Pattern: après <div class="section-kicker">Entrées du journal</div>
    # et remplacer jusqu'à </main> ou <article class="journal-empty">
    
    kicker_pattern = r'(<div class="section-kicker">Entrées du journal</div>)'
    
    if re.search(kicker_pattern, content, re.IGNORECASE):
        # Trouver la position après le kicker
        match = re.search(kicker_pattern, content, re.IGNORECASE)
        insert_pos = match.end()
        
        # Trouver la fin de la section (</main> ou journal-empty)
        remaining = content[insert_pos:]
        
        # Chercher journal-empty ou </main>
        end_match = re.search(r'<article class="journal-empty">.*?</article>|</main>', remaining, re.DOTALL)
        
        if end_match:
            # Construire le nouveau contenu
            if '<article class="journal-empty">' in end_match.group():
                # Remplacer journal-empty par les vraies entrées
                new_content = (
                    content[:insert_pos] + 
                    "\n" + "\n".join(entries_html) + "\n" +
                    content[insert_pos + end_match.start() + len(end_match.group()):]
                )
            else:
                # Insérer avant </main>
                new_content = (
                    content[:insert_pos] + 
                    "\n" + "\n".join(entries_html) + "\n" +
                    remaining
                )
            
            result["ok"] = True
            result["trace"].append(f"✅ {len(entries_html)} entrées insérées après section-kicker")
        else:
            # Fallback: insérer juste après le kicker
            new_content = (
                content[:insert_pos] + 
                "\n" + "\n".join(entries_html) + "\n" +
                content[insert_pos:]
            )
            result["ok"] = True
            result["trace"].append(f"✅ {len(entries_html)} entrées (fallback)")
    else:
        result["message"] = "Section-kicker 'Entrées du journal' non trouvé"
        return result
    
    # Backup + écriture
    backup = journal_path.with_suffix(".html.backup")
    shutil.copy2(journal_path, backup)
    journal_path.write_text(new_content, encoding="utf-8")
    
    result["count"] = len(entries_html)
    result["message"] = f"{len(entries_html)} entrées dans le journal"
    return result


# ═══════════════════════════════════════════════════════════════════
#  INJECTION HTML - PAGE PRINCIPALE (Top 3 par vues)
# ═══════════════════════════════════════════════════════════════════

def inject_top_videos_into_main(main_path: Path, videos: List[Dict[str, Any]], max_cards: int = 3) -> Dict[str, Any]:
    """
    Injecte les TOP vidéos (par nombre de vues) dans la page principale.
    Utilise les marqueurs <!-- AUTO-PUBLISH-SHORTS-START --> et <!-- AUTO-PUBLISH-SHORTS-END -->
    """
    result = {"ok": False, "message": "", "trace": [], "count": 0}
    
    if not main_path.exists():
        result["message"] = f"Page principale introuvable: {main_path}"
        return result
    
    content = main_path.read_text(encoding="utf-8")
    
    # Vérifier si les marqueurs existent
    start_marker = "<!-- AUTO-PUBLISH-SHORTS-START -->"
    end_marker = "<!-- AUTO-PUBLISH-SHORTS-END -->"
    
    if start_marker not in content or end_marker not in content:
        result["message"] = "Marqueurs AUTO-PUBLISH-SHORTS non trouvés"
        result["trace"].append("❌ Marqueurs START/END absents dans la page")
        return result
    
    # TRIER PAR NOMBRE DE VUES (décroissant)
    videos_by_views = sorted(
        videos,
        key=lambda v: v.get("view_count", 0),
        reverse=True
    )
    
    # Afficher le classement
    print(f"\n   📊 Classement par vues:")
    for i, v in enumerate(videos_by_views[:5]):
        marker = "⭐" if i < max_cards else "  "
        print(f"      {marker} {i+1}. {v['title'][:40]}... ({v['view_count']:,} vues)")
    
    # Générer le HTML pour les top vidéos
    cards_html = []
    for i, video in enumerate(videos_by_views[:max_cards]):
        card = generate_main_card_html(video, entry_num=i + 1)
        cards_html.append(card)
    
    # Construire le nouveau contenu entre les marqueurs
    new_content = "\n" + "\n".join(cards_html) + "\n"
    
    # Remplacer le contenu entre les marqueurs
    pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
    replacement = start_marker + new_content + end_marker
    
    new_page_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Backup + écriture
    backup = main_path.with_suffix(".html.backup")
    shutil.copy2(main_path, backup)
    main_path.write_text(new_page_content, encoding="utf-8")
    
    result["ok"] = True
    result["count"] = len(cards_html)
    result["message"] = f"Top {len(cards_html)} vidéos (par vues) injectées"
    result["trace"].append(f"✅ Top {len(cards_html)} par nombre de vues")
    
    return result


# ═══════════════════════════════════════════════════════════════════
#  MAIN CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Auto-publish road trip videos from YouTube playlist")
    parser.add_argument("--config", required=True, help="Path to auto_publish_config.json")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas modifier les fichiers")
    args = parser.parse_args()
    
    # Charger la configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ Config introuvable: {config_path}")
        sys.exit(1)
    
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    
    print("=" * 60)
    print("LCDMH — Auto-publish Road Trip CLI v3.1")
    print("🎯 Top 3 par VUES + Journal complet")
    print("🔒 Filtre: UNIQUEMENT les vidéos PUBLIQUES")
    print(f"Config: {config_path}")
    print("=" * 60)
    
    # Extraire les paramètres
    playlist_id = config.get("playlist_id", "")
    playlist_name = config.get("playlist_name", "")
    journal_page = config.get("journal_page", "")
    main_page = config.get("main_page", "")
    max_main_cards = config.get("max_main_cards", 3)
    slug = config.get("slug", "")
    
    print(f"\n📋 Playlist: {playlist_name}")
    print(f"   ID: {playlist_id}")
    print(f"   Journal: {journal_page}")
    print(f"   Main: {main_page}")
    print(f"   Max cards (top vues): {max_main_cards}")
    
    # Chemins des fichiers HTML
    journal_path = REPO_ROOT / journal_page
    main_path = REPO_ROOT / main_page
    
    print(f"\n📂 Chemins:")
    print(f"   Journal: {journal_path} {'✅' if journal_path.exists() else '❌'}")
    print(f"   Main: {main_path} {'✅' if main_path.exists() else '❌'}")
    
    if not journal_path.exists():
        print(f"\n❌ Le fichier journal n'existe pas: {journal_path}")
        sys.exit(1)
    
    # Récupérer les vidéos de la playlist AVEC les stats
    print(f"\n🎬 Récupération des vidéos YouTube (avec statistiques)...")
    try:
        videos = fetch_playlist_videos_with_stats(playlist_id)
        print(f"   ✅ {len(videos)} vidéos valides trouvées")
    except Exception as e:
        print(f"❌ Erreur YouTube API: {e}")
        sys.exit(1)
    
    if not videos:
        print("   Aucune vidéo valide dans la playlist.")
        sys.exit(0)
    
    # Afficher les stats globales
    total_views = sum(v.get("view_count", 0) for v in videos)
    print(f"   📊 Total vues playlist: {total_views:,}")
    
    if args.dry_run:
        print("\n🔍 Mode dry-run: aucune modification effectuée.")
        print("\n   Vidéos (triées par vues):")
        for v in sorted(videos, key=lambda x: x.get("view_count", 0), reverse=True):
            print(f"      • {v['title'][:40]}... ({v['view_count']:,} vues)")
        sys.exit(0)
    
    # Reconstruire le journal avec toutes les vidéos
    print(f"\n📖 Reconstruction du journal...")
    result_journal = rebuild_journal(journal_path, videos)
    if result_journal["ok"]:
        print(f"   ✅ {result_journal['message']}")
        for trace in result_journal.get("trace", []):
            print(f"      {trace}")
    else:
        print(f"   ❌ {result_journal['message']}")
    
    # Injecter le TOP 3 par vues dans la page principale
    if main_path.exists():
        print(f"\n🏆 Injection TOP {max_main_cards} par vues dans la page principale...")
        result_main = inject_top_videos_into_main(main_path, videos, max_main_cards)
        if result_main["ok"]:
            print(f"   ✅ {result_main['message']}")
            for trace in result_main.get("trace", []):
                print(f"      {trace}")
        else:
            print(f"   ❌ {result_main['message']}")
            for trace in result_main.get("trace", []):
                print(f"      {trace}")
    
    # Mettre à jour la date dans la config
    config["updated_at"] = datetime.now().isoformat()
    config["last_video_count"] = len(videos)
    config["last_total_views"] = total_views
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Journal: {result_journal.get('count', 0)} vidéos (ordre chronologique)")
    print(f"✅ Page principale: Top {max_main_cards} par nombre de vues")
    print(f"{'='*60}")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
