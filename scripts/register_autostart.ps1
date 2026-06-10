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

$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

if (-not $WorkingDirectory) {
    $WorkingDirectory = Split-Path -Parent $ExePath
}
if (-not (Test-Path -LiteralPath $ExePath)) {
    Write-Error "Executable introuvable : $ExePath"
    exit 1
}

$ErrorActionPreference = "SilentlyContinue"
Remove-ItemProperty -Path $RunKey -Name $TaskName -ErrorAction SilentlyContinue
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
}
$schtasks = Join-Path $env:WINDIR "System32\schtasks.exe"
& $schtasks /Delete /TN $TaskName /F *> $null
$ErrorActionPreference = "Stop"

$scriptsDir = Join-Path $WorkingDirectory "scripts"
New-Item -ItemType Directory -Force -Path $scriptsDir | Out-Null

$vbsPath = Join-Path $scriptsDir "autostart_launch.vbs"
$delayMs = $DelaySeconds * 1000
$runCmd = if ($Arguments) { "`"$ExePath`" $Arguments" } else { "`"$ExePath`"" }
$vbs = @"
WScript.Sleep $delayMs
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "$WorkingDirectory"
sh.Run "$runCmd", 0, False
"@
Set-Content -Path $vbsPath -Value $vbs -Encoding ASCII

$launcher = "wscript.exe //B //Nologo ""$vbsPath"""
Set-ItemProperty -Path $RunKey -Name $TaskName -Value $launcher

Write-Host "Demarrage automatique configure (delai ${DelaySeconds}s)."
exit 0
