# ============================================
# SCRIPT : convertir_navigation.ps1
# BUT    : Convertir TOUTES les pages HTML vers
#          un système de navigation unique
# AUTEUR : LCDMH
# DATE   : 2026-03-09
# ============================================

param(
    [string]$chemin_site = "F:\LCDMH",
    [switch]$simulation = $false
)

Write-Host "🚀 CONVERSION DE LA NAVIGATION LCDMH" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "📁 Dossier cible : $chemin_site"
if ($simulation) {
    Write-Host "⚡ MODE SIMULATION : Aucun fichier ne sera modifié" -ForegroundColor Yellow
}
Write-Host ""

# ===== FONCTIONS =====

function Test-CorrectSyntaxe {
    param([string]$contenu)
    
    $erreurs = @()
    
    # Vérifier la balise html lang
    if ($contenu -notmatch '<html lang="fr">') {
        $erreurs += "❌ Balise <html lang='fr'> manquante"
    }
    
    # Vérifier le viewport
    if ($contenu -notmatch '<meta name="viewport"') {
        $erreurs += "❌ Viewport manquant"
    }
    
    # Vérifier qu'il n'y a qu'une seule balise H1
    $nbH1 = ([regex]::Matches($contenu, '<h1[^>]*>')).Count
    if ($nbH1 -ne 1) {
        $erreurs += "❌ $nbH1 balises H1 trouvées (doit être 1)"
    }
    
    # Vérifier la présence de la balise title
    if ($contenu -notmatch '<title>.*</title>') {
        $erreurs += "❌ Balise title manquante"
    }
    
    # Vérifier la meta description
    if ($contenu -notmatch '<meta name="description"') {
        $erreurs += "❌ Meta description manquante"
    }
    
    return $erreurs
}

function Get-NouvelleNavigation {
    return @'
<!-- ======================================== -->
<!-- DÉBUT NAVIGATION LCDMH (fichier unique) -->
<!-- ======================================== -->
<div id="lcdmh-nav-container"></div>
<script>
(function() {
    // Fonction pour charger la navigation
    function chargerNavigation() {
        fetch('/nav.html?t=' + Date.now())
            .then(response => response.text())
            .then(html => {
                document.getElementById('lcdmh-nav-container').innerHTML = html;
                
                // Marquer la page active
                const page = window.location.pathname.split('/').pop() || 'index.html';
                document.querySelectorAll('#lcdmh-nav .nav-links > li > a').forEach(link => {
                    const href = link.getAttribute('href') || '';
                    if (href && href !== '#' && page.indexOf(href.replace('.html', '')) !== -1) {
                        link.classList.add('active');
                    }
                });
            })
            .catch(err => {
                console.error('❌ Navigation non chargée:', err);
                // Fallback : navigation minimale
                document.getElementById('lcdmh-nav-container').innerHTML = 
                    '<nav style="background:#fff;padding:1rem;"><a href="/" style="color:#e67e22;font-weight:bold;font-size:1.5rem;">LCDMH</a></nav>';
            });
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', chargerNavigation);
    } else {
        chargerNavigation();
    }
})();
</script>
<!-- ======================================== -->
<!-- FIN NAVIGATION LCDMH -->
<!-- ======================================== -->
'@
}

