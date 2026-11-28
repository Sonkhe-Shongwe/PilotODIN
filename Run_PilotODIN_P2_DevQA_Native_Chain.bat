@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 DevQA Native Export (Synthetic)
echo PilotODIN P2 DevQA: automated run workspace and predictable preflight.
echo No user projects, AI model, installer, package downloads or old-suite replay.
echo Use the DevQA exports folder displayed in the test window for BOTH native Save As dialogs.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Start_P2_DevQA_Native_Chain_Local.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 DevQA native report integration: PASS) else (echo P2 DevQA native integration incomplete. Share the printed diagnostics ZIP or screenshot.)
pause
exit /b %RESULT%
