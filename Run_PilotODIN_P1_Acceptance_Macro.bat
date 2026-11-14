@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P1 Safe Acceptance Macro
echo.
echo PilotODIN P1 SAFE ACCEPTANCE MACRO
echo =================================
echo Isolated tests, build, browser and read-only memory inventory.
echo Existing backend/frontend processes and project data are not touched.
echo No installs, model downloads, inference or display setting changes.
echo.
if not exist ".venv-live\Scripts\python.exe" (
  echo BLOCKED: .venv-live Python is missing. No installation attempted.
  pause
  exit /b 2
)
".venv-live\Scripts\python.exe" -B "tools\Run_P1_Acceptance_Macro.py"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Scoped automated checks passed. Native gates still require observation.
) else (
  echo Some checks FAILED or BLOCKED. Review the evidence ZIP path above.
)
echo.
pause
exit /b %RESULT%
