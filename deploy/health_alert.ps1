# Runs the Gate 2 health check on the cloud server and, if deploy\alert_topic.txt exists,
# pushes the result to that ntfy.sh topic (free phone app, no account).
#
# The 01:00 UTC run always sends a message, including "OK". That daily message doubles
# as a heartbeat: if it stops arriving, the server itself is down, which a check that
# runs on the server can never report on its own.

$proj = Split-Path -Parent $PSScriptRoot
$py = "C:\Python312\python.exe"
Set-Location $proj

$out = & $py -m src.candidates health 2>&1 | Out-String
$ok = ($LASTEXITCODE -eq 0)
Add-Content -Path "$proj\data\logs\candidate_health.log" -Value $out

$topicFile = "$proj\deploy\alert_topic.txt"
if (-not (Test-Path $topicFile)) { exit 0 }
$topic = (Get-Content $topicFile -Raw).Trim()

$daily = ((Get-Date).ToUniversalTime().Hour -eq 1)
$test = $args -contains "-test"
if ($ok -and -not $daily -and -not $test) { exit 0 }

$title = if ($test) { "KXRAIN collector: test alert" }
         elseif ($ok) { "KXRAIN collector OK" }
         else { "KXRAIN collector PROBLEM" }
$body = ($out -split "`r?`n" | Where-Object { $_.Trim() }) -join "`n"
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-RestMethod -Uri "https://ntfy.sh/$topic" -Method Post -Body $body `
        -Headers @{ Title = $title; Priority = $(if ($ok) { "default" } else { "high" }) } | Out-Null
} catch {
    Add-Content -Path "$proj\data\logs\candidate_health.log" -Value "alert send failed: $_"
}
