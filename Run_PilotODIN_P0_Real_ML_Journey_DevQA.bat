@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P0 - Real Isolated Prepare to Predict
echo ONE genuine P0 functional lifecycle on entirely generated test data.
echo Prepare, train, select, evaluate, predict, approve Quality version,
echo reject stale model, retrain on version 1, select and predict again.
echo Existing venv only, no installer, fonts, local AI, network, or real projects.
echo A fresh disposable home is created BEFORE backend imports.
echo Prefer normal NON-ADMIN Windows. No elevation required.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
  echo BLOCKED: Existing isolated development Python interpreter missing.
  pause
  exit /b 2
)
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p0_real_ml_versioned_api_devqa.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo P0 source and real API lifecycle passed in disposable home only.
  echo Actual Windows UI, peak RAM and installed offline release remain open.
) else (
  echo BLOCKED. Preserve all prior accepted P2 and A3 checkpoints.
  echo Share only safe final JSON and stage. Never upload local training logs.
)
pause
exit /b %RC%
