# Runs the KXRAIN Gate 2 health check and raises a Windows notification if the
# record has a hole. Runs in the logged-in session so the toast is visible.
$proj = Split-Path -Parent $PSScriptRoot
$py = "C:\Users\tyler\AppData\Local\Programs\Python\Python312\python.exe"
Set-Location $proj
$out = & $py -m src.candidates health 2>&1 | Out-String
$ok = ($LASTEXITCODE -eq 0)
Add-Content -Path (Join-Path $proj "data\logs\candidate_health.log") -Value $out
if (-not $ok -or $args -contains "-test") {
    $lines = ($out -split "`r?`n" | Where-Object { $_ -match "PROBLEM" } | Select-Object -First 3) -join "`n"
    if ($args -contains "-test") { $lines = "Test notification. " + $lines }
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $t = $xml.GetElementsByTagName("text")
    $t.Item(0).AppendChild($xml.CreateTextNode("KXRAIN test: data collection problem")) > $null
    $t.Item(1).AppendChild($xml.CreateTextNode($lines)) > $null
    $appId = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show(
        [Windows.UI.Notifications.ToastNotification]::new($xml))
}