function Get-FichierNavHtml {
    return @'
<!-- ======================================== -->
<!-- FICHIER : nav.html (navigation LCDMH)   -->
<!-- ======================================== -->
<nav id="lcdmh-nav" style="background:#fff;box-shadow:0 2px 12px rgba(0,0,0,.07);padding:0 4%;height:70px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:1000;">
    <a href="index.html" style="font-family:Montserrat,sans-serif;font-size:1.6rem;font-weight:800;color:#1a1a1a;text-decoration:none;">LC<span style="color:#e67e22;">D</span>MH</a>
    
    <button class="menu-toggle" id="menuToggle" style="display:none;font-size:1.8rem;background:none;border:none;color:#1a1a1a;cursor:pointer;">☰</button>
    
    <ul class="nav-links" id="navLinks" style="display:flex;gap:1.5rem;list-style:none;margin:0;padding:0;">
        <li><a href="index.html" style="font-size:0.85rem;font-weight:600;color:#555;text-transform:uppercase;text-decoration:none;">Accueil</a></li>
        
        <li class="has-drop" style="position:relative;">
            <a href="roadtrips.html" style="font-size:0.85rem;font-weight:600;color:#555;text-transform:uppercase;text-decoration:none;">Road Trips</a>
            <div class="dropdown" style="display:none;position:absolute;top:100%;left:0;background:#fff;border:1px solid #e5e5e5;border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.12);min-width:200px;padding:0.5rem 0;z-index:999;">
                <a href="roadtrips.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Tous les road trips</a>
                <a href="cap-nord-moto.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;font-weight:700;">🏔️ Cap Nord 2025</a>
                <a href="europe-asie-moto.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;font-weight:700;">🌍 Europe–Asie 2024</a>
                <a href="alpes-aventure-festival-moto.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;font-weight:700;">🏔️ Alpes Festival 2025</a>
                <div style="border-top:1px solid #e0e0e0;margin:5px 0;"></div>
                <a href="roadtrips.html#espagne" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Espagne 2023</a>
                <a href="roadtrips.html#alpes" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Les Alpes</a>
            </div>
        </li>
        
        <li class="has-drop" style="position:relative;">
            <a href="#" style="font-size:0.85rem;font-weight:600;color:#555;text-transform:uppercase;text-decoration:none;">Tests</a>
            <div class="dropdown" style="display:none;position:absolute;top:100%;left:0;background:#fff;border:1px solid #e5e5e5;border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.12);min-width:200px;padding:0.5rem 0;z-index:999;">
                <a href="tests-motos.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Tests motos</a>
                <a href="equipement.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Équipement</a>
                <a href="intercoms.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Intercoms</a>
                <a href="pneus.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Pneus moto</a>
                <a href="photo-video.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Photo / Vidéo</a>
                <a href="securite.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Sécurité</a>
            </div>
        </li>
        
        <li class="has-drop" style="position:relative;">
            <a href="#" style="font-size:0.85rem;font-weight:600;color:#555;text-transform:uppercase;text-decoration:none;">GPS</a>
            <div class="dropdown" style="display:none;position:absolute;top:100%;left:0;background:#fff;border:1px solid #e5e5e5;border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.12);min-width:200px;padding:0.5rem 0;z-index:999;">
                <a href="gps.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Tous les GPS</a>
                <a href="aoocci.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Aoocci (GPS offline)</a>
                <a href="carpuride.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Carpuride (écran déporté)</a>
                <a href="blackview.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Blackview 📱</a>
            </div>
        </li>
        
        <li class="has-drop" style="position:relative;">
            <a href="#" style="font-size:0.85rem;font-weight:600;color:#555;text-transform:uppercase;text-decoration:none;">Partenaires</a>
            <div class="dropdown" style="display:none;position:absolute;top:100%;left:0;background:#fff;border:1px solid #e5e5e5;border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.12);min-width:230px;padding:0.5rem 0;z-index:999;">
                <a href="codes-promo.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;font-weight:700;">💰 Tous les codes promo</a>
                <div style="border-top:1px solid #e0e0e0;margin:5px 0;"></div>
                <a href="komobi.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Komobi 📍 (traceur GPS)</a>
                <a href="aoocci.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Aoocci 🧭 (GPS offline)</a>
                <a href="carpuride.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Carpuride 📺 (écran CarPlay)</a>
                <a href="blackview.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Blackview 📱 (téléphone renforcé)</a>
                <a href="aferiy.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Aferiy ⚡ (batteries bivouac)</a>
                <a href="olight.html" style="display:block;padding:0.5rem 1.1rem;color:#1a1a1a;text-decoration:none;">Olight 🔦 (lampes frontales)</a>
            </div>
        </li>
        
        <li><a href="a-propos.html" style="font-size:0.85rem;font-weight:600;color:#555;text-transform:uppercase;text-decoration:none;">À propos</a></li>
        <li><a href="contact.html" style="font-size:0.85rem;font-weight:600;color:#555;text-transform:uppercase;text-decoration:none;">Contact</a></li>
        
        <!-- Badge dernière vidéo -->
        <li>
            <a href="index.html#videos" style="display:inline-flex;align-items:center;gap:0.4rem;background:#fff3e0;border:1px solid #f0a500;border-radius:20px;padding:0.3rem 0.8rem;font-size:0.72rem;font-weight:700;color:#e67e22;text-decoration:none;">
                <span style="display:inline-block;width:7px;height:7px;background:#e74c3c;border-radius:50%;"></span>
                <span style="font-size:0.65rem;font-weight:800;text-transform:uppercase;">Nouveau</span>
                <span class="video-title" id="nav-last-video-title">Dernière vidéo</span>
            </a>
        </li>
        <li><a href="https://www.youtube.com/@LCDMH?sub_confirmation=1" style="background:#e67e22;color:#fff;padding:0.4rem 1rem;border-radius:30px;font-weight:700;text-decoration:none;">▶ S'abonner</a></li>
        <li><a href="https://www.youtube.com/@LCDMH" style="background:#ff0000;color:#fff;padding:0.4rem 1rem;border-radius:30px;font-weight:700;text-decoration:none;">📺 YouTube</a></li>
    </ul>
</nav>

<style>
@media (max-width: 900px) {
    .nav-links { display: none; flex-direction: column; position: absolute; top: 70px; left: 0; width: 100%; background: #fff; padding: 1rem 0; box-shadow: 0 10px 20px rgba(0,0,0,0.1); z-index: 1000; }
    .nav-links.active { display: flex; }
    .nav-links li { width: 100%; text-align: center; }
    .nav-links a { display: block; padding: 1rem !important; }
    .menu-toggle { display: block !important; }
    .has-drop .dropdown { position: static; width: 100%; box-shadow: none; border: none; border-top: 1px solid #e8e8e8; }
}
</style>

<script>
// Menu toggle mobile
document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.getElementById('menuToggle');
    const list = document.getElementById('navLinks');
    if (toggle && list) {
        toggle.addEventListener('click', function(e) {
            e.stopPropagation();
            list.classList.toggle('active');
        });
    }
    
    // Gestion des dropdowns
    document.querySelectorAll('#lcdmh-nav .has-drop').forEach(item => {
        const dd = item.querySelector('.dropdown');
        const link = item.querySelector('a');
        
        item.addEventListener('mouseenter', () => {
            if (window.innerWidth > 900) dd.style.display = 'block';
        });
        item.addEventListener('mouseleave', () => {
            if (window.innerWidth > 900) dd.style.display = 'none';
        });
        
        if (link) {
            link.addEventListener('click', (e) => {
                if (window.innerWidth <= 900) {
                    e.preventDefault();
                    const isOpen = dd.style.display === 'block';
                    document.querySelectorAll('#lcdmh-nav .dropdown').forEach(d => d.style.display = 'none');
                    dd.style.display = isOpen ? 'none' : 'block';
                }
            });
        }
    });
});
</script>
<!-- ======================================== -->
<!-- FIN FICHIER : nav.html -->
<!-- ======================================== -->
'@
}

