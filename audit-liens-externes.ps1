# LCDMH - Audit des liens externes
# Verifie tous les liens https:// dans les pages HTML
# Classe par domaine, detecte les 404 et domaines inconnus
#
# Usage : powershell -ExecutionPolicy Bypass -File ".\audit-liens-externes.ps1"

param(
    [string]$RepoRoot = (Get-Location).Path
)

# === DOMAINES AUTORISES ===
# Ajoute ici tous les domaines partenaires et connus
$domainesAutorises = @(
    # LCDMH
    "lcdmh.com"
    "www.lcdmh.com"
    # YouTube
    "youtube.com"
    "www.youtube.com"
    "youtu.be"
    "m.youtube.com"
    # Google
    "fonts.googleapis.com"
    "fonts.gstatic.com"
    "www.google.com"
    "maps.google.com"
    "www.googletagmanager.com"
    "www.google-analytics.com"
    # Partenaires LCDMH
    "aoocci.com"
    "www.aoocci.com"
    "carpuride.com"
    "www.carpuride.com"
    "blackview.fr"
    "www.blackview.fr"
    "www.blackview.hk"
    "olight.fr"
    "www.olight.fr"
    "www.olightstore.com"
    "komobi.fr"
    "www.komobi.fr"
    "innovv.com"
    "www.innovv.com"
    "aferiy.com"
    "www.aferiy.com"
    # Affiliation
    "www.awin1.com"
    "amzn.to"
    "www.amazon.fr"
    "amazon.fr"
    # Outils moto / voyage
    "kurviger.de"
    "www.kurviger.de"
    "sygic.com"
    "www.sygic.com"
    # Reseaux sociaux
    "instagram.com"
    "www.instagram.com"
    "facebook.com"
    "www.facebook.com"
    "twitter.com"
    "x.com"
    "www.tiktok.com"
    "tiktok.com"
    # CDN et technique
    "cdnjs.cloudflare.com"
    "cdn.jsdelivr.net"
    "unpkg.com"
    "kit.fontawesome.com"
    "ka-f.fontawesome.com"
    # Autres connus
    "github.com"
    "www.github.com"
    "wa.me"
    "api.whatsapp.com"
)

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$report = @()
$report += "======================================================="
$report += "  AUDIT LIENS EXTERNES - LCDMH"
$report += "  $timestamp"
$report += "======================================================="
$report += ""

# Collecter tous les liens externes
$allLinks = @{}  # url -> liste de pages sources
$domainCount = @{}  # domaine -> nombre de liens

$files = Get-ChildItem -Path $RepoRoot -Recurse -Filter "*.html" | Where-Object {
    $_.FullName -notlike "*\.git\*" -and $_.Name -ne "nav.html"
}

Write-Host "Scan des fichiers HTML..." -ForegroundColor Cyan

foreach ($file in $files) {
    $relPath = $file.FullName.Substring($RepoRoot.Length + 1)
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if (-not $content) { continue }

    $matches = [regex]::Matches($content, '(?:href|src)="(https?://[^"]+)"')
    foreach ($m in $matches) {
        $url = $m.Groups[1].Value.Trim()
        if (-not $allLinks.ContainsKey($url)) {
            $allLinks[$url] = @()
        }
        $allLinks[$url] += $relPath

        # Compter par domaine
        try {
            $uri = [System.Uri]$url
            $domain = $uri.Host
            if (-not $domainCount.ContainsKey($domain)) { $domainCount[$domain] = 0 }
            $domainCount[$domain]++
        } catch {}
    }
}

$totalUrls = $allLinks.Count
$totalRefs = ($allLinks.Values | ForEach-Object { $_.Count } | Measure-Object -Sum).Sum
Write-Host "  URLs uniques : $totalUrls" -ForegroundColor White
Write-Host "  References totales : $totalRefs" -ForegroundColor White
Write-Host "  Domaines : $($domainCount.Count)" -ForegroundColor White
Write-Host ""

# === SECTION 1 : DOMAINES INCONNUS ===
$report += "======================================================="
$report += "SECTION 1 : DOMAINES INCONNUS (a verifier en priorite)"
$report += "======================================================="
$report += ""

$domainesInconnus = @{}
foreach ($domain in $domainCount.Keys) {
    $isKnown = $false
    foreach ($autorise in $domainesAutorises) {
        if ($domain -eq $autorise -or $domain.EndsWith("." + $autorise)) {
            $isKnown = $true
            break
        }
    }
    if (-not $isKnown) {
        $domainesInconnus[$domain] = $domainCount[$domain]
    }
}

if ($domainesInconnus.Count -eq 0) {
    $report += "  OK - Tous les domaines sont connus et autorises."
    Write-Host "  Domaines inconnus : 0" -ForegroundColor Green
} else {
    Write-Host "  DOMAINES INCONNUS : $($domainesInconnus.Count)" -ForegroundColor Red
    $sorted = $domainesInconnus.GetEnumerator() | Sort-Object Value -Descending
    foreach ($entry in $sorted) {
        $report += "  [INCONNU] $($entry.Key) - $($entry.Value) lien(s)"
        # Trouver les URLs et pages pour ce domaine
        foreach ($url in $allLinks.Keys) {
            try {
                $uri = [System.Uri]$url
                if ($uri.Host -eq $entry.Key) {
                    $pages = ($allLinks[$url] | Select-Object -Unique) -join ", "
                    $shortUrl = $url
                    if ($shortUrl.Length -gt 100) { $shortUrl = $shortUrl.Substring(0, 97) + "..." }
                    $report += "       $shortUrl"
                    $report += "       dans: $pages"
                }
            } catch {}
        }
        $report += ""
    }
}
$report += ""

