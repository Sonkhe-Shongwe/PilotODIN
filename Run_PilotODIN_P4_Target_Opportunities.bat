@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P4 Target Opportunity Check
echo.
echo PilotODIN P4 - Target Opportunity Screening
echo ==============================================
echo Tests labelled-target screening, safe abstention and explicit target choice.
echo Uses synthetic isolated data only; existing datasets are untouched.
echo No P0/A4 replay, Tauri installer, model download or Qwen test.
echo.
if not exist ".venv-live\Scripts\python.exe" (
  echo Missing .venv-live Python. Follow the existing local dev setup.
  pause
  exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P4_Target_Opportunities_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo P4 target opportunity tests passed.
) else (
  echo P4 target opportunity test failed. Share the diagnostic ZIP printed above.
)
echo.
pause
exit /b %RESULT%
