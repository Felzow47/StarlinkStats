#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TaskName = "StarlinkWidget"
$VenvPythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$LaunchBat = Join-Path $ProjectRoot "scripts\launch_widget.bat"

if (-not (Test-Path $VenvPythonw)) {
    Write-Warning "venv introuvable. Executez: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
}

$batContent = @"
@echo off
cd /d "$ProjectRoot"
"$VenvPythonw" -m starlink_widget
"@
Set-Content -Path $LaunchBat -Value $batContent -Encoding ASCII

schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

# Delai 30s via trigger XML
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger>
      <Delay>PT30S</Delay>
    </LogonTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c "$LaunchBat"</Arguments>
      <WorkingDirectory>$ProjectRoot</WorkingDirectory>
    </Exec>
  </Actions>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <Enabled>true</Enabled>
  </Settings>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
</Task>
"@
$xmlPath = Join-Path $env:TEMP "starlink_widget_task.xml"
Set-Content -Path $xmlPath -Value $xml -Encoding Unicode
schtasks /Create /TN $TaskName /XML $xmlPath /F | Out-Null
Remove-Item $xmlPath -Force

Write-Host "Tache planifiee '$TaskName' creee (logon + delai 30s)."
Write-Host "Lancement manuel: $LaunchBat"
