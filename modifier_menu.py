import os
import glob
import re

dossier = r"F:\LCDMH"

# Même nouveau bloc
nouveau_bloc = '''<nav>
    <a href="index.html" class="logo">LC<span>D</span>MH</a>
    <button class="menu-toggle" id="menuToggle">☰</button>
    <ul class="nav-links" id="navLinks">
        <li><a href="index.html">Accueil</a></li>
        <li class="has-drop">
            <a href="#">Road Trips</a>
            <div class="dropdown">
                <a href="roadtrips.html">Tous les road trips</a>
                <a href="roadtrips.html#capnord">Cap Nord 2025</a>
                <a href="roadtrips.html#europe-asie">Europe–Asie 2024</a>
                <a href="roadtrips.html#espagne">Espagne 2023</a>
                <a href="roadtrips.html#alpes">Les Alpes</a>
            </div>
        </li>
        <li class="has-drop">
            <a href="#">Tests</a>
            <div class="dropdown">
                <a href="tests-motos.html">Tests motos</a>
                <a href="equipement.html">Équipement</a>
                <a href="intercoms.html">Intercoms</a>
                <a href="pneus.html">Pneus (liens affiliés)</a>
                <a href="photo-video.html">Photo / Vidéo</a>
                <a href="securite.html">Sécurité</a>
            </div>
        </li>
        <li class="has-drop">
            <a href="#">GPS</a>
            <div class="dropdown">
                <a href="gps.html">Tous les GPS</a>
                <a href="aoocci.html">Aoocci (GPS offline)</a>
                <a href="carpuride.html">Carpuride (écran déporté)</a>
                <a href="blackview.html">Blackview 📱 (téléphone renforcé)</a>
            </div>
        </li>
        <li class="has-drop">
            <a href="#">Partenaires</a>
            <div class="dropdown">
                <a href="codes-promo.html">💰 Codes promo</a>
                <a href="blackview.html">Blackview</a>
                <a href="olight.html">Olight (lampes)</a>
                <a href="komobi.html">Komobi (traceur GPS)</a>
                <a href="aferiy.html">⚡ Aferiy (énergie/bivouac)</a>
            </div>
        </li>
        <li><a href="a-propos.html">À propos</a></li>
        <li><a href="contact.html">Contact</a></li>
        <li class="desktop-only"><a href="https://www.youtube.com/@LCDMH?sub_confirmation=1" class="nav-yt">▶ S'abonner</a></li>
        <li class="desktop-only"><a href="https://www.youtube.com/@LCDMH" class="nav-yt-icon">📺 YouTube</a></li>
        <li class="mobile-only"><a href="https://www.youtube.com/@LCDMH?sub_confirmation=1" class="nav-yt">▶ S'abonner</a></li>
        <li class="mobile-only"><a href="https://www.youtube.com/@LCDMH" class="nav-yt-icon">📺 YouTube</a></li>
    </ul>
</nav>'''

fichiers_html = glob.glob(os.path.join(dossier, "*.html"))
compteur = 0

for fichier in fichiers_html:
    with open(fichier, 'r', encoding='utf-8') as f:
        contenu = f.read()
    
    # Pattern plus large qui capture toute la navigation
    pattern = r'<nav>.*?<a href="index\.html" class="logo">.*?</nav>'
    
    if re.search(pattern, contenu, re.DOTALL):
        nouveau_contenu = re.sub(pattern, nouveau_bloc, contenu, flags=re.DOTALL)
        with open(fichier, 'w', encoding='utf-8') as f:
            f.write(nouveau_contenu)
        print(f"✅ Modifié : {os.path.basename(fichier)}")
        compteur += 1
    else:
        print(f"⏭️  Pattern non trouvé : {os.path.basename(fichier)}")

print(f"\n🎉 {compteur} fichier(s) mis à jour !")