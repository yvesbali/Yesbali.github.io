# ═══════════════════════════════════════════════════════════════
# LCDMH — Injection du nav-loader dans toutes les pages HTML
# ═══════════════════════════════════════════════════════════════
#
# Ce script :
# 1. Parcourt tous les fichiers .html du repo
# 2. Saute ceux qui contiennent déjà la balise nav-loader
# 3. Saute nav.html lui-même
# 4. Injecte <script src="/js/lcdmh-nav-loader.js" defer></script>
#    juste après <body> (ou sa variante avec attributs)
# 5. Supprime les anciens bandeaux "Menu temporairement indisponible"
#
# Usage : exécuter depuis la racine du repo
#   cd F:\LCDMH_GitHub_Audit
#   .\inject-nav-loader.ps1
#

$repoRoot = $PSScriptRoot
if (-not $repoRoot) { $repoRoot = Get-Location }

$scriptTag = '<script src="/js/lcdmh-nav-loader.js" defer></script>'
$count = 0
$skipped = 0
$cleaned = 0

$files = Get-ChildItem -Path $repoRoot -Recurse -Filter "*.html" | Where-Object {
    $_.Name -ne "nav.html" -and
    $_.FullName -notlike "*\node_modules\*" -and
    $_.FullName -notlike "*\.git\*"
}

foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8

    # Déjà injecté ?
    if ($content -match "lcdmh-nav-loader\.js") {
        $skipped++
        continue
    }

    $modified = $false

    # Supprimer l'ancien bandeau "Menu temporairement indisponible"
    # Pattern : div/p/span contenant ce texte, souvent dans une .topbar
    $patterns = @(
        '(?s)<div[^>]*class="topbar"[^>]*>.*?</div>\s*',
        '(?s)<div[^>]*>.*?Menu temporairement indisponible.*?</div>\s*',
        '(?s)<p[^>]*>.*?Menu temporairement indisponible.*?</p>\s*'
    )
    foreach ($pattern in $patterns) {
        if ($content -match $pattern) {
            $content = $content -replace $pattern, ''
            $cleaned++
            $modified = $true
        }
    }

    # Injecter après <body...>
    if ($content -match '(<body[^>]*>)') {
        $bodyTag = $Matches[1]
        $content = $content -replace [regex]::Escape($bodyTag), "$bodyTag`n$scriptTag"
        $modified = $true
    }
    else {
        Write-Warning "Pas de <body> trouvé dans : $($file.FullName)"
        continue
    }

    if ($modified) {
        Set-Content -Path $file.FullName -Value $content -Encoding UTF8 -NoNewline
        $count++
        Write-Host "  OK  $($file.FullName)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "═══ RÉSUMÉ ═══" -ForegroundColor Cyan
Write-Host "  Fichiers modifiés : $count" -ForegroundColor Green
Write-Host "  Déjà injectés (skippés) : $skipped" -ForegroundColor Yellow
Write-Host "  Bandeaux 'menu indispo' nettoyés : $cleaned" -ForegroundColor Magenta
Write-Host ""
Write-Host "Prochaines étapes :" -ForegroundColor Cyan
Write-Host "  1. Copier lcdmh-nav-loader.js dans js/ du repo"
Write-Host "  2. git add -A"
Write-Host "  3. git commit -m 'Nav: injection menu dynamique sur toutes les pages'"
Write-Host "  4. git push origin main"
