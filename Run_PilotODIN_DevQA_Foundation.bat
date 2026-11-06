@echo off
setlocal
cd /d "%~dp0"
title PilotODIN DevQA Foundation - Development Only
echo PilotODIN DevQA: isolate QA workspace and run predictive preflight.
echo No user datasets, backend, native app, Qwen, installer or downloads.
if exist ".venv-live\Scripts\python.exe" goto use_venv
where py.exe >nul 2>nul
if errorlevel 1 (
  echo FAIL: Python 3 must already be installed. No package installation.
  pause
  exit /b 1
)
py -3 -B tools\qa_foundation.py check --phase FRAMEWORK-V1
goto done
:use_venv
".venv-live\Scripts\python.exe" -B tools\qa_foundation.py check --phase FRAMEWORK-V1
:done
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo DevQA foundation prepared. Any REVIEW findings still require attention.) else (echo DevQA foundation BLOCKED. Share printed diagnostic ZIP.)
echo This is NOT an application P2 or release test PASS.
pause
exit /b %RESULT%
