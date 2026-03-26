# ============================================================
#  NETTOYAGE COMPLET du depot GitHub Yesbali.github.io
#  
#  ON GARDE UNIQUEMENT : road-trip-cap-nord-2025
#  ON SUPPRIME : tous les tests, Ecosse, Italie, Amerique,
#                lune, lunaire, .backup, etc.
#
#  Lancer : powershell -ExecutionPolicy Bypass -File "supprimer_fichiers_github.ps1"
#  Depuis : F:\LCDMH_GitHub_Audit
# ============================================================

Set-Location -Path "F:\LCDMH_GitHub_Audit"

Write-Host "`n=== Synchronisation avec GitHub ===" -ForegroundColor Cyan
git pull --rebase origin main

# ── Liste des fichiers a supprimer ──

$fichiers = @(

    # ── ROADTRIPS (pages HTML) ──
    "roadtrips/road-trip-incroyable-en-italie-journal.html"
    "roadtrips/road-trip-incroyable-en-italie.html"
    "roadtrips/road-trip-moto-amerique-2026-journal.html"
    "roadtrips/road-trip-moto-amerique-2026.html"
    "roadtrips/road-trip-moto-ecosse-2026-journal.html"
    "roadtrips/road-trip-moto-ecosse-2026-journal.html.backup"
    "roadtrips/road-trip-moto-ecosse-2026.html"
    "roadtrips/road-trip-moto-ecosse-2026.html.backup"
    "roadtrips/road-trip-moto-la-lune-2026-journal.html"
    "roadtrips/road-trip-moto-la-lune-2026.html"
    "roadtrips/road-trip-moto-lunaire-2026-journal.html"
    "roadtrips/road-trip-moto-lunaire-2026.html"
    "roadtrips/road-trip-moto-nouvau-tets-journal.html"
    "roadtrips/road-trip-moto-nouvau-tets.html"
    "roadtrips/road-trip-moto-test-2026-journal.html"
    "roadtrips/road-trip-moto-test-2026-journal.html.backup"
    "roadtrips/road-trip-moto-test-2026.html"
    "roadtrips/road-trip-moto-test-2026.html.backup"
    "roadtrips/road-trip-moto-test-3-2026-journal.html"
    "roadtrips/road-trip-moto-test-3-2026.html"
    "roadtrips/road-trip-moto-test-journal.html"
    "roadtrips/road-trip-moto-test-journal.html.backup"
    "roadtrips/road-trip-moto-test-lunaire-journal.html"
    "roadtrips/road-trip-moto-test-lunaire-journal.html.backup"
    "roadtrips/road-trip-moto-test-lunaire.html"
    "roadtrips/road-trip-moto-test.html"
    "roadtrips/road-trip-moto-test.html.backup"
    "roadtrips/road-trip-moto-test2-2026-journal.html"
    "roadtrips/road-trip-moto-test2-2026.html"

    # ── ROADBOOKS (PDF) ──
    "roadbooks/road-trip-incroyable-en-italie-roadbook.pdf"
    "roadbooks/road-trip-moto-amerique-2026-roadbook.pdf"
    "roadbooks/road-trip-moto-ecosse-2026-roadbook.pdf"
    "roadbooks/road-trip-moto-la-lune-2026-roadbook.pdf"
    "roadbooks/road-trip-moto-lunaire-2026-roadbook.pdf"
    "roadbooks/road-trip-moto-nouvau-tets-roadbook.pdf"
    "roadbooks/road-trip-moto-test-2026-roadbook.pdf"
    "roadbooks/road-trip-moto-test-3-2026-roadbook.pdf"
    "roadbooks/road-trip-moto-test-lunaire-roadbook.pdf"
    "roadbooks/road-trip-moto-test-roadbook.pdf"
    "roadbooks/road-trip-moto-test2-2026-roadbook.pdf"
)

# ── Dossiers a supprimer (roadbooks HTML, kurviger, images) ──

