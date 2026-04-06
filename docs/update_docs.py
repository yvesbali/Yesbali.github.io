"""
Met à jour le document de cadrage LCDMH avec le travail des sessions 6-9
"""

cadrage_path = r'F:\Automate_YT\LCDMH_Cadrage_Projet.html'

with open(cadrage_path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# 1. Mettre a jour la date
old = 'Dernière mise à jour : 05 avril 2026 · Session 7'
new = 'Dernière mise à jour : 06 avril 2026 · Session 9'
if old in content:
    content = content.replace(old, new)
    changes += 1
    print('OK: Date mise a jour -> Session 9')

old2 = 'Dernière mise à jour : 05 avril 2026 · Session 8'
if old2 in content:
    content = content.replace(old2, new)
    changes += 1
    print('OK: Date mise a jour -> Session 9')

# 2. Mettre a jour le sous-titre
old = 'Audit automatique validé · Recyclage social refondu'
new = 'Blogger + Pinterest auto · GA4 installé · SEO audit complet · fetch_youtube réparé'
if old in content:
    content = content.replace(old, new)
    changes += 1
    print('OK: Sous-titre mis a jour')

# 3. Ajouter session 9 dans historique
if 'Session 9' not in content:
    session9 = """<tr><td><strong>9</strong></td><td>06/04/2026</td><td>Blogger auto-publisher (lcdmh.blogspot.com + Pinterest via Make.com), thème LCDMH noir/orange, codes promo sidebar, GA4 G-5DP7XR1C7W installé via nav-loader.js, fetch_youtube.py réparé (YOUTUBE_REFRESH_TOKEN synchronisé), 6 canonicals corrigés (/guides/→/articles/), 11 articles ajoutés au sitemap (180 total), 27 pages SEO corrigées (meta desc, canonical, OG tags, alt images), onglet Blogger dans dashboard SEO Streamlit, pages de test supprimées, 3 articles soumis indexation Google, fichier parasite supprimé, app Pinterest API soumise.</td></tr>"""
    
    # Chercher la fin du tableau historique
    markers = [
        'Recyclage social refondu sans yt-dlp',
        'Règles N°4',
        'session 8',
        'Session 8',
    ]
    
    inserted = False
    for marker in markers:
        if marker in content:
            # Trouver la fin de la ligne qui contient ce marqueur
            idx = content.index(marker)
            # Trouver le </tr> suivant
            tr_end = content.index('</tr>', idx) + 5
            content = content[:tr_end] + '\n' + session9 + content[tr_end:]
            changes += 1
            inserted = True
            print('OK: Session 9 ajoutee a historique')
            break
    
    if not inserted:
        print('SKIP: Impossible de trouver le point insertion pour session 9')
else:
    print('SKIP: Session 9 deja presente')

# 4. Mettre a jour le footer
old_footer = 'Session 8 · Recyclage social refondu · Auto-publish corrigé · 6 règles absolues · Lecture obligatoire en début de session'
new_footer = 'Session 9 · Blogger + Pinterest auto · GA4 · SEO audit complet · 6 règles absolues · Lecture obligatoire'
if old_footer in content:
    content = content.replace(old_footer, new_footer)
    changes += 1
    print('OK: Footer mis a jour')

# 5. Ajouter section Blogger + GA4 dans le plan d action
if 'MAKE_WEBHOOK_BLOGGER' not in content:
    blogger_task = """<tr><td><span class="tag tag-green">Fait</span></td>
<td><strong>Blogger + Pinterest auto-publisher</strong> — lcdmh.blogspot.com, thème LCDMH, codes promo sidebar, Make.com Webhook→Blogger→Pinterest, 2 articles publiés, secret MAKE_WEBHOOK_BLOGGER</td>
<td><span class="tag tag-green">✅ Session 9</span></td>
</tr>
<tr><td><span class="tag tag-green">Fait</span></td>
<td><strong>GA4 installé</strong> — G-5DP7XR1C7W via js/lcdmh-nav-loader.js sur toutes les pages</td>
<td><span class="tag tag-green">✅ Session 9</span></td>
</tr>
<tr><td><span class="tag tag-green">Fait</span></td>
<td><strong>fetch_youtube.py réparé</strong> — YOUTUBE_REFRESH_TOKEN synchronisé avec yt_token_analytics.json</td>
<td><span class="tag tag-green">✅ Session 9</span></td>
</tr>
<tr><td><span class="tag tag-green">Fait</span></td>
<td><strong>SEO audit complet</strong> — 6 canonicals, 11 articles sitemap, 27 pages meta/OG corrigées, 3 articles soumis indexation Google</td>
<td><span class="tag tag-green">✅ Session 9</span></td>
</tr>"""
    
    # Inserer dans la section plan d action urgent
    if 'URGENT' in content or 'À faire maintenant' in content:
        # Chercher le debut de la table urgente
        for marker in ['À faire maintenant', 'URGENT']:
            if marker in content:
                idx = content.index(marker)
                tbody = content.index('<tbody>', idx) + 7
                content = content[:tbody] + '\n' + blogger_task + content[tbody:]
                changes += 1
                print('OK: Taches session 9 ajoutees au plan action')
                break
    else:
        print('SKIP: Section plan action non trouvee')
else:
    print('SKIP: Taches session 9 deja presentes')

# Sauvegarder
with open(cadrage_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print(f'\nSAUVEGARDE: {cadrage_path}')
print(f'Taille: {len(content)} caracteres')
print(f'Modifications: {changes}')