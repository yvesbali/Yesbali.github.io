import os
import json
import requests
import re

# --- CONFIGURATION ---
# Récupération des secrets GitHub
CLIENT_ID = os.environ.get('YOUTUBE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('YOUTUBE_CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('YOUTUBE_REFRESH_TOKEN')

def get_access_token():
    """Récupère un nouveau jeton d'accès via le refresh token"""
    url = "https://oauth2.googleapis.com/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    r = requests.post(url, data=payload)
    return r.json().get('access_token')

def get_playlist_videos(token, playlist_id):
    """Récupère les vidéos d'une playlist précise"""
    url = f"https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        'part': 'snippet,contentDetails',
        'maxResults': 50,
        'playlistId': playlist_id,
        'access_token': token
    }
    r = requests.get(url, params=params)
