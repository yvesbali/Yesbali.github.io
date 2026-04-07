#!/usr/bin/env python3
"""
Script de publication automatique Facebook depuis bibliothèque JSON
Génère un payload compatible avec le scénario Make LCDMH
Extrait les miniatures YouTube pour Instagram carrousel
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List

# ========== CONFIGURATION ==========
WEBHOOK_URL = "https://hook.eu1.make.com/rxcntbgy3j9w6yge67xqeg6gd1n4dy69"
LIBRARY_FILE = "facebook_payload_test.json"  # Fichier bibliothèque
# ===================================


def load_library(filepath: str) -> Dict:
    """Charge la bibliothèque de posts depuis le fichier JSON"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_library(filepath: str, data: Dict):
    """Sauvegarde la bibliothèque mise à jour"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_next_post(library: Dict) -> Optional[Dict]:
    """
    Trouve le prochain post à publier selon la date/heure programmée
    Retourne le post le plus ancien non publié dont l'heure est passée
    """
    now = datetime.now()
    
    unpublished = [
        post for post in library['posts'] 
        if not post.get('published', False)
    ]
    
    if not unpublished:
        print("✅ Tous les posts ont été publiés")
        return None
    
    # Trier par date puis heure
    for post in sorted(unpublished, key=lambda p: (p['scheduled_date'], p['scheduled_time'])):
        scheduled_datetime = datetime.strptime(
            f"{post['scheduled_date']} {post['scheduled_time']}", 
            "%Y-%m-%d %H:%M"
        )
        
        if scheduled_datetime <= now:
            return post
    
    print(f"⏳ Aucun post à publier maintenant. Prochain : {unpublished[0]['scheduled_date']} {unpublished[0]['scheduled_time']}")
    return None


def get_youtube_thumbnails(video_id: str) -> List[str]:
    """
    Génère les URLs de miniatures YouTube
    Retourne 2 URLs (haute et moyenne résolution) pour Instagram carrousel
    """
    return [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",  # 1280x720
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"        # 480x360
    ]


def create_payload(post: Dict) -> Dict:
    """
    Transforme un post de la bibliothèque en payload Make
    Compatible avec le scénario "Publication Photos&Videos"
    """
    video_id = post['video_id']
    thumbnails = get_youtube_thumbnails(video_id)
    
    payload = {
        "title": post['message'].split('\n')[0],  # Première ligne comme titre
        "location": "",  # Vide pour les posts programmés
        "description": post['message'],
        "mode": "standard",
        "mediaType": "photos",  # On traite les vidéos YouTube comme des photos (miniatures)
        
        # Flags de publication
        "publish_fb": True,   # Toujours publier sur Facebook
        "publish_ig": True,   # Publier sur Instagram (carrousel avec 2 miniatures)
        "publish_pin": False, # Désactiver Pinterest pour les posts programmés
        
        # Array de 2 photos minimum pour Instagram carrousel
        "photos": [
            {"secure_url": thumbnails[0]},
            {"secure_url": thumbnails[1]}
        ],
        
        # Liens
        "link_web": "https://lcdmh.com",
        "link_yt": post['link'],  # Lien YouTube original
        
        # Métadonnées
        "source": "scheduled_post",
        "post_id": post['id'],
        "category": post.get('category', ''),
        "partenaire": post.get('partenaire', '')
    }
    
    return payload


def send_to_make(payload: Dict) -> bool:
    """
    Envoie le payload au webhook Make
    Retourne True si succès, False sinon
    """
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Publication réussie : {payload['post_id']}")
            return True
        else:
            print(f"❌ Erreur HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur d'envoi: {str(e)}")
        return False


def mark_as_published(library: Dict, post_id: str):
    """Marque un post comme publié dans la bibliothèque"""
    for post in library['posts']:
        if post['id'] == post_id:
            post['published'] = True
            break


def main():
    """Fonction principale"""
    print("🚀 LCDMH - Publication automatique Facebook")
    print("=" * 50)
    
    # Charger la bibliothèque
    print(f"📖 Chargement de {LIBRARY_FILE}...")
    library = load_library(LIBRARY_FILE)
    print(f"✅ {library['meta']['total_posts']} posts chargés ({library['meta']['periode']})")
    
    # Trouver le prochain post
    print("\n🔍 Recherche du prochain post à publier...")
    next_post = get_next_post(library)
    
    if not next_post:
        print("⏹️  Aucun post à publier pour le moment")
        return
    
    # Afficher les détails
    print(f"\n📝 Post trouvé:")
    print(f"   ID       : {next_post['id']}")
    print(f"   Date     : {next_post['scheduled_date']} {next_post['scheduled_time']}")
    print(f"   Type     : {next_post['type']}")
    print(f"   Vidéo    : {next_post['video_id']}")
    print(f"   Catégorie: {next_post.get('category', 'N/A')}")
    
    # Créer le payload
    print("\n🔧 Génération du payload Make...")
    payload = create_payload(next_post)
    print(f"✅ Payload créé avec {len(payload['photos'])} miniatures YouTube")
    
    # Envoyer à Make
    print(f"\n📤 Envoi vers Make ({WEBHOOK_URL[:50]}...)...")
    success = send_to_make(payload)
    
    if success:
        # Marquer comme publié
        mark_as_published(library, next_post['id'])
        save_library(LIBRARY_FILE, library)
        print(f"✅ Post {next_post['id']} marqué comme publié")
        print("\n🎉 Publication terminée avec succès !")
    else:
        print("\n❌ Échec de la publication")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
