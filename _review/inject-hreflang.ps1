# ═══════════════════════════════════════════════════════════════
# Script : Injection hreflang dans toutes les pages LCDMH
# Usage  : Ouvrir PowerShell dans F:\LCDMH_GitHub_Audit\ puis :
#          .\inject-hreflang.ps1
# ═══════════════════════════════════════════════════════════════

$baseUrl = "https://lcdmh.com"
$root = Get-Location
$count = 0
$skipped = 0

# Trouver tous les fichiers HTML
$files = Get-ChildItem -Path $root -Filter "*.html" -Recurse | Where-Object {
    $_.FullName -notmatch "_audit|_review|data[\\/]articles|Log Archives|facebook|seo[\\/]|index_files|roadbooks-html|LCDMH_Cadrage|widget-roadtrip"
}

foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    
    # Vérifier si hreflang est déjà présent
    if ($content -match 'hreflang') {
        $skipped++
        continue
    }
    
    # Calculer l'URL canonique
    $relPath = $file.FullName.Replace($root.Path + "\", "").Replace("\", "/")
    $pageUrl = "$baseUrl/$relPath"
    
    # Si c'est index.html à la racine
    if ($relPath -eq "index.html") {
        $pageUrl = "$baseUrl/"
    }
    
    # Construire les balises hreflang
    $hreflangTags = @"

    <!-- hreflang : ciblage francophone international -->
    <link rel="alternate" hreflang="fr" href="$pageUrl">
    <link rel="alternate" hreflang="x-default" href="$pageUrl">
"@

    # Injecter juste avant </head>
    $newContent = $content -replace '(</head>)', "$hreflangTags`n`$1"
    
    # Écrire le fichier
    [System.IO.File]::WriteAllText($file.FullName, $newContent, [System.Text.UTF8Encoding]::new($false))
    
    $count++
    Write-Host "OK $relPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "═══ TERMINÉ ═══" -ForegroundColor Cyan
Write-Host "$count pages modifiées" -ForegroundColor White
Write-Host "$skipped pages ignorées (hreflang déjà présent)" -ForegroundColor Gray