$dossiers = @(
    "roadbooks-html/road-trip-incroyable-en-italie"
    "roadbooks-html/road-trip-moto-amerique-2026"
    "roadbooks-html/road-trip-moto-ecosse-2026"
    "roadbooks-html/road-trip-moto-la-lune-2026"
    "roadbooks-html/road-trip-moto-lunaire-2026"
    "roadbooks-html/road-trip-moto-nouvau-tets"
    "roadbooks-html/road-trip-moto-test-2026"
    "roadbooks-html/road-trip-moto-test-3-2026"
    "roadbooks-html/road-trip-moto-test-lunaire"
    "roadbooks-html/road-trip-moto-test"
    "roadbooks-html/road-trip-moto-test2-2026"
    "kurviger/road-trip-incroyable-en-italie.kurviger"
    "kurviger/road-trip-moto-amerique-2026.kurviger"
    "kurviger/road-trip-moto-ecosse-2026.kurviger"
    "kurviger/road-trip-moto-la-lune-2026.kurviger"
    "kurviger/road-trip-moto-lunaire-2026.kurviger"
    "kurviger/road-trip-moto-nouvau-tets.kurviger"
    "kurviger/road-trip-moto-test-2026.kurviger"
    "kurviger/road-trip-moto-test-3-2026.kurviger"
    "kurviger/road-trip-moto-test-lunaire.kurviger"
    "kurviger/road-trip-moto-test.kurviger"
    "kurviger/road-trip-moto-test2-2026.kurviger"
    "images/roadtrips/road-trip-incroyable-en-italie"
    "images/roadtrips/road-trip-moto-amerique-2026"
    "images/roadtrips/road-trip-moto-ecosse-2026"
    "images/roadtrips/road-trip-moto-la-lune-2026"
    "images/roadtrips/road-trip-moto-lunaire-2026"
    "images/roadtrips/road-trip-moto-nouvau-tets"
    "images/roadtrips/road-trip-moto-test-2026"
    "images/roadtrips/road-trip-moto-test-3-2026"
    "images/roadtrips/road-trip-moto-test-lunaire"
    "images/roadtrips/road-trip-moto-test"
    "images/roadtrips/road-trip-moto-test2-2026"
)

# ── ÉTAPE 1 : Afficher ce qu'on va supprimer ──

Write-Host "`n=== FICHIERS A SUPPRIMER ===" -ForegroundColor Yellow
$count = 0

foreach ($f in $fichiers) {
    if (Test-Path $f) {
        Write-Host "  [FICHIER] $f" -ForegroundColor Red
        $count++
    }
}

foreach ($d in $dossiers) {
    if (Test-Path $d) {
        Write-Host "  [DOSSIER] $d" -ForegroundColor Red
        $count++
    }
}

Write-Host "`n  Total : $count elements trouves a supprimer" -ForegroundColor Yellow
Write-Host "  ON GARDE : road-trip-cap-nord-2025 (+ sandbox)" -ForegroundColor Green

if ($count -eq 0) {
    Write-Host "`nRien a supprimer, tout est deja propre." -ForegroundColor Green
    Read-Host "Appuyez sur Entree pour fermer"
    exit
}

# ── ÉTAPE 2 : Confirmation ──

Write-Host ""
$confirm = Read-Host "Confirmer la suppression ? (oui/non)"
if ($confirm -ne "oui") {
    Write-Host "Annule." -ForegroundColor DarkGray
    Read-Host "Appuyez sur Entree pour fermer"
    exit
}

# ── ÉTAPE 3 : Suppression ──

Write-Host "`n=== Suppression en cours ===" -ForegroundColor Cyan
$deleted = 0

foreach ($f in $fichiers) {
    if (Test-Path $f) {
        git rm -f $f 2>$null
        Write-Host "  Supprime : $f" -ForegroundColor Yellow
        $deleted++
    }
}

foreach ($d in $dossiers) {
    if (Test-Path $d) {
        git rm -rf $d 2>$null
        Write-Host "  Supprime : $d/" -ForegroundColor Yellow
        $deleted++
    }
}

# ── ÉTAPE 4 : Créer le dossier sandbox ──

Write-Host "`n=== Creation du dossier sandbox ===" -ForegroundColor Cyan

$sandboxDir = "roadtrips/sandbox"
if (-not (Test-Path $sandboxDir)) {
    New-Item -ItemType Directory -Path $sandboxDir -Force | Out-Null
}

$readmeContent = @"
# Sandbox - Dossier de test

Ce dossier est reserve aux tests de generation de road trips.
Les fichiers ici ne sont PAS de vrais road trips.

Ne pas supprimer ce dossier.
"@

Set-Content -Path "$sandboxDir/README.md" -Value $readmeContent -Encoding UTF8
git add "$sandboxDir/README.md"
Write-Host "  Cree : $sandboxDir/README.md" -ForegroundColor Green

# ── ÉTAPE 5 : Commit et push ──

Write-Host "`n=== Commit et push ($deleted fichiers supprimes) ===" -ForegroundColor Cyan
git add -A
git commit -m "Nettoyage : suppression de $deleted fichiers/dossiers de test + creation sandbox"
git push origin main

Write-Host "`n=== TERMINE ===" -ForegroundColor Green
Write-Host "  $deleted elements supprimes" -ForegroundColor Green
Write-Host "  Sandbox cree dans roadtrips/sandbox/" -ForegroundColor Green
Write-Host "  Seul road-trip-cap-nord-2025 est conserve" -ForegroundColor Green
Read-Host "`nAppuyez sur Entree pour fermer"
