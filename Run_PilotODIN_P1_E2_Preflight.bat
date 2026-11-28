@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P1 and E2 Early Check
echo.
echo PilotODIN P1 Import Recovery + E2 Read-Only Inventory
echo ====================================================
echo Only the NEW synthetic P1 import tests are run.
echo Existing P0/A4, Tauri Save As, AI and installer tests are not repeated.
echo No models are downloaded and no inference is started.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Verify_P1_E2_Local.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo P1 checks passed. E2 memory inventory collected; no offline certification.
) else (
  echo P1/E2 check blocked; see the diagnostics ZIP printed above.
)
echo.
pause
exit /b %RESULT%
