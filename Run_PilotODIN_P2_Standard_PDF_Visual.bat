@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 BE-030 Standard PDF Visual Review (Synthetic DevQA)
echo PilotODIN P2 BE-030: current STANDARD PDF layout and chart visual review.
echo Creates one entirely NEW disposable DevQA project with eight invented rows.
echo Uses normal saved-report HTML/PDF endpoints, not Unicode development fonts.
echo No user projects, downloads, installs, AI, training or modifications to saved work.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
  echo REQUIRED EXISTING .venv-live Python is missing. This launcher installs nothing.
  pause
  exit /b 1
)
if defined PILOTODIN_HOME (
  echo REFUSED: PILOTODIN_HOME already points to another workspace.
  echo Close any prior QA session and run in a fresh terminal.
  pause
  exit /b 1
)
if defined PILOTODIN_DESKTOP_SESSION (
  echo REFUSED: a desktop session environment is already active.
  pause
  exit /b 1
)
echo Checking isolated QA source before creating any synthetic project...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_legacy_pdf_*.py"
if ERRORLEVEL 1 (
  echo QA source preflight FAILED. No disposable report was generated.
  pause
  exit /b 1
)
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\Run_P2_Legacy_PDF_Visual_Local.py"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo BE-030 synthetic API and PDF content checks complete. OWNER VISUAL REVIEW REQUIRED.
  echo Check the actual printed PDF, page images, chart, tables, clipping and pagination.
) else (
  echo BE-030 synthetic runner FAILED OR WAS BLOCKED. No owner visual PASS claimed.
  echo Share only the error and printed status-only archive path.
)
pause
exit /b %RESULT%
