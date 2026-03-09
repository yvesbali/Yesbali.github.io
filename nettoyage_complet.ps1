# ============================================
# SCRIPT : nettoyage_complet.ps1
# BUT    : NETTOYER TOUS les fichiers HTML de F:\LCDMH
#          - Supprimer anciens scripts
#          - Ajouter le bon script navigation
#          - Corriger les chemins
# AUTEUR : LCDMH
# DATE   : 2026-03-09
# ============================================

param(
    [string]$chemin_site = "F:\LCDMH",
    [switch]$simulation = $false
)

Write-Host "🔥 NETTOYAGE COMPLET LCDMH" -ForegroundColor Magenta
Write-Host "==========================" -ForegroundColor Magenta
Write-Host "📁 Dossier cible : $chemin_site"
if ($simulation) {
    Write-Host "⚡ MODE SIMULATION : Aucun fichier ne sera modifié" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  MODE RÉEL : Les fichiers seront modifiés (backup créés)" -ForegroundColor Red
}
Write-Host ""

# ===== FONCTIONS =====

function Get-BonScriptNavigation {
    return @'
<!-- ======================================== -->
<!-- NAVIGATION UNIQUE LCDMH (NE PAS MODIFIER) -->
<!-- ======================================== -->
<div id="lcdmh-nav-container"></div>
<script>
(function() {
    // Charger la navigation depuis nav.html (chemin relatif)
    fetch('nav.html?t=' + Date.now())
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
            // Fallback ultra minimal
            document.getElementById('lcdmh-nav-container').innerHTML = 
                '<nav style="background:#fff;padding:1rem;"><a href="index.html" style="color:#e67e22;font-weight:bold;font-size:1.5rem;">LCDMH</a></nav>';
        });
})();
</script>
<!-- ======================================== -->
'@
}

function Test-SiFichierASauver {
    param([string]$nom)
    # Ne pas traiter nav.html lui-même
    return $nom -ne "nav.html"
}

function Test-SiNavigationExistante {
    param([string]$contenu)
    # Vérifie s'il y a déjà un script qui charge nav.html
    return $contenu -match 'fetch\(.*nav\.html'
}

function Get-ContenuNettoye {
    param([string]$contenuOriginal)
    
    $bonScript = Get-BonScriptNavigation
    $contenuNettoye = $contenuOriginal
    
    # ÉTAPE 1 : Supprimer TOUS les anciens scripts de navigation
    # Pattern pour le script avec la variable isMobile
    $contenuNettoye = $contenuNettoye -replace '(?s)<script>\s*// === NAVIGATION JS.*?</script>', ''
    
    # Pattern pour le script du badge dernière vidéo
    $contenuNettoye = $contenuNettoye -replace '(?s)<script>\s*// ===== BADGE DERNIÈRE VIDÉO.*?</script>', ''
    
    # Pattern pour le script qui chargeait /nav.html (avec slash)
    $contenuNettoye = $contenuNettoye -replace '(?s)<div id="lcdmh-nav-container">.*?<script>.*?fetch\(.*?nav\.html.*?</script>', ''
    
    # ÉTAPE 2 : Ajouter le BON script après <body>
    if ($contenuNettoye -match '<body>') {
        $contenuNettoye = $contenuNettoye -replace '<body>', "<body>`n`n$bonScript"
    } else {
        # Si pas de body, ajouter après <html>
        $contenuNettoye = $contenuNettoye -replace '<html[^>]*>', "`$0`n$bonScript"
    }
    
    # ÉTAPE 3 : Corriger les liens YouTube (optionnel)
    # Remplacer les liens watch?v= par embed/ pour les vidéos
    # $contenuNettoye = $contenuNettoye -replace 'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', 'youtube.com/embed/$1'
    
    return $contenuNettoye
}

# ===== MAIN =====

# Récupérer TOUS les fichiers HTML
$htmlFiles = Get-ChildItem -Path $chemin_site -Filter "*.html" -File | Sort-Object Name
$compteurTotal = $htmlFiles.Count
$compteurModifies = 0
$compteurInchanges = 0
$fichiersModifies = @()
$fichiersInchanges = @()
$fichiersErreurs = @()

Write-Host "📑 ANALYSE DE $compteurTotal FICHIERS :" -ForegroundColor Cyan
Write-Host ""

