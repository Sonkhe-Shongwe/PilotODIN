@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Report Display DevQA (Synthetic Only)
echo PilotODIN P2: check report omission disclosure and PDF page bounds.
echo Uses a fresh isolated DevQA workspace. No actual projects, native app or ML.
echo Does not repeat the accepted 12-case mixed-evidence or native Save As suites.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCK: Existing .venv-live Python not found. No installation attempted.
 pause
 exit /b 2
)
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_report_display_devqa.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
 echo Focused display checks passed; manual PDF visual acceptance remains open.
) else (
 echo P2 report display checks FAILED or BLOCKED. Share status-only ZIP.
)
pause
exit /b %EXIT_CODE%
