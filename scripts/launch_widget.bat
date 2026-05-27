@echo off
setlocal EnableExtensions

rem Racine du projet (scripts\..)
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "VENV_PY=%ROOT%\.venv\Scripts\pythonw.exe"
set "CLEAN_PS=%~dp0clean_widget.ps1"

cd /d "%ROOT%"

echo.
echo [Starlink Widget] Demarrage propre...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%CLEAN_PS%" -Root "%ROOT%"
if errorlevel 1 (
    echo ERREUR: echec du nettoyage.
    pause
    exit /b 1
)

echo.
echo [Starlink Widget] Lancement du widget...
echo.

if not exist "%VENV_PY%" (
    echo ERREUR: environnement virtuel introuvable.
    echo        Attendu: %VENV_PY%
    echo        Lancez: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

start "" "%VENV_PY%" -m starlink_widget

endlocal
