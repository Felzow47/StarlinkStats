#Requires -Version 5.1
$TaskName = "StarlinkWidget"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$ApprovedKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
$ErrorActionPreference = "Stop"

function Remove-LegacyScheduledTask {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $schtasks = Join-Path $env:WINDIR "System32\schtasks.exe"
    if (-not (Test-Path -LiteralPath $schtasks)) {
        return $false
    }

    & $env:ComSpec /d /c "`"$schtasks`" /Delete /TN `"$Name`" /F >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

try {
    Remove-ItemProperty -Path $RunKey -Name $TaskName -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path $ApprovedKey -Name $TaskName -ErrorAction SilentlyContinue

    $deletedTask = Remove-LegacyScheduledTask -Name $TaskName
    if ($deletedTask) {
        Write-Host "Tache '$TaskName' supprimee (schtasks)."
    } else {
        Write-Host "Demarrage automatique deja absent."
    }
    exit 0
} catch {
    Write-Error "Echec suppression demarrage automatique : $($_.Exception.Message)"
    exit 1
}