# === SECTION 2 : VERIFICATION HTTP (404, timeouts) ===
$report += "======================================================="
$report += "SECTION 2 : VERIFICATION HTTP (404, erreurs, timeouts)"
$report += "======================================================="
$report += ""

Write-Host "Verification HTTP des $totalUrls URLs..." -ForegroundColor Cyan
$broken = @()
$ok = 0
$errors = 0
$skipped = 0
$i = 0

# Limiter aux URLs de pages (pas les CDN/fonts/analytics)
$skipDomains = @("fonts.googleapis.com", "fonts.gstatic.com", "www.googletagmanager.com",
    "www.google-analytics.com", "cdnjs.cloudflare.com", "cdn.jsdelivr.net",
    "unpkg.com", "kit.fontawesome.com", "ka-f.fontawesome.com")

foreach ($url in $allLinks.Keys) {
    $i++
    if ($i % 10 -eq 0) {
        Write-Host "  [$i/$totalUrls] en cours..." -ForegroundColor Gray
    }

    # Skip CDN et analytics
    $skipThis = $false
    try {
        $uri = [System.Uri]$url
        if ($uri.Host -in $skipDomains) { $skipped++; continue }
    } catch { $skipped++; continue }

    try {
        $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop -MaximumRedirection 5
        $statusCode = $response.StatusCode
        if ($statusCode -ge 400) {
            $pages = ($allLinks[$url] | Select-Object -Unique) -join ", "
            $broken += [PSCustomObject]@{ Status=$statusCode; Url=$url; Pages=$pages }
            $errors++
        } else {
            $ok++
        }
    } catch {
        $statusCode = 0
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        $pages = ($allLinks[$url] | Select-Object -Unique) -join ", "

        # Distinguer 403 (souvent du bot-blocking) des vrais 404
        $label = "ERREUR"
        if ($statusCode -eq 403) { $label = "403-BLOQUE" }
        elseif ($statusCode -eq 404) { $label = "404-ABSENT" }
        elseif ($statusCode -eq 0) { $label = "TIMEOUT" }
        else { $label = "HTTP-$statusCode" }

        $broken += [PSCustomObject]@{ Status=$label; Url=$url; Pages=$pages }
        $errors++
    }
}

if ($broken.Count -eq 0) {
    $report += "  OK - Tous les liens externes repondent correctement."
    Write-Host "  Liens en erreur : 0" -ForegroundColor Green
} else {
    Write-Host "  LIENS EN ERREUR : $($broken.Count)" -ForegroundColor Red
    foreach ($b in ($broken | Sort-Object Status)) {
        $report += "  [$($b.Status)] $($b.Url)"
        $report += "       dans: $($b.Pages)"
        $report += ""
    }
}

$report += ""

# === SECTION 3 : TOUS LES DOMAINES (inventaire) ===
$report += "======================================================="
$report += "SECTION 3 : INVENTAIRE COMPLET DES DOMAINES"
$report += "======================================================="
$report += ""

$sortedDomains = $domainCount.GetEnumerator() | Sort-Object Value -Descending
foreach ($entry in $sortedDomains) {
    $isKnown = $domainesAutorises -contains $entry.Key
    $tag = if ($isKnown) { "OK" } else { "???" }
    $report += "  [$tag] $($entry.Key) - $($entry.Value) lien(s)"
}

$report += ""
$report += "======================================================="
$report += "RESUME"
$report += "======================================================="
$report += "  URLs uniques        : $totalUrls"
$report += "  Domaines            : $($domainCount.Count)"
$report += "  Domaines inconnus   : $($domainesInconnus.Count)"
$report += "  Liens OK            : $ok"
$report += "  Liens en erreur     : $errors"
$report += "  Liens CDN (skip)    : $skipped"
$report += ""
$report += "  Audit termine : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$report += "======================================================="

$reportPath = Join-Path $RepoRoot "audit-liens-externes-rapport.txt"
$report | Out-File -FilePath $reportPath -Encoding ASCII

Write-Host ""
Write-Host "=== AUDIT TERMINE ===" -ForegroundColor Cyan
Write-Host "  URLs verifiees      : $totalUrls" -ForegroundColor White
Write-Host "  Domaines inconnus   : $($domainesInconnus.Count)" -ForegroundColor $(if ($domainesInconnus.Count -gt 0) { "Red" } else { "Green" })
Write-Host "  Liens en erreur     : $errors" -ForegroundColor $(if ($errors -gt 0) { "Red" } else { "Green" })
Write-Host "  Rapport : $reportPath" -ForegroundColor Yellow
Write-Host ""