# ===== MAIN =====

# 1. Créer le fichier nav.html
$navPath = Join-Path $chemin_site "nav.html"
if (-not $simulation) {
    Set-Content -Path $navPath -Value (Get-FichierNavHtml) -Encoding UTF8
    Write-Host "✅ Création de $navPath" -ForegroundColor Green
} else {
    Write-Host "🔍 [SIMULATION] Création de $navPath" -ForegroundColor Yellow
}

# 2. Récupérer tous les fichiers HTML
$htmlFiles = Get-ChildItem -Path $chemin_site -Filter "*.html" -File
$compteur = 0
$fichiersModifies = @()
$fichiersErreurs = @()

foreach ($file in $htmlFiles) {
    # Ne pas traiter nav.html lui-même
    if ($file.Name -eq "nav.html") { continue }
    
    Write-Host "📄 Traitement : $($file.Name)" -ForegroundColor Gray
    $contenuOriginal = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    
    # Sauvegarde (optionnelle)
    # Copy-Item -Path $file.FullName -Destination "$($file.FullName).backup" -Force
    
    # Vérifier la syntaxe
    $erreurs = Test-CorrectSyntaxe -contenu $contenuOriginal
    if ($erreurs.Count -gt 0) {
        Write-Host "   ⚠️ Erreurs détectées :" -ForegroundColor Yellow
        foreach ($err in $erreurs) {
            Write-Host "      $err" -ForegroundColor Yellow
        }
        $fichiersErreurs += $file.Name
    }
    
    # Remplacer l'ancienne navigation par la nouvelle
    $nouveauContenu = $contenuOriginal
    
    # Pattern pour trouver la navigation existante (du début jusqu'à </nav>)
    $pattern = '(?s)<nav.*?</nav>'
    $remplacement = Get-NouvelleNavigation
    
    if ($nouveauContenu -match $pattern) {
        $nouveauContenu = $nouveauContenu -replace $pattern, $remplacement
        Write-Host "   ✅ Navigation remplacée" -ForegroundColor Green
        
        if (-not $simulation) {
            Set-Content -Path $file.FullName -Value $nouveauContenu -Encoding UTF8
        }
        $compteur++
        $fichiersModifies += $file.Name
    } else {
        Write-Host "   ⚠️ Aucune balise <nav> trouvée" -ForegroundColor Yellow
    }
}

# 3. Rapport final
Write-Host ""
Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host "📊 RAPPORT DE CONVERSION" -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host "✅ Fichiers modifiés : $compteur"
if ($fichiersModifies.Count -gt 0) {
    $fichiersModifies | ForEach-Object { Write-Host "   - $_" -ForegroundColor Green }
}

if ($fichiersErreurs.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️ Fichiers avec erreurs de syntaxe : $($fichiersErreurs.Count)" -ForegroundColor Yellow
    $fichiersErreurs | ForEach-Object { Write-Host "   - $_" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "📁 Fichier nav.html créé dans $chemin_site" -ForegroundColor Cyan
Write-Host ""
Write-Host "🚀 Action suivante :" -ForegroundColor Green
Write-Host "   1. Vérifie quelques pages en local"
Write-Host "   2. Publie tout le site sur GitHub"
Write-Host "   3. Le bouton 'Dernière vidéo' pointera toujours vers l'accueil"
Write-Host ""

if ($simulation) {
    Write-Host "ℹ️ Mode SIMULATION activé : aucun fichier n'a été modifié" -ForegroundColor Yellow
}