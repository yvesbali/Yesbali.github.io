@echo off
chcp 65001 >nul
title LCDMH - Git Push securise

cd /d "F:\LCDMH_GitHub_Audit"

echo.
echo ========================================
echo   LCDMH - Verification avant push
echo ========================================
echo.

REM Suppression du verrou si present
if exist ".git\index.lock" (
    echo [!] Verrou git detecte, suppression...
    del ".git\index.lock"
    echo [OK] Verrou supprime.
    echo.
)

REM Verification des changements
echo [1/4] Fichiers modifies :
echo.
git diff HEAD --stat
echo.
git status --short
echo.

REM Pause pour relecture
echo ----------------------------------------
echo Verifie que les changements ci-dessus
echo correspondent bien a ce que tu as fait.
echo ----------------------------------------
echo.
pause

REM Saisie du message de commit
echo.
set /p MSG=Message de commit :
if "%MSG%"=="" set MSG=Mise a jour LCDMH

REM Ajout de tous les fichiers modifies (trackes)
echo.
echo [2/4] Ajout des fichiers...
git add -u
echo [OK] Fichiers ajoutes.

REM Commit
echo.
echo [3/4] Commit en cours...
git commit -m "%MSG%"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Rien a commiter ou erreur de commit.
    git status
    echo.
    pause
    exit /b
)

REM Push
echo.
echo [4/4] Push vers GitHub...
git push
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   [OK] Push reussi ! Site mis a jour.
    echo   GitHub Pages redeploit dans 1-2 min.
    echo ========================================
) else (
    echo.
    echo [!] Erreur lors du push. Verifie la connexion.
)

echo.
pause >nul
