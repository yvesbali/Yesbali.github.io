# Règles LCDMH — Conventions absolues

## RÈGLE N°1 — Encodage Python
Toujours écrire les fichiers HTML/CSS/JS avec Python :
```python
open(path, 'w', encoding='utf-8', newline='\n')
```
**JAMAIS PowerShell Set-Content** (casse les accents et les sauts de ligne).

## RÈGLE N°7 — Navigation
Tous les HTMLs ont déjà `<script src="/js/lcdmh-nav-loader.js" defer></script>`.
Ne JAMAIS toucher à cette ligne, ne jamais la dupliquer.

## RÈGLE N°8 — Publication article
1. HTML dans `articles/`
2. Photos dans `articles/images/[slug]/`
3. Vignette dans le tableau `ARTICLES` de `articles.html`
4. URL dans `sitemap.xml` (avant `</urlset>`)
5. Commit + push

## Nommage
- Slugs articles : tout en minuscules, tirets, max 60 chars
- Images : `slug-article-description.webp` (ou .jpg si déjà existant)
- CSS réutilisable : `css/guide-pratique.css` (déjà en place)

## Git
- Branche : `main`
- Push : Yves le fait depuis son terminal Windows (`git push origin main`)
- Cowork crée les commits via : write-tree → commit-tree → écriture directe dans refs/heads/main
- NE PAS utiliser `git push --force`
- NE PAS modifier les fichiers .github/workflows/ sans briefing de Claude

## Streamlit (app.py)
- Dossier : F:\LCDMH_GitHub_Audit\..\Automate_YT\ (monté dans /mnt/Automate_YT/)
- Nouvelles pages : créer `page_[nom]_NEW.py`, puis renommer après validation
- Routing dans app.py : radio buttons → `st.session_state["page"]`
