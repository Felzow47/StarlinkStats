; NSIS - Starlink Widget
; Compiler avec makensis ou scripts\build_installer.ps1

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "WinMessages.nsh"

!define APP_NAME "Starlink Widget"
!define APP_VERSION "0.1.5"
!define APP_PUBLISHER "Felzow47"
!define APP_EXE "StarlinkWidget.exe"
!define UNINST_REG_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
!define APP_SETTINGS_REG_KEY "Software\StarlinkWidget"

!define DIST_DIR "..\dist\StarlinkWidget"
!define OUTPUT_DIR "..\dist\installer"

Var AutostartChecked
Var DesktopChecked
Var HWNDAutostart
Var HWNDDesktop

Name "${APP_NAME}"
OutFile "${OUTPUT_DIR}\StarlinkWidget-Setup.exe"
InstallDir "$LOCALAPPDATA\StarlinkWidget"
InstallDirRegKey HKCU "${UNINST_REG_KEY}" "InstallLocation"
RequestExecutionLevel user
ShowInstDetails show
Unicode true
SetCompressor /SOLID lzma

!define MUI_ICON "..\assets\starlink_widget.ico"
!define MUI_UNICON "..\assets\starlink_widget.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEFINISHPAGE_BITMAP "wizard_sidebar.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "wizard_sidebar.bmp"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
Page custom OptionsPage OptionsPageLeave
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_NOAUTOCLOSE
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Lancer ${APP_NAME}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "French"

Function OptionsPage
  !insertmacro MUI_HEADER_TEXT "Options" "Choisissez les options d'installation."

  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateCheckbox} 0 0 100% 24u "Lancer Starlink Widget au demarrage de Windows (delai 30 s)"
  Pop $HWNDAutostart
  ${NSD_Uncheck} $HWNDAutostart

  ${NSD_CreateCheckbox} 0 28u 100% 24u "Creer un raccourci sur le Bureau"
  Pop $HWNDDesktop
  ${NSD_Uncheck} $HWNDDesktop

  nsDialogs::Show
FunctionEnd

Function OptionsPageLeave
  ${NSD_GetState} $HWNDAutostart $AutostartChecked
  ${NSD_GetState} $HWNDDesktop $DesktopChecked
FunctionEnd

Section "Installation" SecInstall
  DetailPrint "Reset du dossier d'installation (prefs utilisateur conservees)..."
  SetOutPath "$PLUGINSDIR"
  File "..\scripts\install_reset.ps1"
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\install_reset.ps1" -InstallDir "$INSTDIR"'
  Pop $0
  Pop $1
  ${If} $0 != 0
    DetailPrint "ERREUR : reset installation non termine."
    DetailPrint "Code retour PowerShell : $0"
    DetailPrint "Sortie PowerShell : $1"
    MessageBox MB_ICONSTOP|MB_OK "Le reset du dossier d'installation a echoue.$\r$\n$\r$\nSortie : $1$\r$\n$\r$\nL'installation va s'arreter."
    Abort
  ${EndIf}
  Delete "$PLUGINSDIR\install_reset.ps1"

  SetOutPath "$INSTDIR"
  File /r "${DIST_DIR}\*.*"

  SetOutPath "$INSTDIR\scripts"
  File "..\scripts\register_autostart.ps1"
  File "..\scripts\uninstall_autostart.ps1"
  File "..\scripts\uninstall_cleanup.ps1"
  File "..\scripts\install_reset.ps1"

  IfFileExists "$INSTDIR\config.json" +3 0
    SetOutPath "$INSTDIR"
    File /oname=config.json "..\config.json.example"

  SetOutPath "$INSTDIR\assets"
  File "..\assets\starlink_widget.ico"

  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\assets\starlink_widget.ico"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Desinstaller.lnk" "$INSTDIR\Uninstall.exe"

  ${If} $DesktopChecked == ${BST_CHECKED}
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\assets\starlink_widget.ico"
  ${EndIf}

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  WriteRegStr HKCU "${UNINST_REG_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINST_REG_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINST_REG_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINST_REG_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_REG_KEY}" "DisplayIcon" "$INSTDIR\assets\starlink_widget.ico"
  WriteRegStr HKCU "${UNINST_REG_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINST_REG_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_REG_KEY}" "NoRepair" 1

  ${If} $AutostartChecked == ${BST_CHECKED}
    DetailPrint "Configuration du demarrage automatique..."
    nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\scripts\register_autostart.ps1" -ExePath "$INSTDIR\${APP_EXE}" -WorkingDirectory "$INSTDIR" -Arguments "--autostart"'
    Pop $0
    Pop $1
    ${If} $0 != 0
      DetailPrint "ATTENTION : demarrage automatique non configure."
      DetailPrint "Code retour PowerShell : $0"
      DetailPrint "Sortie PowerShell : $1"
      MessageBox MB_ICONEXCLAMATION|MB_OK "Starlink Widget est installe, mais le demarrage automatique n'a pas pu etre configure.$\r$\n$\r$\nVous pouvez l'activer plus tard depuis l'icone dans la barre des taches."
    ${Else}
      DetailPrint "Demarrage automatique configure."
    ${EndIf}
  ${EndIf}

SectionEnd

Section "Uninstall"
  DetailPrint "Arret du widget et nettoyage systeme..."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\scripts\uninstall_cleanup.ps1"'

  DetailPrint "Suppression des raccourcis..."
  Delete "$DESKTOP\${APP_NAME}.lnk"
  Delete "$SMSTARTUP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"

  DetailPrint "Suppression des entrees registre..."
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "StarlinkWidget"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run" "StarlinkWidget"
  DeleteRegKey HKCU "${APP_SETTINGS_REG_KEY}"
  DeleteRegKey HKCU "${UNINST_REG_KEY}"

  DetailPrint "Suppression des fichiers installes..."
  RMDir /r "$INSTDIR"
SectionEnd
