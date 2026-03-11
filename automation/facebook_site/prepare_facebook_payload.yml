import json
import re
import requests
from bs4 import BeautifulSoup
import random

# --- CONFIGURATION ---
SITE_URL = "https://lcdmh.com"
WEBHOOK_URL = "https://hook.eu1.make.com/eaa6xfheiv6uriro4ek6hjvcihew6n1f"

def get_site_content():
    """Scanne la page d'accueil pour trouver tous les articles"""
    links = []
    try:
        res = requests.get(SITE_URL, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            # On cible les pages d'articles .html
            if href.endswith('.html') and 'index' not in href:
                full_url = href if href.startswith('http') else f"{SITE_URL}/{href.lstrip('/')}"
                if full_url not in links:
                    links.append(full_url)
    except Exception as e:
        print(f"Erreur scan site : {e}")
    return links

def analyze_page(url):
    """Extrait les infos de la page pour Pinterest et Facebook"""
    try:
        res = requests.get(url, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Récupère le titre de la page
        title = soup.title.string.replace(' - LCDMH', '') if soup.title else "Souvenir LCDMH"
        
        # Extrait l'ID de la vidéo YouTube pour l'image
        yt_match = re.search(r'(?:v=|embed\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', res.text)
        yt_id = yt_match.group(1) if yt_match else None
        
        # --- LOGIQUE DES CATEGORIES (Tableaux Pinterest) ---
        category = "Roadtrips" # Par défaut
        url_lower = url.lower()
        if "test" in url_lower or "essai" in url_lower:
            category = "Tests Équipement"
        elif "tuto" in url_lower:
            category = "Tutos"
        
        # Image : Miniature YT (hqdefault) ou Logo du site
        image_url = f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg" if yt_id else f"{SITE_URL}/images/logo-social.jpg"
        
        return {
            "title": title,
            "link": url,
            "category": category,
            "image_url": image_url
        }
    except:
        return None

# --- EXECUTION ---
print("🔍 Analyse du site lcdmh.com...")
all_links = get_site_content()

if all_links:
    chosen_url = random.choice(all_links)
    post_data = analyze_page(chosen_url)
    
    if post_data:
        payload = {
            "mode": "flashback",
            "title": post_data['title'],
            "category": post_data['category'], 
            "message": f"🔙 FLASHBACK : {post_data['title']}\nOn se replonge dans cette aventure ? 🏍️",
            "link": post_data['link'],
            "image_url": post_data['image_url']
        }
        
        print(f"🚀 Envoi du Flashback : {payload['title']} ({payload['category']})")
        requests.post(WEBHOOK_URL, json=payload)
    else:
        print("Erreur analyse page.")
else:
    print("Aucun lien trouvé.")