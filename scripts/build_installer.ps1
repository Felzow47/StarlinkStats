#Requires -Version 5.1
<#
.SYNOPSIS
    Compile StarlinkWidget (PyInstaller) puis l'installeur NSIS.
.EXAMPLE
    .\scripts\build_installer.ps1
    .\scripts\build_installer.ps1 -SkipInstaller
#>
param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$DistApp = Join-Path $Root "dist\StarlinkWidget"
$Nsi = Join-Path $Root "installer\starlink_widget.nsi"
$NsisVersion = "3.11"
$NsisZipName = "nsis-$NsisVersion.zip"
$NsisUrl = "https://sourceforge.net/projects/nsis/files/NSIS%203/$NsisVersion/$NsisZipName/download"

function Find-Makensis {
    $bundled = Get-ChildItem -Path (Join-Path $Root "tools") -Filter "makensis.exe" -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($bundled) { return $bundled.FullName }

    $cmd = Get-Command makensis.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    foreach ($path in @(
        "${env:ProgramFiles(x86)}\NSIS\makensis.exe",
        "$env:ProgramFiles\NSIS\makensis.exe"
    )) {
        if (Test-Path -LiteralPath $path) { return $path }
    }
    return $null
}

function Ensure-Makensis {
    $existing = Find-Makensis
    if ($existing) { return $existing }

    Write-Host "[build] Telechargement NSIS portable ($NsisVersion)..."
    $ToolsDir = Join-Path $Root "tools"
    $ZipPath = Join-Path $env:TEMP $NsisZipName
    New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & curl.exe -fsSL -o $ZipPath $NsisUrl
    } else {
        Invoke-WebRequest -Uri $NsisUrl -OutFile $ZipPath -UseBasicParsing -MaximumRedirection 10
    }

    if (-not (Test-Path -LiteralPath $ZipPath) -or (Get-Item -LiteralPath $ZipPath).Length -lt 1MB) {
        throw "Telechargement NSIS invalide (fichier absent ou trop petit). URL : $NsisUrl"
    }

    Expand-Archive -LiteralPath $ZipPath -DestinationPath $ToolsDir -Force
    Remove-Item -LiteralPath $ZipPath -Force

    $makensis = Find-Makensis
    if (-not $makensis) {
        throw "NSIS telecharge mais makensis.exe introuvable dans $ToolsDir"
    }
    Write-Host "[build] NSIS pret : $makensis"
    return $makensis
}

Set-Location $Root

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "[build] Creation du venv..."
    python -m venv .venv
}

Write-Host "[build] Dependances runtime + build..."
& $VenvPython -m pip install -r requirements-build.txt -q

$SvgLogo = Join-Path $Root "assets\Vector.svg"
if (Test-Path -LiteralPath $SvgLogo) {
    Write-Host "[build] Icone depuis SVG..."
    & $VenvPython (Join-Path $Root "scripts\convert_logo_to_ico.py")
}

Write-Host "[build] PyInstaller..."
& $VenvPython -m PyInstaller --noconfirm --clean (Join-Path $Root "installer\starlink_widget.spec")
if (-not (Test-Path -LiteralPath (Join-Path $DistApp "StarlinkWidget.exe"))) {
    throw "Echec PyInstaller : StarlinkWidget.exe introuvable dans $DistApp"
}

if ($SkipInstaller) {
    Write-Host "[build] Termine (sans installeur). Sortie : $DistApp"
    exit 0
}

$InstallerDir = Join-Path $Root "dist\installer"
New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null

$InstallerJpg = Join-Path $Root "assets\installateur.jpg"
if (Test-Path -LiteralPath $InstallerJpg) {
    Write-Host "[build] Image laterale installeur..."
    & $VenvPython (Join-Path $Root "scripts\prepare_installer_graphics.py")
}

$Makensis = Ensure-Makensis
Write-Host "[build] NSIS..."
& $Makensis $Nsi

$SetupExe = Join-Path $InstallerDir "StarlinkWidget-Setup.exe"
if (Test-Path -LiteralPath $SetupExe) {
    Write-Host "[build] Installeur pret : $SetupExe"
} else {
    throw "Echec NSIS"
}
