#Requires -Version 5.1
<#
.SYNOPSIS
    Demarrage au logon (cle Run + delai, sans droits admin).
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [string]$WorkingDirectory = "",
    [string]$Arguments = "",
    [string]$TaskName = "StarlinkWidget",
    [int]$DelaySeconds = 30
)

$ErrorActionPreference = "Stop"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

function Remove-LegacyScheduledTask {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $schtasks = Join-Path $env:WINDIR "System32\schtasks.exe"
    if (-not (Test-Path -LiteralPath $schtasks)) {
        return
    }

    & $env:ComSpec /d /c "`"$schtasks`" /Delete /TN `"$Name`" /F >nul 2>&1"
}

try {
    if (-not $WorkingDirectory) {
        $WorkingDirectory = Split-Path -Parent $ExePath
    }
    if (-not (Test-Path -LiteralPath $ExePath)) {
        throw "Executable introuvable : $ExePath"
    }

    Remove-ItemProperty -Path $RunKey -Name $TaskName -ErrorAction SilentlyContinue
    Remove-LegacyScheduledTask -Name $TaskName

    $scriptsDir = Join-Path $WorkingDirectory "scripts"
    New-Item -ItemType Directory -Force -Path $scriptsDir | Out-Null

    $vbsPath = Join-Path $scriptsDir "autostart_launch.vbs"
    $delayMs = [Math]::Max(0, $DelaySeconds) * 1000
    $runCmd = if ($Arguments) { "`"$ExePath`" $Arguments" } else { "`"$ExePath`"" }
    $escapedWorkingDirectory = $WorkingDirectory.Replace('"', '""')
    $escapedRunCmd = $runCmd.Replace('"', '""')
    $vbs = @"
WScript.Sleep $delayMs
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "$escapedWorkingDirectory"
sh.Run "$escapedRunCmd", 0, False
"@
    Set-Content -Path $vbsPath -Value $vbs -Encoding ASCII -Force

    New-Item -Path $RunKey -Force | Out-Null

    $wscript = Join-Path $env:WINDIR "System32\wscript.exe"
    if (-not (Test-Path -LiteralPath $wscript)) {
        $wscript = "wscript.exe"
    }
    $launcher = "`"$wscript`" //B //Nologo `"$vbsPath`""
    Set-ItemProperty -Path $RunKey -Name $TaskName -Value $launcher

    Write-Host "Demarrage automatique configure (delai ${DelaySeconds}s)."
    exit 0
} catch {
    Write-Error "Echec configuration demarrage automatique : $($_.Exception.Message)"
    exit 1
}

