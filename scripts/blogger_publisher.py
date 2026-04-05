#!/usr/bin/env python3
import json, os, sys, re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlencode

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print('pip install requests beautifulsoup4')
    sys.exit(1)

SITE_URL = 'https://lcdmh.com'
ARTICLES_PAGE = f'{SITE_URL}/articles.html'
MAKE_WEBHOOK_URL = os.environ.get('MAKE_WEBHOOK_BLOGGER', '')
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
TRACKING_FILE = os.path.join(REPO_ROOT, 'data', 'articles_published_blogger.json')
UTM_PARAMS = {'utm_source': 'blogger', 'utm_medium': 'teaser', 'utm_campaign': 'lcdmh-blog'}

CATEGORY_LABELS = {
    'road trip': ['Road Trip', 'Moto', 'Voyage'],
    'test': ['Test Materiel', 'Moto', 'Equipement'],
    'guide': ['Guide', 'Moto', 'Conseils'],
    'cap nord': ['Road Trip', 'Norvege', 'Cap Nord'],
    'norvege': ['Road Trip', 'Norvege', 'Scandinavie'],
    'alpes': ['Road Trip', 'Alpes', 'France'],
    'eclairage': ['Test Materiel', 'Bivouac', 'Eclairage'],
    'pneus': ['Test Materiel', 'Pneus', 'Comparatif'],
    'entretien': ['Guide', 'Entretien', 'Moto'],
    'batterie': ['Test Materiel', 'Bivouac', 'Energie'],
}

def add_utm(url, extra=None):
    params = dict(UTM_PARAMS)
    if extra:
        params.update(extra)
    sep = '&' if '?' in url else '?'
    return f'{url}{sep}{urlencode(params)}'

def detect_labels(title, category):
    labels = set()
    text = f'{title} {category}'.lower()
    for kw, lbl in CATEGORY_LABELS.items():
        if kw in text:
            labels.update(lbl)
    if not labels:
        labels = {'Moto', 'LCDMH'}
    labels.add('LCDMH')
    return sorted(labels)

def fetch_article_list():
    print(f'Recuperation de {ARTICLES_PAGE}...')
    resp = requests.get(ARTICLES_PAGE, timeout=30)
    resp.encoding = 'utf-8'
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    articles = []
    seen = set()
    for link in soup.find_all('a', href=True):
        href = link['href']
        if 'articles/' not in href or not href.endswith('.html'):
            continue
        url = urljoin(SITE_URL, href)
        if url in seen:
            continue
        seen.add(url)
        h3 = link.find('h3')
        title = h3.get_text(strip=True) if h3 else ''
        category = ''
        for el in link.find_all(['span', 'div', 'p', 'small']):
            txt = el.get_text(strip=True)
            if any(c in txt for c in ['Road Trip', 'Test', 'Guide']):
                category = txt
                break
        description = ''
        for p in link.find_all('p'):
            txt = p.get_text(strip=True)
            if txt and txt != title and len(txt) > 20:
                description = txt
                break
        img = link.find('img')
        thumbnail = urljoin(SITE_URL, img['src']) if img and img.get('src') else ''
        slug = href.split('/')[-1].replace('.html', '')
        articles.append({'url': url, 'slug': slug, 'title': title, 'category': category, 'description': description, 'thumbnail': thumbnail})
    print(f'{len(articles)} articles trouves')
    return articles

def fetch_article_content(url):
    print(f'Lecture de {url}...')
    resp = requests.get(url, timeout=30)
    resp.encoding = 'utf-8'
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    h1 = soup.find('h1')
    title = h1.get_text(strip=True) if h1 else ''
    meta = soup.find('meta', attrs={'name': 'description'})
    meta_desc = meta['content'] if meta and meta.get('content') else ''
    content_parts = []
    stop_kw = ['FAQ', 'Ce que la communaut', 'acheter', 'Rejoins la communaut', 'Produits mentionn', 'Vos questions']
    for el in soup.find_all(['h2', 'h3', 'p']):
        text = el.get_text(strip=True)
        if any(kw in text for kw in stop_kw):
            break
        if text and len(text) > 10:
            content_parts.append({'tag': el.name, 'text': text})
    hero = ''
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if 'articles/images/' in src:
            hero = urljoin(SITE_URL, src)
            break
    return {'title': title, 'meta_description': meta_desc, 'content_parts': content_parts, 'hero_image': hero}

