@echo off
setlocal
cd /d "%~dp0"
title PilotODIN E2 Memory Triage
echo.
echo PilotODIN E2 - Read-Only Memory Detail
echo =======================================
echo Lists the 12 largest process families by current memory usage.
echo ZIP includes executable names only - no file paths or personal data.
echo No imports, ML tests, model downloads, inference or installers are run.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Probe_E2_Memory_Triage.ps1"
set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" (
  echo.
  echo Memory diagnostic created. Upload the ZIP printed above.
) else (
  echo.
  echo Memory diagnostic could not be completed. Copy the error shown above.
)
echo.
pause
exit /b %RESULT%
