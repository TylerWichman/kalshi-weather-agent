# One-time setup of the KXRAIN data collectors on a Windows cloud server.
# See docs/cloud-server.md. Run in an Administrator PowerShell on the server:
#
#   powershell -ExecutionPolicy Bypass -File C:\kalshi-weather-agent\deploy\setup_server.ps1
#
# Optional phone alerts via the free ntfy app (no account). Pick a long random topic:
#   ... setup_server.ps1 -AlertTopic kalshi-rain-<random>
#
# Safe to re-run: every step checks or overwrites rather than duplicating.

param([string]$AlertTopic = "")

$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
$py = "C:\Python312\python.exe"

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this from an Administrator PowerShell."
}
if (-not (Test-Path "$proj\src\candidates.py")) {
    throw "Expected the project at $proj (src\candidates.py not found). Unzip it to C:\kalshi-weather-agent."
}

Step "Clock -> UTC (the pre-registered decision time is 00:00 UTC; no DST on this machine)"
Set-TimeZone -Id "UTC"
[TimeZoneInfo]::ClearCachedData()   # this session otherwise keeps the old zone
Get-Date -Format "yyyy-MM-dd HH:mm:ss 'UTC'"

Step "Python 3.12 (all users, C:\Python312)"
if (-not (Test-Path $py)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $inst = Join-Path $env:TEMP "python-3.12.10-amd64.exe"
    Invoke-WebRequest "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" `
        -OutFile $inst -UseBasicParsing
    Start-Process $inst -Wait -ArgumentList `
        "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_launcher=0 TargetDir=C:\Python312"
}
& $py --version
# numpy is only needed to run the Gate 2 analysis itself on this machine.
& $py -m pip install --quiet --disable-pip-version-check numpy

if ($AlertTopic) {
    Step "Phone alerts -> ntfy.sh topic '$AlertTopic'"
    Set-Content -Path "$proj\deploy\alert_topic.txt" -Value $AlertTopic -Encoding ascii
}

Step "Initial load from Kalshi's API (about 15 minutes: every settled KXRAIN event, WTI, natgas)"
Push-Location $proj
New-Item -ItemType Directory -Force "$proj\data\logs" | Out-Null
& $py -m src.candidates history --series KXRAIN,KXWTI,KXNATGASW
& $py -m src.candidates books
Pop-Location

Step "Scheduled tasks (run as SYSTEM: no login needed, survive Windows Update restarts)"
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
function Register($name, $file, $triggers, $limitMin, $multi = "IgnoreNew") {
    if ($file -like "*.ps1") {
        $a = New-ScheduledTaskAction -Execute "powershell.exe" -WorkingDirectory $proj `
            -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$proj\$file`""
    } else {
        $a = New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $proj `
            -Argument "/c `"$proj\$file`""
    }
    $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances $multi `
        -ExecutionTimeLimit (New-TimeSpan -Minutes $limitMin)
    Register-ScheduledTask -TaskName $name -Action $a -Trigger $triggers -Settings $s `
        -Principal $principal -Force | Out-Null
    Write-Host "  $name"
}
$every10 = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 3650)
Register "KalshiCandidateBooks" "scripts\run_candidate_books.cmd" $every10 9
Register "KalshiRainDecisionBooks" "scripts\run_rain_decision_books.cmd" `
    @((New-ScheduledTaskTrigger -Daily -At "23:51"), (New-ScheduledTaskTrigger -Daily -At "23:56")) 4 "Parallel"
Register "KalshiCandidateHistory" "scripts\run_candidate_history.cmd" `
    (New-ScheduledTaskTrigger -Daily -At "18:00") 120
Register "KalshiPaperTrade" "scripts\run_paper_trade.cmd" `
    (New-ScheduledTaskTrigger -Daily -At "00:01") 10
Register "KalshiCandidateHealth" "deploy\health_alert.ps1" `
    @((New-ScheduledTaskTrigger -Daily -At "01:00"), (New-ScheduledTaskTrigger -Daily -At "13:00")) 10

Step "Checking each task runs"
foreach ($n in "KalshiCandidateBooks", "KalshiRainDecisionBooks") { Start-ScheduledTask -TaskName $n }
Start-Sleep -Seconds 60
$bad = 0
foreach ($n in "KalshiCandidateBooks", "KalshiRainDecisionBooks") {
    $r = (Get-ScheduledTask -TaskName $n | Get-ScheduledTaskInfo).LastTaskResult
    Write-Host ("  {0,-26} result {1}" -f $n, $r)
    if ($r -ne 0) { $bad++ }
}

Step "Health"
Push-Location $proj
& $py -m src.candidates health
& $py -m src.candidates status
Pop-Location
if ($AlertTopic) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$proj\deploy\health_alert.ps1" -test
    Write-Host "  A test alert was sent to ntfy topic '$AlertTopic'."
}

if ($bad -eq 0) {
    Write-Host "`nSETUP COMPLETE. Collectors are running." -ForegroundColor Green
} else {
    Write-Host "`nSETUP FINISHED WITH $bad FAILED TASK(S). Check $proj\data\logs." -ForegroundColor Red
}
