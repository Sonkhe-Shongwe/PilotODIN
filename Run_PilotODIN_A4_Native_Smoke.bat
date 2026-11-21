@echo off
setlocal
cd /d "%~dp0"
title PilotODIN A4 Native Windows Smoke
echo.
echo PilotODIN A4 - Native Windows Save As verification
echo =================================================
echo This compiles and runs a DEVELOPMENT Tauri window.
echo It does not create an installer or download AI models.
echo Start the normal PilotODIN Live Dev backend first.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Verify_A4_Native_Windows.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Native verification script finished. See its printed PASS and manual outcomes.
) else (
  echo Native verification stopped with error code %RESULT%.
  echo Review the generated diagnostics archive.
)
echo.
pause
exit /b %RESULT%
