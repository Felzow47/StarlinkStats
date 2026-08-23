#Requires -Version 5.1
<#
.SYNOPSIS
    Demarrage au logon (cle Run + autorisation StartupApproved, sans droits admin).
    Le delai apres logon est gere par l'application (--autostart).
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [string]$WorkingDirectory = "",
    [string]$Arguments = "",
    [string]$TaskName = "StarlinkWidget",
    [int]$DelaySeconds = 30,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)
# python subprocess passe parfois "--autostart" hors de -Arguments ; PowerShell le voit comme switch.
if (-not $Arguments -and $RemainingArgs) {
    $Arguments = ($RemainingArgs | ForEach-Object { "$_".Trim() }) -join " "
}

$ErrorActionPreference = "Stop"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$ApprovedKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"

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

    $vbsPath = Join-Path $WorkingDirectory "scripts\autostart_launch.vbs"
    if (Test-Path -LiteralPath $vbsPath) {
        Remove-Item -LiteralPath $vbsPath -Force -ErrorAction SilentlyContinue
    }

    New-Item -Path $RunKey -Force | Out-Null
    $runCmd = if ($Arguments) { "`"$ExePath`" $Arguments" } else { "`"$ExePath`"" }
    Set-ItemProperty -Path $RunKey -Name $TaskName -Value $runCmd

    # Windows peut laisser l'entree desactivee dans Parametres > Applications > Demarrage
    # (octet 0x03) meme si la cle Run existe. Sans 0x02, le widget ne se lance pas.
    New-Item -Path $ApprovedKey -Force | Out-Null
    $enabledBytes = [byte[]](0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)
    New-ItemProperty -Path $ApprovedKey -Name $TaskName -PropertyType Binary -Value $enabledBytes -Force | Out-Null

    Write-Host "Demarrage automatique configure (delai applicatif ${DelaySeconds}s via --autostart)."
    exit 0
} catch {
    Write-Error "Echec configuration demarrage automatique : $($_.Exception.Message)"
    exit 1
}
