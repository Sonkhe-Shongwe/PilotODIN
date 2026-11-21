@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Real Report to Native Save As
echo PilotODIN P2: Actual saved report - isolated FastAPI - Tauri native Save As.
echo Synthetic data and temporary backend only; no existing port 8000, model or installer.
echo Do NOT close PowerShell before finishing both native Export actions.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Verify_P2_Native_Live_Report_Local.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 real report-to-native Save As gate: PASS) else (echo P2 real report-to-native gate failed. Share the printed diagnostic ZIP.)
pause
exit /b %RESULT%
