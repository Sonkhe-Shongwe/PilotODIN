@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P4 Prediction Timing Review
echo PilotODIN P4: read-only timing and label-source review checks
echo Synthetic isolated tests only; no user data import, ML, Qwen or installer.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing isolated .venv-live Python; use established development setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P4_Prediction_Timing_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P4 timing focused gate passed.) else (echo P4 timing gate failed; share one diagnostics ZIP.)
pause
exit /b %RESULT%
