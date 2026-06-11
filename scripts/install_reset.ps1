#Requires -Version 5.1
<#
.SYNOPSIS
    Reset complet du dossier d'installation avant une (re)installation.
    Conserve config.json ; ne touche pas aux preferences utilisateur (registre).
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"

$BackupRoot = Join-Path $env:TEMP "StarlinkWidget-install-backup"
$ConfigBackup = Join-Path $BackupRoot "config.json"
$ConfigPath = Join-Path $InstallDir "config.json"

function Restore-ConfigBackup {
    if (-not (Test-Path -LiteralPath $ConfigBackup)) {
        return
    }
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item -LiteralPath $ConfigBackup -Destination $ConfigPath -Force
    Write-Host "[install] config.json restaure."
}

try {
    Write-Host "[install] Arret de StarlinkWidget..."
    Get-Process -Name "StarlinkWidget" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 400

    if (Test-Path -LiteralPath $BackupRoot) {
        Remove-Item -LiteralPath $BackupRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

    if (Test-Path -LiteralPath $ConfigPath) {
        Copy-Item -LiteralPath $ConfigPath -Destination $ConfigBackup -Force
        Write-Host "[install] Sauvegarde config.json..."
    }

    if (Test-Path -LiteralPath $InstallDir) {
        Write-Host "[install] Suppression du dossier d'installation..."
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
    }

    Restore-ConfigBackup
    Write-Host "[install] Reset dossier d'installation termine (prefs utilisateur conservees)."
    exit 0
} catch {
    Write-Error "[install] Echec reset installation : $($_.Exception.Message)"
    exit 1
} finally {
    if (Test-Path -LiteralPath $BackupRoot) {
        Remove-Item -LiteralPath $BackupRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
