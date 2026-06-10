#Requires -Version 5.1
$TaskName = "StarlinkWidget"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Tache '$TaskName' supprimee."
}

Remove-ItemProperty -Path $RunKey -Name $TaskName -ErrorAction SilentlyContinue

$schtasks = Join-Path $env:WINDIR "System32\schtasks.exe"
& $schtasks /Delete /TN $TaskName /F *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Tache '$TaskName' supprimee (schtasks)."
} elseif (-not $task) {
    Write-Host "Demarrage automatique deja absent."
}
