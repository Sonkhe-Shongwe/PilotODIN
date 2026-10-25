@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P1 Resource Settings Verification
echo.
echo PilotODIN P1 Resource-Aware Mode Verification
echo =============================================
echo Tests isolated resource preferences, API and Settings UI types.
echo Full P0/A4 suite, native Save As and AI inference are NOT repeated.
echo Your existing project files are not tested or modified.
echo.
if not exist ".venv-live\Scripts\python.exe" (
  echo Missing .venv-live Python. Use the normal PilotODIN development setup.
  pause
  exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P1_Resource_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Resource settings regression and frontend build passed.
) else (
  echo Resource verification failed. Please upload the ZIP printed above.
)
echo.
pause
exit /b %RESULT%