def generate_teaser(info, content):
    title = content['title'] or info['title']
    url = info['url']
    tracked = add_utm(url, {'utm_content': info['slug']})
    hero = content.get('hero_image') or info.get('thumbnail', '')
    desc = content.get('meta_description') or info.get('description', '')
    intros = []
    for p in content['content_parts']:
        if p['tag'] == 'p' and len(p['text']) > 50:
            intros.append(p['text'])
            if len(intros) >= 2:
                break
    points = []
    for p in content['content_parts']:
        if p['tag'] == 'h2':
            clean = re.sub(r'^[\U0001F300-\U0001FAFF\U00002702-\U000027B0\s]+', '', p['text'])
            if clean and len(clean) > 3:
                points.append(clean)
    labels = detect_labels(title, info.get('category', ''))
    h = []
    h.append(f'<p><em>Cet article est un apercu. <a href="{tracked}">Lire l\'article complet sur LCDMH.com</a></em></p>')
    if hero:
        h.append(f'<div style="text-align:center"><a href="{tracked}"><img src="{hero}" alt="{title}" style="max-width:100%;border-radius:8px" /></a></div>')
    if desc:
        h.append(f'<p><strong>{desc}</strong></p>')
    for para in intros:
        h.append(f'<p>{para}</p>')
    if points:
        h.append('<h3>Dans cet article</h3><ul>')
        for pt in points[:5]:
            h.append(f'<li>{pt}</li>')
        h.append('</ul>')
    h.append(f'<hr /><div style="background:#fff3e6;border:2px solid #ff6b35;border-radius:12px;padding:20px;text-align:center;margin:20px 0"><h3 style="color:#ff6b35">Lire l\'article complet</h3><p>Test detaille, photos terrain, avis communaute et codes promo exclusifs :</p><p style="margin:15px 0"><a href="{tracked}" style="background:#ff6b35;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:1.1em">{title} - Lire sur LCDMH.com</a></p></div>')
    yt = add_utm('https://www.youtube.com/@LCDMH?sub_confirmation=1')
    site = add_utm(f'{SITE_URL}/articles.html', {'utm_content': 'footer'})
    h.append(f'<hr /><p style="text-align:center;color:#666"><strong>LCDMH - La Chaine du Motard Heureux</strong><br />Road trips moto en Europe - Tests terrain - Guides pratiques<br /><a href="{yt}">YouTube</a> - <a href="{site}">Tous les articles</a></p>')
    return {'title': title, 'content': '\n'.join(h), 'labels': labels, 'category': info.get('category',''), 'excerpt': desc[:300], 'featured_image': hero, 'original_url': url, 'tracked_url': tracked, 'slug': info['slug']}

def load_tracking():
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'published': [], 'last_update': None, 'total_published': 0}

