import json
import re
import requests
from bs4 import BeautifulSoup
import random

# --- CONFIGURATION ---
SITE_URL = "https://lcdmh.com"
WEBHOOK_URL = "https://hook.eu1.make.com/eaa6xfheiv6uriro4ek6hjvcihew6n1f"

def get_site_content():
    links = []
    try:
        res = requests.get(SITE_URL, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.endswith('.html') and 'index' not in href:
                full_url = href if href.startswith('http') else f"{SITE_URL}/{href.lstrip('/')}"
                if full_url not in links:
                    links.append(full_url)
    except Exception as e:
        print(f"Erreur scan : {e}")
    return links

def analyze_page(url):
    try:
        res = requests.get(url, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string.replace(' - LCDMH', '') if soup.title else "Aventure Moto"
        
        # --- LOGIQUE DE DÉTECTION AMÉLIORÉE ---
        category = "Roadtrips"
        url_lower = url.lower()
        
        # On cherche des mots clés dans l'URL ou le Titre
        if any(x in url_lower or x in title.lower() for x in ["test", "essai", "equipement", "sena", "casque", "intercom"]):
            category = "Tests Équipement"
        elif any(x in url_lower or x in title.lower() for x in ["tuto", "mecanique", "astuce", "comment"]):
            category = "Tutos Moto"
        
        yt_match = re.search(r'(?:v=|embed\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', res.text)
        yt_id = yt_match.group(1) if yt_match else None
        
        return {
            "title": title,
            "link": url,
            "category": category,
            "image_url": f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg" if yt_id else f"{SITE_URL}/images/logo-social.jpg"
        }
    except:
        return None

# --- EXECUTION ÉQUILIBRÉE ---
all_links = get_site_content()
if all_links:
    # 1. On analyse un échantillon pour classer par catégories
    buckets = {"Roadtrips": [], "Tests Équipement": [], "Tutos Moto": []}
    
    # On prend 20 liens au hasard pour trouver des catégories différentes
    sample = random.sample(all_links, min(len(all_links), 30))
    
    for link in sample:
        data = analyze_page(link)
        if data:
            buckets[data['category']].append(data)
    
    # 2. On choisit une catégorie qui n'est pas vide
    available_categories = [c for c in buckets if buckets[c]]
    chosen_cat = random.choice(available_categories)
    
    # 3. On choisit un post dans cette catégorie
    post = random.choice(buckets[chosen_cat])
    
    payload = {
        "mode": "flashback",
        "title": post['title'],
        "category": post['category'], 
        "message": f"🔙 FLASHBACK : {post['title']}\nUne pépite à (re)découvrir ! 🏍️",
        "link": post['link'],
        "image_url": post['image_url']
    }
    
    requests.post(WEBHOOK_URL, json=payload)
    print(f"✅ Envoyé : {post['title']} ({post['category']})")
