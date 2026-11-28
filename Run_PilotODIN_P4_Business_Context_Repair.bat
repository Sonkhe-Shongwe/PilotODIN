@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P4 Focused Repair Check
echo PilotODIN P4 business context: frontend repair only
echo Retains earlier owner result: 17 backend tests PASS.
echo No model download, installer, user data changes, or old-suite replay.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing isolated .venv-live Python.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P4_Business_Context_Repair_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P4 focused repair checks passed.) else (echo Repair failed; share printed diagnostics ZIP.)
pause
exit /b %RESULT%
