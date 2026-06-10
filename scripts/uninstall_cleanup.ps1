#Requires -Version 5.1
<#
.SYNOPSIS
    Supprime tout ce que Starlink Widget a ajoute ou modifie hors du dossier d'installation.
#>
$ErrorActionPreference = "SilentlyContinue"

$TaskName = "StarlinkWidget"
$SettingsRegKey = "HKCU:\Software\StarlinkWidget"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$Schtasks = Join-Path $env:WINDIR "System32\schtasks.exe"

Write-Host "[uninstall] Arret de StarlinkWidget..."
Get-Process -Name "StarlinkWidget" -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

Write-Host "[uninstall] Suppression demarrage automatique..."
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
}
& $Schtasks /Delete /TN $TaskName /F *> $null
Remove-ItemProperty -Path $RunKey -Name $TaskName -ErrorAction SilentlyContinue

Write-Host "[uninstall] Suppression preferences (registre)..."
if (Test-Path -LiteralPath $SettingsRegKey) {
    Remove-Item -LiteralPath $SettingsRegKey -Recurse -Force
}
cmd /c 'reg delete "HKCU\Software\StarlinkWidget" /f >nul 2>&1'

$appDataDir = Join-Path $env:APPDATA "StarlinkWidget"
if (Test-Path -LiteralPath $appDataDir) {
    Write-Host "[uninstall] Suppression AppData Roaming..."
    Remove-Item -LiteralPath $appDataDir -Recurse -Force
}

Write-Host "[uninstall] Nettoyage systeme termine."
