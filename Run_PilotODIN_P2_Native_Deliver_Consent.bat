@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Native Deliver Consent (Synthetic DevQA)
echo This launches the REAL Tauri UnifiedShell with a new isolated four-row synthetic project.
echo It NEVER installs a package, launches AI, modifies original datasets, or approves Unicode fonts.
echo Do not click Save, Upload, Export, or training controls. Observe only Leave Deliver / Keep editing.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Run_P2_Native_Deliver_Consent_Local.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 native consent: OWNER OBSERVATION RECORDED; still needs QA review.) else (echo P2 native consent: NOT ACCEPTED. Share the printed QA diagnostics path.)
pause
exit /b %RESULT%