$numero = 0
foreach ($file in $htmlFiles) {
    $numero++
    Write-Progress -Activity "Nettoyage des fichiers HTML" -Status "$numero / $compteurTotal : $($file.Name)" -PercentComplete (($numero / $compteurTotal) * 100)
    
    # Ignorer nav.html
    if (-not (Test-SiFichierASauver -nom $file.Name)) {
        Write-Host "⏭️  $($file.Name) : ignoré (fichier navigation)" -ForegroundColor Gray
        continue
    }
    
    Write-Host "📄 $($file.Name) :" -ForegroundColor White -NoNewline
    
    try {
        $contenuOriginal = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        $contenuNettoye = Get-ContenuNettoye -contenuOriginal $contenuOriginal
        
        # Vérifier si des modifications ont été faites
        if ($contenuOriginal -ne $contenuNettoye) {
            Write-Host " ⚠️ modifications nécessaires" -ForegroundColor Yellow -NoNewline
            
            if (-not $simulation) {
                # CRÉER UNE SAUVEGARDE
                $backupPath = "$($file.FullName).bak"
                Copy-Item -Path $file.FullName -Destination $backupPath -Force
                Write-Host " (backup .bak créé)" -ForegroundColor Gray -NoNewline
                
                # ÉCRIRE LE NOUVEAU CONTENU
                Set-Content -Path $file.FullName -Value $contenuNettoye -Encoding UTF8 -NoNewline
                Write-Host " → ✅ nettoyé" -ForegroundColor Green
            } else {
                Write-Host " → 🔍 [SIMULATION] serait nettoyé" -ForegroundColor Yellow
            }
            
            $compteurModifies++
            $fichiersModifies += $file.Name
        } else {
            Write-Host " ✅ déjà propre" -ForegroundColor Green
            $compteurInchanges++
            $fichiersInchanges += $file.Name
        }
    }
    catch {
        Write-Host " ❌ ERREUR : $_" -ForegroundColor Red
        $fichiersErreurs += $file.Name
    }
}

Write-Progress -Activity "Nettoyage des fichiers HTML" -Completed

# ===== RAPPORT FINAL =====
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Magenta
Write-Host "📊 RAPPORT FINAL DE NETTOYAGE" -ForegroundColor Magenta
Write-Host "=" * 70 -ForegroundColor Magenta
Write-Host ""

Write-Host "📁 Dossier : $chemin_site" -ForegroundColor White
Write-Host "📊 Total fichiers HTML : $compteurTotal" -ForegroundColor White
Write-Host "✅ Fichiers déjà propres : $compteurInchanges" -ForegroundColor Green
Write-Host "🔧 Fichiers modifiés : $compteurModifies" -ForegroundColor Yellow
Write-Host "❌ Fichiers en erreur : $($fichiersErreurs.Count)" -ForegroundColor Red
Write-Host ""

if ($fichiersModifies.Count -gt 0) {
    Write-Host "📄 FICHIERS MODIFIÉS :" -ForegroundColor Yellow
    $fichiersModifies | ForEach-Object {
        Write-Host "   - $_" -ForegroundColor Gray
    }
    Write-Host ""
}

if ($fichiersInchanges.Count -gt 0) {
    Write-Host "📄 FICHIERS DÉJÀ PROPRES :" -ForegroundColor Green
    $fichiersInchanges | ForEach-Object {
        Write-Host "   - $_" -ForegroundColor Gray
    }
    Write-Host ""
}

if ($fichiersErreurs.Count -gt 0) {
    Write-Host "📄 FICHIERS EN ERREUR :" -ForegroundColor Red
    $fichiersErreurs | ForEach-Object {
        Write-Host "   - $_" -ForegroundColor Red
    }
    Write-Host ""
}

# ===== INSTRUCTIONS FINALES =====
Write-Host "🔍 PROCÉDURE DE VÉRIFICATION :" -ForegroundColor Cyan
Write-Host "1. Ouvre ces pages en local (double-clique) :" -ForegroundColor White
Write-Host "   - index.html" -ForegroundColor Gray
Write-Host "   - cap-nord-moto.html" -ForegroundColor Gray
Write-Host "   - europe-asie-moto.html" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Vérifie pour CHAQUE page :" -ForegroundColor White
Write-Host "   ✅ Le menu s'affiche en haut" -ForegroundColor Gray
Write-Host "   ✅ Les dropdowns fonctionnent (survole Road Trips)" -ForegroundColor Gray
Write-Host "   ✅ Le bouton 'Dernière vidéo' est présent" -ForegroundColor Gray
Write-Host "   ✅ Le module road trip s'affiche (si ressources publiées)" -ForegroundColor Gray
Write-Host ""

if ($simulation) {
    Write-Host "ℹ️ Mode SIMULATION activé : AUCUN fichier n'a été modifié" -ForegroundColor Yellow
    Write-Host "   Pour appliquer les changements :" -ForegroundColor Yellow
    Write-Host "   .\nettoyage_complet.ps1" -ForegroundColor White
} else {
    Write-Host "✅ NETTOYAGE TERMINÉ !" -ForegroundColor Green
    Write-Host "💾 Les fichiers originaux ont été sauvegardés avec l'extension .bak" -ForegroundColor Gray
    Write-Host ""
    Write-Host "📦 POUR RÉIMPORTER TOUT LE SITE :" -ForegroundColor Cyan
    Write-Host "git add ." -ForegroundColor Yellow
    Write-Host "git commit -m '🧹 Nettoyage complet navigation ($compteurModifies fichiers)'" -ForegroundColor Yellow
    Write-Host "git push" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "⚠️  SI PROBLÈME :" -ForegroundColor Red
    Write-Host "   Renomme un fichier .bak pour restaurer l'original" -ForegroundColor White
}