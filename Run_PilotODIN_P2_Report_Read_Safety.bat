@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Report Read Safety Batch
echo PilotODIN P2: evidence reload, export safety, edited-during-Open protection
echo Actual TypeScript gate behaviors, affected Node contracts and Vite build.
echo Synthetic isolated checks only. No owner report/data writes or Qwen/installer.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing .venv-live Python. Use existing local development setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P2_Report_Read_Safety_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 report read-safety batch checks passed.) else (echo P2 report read-safety checks failed. Share the ZIP printed above.)
pause
exit /b %RESULT%
