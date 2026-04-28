# IndexNow — Notification instantanée Bing/Yandex/Seznam/Naver
# Usage : .\indexnow-ping.ps1
# Doc : https://www.indexnow.org/

$key = "1ffe11fd716a4f389f34bc02922c1684"
$keyLocation = "https://lcdmh.com/$key.txt"
$host = "lcdmh.com"

$urls = @(
    "https://lcdmh.com/articles/mekanik-annecy-honda-nt1100-panne-garantie.html",
    "https://lcdmh.com/articles.html",
    "https://lcdmh.com/articles/test-honda-nt1100-avis-25000-km-road-trip.html",
    "https://lcdmh.com/articles/retour-honda-nt-1100-a-26000-kms.html",
    "https://lcdmh.com/sitemap.xml"
)

$body = @{
    host = $host
    key = $key
    keyLocation = $keyLocation
    urlList = $urls
} | ConvertTo-Json

Write-Host "Envoi IndexNow vers Bing/Yandex/Seznam/Naver..." -ForegroundColor Cyan
Write-Host "URLs notifiees : $($urls.Count)" -ForegroundColor Cyan
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri "https://api.indexnow.org/indexnow" `
        -Method POST `
        -ContentType "application/json; charset=utf-8" `
        -Body $body `
        -UseBasicParsing

    Write-Host "[OK] Code HTTP : $($response.StatusCode)" -ForegroundColor Green
    if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 202) {
        Write-Host "[OK] Notification reussie. Bing/Yandex vont crawler dans les minutes qui viennent." -ForegroundColor Green
    }
} catch {
    Write-Host "[!] Erreur : $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        Write-Host "Code : $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Note : Google n'accepte pas IndexNow." -ForegroundColor Yellow
Write-Host "Pour Google : passer par Google Search Console > Inspection d'URL > Demander une indexation" -ForegroundColor Yellow
Write-Host "URL a soumettre : https://lcdmh.com/articles/mekanik-annecy-honda-nt1100-panne-garantie.html" -ForegroundColor Yellow
