# ============================================
# SCRIPT : nettoyer_navigation.ps1
# BUT    : Supprimer les scripts de navigation en double
#          dans tous les fichiers HTML de F:\LCDMH
# AUTEUR : LCDMH
# DATE   : 2026-03-09
# ============================================

param(
    [string]$chemin_site = "F:\LCDMH",
    [switch]$simulation = $false,
    [switch]$creer_backup = $true
)

Write-Host "🧹 NETTOYAGE DES FICHIERS HTML LCDMH" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "📁 Dossier cible : $chemin_site"
if ($simulation) {
    Write-Host "⚡ MODE SIMULATION : Aucun fichier ne sera modifié" -ForegroundColor Yellow
}
if ($creer_backup) {
    Write-Host "💾 Sauvegarde activée : fichiers .backup créés" -ForegroundColor Green
}
Write-Host ""

# ===== FONCTIONS =====

function Get-NouveauScriptNavigation {
    return @'
<!-- ======================================== -->
<!-- NAVIGATION UNIQUE LCDMH -->
<!-- ======================================== -->
<div id="lcdmh-nav-container"></div>
<script>
(function() {
    // Déterminer le chemin de base (pour que ça marche en local et sur le serveur)
    var baseUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
        ? '' 
        : '/';
    
    fetch(baseUrl + 'nav.html?t=' + Date.now())
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
            document.getElementById('lcdmh-nav-container').innerHTML = 
                '<nav style="background:#fff;padding:1rem;"><a href="index.html" style="color:#e67e22;font-weight:bold;font-size:1.5rem;">LCDMH</a></nav>';
        });
})();
</script>
<!-- ======================================== -->
'@
}

function Test-ContientAncienScript {
    param([string]$contenu)
    
    # Patterns pour détecter l'ancien script de navigation
    $patterns = @(
        'var isMobile = function\(\)\{ return window\.innerWidth <= 900; \};',
        'document\.querySelectorAll\('\''#lcdmh-nav \.has-drop'\''\)',
        'item\.addEventListener\('\''mouseenter'\'',
        'dd\.style\.display='\''block'\'''
    )
    
    foreach ($pattern in $patterns) {
        if ($contenu -match $pattern) {
            return $true
        }
    }
    return $false
}

function Test-ContientNouveauScript {
    param([string]$contenu)
    
    # Vérifier si le nouveau script est déjà présent
    return ($contenu -match 'fetch\(.*nav\.html')
}

function Get-ContenuNettoye {
    param([string]$contenuOriginal)
    
    $nouveauScript = Get-NouveauScriptNavigation
    $contenuNettoye = $contenuOriginal
    
    # 1. Supprimer l'ancien script de navigation (s'il existe)
    # Pattern pour capturer tout l'ancien script (de <script> jusqu'à </script>)
    $patternAncienScript = '(?s)<script>\s*// === NAVIGATION JS.*?</script>'
    $contenuNettoye = $contenuNettoye -replace $patternAncienScript, ''
    
    # 2. Vérifier si le nouveau script est déjà présent
    if ($contenuNettoye -notmatch 'fetch\(.*nav\.html') {
        # Chercher l'emplacement idéal pour insérer le nouveau script
        # Après la balise <body> ou après un éventuel commentaire de début
        if ($contenuNettoye -match '<body>') {
            $contenuNettoye = $contenuNettoye -replace '<body>', "<body>`n`n$nouveauScript"
        } elseif ($contenuNettoye -match '<!-- ======================================== -->\s*<!-- === DÉBUT NAVIGATION =================== -->') {
            $contenuNettoye = $contenuNettoye -replace '<!-- === DÉBUT NAVIGATION =================== -->.*?<!-- === FIN NAVIGATION ===================== -->', $nouveauScript
        } else {
            # Fallback : insérer après <body>
            $contenuNettoye = $contenuNettoye -replace '<body>', "<body>`n`n$nouveauScript"
        }
    }
    
    return $contenuNettoye
}

# ===== MAIN =====

# Récupérer tous les fichiers HTML
$htmlFiles = Get-ChildItem -Path $chemin_site -Filter "*.html" -File | Sort-Object Name
$compteurModifies = 0
$compteurDejaOk = 0
$fichiersModifies = @()
$fichiersDejaOk = @()
$fichiersErreurs = @()

Write-Host "📑 ANALYSE DES FICHIERS :" -ForegroundColor Cyan
Write-Host ""

