@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P5 ML Coordination Check
echo.
echo PilotODIN P5 - Low-Memory Training Coordination
echo ===============================================
echo Tests atomic single-slot admission, failures, and restart recovery.
echo Uses isolated synthetic SQLite and sample data only.
echo No P0, A4 exports, model downloads, Qwen or installers are run.
echo.
if not exist ".venv-live\Scripts\python.exe" (
  echo Python development environment missing. Use existing PilotODIN Live Dev setup.
  pause
  exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P5_ML_Coordination_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo P5 focused synthetic regressions passed.
) else (
  echo P5 focused regressions failed. Upload the diagnostics ZIP shown above.
)
echo.
pause
exit /b %RESULT%
