@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Mixed Evidence DevQA (Synthetic Only)
echo PilotODIN P2: verify four-source evidence reporting in isolated DevQA.
echo Test-only local FastAPI and SQLite; no app window, model training or installer.
echo Does NOT touch existing PilotODIN project data or repeat accepted native tests.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
  echo BLOCK: Existing .venv-live Python missing. No package installation attempted.
  pause
  exit /b 2
)
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_mixed_report_devqa.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
 echo Scoped synthetic tests completed. REVIEW still required for disclosure and visual-layout risks.
) else (
 echo Scoped P2 mixed evidence gate FAILED or BLOCKED. Share the printed diagnostic ZIP.
)
pause
exit /b %EXIT_CODE%
