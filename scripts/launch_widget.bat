@echo off
REM Chemins mis a jour par install_autostart.ps1
cd /d "%~dp0.."
if exist ".venv\Scripts\pythonw.exe" (
    ".venv\Scripts\pythonw.exe" -m starlink_widget
) else (
    pythonw -m starlink_widget
)
