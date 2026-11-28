@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P4 Two-Axis Evidence Review
echo PilotODIN P4: technical readiness vs decision relevance
echo Isolated synthetic checks only; no ML fit, Qwen, installer or user data changes.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing isolated .venv-live Python. Use established development setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P4_Two_Axis_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P4 two-axis focused gate passed.) else (echo Gate failed; share printed diagnostics ZIP.)
pause
exit /b %RESULT%
