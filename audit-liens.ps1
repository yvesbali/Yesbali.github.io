# LCDMH - Audit complet des liens internes
# Usage : powershell -ExecutionPolicy Bypass -File ".\audit-liens.ps1"

param(
    [string]$RepoRoot = (Get-Location).Path
)

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$report = @()
$report += "======================================================="
$report += "  AUDIT LIENS INTERNES - LCDMH"
$report += "  $timestamp"
$report += "  Repo : $RepoRoot"
$report += "======================================================="
$report += ""

$totalFiles = 0
$totalLinks = 0
$totalBroken = 0
$totalExternal = 0
$totalAnchors = 0
$totalSkipped = 0

$brokenByPage = @{}
$allMissingTargets = @{}

$files = Get-ChildItem -Path $RepoRoot -Recurse -Filter "*.html" | Where-Object {
    $_.FullName -notlike "*\.git\*" -and
    $_.FullName -notlike "*\node_modules\*" -and
    $_.Name -ne "nav.html"
}

$totalFiles = $files.Count

foreach ($file in $files) {
    $relPath = $file.FullName.Substring($RepoRoot.Length + 1)
    $fileDir = $file.DirectoryName
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if (-not $content) { continue }

    $pattern = '(?:href|src|action)="([^"]*)"'
    $regexMatches = [regex]::Matches($content, $pattern)

    foreach ($m in $regexMatches) {
        $url = $m.Groups[1].Value.Trim()
        $totalLinks++

        if (-not $url -or $url -eq "#" -or $url -eq "javascript:void(0)") {
            $totalSkipped++
            continue
        }

        if ($url -match "^https?://" -or $url -match "^mailto:" -or $url -match "^tel:" -or $url -match "^data:") {
            $totalExternal++
            continue
        }

        if ($url -match "^#") {
            $totalAnchors++
            continue
        }

        $cleanUrl = $url -replace "[#?].*$", ""
        if (-not $cleanUrl) { continue }

        if ($cleanUrl.StartsWith("/")) {
            $targetPath = Join-Path $RepoRoot $cleanUrl.TrimStart("/")
        } else {
            $targetPath = Join-Path $fileDir $cleanUrl
        }

        try {
            $targetPath = [System.IO.Path]::GetFullPath($targetPath)
        } catch {
            $totalBroken++
            if (-not $brokenByPage.ContainsKey($relPath)) { $brokenByPage[$relPath] = @() }
            $brokenByPage[$relPath] += "  INVALIDE : $url"
            continue
        }

        $exists = (Test-Path -LiteralPath $targetPath)

        if ($exists -and (Test-Path -LiteralPath $targetPath -PathType Container)) {
            $indexInDir = Join-Path $targetPath "index.html"
            $exists = (Test-Path -LiteralPath $indexInDir)
        }

        if (-not $exists) {
            $totalBroken++
            if (-not $brokenByPage.ContainsKey($relPath)) { $brokenByPage[$relPath] = @() }
            $brokenByPage[$relPath] += "  [BROKEN] $url"

            if (-not $allMissingTargets.ContainsKey($cleanUrl)) {
                $allMissingTargets[$cleanUrl] = @()
            }
            $allMissingTargets[$cleanUrl] += $relPath
        }
    }
}

$report += "RESUME"
$report += "------"
$report += "  Fichiers HTML scannes : $totalFiles"
$report += "  Liens totaux trouves  : $totalLinks"
$report += "  Liens internes OK     : $($totalLinks - $totalBroken - $totalExternal - $totalAnchors - $totalSkipped)"
$report += "  Liens externes        : $totalExternal (non verifies)"
$report += "  Ancres (#)            : $totalAnchors"
$report += "  Ignores (vides/js)    : $totalSkipped"
$report += "  LIENS CASSES          : $totalBroken"
$report += "  Pages avec erreurs    : $($brokenByPage.Count)"
$report += ""

if ($totalBroken -eq 0) {
    $report += "OK - Aucun lien casse detecte !"
} else {
    $report += "======================================================="
    $report += "DETAIL PAR PAGE"
    $report += "======================================================="
    $report += ""

    foreach ($page in ($brokenByPage.Keys | Sort-Object)) {
        $links = $brokenByPage[$page]
        $report += "PAGE: $page ($($links.Count) lien(s) casse(s))"
        foreach ($l in $links) {
            $report += $l
        }
        $report += ""
    }

    $report += "======================================================="
    $report += "CIBLES MANQUANTES (par frequence)"
    $report += "======================================================="
    $report += ""

    $sorted = $allMissingTargets.GetEnumerator() | Sort-Object { $_.Value.Count } -Descending
    foreach ($entry in $sorted) {
        $target = $entry.Key
        $pages = $entry.Value
        $report += "  MANQUANT: $target - reference dans $($pages.Count) page(s)"
        if ($pages.Count -le 5) {
            foreach ($p in $pages) {
                $report += "       dans: $p"
            }
        } else {
            for ($i = 0; $i -lt 3; $i++) {
                $report += "       dans: $($pages[$i])"
            }
            $report += "       ... et $($pages.Count - 3) autre(s)"
        }
    }
}

$report += ""
$report += "======================================================="
$report += "  Audit termine : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$report += "======================================================="

$reportPath = Join-Path $RepoRoot "audit-liens-rapport.txt"
$report | Out-File -FilePath $reportPath -Encoding ASCII
Write-Host ""
Write-Host "=== AUDIT TERMINE ===" -ForegroundColor Cyan
Write-Host "  Fichiers scannes  : $totalFiles" -ForegroundColor White
Write-Host "  Liens verifies    : $totalLinks" -ForegroundColor White

if ($totalBroken -gt 0) {
    Write-Host "  LIENS CASSES      : $totalBroken" -ForegroundColor Red
    Write-Host "  Pages concernees  : $($brokenByPage.Count)" -ForegroundColor Red
} else {
    Write-Host "  Aucun lien casse !" -ForegroundColor Green
}

Write-Host ""
Write-Host "  Rapport : $reportPath" -ForegroundColor Yellow
Write-Host ""
