;
;   NSIS script to build FRCTools installer
;
;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"
  
  !define APP_REG_ID "FRCTools"
  
  !define APP_DESCRIPTION "FRC Tools for Fusion"

  !define UNINSTALL_REG_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_REG_ID}"

;--------------------------------
;General

  ;Name and file
  Name "${APP_DESCRIPTION}"
  OutFile "build/FRCTools-win.exe"
  Unicode True

  ;Default installation folder
  InstallDir "$APPDATA\Autodesk\Autodesk Fusion 360\API\AddIns\FRCTools"
  
  ;Get installation folder from registry if available
  InstallDirRegKey HKCU "Software\${APP_REG_ID}" ""

  ;Request application privileges for Windows Vista
  RequestExecutionLevel user

;--------------------------------
;Interface Configuration

  !define MUI_ICON  ".\docs\icons\installer.ico"
  !define MUI_UNICON  ".\docs\icons\installer.ico"
  !define MUI_HEADERIMAGE
  !define MUI_HEADERIMAGE_BITMAP ".\docs\icons\CCDistance.bmp" ; optional
  !define MUI_HEADERIMAGE_BITMAP_STRETCH "AspectFitHeight"
  !define MUI_HEADERIMAGE_UNBITMAP ".\docs\icons\CCDistance.bmp" ; optional
  !define MUI_HEADERIMAGE_UNBITMAP_STRETCH "AspectFitHeight"
  !define MUI_ABORTWARNING

;--------------------------------
;Pages

  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
  
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  
;--------------------------------
;Languages
 
  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section "Add in" SecAddIn

  SetOutPath "$INSTDIR"
  
  File FRCTools.py
  File FRCTools.Manifest
  File config.py
  File /r /x __pycache__ /x *.pyc commands
  File /r /x __pycache__ /x *.pyc lib
  File /r /x __pycache__ /x *.pyc generators
  
  ;Store installation folder
  WriteRegStr HKCU "Software\${APP_REG_ID}" "" $INSTDIR
  
  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  
  WriteRegStr HKCU ${UNINSTALL_REG_KEY} "" ""
  WriteRegStr HKCU ${UNINSTALL_REG_KEY} "DisplayName" "${APP_DESCRIPTION}"
  WriteRegStr HKCU ${UNINSTALL_REG_KEY} "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd
 
;--------------------------------
;Uninstaller Section

Section "Uninstall"

  ;ADD YOUR OWN FILES HERE...

  Delete "$INSTDIR\Uninstall.exe"

  RMDir /r "$INSTDIR"

  DeleteRegKey HKCU "Software\${APP_REG_ID}"
  DeleteRegKey HKCU ${UNINSTALL_REG_KEY}

SectionEnd