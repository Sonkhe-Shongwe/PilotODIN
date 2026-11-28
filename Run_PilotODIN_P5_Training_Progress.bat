@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P5 Training Progress Check
echo.
echo PilotODIN P5 - Durable Training Stage Progress
echo ==============================================
echo Tests factual SQLite stage history, restart recovery and Evaluate polling.
echo Uses synthetic isolated data only; existing datasets are untouched.
echo No P0/A4 replay, Tauri installer, model download or Qwen test.
echo.
if not exist ".venv-live\Scripts\python.exe" (
  echo Missing .venv-live Python. Follow the existing local dev setup.
  pause
  exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P5_Training_Progress_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo P5 focused progress package passed.
) else (
  echo P5 check did not pass. Share the diagnostic ZIP printed above.
)
echo.
pause
exit /b %RESULT%
