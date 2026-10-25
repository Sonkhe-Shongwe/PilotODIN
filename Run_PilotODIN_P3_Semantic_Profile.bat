@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P3 Semantic Understanding Check
echo.
echo PilotODIN P3 - Deterministic Dataset Semantics
echo ==============================================
echo Tests tentative domain/grain meaning, version isolation and read-only dictionary.
echo Uses synthetic isolated data only; existing datasets are untouched.
echo No P0/A4 replay, Tauri installer, model download or Qwen test.
echo.
if not exist ".venv-live\Scripts\python.exe" (
  echo Missing .venv-live Python. Follow the existing local dev setup.
  pause
  exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P3_Semantic_Profile_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo P3 focused semantic-profile package passed.
) else (
  echo P5 check did not pass. Share the diagnostic ZIP printed above.
)
echo.
pause
exit /b %RESULT%
