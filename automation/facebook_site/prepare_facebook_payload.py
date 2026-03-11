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
        print(f"Erreur scan site : {e}")
    return links

def analyze_page(url):
    try:
        res = requests.get(url, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string.replace(' - LCDMH', '') if soup.title else "Souvenir LCDMH"
        yt_match = re.search(r'(?:v=|embed\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', res.text)
        yt_id = yt_match.group(1) if yt_match else None
        
        category = "Roadtrips"
        url_lower = url.lower()
        if "test" in url_lower or "essai" in url_lower: category = "Tests Équipement"
        elif "tuto" in url_lower: category = "Tutos"
        
        image_url = f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg" if yt_id else f"{SITE_URL}/images/logo-social.jpg"
        
        return {"title": title, "link": url, "category": category, "image_url": image_url}
    except:
        return None

print("🔍 Scan du site en cours...")
all_links = get_site_content()
if all_links:
    chosen_url = random.choice(all_links)
    post_data = analyze_page(chosen_url)
    if post_data:
        payload = {
            "mode": "flashback",
            "title": post_data['title'],
            "category": post_data['category'], 
            "message": f"🔙 FLASHBACK : {post_data['title']}\\nOn se replonge dans cette aventure ? 🏍️",
            "link": post_data['link'],
            "image_url": post_data['image_url']
        }
        requests.post(WEBHOOK_URL, json=payload)
        print(f"🚀 Envoyé : {payload['title']}")
