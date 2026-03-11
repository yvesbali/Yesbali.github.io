import json
import re
import requests
import random
import os

# --- CONFIGURATION ---
WEBHOOK_URL = "https://hook.eu1.make.com/eaa6xfheiv6uriro4ek6hjvcihew6n1f"

def get_yt_id(url):
    """Extrait proprement l'ID de 11 caractères d'une vidéo YouTube"""
    if not url: return None
    pattern = r'(?:v=|embed\/|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

# --- LOGIQUE DE SELECTION ---
try:
    if os.path.exists('facebook_post_selected.json'):
        with open('facebook_post_selected.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            mode = "production"
    else:
        # TES ARCHIVES (Ajoute tes vrais liens YouTube ici)
        archives = [
            {"title": "Road Trip Cap Nord", "link": "https://lcdmh.com/cap-nord-moto.html", "yt": "https://www.youtube.com/watch?v=mF8bC-E_8W0"},
            {"title": "Test Intercom Sena", "link": "https://lcdmh.com/test-sena.html", "yt": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        ]
        data = random.choice(archives)
        mode = "flashback"
except:
    exit()

# --- RÉPARATION DU LIEN IMAGE ---
# On va chercher l'ID vidéo dans le champ 'yt' ou 'link'
video_id = get_yt_id(data.get('yt')) or get_yt_id(data.get('link'))

if video_id:
    # On envoie l'image YouTube à Pinterest (hqdefault est ultra fiable)
    image_finale = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
else:
    # Si vraiment pas de vidéo, on envoie le logo (vérifie bien que ce logo existe !)
    image_finale = "https://lcdmh.com/images/logo-social.jpg"

payload = {
    "mode": mode,
    "title": data.get('title'),
    "category": data.get('category', 'Roadtrips'), # Valeur par défaut si vide
    "message": f"🔙 FLASHBACK : {data.get('title')}" if mode == "flashback" else data.get('message'),
    "link": data.get('link'),
    "image_url": image_finale # CE LIEN FONCTIONNE SUR PINTEREST
}

# --- ENVOI A MAKE ---
print(f"🚀 Envoi du {mode} : {payload['title']}")
print(f"📸 Image Pinterest : {payload['image_url']}")
requests.post(WEBHOOK_URL, json=payload)
