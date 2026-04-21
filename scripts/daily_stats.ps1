<#
  daily_stats.ps1 — LCDMH
  =======================
  Job quotidien qui :
    1. (Re)génère seo_stats.json via fetch_youtube.py (API YT Data + Analytics)
    2. Alimente data/baselines/daily_stats_log.xlsx avec une ligne du jour
    3. Journalise dans logs/daily_stats_YYYY-MM.log
    4. Commit + push GitHub optionnel
    5. Remet le PC en veille si lancé via la tâche planifiée WakeToRun

  Usage manuel :
      pwsh -ExecutionPolicy Bypass -File scripts\daily_stats.ps1
      pwsh -ExecutionPolicy Bypass -File scripts\daily_stats.ps1 -Commit
      pwsh -ExecutionPolicy Bypass -File scripts\daily_stats.ps1 -Commit -Sleep

  Usage tâche planifiée (wake + exécution + veille) :
      voir scripts\daily_stats_task.xml à importer via schtasks /Create /XML
#>

param(
  [switch] $Commit = $false,      # git add/commit/push après collecte
  [switch] $Sleep  = $false,      # remet le PC en veille à la fin
  [switch] $Dry    = $false,      # ne touche pas seo_stats.json (pour tester le log)
  [switch] $Email  = $false,      # envoie le mail quotidien via send_daily_email.py
  [string] $RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

# ----- 0. Auto-chargement credentials depuis F:\Automate_YT si vars d'env absentes -----
if (-not $env:YT_TOKEN_ANALYTICS) {
  $tokAnalytics = "F:\Automate_YT\yt_token_analytics.json"
  if (Test-Path $tokAnalytics) {
    $env:YT_TOKEN_ANALYTICS = Get-Content $tokAnalytics -Raw
  }
}
if (-not $env:GMAIL_APP_PASSWORD) {
  $env:GMAIL_APP_PASSWORD = [Environment]::GetEnvironmentVariable("GMAIL_APP_PASSWORD", "User")
}
if (-not $env:GMAIL_USER) { $env:GMAIL_USER = "yvesbali@gmail.com" }

# ----- Logs -----
$logDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir ("daily_stats_{0:yyyy-MM}.log" -f (Get-Date))

function Log($msg) {
  $line = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $msg
  Add-Content -Path $logFile -Value $line
  Write-Host $line
}

Log "=== daily_stats start (Commit=$Commit Sleep=$Sleep Dry=$Dry) ==="

# ----- 1. Credentials check -----
if (-not $env:YT_TOKEN_ANALYTICS) {
  Log "ERREUR : variable d'environnement YT_TOKEN_ANALYTICS absente."
  Log "Remède : ouvre une session PowerShell admin et lance :"
  Log '  [Environment]::SetEnvironmentVariable("YT_TOKEN_ANALYTICS", "<JSON complet>", "User")'
  if ($Sleep) { rundll32.exe powrprof.dll,SetSuspendState 0,1,0 }
  exit 1
}

# ----- 2. fetch_youtube.py -----
if (-not $Dry) {
  Log "Lancement fetch_youtube.py…"
  try {
    python fetch_youtube.py 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
    Log "fetch_youtube.py : OK"
  } catch {
    Log ("fetch_youtube.py : ERREUR — {0}" -f $_.Exception.Message)
  }
} else {
  Log "Mode --Dry : fetch_youtube.py non exécuté."
}

# ----- 3. Collecte stats + ajout ligne dans daily_stats_log.xlsx -----
Log "Ajout ligne dans daily_stats_log.xlsx…"
python scripts\append_daily_log.py 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null

# ----- 3b. Email quotidien -----
if ($Email) {
  if (-not $env:GMAIL_APP_PASSWORD) {
    Log "ERREUR : GMAIL_APP_PASSWORD absent — email ignoré."
    Log "Remède : génère un app password sur https://myaccount.google.com/apppasswords"
    Log "         puis : [Environment]::SetEnvironmentVariable('GMAIL_APP_PASSWORD','xxxxxxxxxxxxxxxx','User')"
  } else {
    Log "Envoi email daily…"
    python scripts\send_daily_email.py 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
  }
}

# ----- 4. Commit git -----
if ($Commit) {
  Log "Commit + push…"
  & git add data/baselines/daily_stats_log.xlsx seo_stats.json data/videos.json 2>&1 | Out-Null
  $changes = & git status --porcelain
  if ($changes) {
    & git commit -m ("chore(stats): daily snapshot {0:yyyy-MM-dd}" -f (Get-Date)) 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
    & git push 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
    Log "Push : OK"
  } else {
    Log "Aucun changement à committer."
  }
}

Log "=== daily_stats end ==="

# ----- 5. Retour en veille -----
if ($Sleep) {
  Log "Retour en veille dans 15s…"
  Start-Sleep -Seconds 15
  # S4 = hiberne (plus économe), S3 = veille classique
  # 0,1,0 = sleep (pas hibernate) ; 1,1,0 = hibernate
  rundll32.exe powrprof.dll,SetSuspendState 0,1,0
}
