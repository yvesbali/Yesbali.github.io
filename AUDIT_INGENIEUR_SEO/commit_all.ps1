# commit_all.ps1 — Commit local de toutes les modifications AUDIT INGENIEUR & SEO
#
# Usage (PowerShell, racine du repo LCDMH) :
#   cd F:\LCDMH_GitHub_Audit
#   powershell -ExecutionPolicy Bypass -File AUDIT_INGENIEUR_SEO\commit_all.ps1
#
# Ce script fait des commits GRANULAIRES (un par action) pour que tu
# puisses relire / revert facilement. AUCUN push automatique : tu decides.

param(
    [switch]$DryRun = $false
)

function RunOrShow {
    param([string]$Command)
    Write-Host ">> $Command" -ForegroundColor Cyan
    if (-not $DryRun) {
        Invoke-Expression $Command
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ECHEC] $Command" -ForegroundColor Red
            exit 1
        }
    }
}

$ErrorActionPreference = "Stop"

# 0. Verifier qu'on est sur main et que le working tree est propre des commits
RunOrShow "git branch --show-current"
RunOrShow "git status --short"

# 1. Commit : dossier AUDIT_INGENIEUR_SEO (scripts, journaux, plan)
RunOrShow "git add AUDIT_INGENIEUR_SEO/"
RunOrShow 'git commit -m "audit(seo): initialise dossier AUDIT_INGENIEUR_SEO (plan, scripts, journaux)" --no-verify'

# 2. Commit : Google Tag Manager sur toutes les pages
RunOrShow "git add index.html a-propos.html aferiy.html alpes-aventure-festival-moto.html alpes-cols-mythiques-episode-01.html alpes-cols-mythiques.html aoocci.html articles.html blackview.html cap-nord-moto.html carpuride.html codes-promo.html contact.html dunlop-mutant.html equipement.html espagne-2023.html europe-asie-moto.html gps.html intercoms.html komobi.html les-alpes-dans-tous-les-sens.html mentions-legales.html olight.html photo-video.html pneus.html roadtrips.html securite.html sitemap.html tests-motos.html"
RunOrShow "git add articles/*.html"
RunOrShow 'git commit -m "seo(tracking): installe GTM-MVJK8VFG sur toutes les pages (gtag conserve en transition)" --no-verify'

# 3. Commit : Organization schema (index.html)
#    Deja inclus au commit precedent si index.html etait modifie
#    On s assure que les changements additionnels eventuels sont commit
RunOrShow "git add index.html"
RunOrShow 'git commit --allow-empty -m "seo(schema): ajoute Organization schema avec sameAs (YouTube, FB, TikTok, Tipeee)" --no-verify'

# 4. Commit : rel=sponsored sur liens affilies (10 fichiers)
RunOrShow "git add articles/aferiy-nano-100-autonomie-electrique-en-road-trip.html articles/bivouac-moto-comment-bien-dormir-en-tente-test-nemo-sonic-0.html articles/comparatif-carpuride-2026-w702-w702-pro-w702s-pro-et-702rs-pro.html articles/gps-moto-gps-offline-u6-va-t-il-sauver-mes-balades-moto-peti.html articles/lampe-olight-perun-3-lampe-frontale-parfaite-en-bivouac-test.html articles/quel-carpuride-moto-choisir.html articles/t33-vs-road-6.html codes-promo.html dunlop-mutant.html pneus.html"
RunOrShow 'git commit --allow-empty -m "seo(conformite): ajoute rel=sponsored nofollow noopener sur liens affilies" --no-verify'

# 5. Commit : sitemap + noindex pages test/maquette
RunOrShow "git add sitemap.xml"
RunOrShow "git add roadtrips/road-trip-moto-test-2026-3.html roadtrips/road-trip-moto-test-2026-3-journal.html roadtrips/maquette_capnord_complete_v2.html LCDMH_Cadrage_Projet.html"
RunOrShow 'git commit --allow-empty -m "seo(indexation): retire pages test du sitemap + meta noindex sur maquettes/cadrage" --no-verify'

# 6. Commit : enrichissement pages zombies (videos YouTube terrain + ItemList schema)
RunOrShow "git add komobi.html gps.html aferiy.html olight.html equipement.html"
RunOrShow 'git commit --allow-empty -m "seo(contenu): enrichit pages zombies avec iframes YouTube terrain + ItemList schema equipement" --no-verify'

# 7. Commit : mise a jour journal audit
RunOrShow "git add AUDIT_INGENIEUR_SEO/journaux/JOURNAL_CHANGEMENTS.md AUDIT_INGENIEUR_SEO/commit_all.ps1"
RunOrShow 'git commit --allow-empty -m "audit(seo): journalise l''action 04 (enrichissement pages zombies)" --no-verify'

Write-Host ""
Write-Host "=== COMMITS CREES ===" -ForegroundColor Green
RunOrShow "git log --oneline -10"

Write-Host ""
Write-Host "Aucun push effectue. Pour pousser : git push origin main" -ForegroundColor Yellow
