@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Native Export Development QA
echo PilotODIN P2: real Windows native Save As, synthetic reports only
echo Follow the temporary save-folder instructions in the PowerShell window.
echo No existing backend, user datasets, AI, installer or historical suite replay.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Verify_P2_Native_Export_Local.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 native export focused acceptance: PASS) else (echo P2 native export checks FAILED or INCOMPLETE. Share the ZIP printed above.)
pause
exit /b %RESULT%
