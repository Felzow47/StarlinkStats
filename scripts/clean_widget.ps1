# Nettoyage complet avant lancement du widget Starlink.
param(
    [Parameter(Mandatory = $true)]
    [string]$Root
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "[clean] Arret des instances starlink_widget..."
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -in @("pythonw.exe", "python.exe") -and
        $_.CommandLine -like "*starlink_widget*"
    } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Sleep -Milliseconds 500

Write-Host "[clean] Cache Python et logs..."
Get-ChildItem -LiteralPath $Root -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -LiteralPath $Root -Recurse -File -Filter "*.pyc" |
    Remove-Item -Force -ErrorAction SilentlyContinue

Get-ChildItem -LiteralPath $Root -Recurse -File -Filter "*.pyo" |
    Remove-Item -Force -ErrorAction SilentlyContinue

$pytestCache = Join-Path $Root ".pytest_cache"
if (Test-Path -LiteralPath $pytestCache) {
    Remove-Item -LiteralPath $pytestCache -Recurse -Force -ErrorAction SilentlyContinue
}

Get-ChildItem -LiteralPath $Root -File -Filter "*.log" |
    Remove-Item -Force -ErrorAction SilentlyContinue

Get-ChildItem -LiteralPath $Root -File -Filter "debug-*.log" |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "[clean] Preferences QSettings (registre + AppData)..."
cmd /c "reg delete ""HKCU\Software\StarlinkWidget"" /f >nul 2>&1"

$appDataDir = Join-Path $env:APPDATA "StarlinkWidget"
if (Test-Path -LiteralPath $appDataDir) {
    Remove-Item -LiteralPath $appDataDir -Recurse -Force -ErrorAction SilentlyContinue
}

$localAppDataDir = Join-Path $env:LOCALAPPDATA "StarlinkWidget"
if (Test-Path -LiteralPath $localAppDataDir) {
    Remove-Item -LiteralPath $localAppDataDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "[clean] Termine."