foreach ($file in $htmlFiles) {
    # Ignorer nav.html lui-même
    if ($file.Name -eq "nav.html") { 
        Write-Host "⏭️  $($file.Name) : ignoré (fichier navigation)" -ForegroundColor Gray
        continue 
    }
    
    Write-Host "📄 $($file.Name) :" -ForegroundColor White -NoNewline
    
    try {
        $contenuOriginal = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        
        # Vérifier si le fichier contient l'ancien script
        $aAncienScript = Test-ContientAncienScript -contenu $contenuOriginal
        $aNouveauScript = Test-ContientNouveauScript -contenu $contenuOriginal
        
        if (-not $aAncienScript -and $aNouveauScript) {
            Write-Host " ✅ déjà propre" -ForegroundColor Green
            $compteurDejaOk++
            $fichiersDejaOk += $file.Name
            continue
        }
        
        if ($aAncienScript) {
            Write-Host " ⚠️ ancien script détecté" -ForegroundColor Yellow -NoNewline
            
            # Nettoyer le contenu
            $contenuNettoye = Get-ContenuNettoye -contenuOriginal $contenuOriginal
            
            if (-not $simulation) {
                # Créer une sauvegarde si demandé
                if ($creer_backup) {
                    $backupPath = "$($file.FullName).backup"
                    Copy-Item -Path $file.FullName -Destination $backupPath -Force
                    Write-Host " (backup créé)" -ForegroundColor Gray -NoNewline
                }
                
                # Écrire le nouveau contenu
                Set-Content -Path $file.FullName -Value $contenuNettoye -Encoding UTF8
                Write-Host " → ✅ nettoyé" -ForegroundColor Green
            } else {
                Write-Host " → 🔍 [SIMULATION] serait nettoyé" -ForegroundColor Yellow
            }
            
            $compteurModifies++
            $fichiersModifies += $file.Name
        } else {
            Write-Host " ✅ déjà propre" -ForegroundColor Green
            $compteurDejaOk++
            $fichiersDejaOk += $file.Name
        }
    }
    catch {
        Write-Host " ❌ ERREUR : $_" -ForegroundColor Red
        $fichiersErreurs += $file.Name
    }
}

# ===== RAPPORT FINAL =====
Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "📊 RAPPORT DE NETTOYAGE" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

Write-Host "📁 Dossier : $chemin_site" -ForegroundColor White
Write-Host "✅ Fichiers déjà propres : $compteurDejaOk" -ForegroundColor Green
Write-Host "🔧 Fichiers modifiés : $compteurModifies" -ForegroundColor Yellow
Write-Host "❌ Fichiers en erreur : $($fichiersErreurs.Count)" -ForegroundColor Red
Write-Host ""

if ($fichiersModifies.Count -gt 0) {
    Write-Host "📄 Fichiers modifiés :" -ForegroundColor Cyan
    $fichiersModifies | ForEach-Object {
        Write-Host "   - $_" -ForegroundColor Gray
    }
    Write-Host ""
}

if ($fichiersDejaOk.Count -gt 0) {
    Write-Host "📄 Fichiers déjà propres :" -ForegroundColor Cyan
    $fichiersDejaOk | ForEach-Object {
        Write-Host "   - $_" -ForegroundColor Gray
    }
    Write-Host ""
}

if ($fichiersErreurs.Count -gt 0) {
    Write-Host "📄 Fichiers en erreur :" -ForegroundColor Cyan
    $fichiersErreurs | ForEach-Object {
        Write-Host "   - $_" -ForegroundColor Red
    }
    Write-Host ""
}

# ===== VÉRIFICATION FINALE =====
Write-Host "🔍 VÉRIFICATION :" -ForegroundColor Cyan
Write-Host "1. Ouvre index.html en local" -ForegroundColor White
Write-Host "2. Vérifie que le menu s'affiche" -ForegroundColor White
Write-Host "3. Vérifie que les dropdowns fonctionnent" -ForegroundColor White
Write-Host "4. Teste quelques pages road trip" -ForegroundColor White
Write-Host ""

if ($simulation) {
    Write-Host "ℹ️ Mode SIMULATION activé : aucun fichier n'a été modifié" -ForegroundColor Yellow
    Write-Host "   Relance sans -simulation pour appliquer les changements" -ForegroundColor Yellow
} else {
    Write-Host "✅ NETTOYAGE TERMINÉ !" -ForegroundColor Green
    if ($creer_backup) {
        Write-Host "💾 Les fichiers originaux ont été sauvegardés avec l'extension .backup" -ForegroundColor Gray
        Write-Host "   Pour restaurer : copiez le fichier .backup par-dessus l'original" -ForegroundColor Gray
    }
}