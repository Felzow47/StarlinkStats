#Requires -Version 5.1
<#
.SYNOPSIS
    Supprime tout ce que Starlink Widget a ajoute ou modifie hors du dossier d'installation.
#>
$ErrorActionPreference = "SilentlyContinue"

$AppName = "Starlink Widget"
$TaskName = "StarlinkWidget"
$SettingsRegKey = "HKCU:\Software\StarlinkWidget"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$UninstallRegKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppName"
$Schtasks = Join-Path $env:WINDIR "System32\schtasks.exe"

function Remove-RegistryTreeSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$KeyPath,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (Test-Path -LiteralPath $KeyPath) {
        Write-Host "[uninstall] Suppression $Label..."
        Remove-Item -LiteralPath $KeyPath -Recurse -Force
    }
}

function Remove-DirectorySafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (Test-Path -LiteralPath $Path) {
        Write-Host "[uninstall] Suppression $Label..."
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Remove-FileSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (Test-Path -LiteralPath $Path) {
        Write-Host "[uninstall] Suppression $Label..."
        Remove-Item -LiteralPath $Path -Force
    }
}

Write-Host "[uninstall] Arret de StarlinkWidget..."
Get-Process -Name "StarlinkWidget" -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

Write-Host "[uninstall] Suppression demarrage automatique..."
Remove-ItemProperty -Path $RunKey -Name $TaskName -ErrorAction SilentlyContinue
if (Test-Path -LiteralPath $Schtasks) {
    & $env:ComSpec /d /c "`"$Schtasks`" /Delete /TN `"$TaskName`" /F >nul 2>&1"
}

Remove-RegistryTreeSafe -KeyPath $SettingsRegKey -Label "preferences registre"
Remove-RegistryTreeSafe -KeyPath $UninstallRegKey -Label "entree desinstallation"
cmd /c 'reg delete "HKCU\Software\StarlinkWidget" /f >nul 2>&1'
cmd /c 'reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Starlink Widget" /f >nul 2>&1'

$desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"
$startupLink = Join-Path ([Environment]::GetFolderPath("Startup")) "$AppName.lnk"
$programsDir = Join-Path ([Environment]::GetFolderPath("Programs")) $AppName

Remove-FileSafe -Path $desktopLink -Label "raccourci Bureau"
Remove-FileSafe -Path $startupLink -Label "raccourci Demarrage"
Remove-DirectorySafe -Path $programsDir -Label "raccourcis menu Demarrer"

$appDataRoaming = Join-Path $env:APPDATA "StarlinkWidget"
$legacyPrograms = Join-Path $env:LOCALAPPDATA "Programs\StarlinkWidget"

Remove-DirectorySafe -Path $appDataRoaming -Label "AppData Roaming"
Remove-DirectorySafe -Path $legacyPrograms -Label "ancien dossier Programs local"

$remaining = @()
$runValue = (Get-ItemProperty -Path $RunKey -Name $TaskName -ErrorAction SilentlyContinue).$TaskName
if ($runValue) {
    $remaining += "Run HKCU/$TaskName"
}
if (Test-Path -LiteralPath $SettingsRegKey) {
    $remaining += "Registre preferences"
}
if (Test-Path -LiteralPath $UninstallRegKey) {
    $remaining += "Registre desinstallation"
}
if (Test-Path -LiteralPath $desktopLink) {
    $remaining += "Raccourci Bureau"
}
if (Test-Path -LiteralPath $startupLink) {
    $remaining += "Raccourci Demarrage"
}
if (Test-Path -LiteralPath $programsDir) {
    $remaining += "Raccourcis menu Demarrer"
}
if (Test-Path -LiteralPath $appDataRoaming) {
    $remaining += "AppData Roaming"
}
if (Test-Path -LiteralPath $legacyPrograms) {
    $remaining += "Programs local (legacy)"
}
if (Test-Path -LiteralPath $Schtasks) {
    & $env:ComSpec /d /c "`"$Schtasks`" /Query /TN `"$TaskName`" >nul 2>&1"
    if ($LASTEXITCODE -eq 0) {
        $remaining += "Tache planifiee $TaskName"
    }
}

if ($remaining.Count -gt 0) {
    Write-Warning ("[uninstall] Traces residuelles detectees : " + ($remaining -join ", "))
} else {
    Write-Host "[uninstall] Verification post-nettoyage OK : aucune trace residuelle detectee."
}
Write-Host "[uninstall] Nettoyage systeme termine."

