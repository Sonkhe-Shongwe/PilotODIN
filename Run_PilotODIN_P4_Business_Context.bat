@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P4 Business Context Check
echo.
echo PilotODIN P4 - Business Context Provenance
echo ==============================================
echo Tests user-submitted context, project/version isolation and retained target safeguards.
echo Uses synthetic isolated data only; existing datasets are untouched.
echo No P0/A4 replay, Tauri installer, model download or Qwen test.
echo.
if not exist ".venv-live\Scripts\python.exe" (
  echo Missing .venv-live Python. Follow the existing local dev setup.
  pause
  exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P4_Business_Context_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo P4 business context focused checks passed.
) else (
  echo P4 business context focused checks failed. Share the diagnostic ZIP printed above.
)
echo.
pause
exit /b %RESULT%