def save_tracking(data):
    os.makedirs(os.path.dirname(TRACKING_FILE), exist_ok=True)
    data['last_update'] = datetime.now(timezone.utc).isoformat()
    data['total_published'] = len(data.get('published', []))
    with open(TRACKING_FILE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_published(tracking, slug):
    return any(p['slug'] == slug for p in tracking.get('published', []))

def mark_published(tracking, slug, title, url):
    tracking['published'].append({'slug': slug, 'title': title, 'original_url': url, 'tracked_url': add_utm(url, {'utm_content': slug}), 'published_at': datetime.now(timezone.utc).isoformat()})
    save_tracking(tracking)

def send_to_make(teaser):
    if not MAKE_WEBHOOK_URL:
        print('Variable MAKE_WEBHOOK_BLOGGER non configuree !')
        print('Ajouter le secret dans GitHub Settings Secrets Actions')
        return False
    payload = {'title': teaser['title'], 'content': teaser['content'], 'labels': teaser['labels'], 'slug': teaser['slug'], 'original_url': teaser['original_url'], 'tracked_url': teaser['tracked_url'], 'featured_image': teaser.get('featured_image',''), 'excerpt': teaser.get('excerpt',''), 'is_draft': False, 'source': 'lcdmh-blogger-publisher', 'timestamp': datetime.now(timezone.utc).isoformat()}
    print('Envoi vers Make.com webhook...')
    try:
        resp = requests.post(MAKE_WEBHOOK_URL, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
        if resp.status_code == 200:
            print('Envoye avec succes a Make.com !')
            return True
        else:
            print(f'Erreur Make.com : {resp.status_code} - {resp.text[:200]}')
            return False
    except Exception as e:
        print(f'Erreur reseau : {e}')
        return False

def cmd_list():
    articles = fetch_article_list()
    tracking = load_tracking()
    print()
    print('=' * 65)
    print(f'  ARTICLES LCDMH - {len(articles)} disponibles')
    print('=' * 65)
    print()
    for i, art in enumerate(articles, 1):
        pub = is_published(tracking, art['slug'])
        icon = '[Publie]' if pub else '[A publier]'
        print(f'  {i:2d}. {icon} {art["title"]}')
        print(f'      {art["url"]}')
        print()
    pub_count = sum(1 for a in articles if is_published(tracking, a['slug']))
    remaining = len(articles) - pub_count
    print('-' * 65)
    print(f'  Publies : {pub_count} / Restants : {remaining}')
    if remaining > 0:
        print(f'  A 2 articles/semaine : {remaining / 2:.0f} semaines de contenu')
    print()

def cmd_stats():
    tracking = load_tracking()
    published = tracking.get('published', [])
    print()
    print('=' * 65)
    print('  STATISTIQUES - Blogger Publisher LCDMH')
    print('=' * 65)
    print(f'  Total publie : {len(published)}')
    print(f'  Derniere MAJ : {tracking.get("last_update", "jamais")}')
    if published:
        print()
        print('  Articles publies :')
        for p in published:
            date = p.get('published_at', '?')[:10]
            print(f'    [{date}] {p["title"]}')
    print()

def cmd_publish(force_slug=None, dry_run=False):
    articles = fetch_article_list()
    tracking = load_tracking()
    target = None
    if force_slug:
        for art in articles:
            if art['slug'] == force_slug or force_slug in art['slug']:
                target = art
                break
        if not target:
            print(f'Article {force_slug} non trouve')
            return False
    else:
        for art in articles:
            if not is_published(tracking, art['slug']):
                target = art
                break
        if not target:
            print('Tous les articles ont deja ete publies !')
            return True
    print(f'Article selectionne : {target["title"]}')
    content = fetch_article_content(target['url'])
    teaser = generate_teaser(target, content)
    print(f'Teaser genere : {len(teaser["content"])} caracteres')
    print(f'Labels : {teaser["labels"]}')
    if dry_run:
        print()
        print('-' * 50)
        print('APERCU DU TEASER :')
        print('-' * 50)
        preview = BeautifulSoup(teaser['content'], 'html.parser').get_text(separator='\n')
        print(preview[:1000])
        print('-' * 50)
        print('Mode dry-run - rien envoye')
        return True
    success = send_to_make(teaser)
    if success:
        mark_published(tracking, target['slug'], target['title'], target['url'])
        remaining = sum(1 for a in articles if not is_published(tracking, a['slug'])) - 1
        print(f'Article publie ! {remaining} restants')
    return success

if __name__ == '__main__':
    args = sys.argv[1:]
    if '--list' in args:
        cmd_list()
    elif '--stats' in args:
        cmd_stats()
    elif '--dry-run' in args:
        slug = None
        if '--force' in args:
            idx = args.index('--force')
            if idx + 1 < len(args):
                slug = args[idx + 1]
        cmd_publish(force_slug=slug, dry_run=True)
    elif '--force' in args:
        idx = args.index('--force')
        if idx + 1 < len(args):
            cmd_publish(force_slug=args[idx + 1])
        else:
            print('Usage : --force <slug>')
    elif '--help' in args or '-h' in args:
        print('Usage: python blogger_publisher.py [--list|--dry-run|--force <slug>|--stats]')
    else:
        cmd_publish()
