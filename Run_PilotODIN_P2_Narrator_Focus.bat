@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 A01 Windows Keyboard + Narrator QA (Synthetic DevQA)
echo P2-A01 FOCUSED ACCESSIBILITY ONLY: separate from accepted five-step native consent.
echo This uses the existing isolated Tauri full shell with a disposable four-row project.
echo No installation, model training, report save, upload, export, or original datasets.
echo Close any older PilotODIN dev QA windows before launching.
echo Narrator shortcut: Windows+Ctrl+Enter. Use Tab, Shift+Tab and Enter/Space.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Run_P2_Native_Deliver_Consent_Local.ps1" -AccessibilityOnly
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2-A01: OWNER ACCESSIBILITY OBSERVATIONS RECORDED; REVIEW REQUIRED.) else (echo P2-A01: NOT ACCEPTED OR NOT ALL OBSERVED; record the status-only DevQA path.)
pause
exit /b %RESULT%
