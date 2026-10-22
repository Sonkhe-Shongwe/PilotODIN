@echo off
setlocal
cd /d "%~dp0.."
echo PilotODIN Build E: Windows frontend verification only
echo This does not modify existing PilotODIN projects or start AI.
where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo PowerShell is unavailable.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify_Frontend_Windows.ps1"
set "CODE=%ERRORLEVEL%"
echo.
echo Results saved under frontend-check-results
if not "%CODE%"=="0" echo Compilation could not be verified. See logs for the exact failure.
pause
exit /b %CODE%
