#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$Entry = Join-Path $PSScriptRoot "autostart_entry.py"

if (-not (Test-Path -LiteralPath $VenvPythonw)) {
    Write-Warning "venv introuvable. Executez: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path -LiteralPath $Entry)) {
    Write-Warning "Lanceur introuvable: $Entry"
    exit 1
}

& (Join-Path $PSScriptRoot "register_autostart.ps1") `
    -ExePath $VenvPythonw `
    -WorkingDirectory $ProjectRoot `
    -Arguments "`"$Entry`""

Write-Host "Lancement manuel: $VenvPythonw -m starlink_widget"
