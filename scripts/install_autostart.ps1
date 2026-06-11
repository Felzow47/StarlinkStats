#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"

if (-not (Test-Path -LiteralPath $VenvPythonw)) {
    Write-Warning "venv introuvable. Executez: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

& (Join-Path $PSScriptRoot "register_autostart.ps1") `
    -ExePath $VenvPythonw `
    -WorkingDirectory $ProjectRoot `
    -Arguments "-m starlink_widget --autostart"

Write-Host "Lancement manuel: $VenvPythonw -m starlink_widget"
