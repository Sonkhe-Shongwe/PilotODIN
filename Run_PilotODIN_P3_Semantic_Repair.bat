@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P3 Semantic Repair Check
echo.
echo PilotODIN P3 - Targeted Semantic Repair
echo ==============================================
echo Retests business grain uncertainty and API origin guard; frontend build already passed.
echo Uses synthetic isolated data only; existing datasets are untouched.
echo No P0/A4 replay, Tauri installer, model download or Qwen test.
echo.
if not exist ".venv-live\Scripts\python.exe" (
  echo Missing .venv-live Python. Follow the existing local dev setup.
  pause
  exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P3_Semantic_Repair_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo P3 focused semantic repairs passed.
) else (
  echo P3 repair checks did not pass. Share the diagnostic ZIP printed above.
)
echo.
pause
exit /b %RESULT%
