# install_to_automate_yt.ps1 — deploie le pipeline retention_extractor
# dans F:\Automate_YT\ pour integration dans l'app Streamlit existante.
#
# A lancer depuis le clone Git du repo :
#   cd C:\Users\yves\Yesbali.github.io
#   powershell -ExecutionPolicy Bypass -File scripts\retention_extractor\install_to_automate_yt.ps1
#
# Effet :
#   1. Cree F:\Automate_YT\retention_extractor\ (si absent)
#   2. Copie tous les scripts .py et .json depuis le repo vers ce dossier
#   3. Copie page_retention_extractor.py a la racine F:\Automate_YT\
#   4. Verifie la presence du yt_token_analytics.json
#   5. Installe les dependances Python (yt-dlp, requests)
#   6. Verifie ffmpeg
#   7. Affiche le patch a coller dans app.py

param(
    [string]$TargetRoot = "F:\Automate_YT",
    [switch]$SkipPip,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Installation retention_extractor -> $TargetRoot ===" -ForegroundColor Cyan
Write-Host ""

# 1) Verifs prealables
if (-not (Test-Path $TargetRoot)) {
    Write-Host "ERREUR : $TargetRoot n'existe pas." -ForegroundColor Red
    Write-Host "Passe le bon chemin via -TargetRoot C:\chemin\vers\Automate_YT"
    exit 1
}

$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$SourceDir = Join-Path $RepoRoot "scripts\retention_extractor"

if (-not (Test-Path $SourceDir)) {
    Write-Host "ERREUR : dossier source introuvable : $SourceDir" -ForegroundColor Red
    exit 1
}

Write-Host "Source : $SourceDir"
Write-Host "Cible  : $TargetRoot"
Write-Host ""

# 2) Copie du dossier retention_extractor/
$PipelineTarget = Join-Path $TargetRoot "retention_extractor"
if ((Test-Path $PipelineTarget) -and (-not $Force)) {
    Write-Host "[*] $PipelineTarget existe deja. Mise a jour des fichiers..." -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path $PipelineTarget -Force | Out-Null
    Write-Host "[+] Cree $PipelineTarget"
}

# Copier tous les scripts du pipeline, SAUF la page Streamlit (qui va a la racine)
$PipelineFiles = @(
    "common.py",
    "list_candidates.py",
    "fetch_retention.py",
    "detect_peaks.py",
    "extract_clips.py",
    "upload_clip.py",
    "run_pipeline.py",
    "config.example.json",
    "requirements.txt",
    "README.md"
)
foreach ($f in $PipelineFiles) {
    $src = Join-Path $SourceDir $f
    $dst = Join-Path $PipelineTarget $f
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "    -> $f"
    } else {
        Write-Host "    ! source manquante : $f" -ForegroundColor Yellow
    }
}

# 3) Copie de la page Streamlit a la racine de F:\Automate_YT\
$PageSrc = Join-Path $SourceDir "page_retention_extractor.py"
$PageDst = Join-Path $TargetRoot "page_retention_extractor.py"
if (Test-Path $PageSrc) {
    if ((Test-Path $PageDst) -and (-not $Force)) {
        Write-Host ""
        Write-Host "[*] $PageDst existe deja. Ecraser ? (o/N)" -ForegroundColor Yellow
        $r = Read-Host
        if ($r -ne "o" -and $r -ne "O") {
            Write-Host "    (conserve l'existant)"
        } else {
            Copy-Item $PageSrc $PageDst -Force
            Write-Host "    -> page_retention_extractor.py (ecrase)"
        }
    } else {
        Copy-Item $PageSrc $PageDst -Force
        Write-Host ""
        Write-Host "[+] page_retention_extractor.py -> $TargetRoot"
    }
}

# 4) Creer config.json si absent
$ConfigTarget = Join-Path $PipelineTarget "config.json"
if (-not (Test-Path $ConfigTarget)) {
    $example = Join-Path $PipelineTarget "config.example.json"
    Copy-Item $example $ConfigTarget -Force
    Write-Host "[+] config.json cree depuis config.example.json"
}

# 5) Verifier yt_token_analytics.json
$TokenPath = Join-Path $TargetRoot "yt_token_analytics.json"
Write-Host ""
if (Test-Path $TokenPath) {
    Write-Host "[OK] yt_token_analytics.json present dans $TargetRoot" -ForegroundColor Green
} else {
    Write-Host "[!!] yt_token_analytics.json MANQUANT dans $TargetRoot" -ForegroundColor Red
    Write-Host "     -> Lance 'python scripts\generate_yt_token.py' depuis le clone Git"
    Write-Host "     -> Ou copie-le depuis un autre dossier s'il existe deja."
}

# 6) Dependances Python
if (-not $SkipPip) {
    Write-Host ""
    Write-Host "[*] pip install -r requirements.txt ..."
    $req = Join-Path $PipelineTarget "requirements.txt"
    & python -m pip install --quiet --disable-pip-version-check -r $req
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Dependances Python installees" -ForegroundColor Green
    } else {
        Write-Host "[!!] pip install a echoue (code $LASTEXITCODE)" -ForegroundColor Red
    }
}

# 7) Verifier ffmpeg
Write-Host ""
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) {
    Write-Host "[OK] ffmpeg present : $($ffmpeg.Source)" -ForegroundColor Green
} else {
    Write-Host "[!!] ffmpeg absent du PATH. Installe via : winget install Gyan.FFmpeg" -ForegroundColor Yellow
}

$ytdlp = Get-Command yt-dlp -ErrorAction SilentlyContinue
if ($ytdlp) {
    Write-Host "[OK] yt-dlp present : $($ytdlp.Source)" -ForegroundColor Green
} else {
    Write-Host "[OK] yt-dlp via 'python -m yt_dlp' (installe par pip)" -ForegroundColor Green
}

# 8) Rappel d'integration app.py
Write-Host ""
Write-Host "=== TERMINE ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Patch a ajouter dans $TargetRoot\app.py :" -ForegroundColor Yellow
Write-Host ""
Write-Host "  # 1) En haut du fichier, avec les autres imports de pages :"
Write-Host "  from page_retention_extractor import page_retention_extractor" -ForegroundColor White
Write-Host ""
Write-Host "  # 2) Dans le dict/routing de pages, ajoute une entree :"
Write-Host '  "Retention Extractor (clips best-of)": page_retention_extractor,' -ForegroundColor White
Write-Host ""
Write-Host "Puis relance ton app Streamlit :"
Write-Host "  streamlit run $TargetRoot\app.py" -ForegroundColor White
Write-Host ""
