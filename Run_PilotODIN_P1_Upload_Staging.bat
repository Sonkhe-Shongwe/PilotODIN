@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P1 Upload Staging Recovery
echo PilotODIN P1: atomic upload staging and failure recovery
echo Synthetic isolated tests only. Existing project datasets and models untouched.
echo No Vite, Qwen, installer, hosted Actions or unrelated suite replay.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing .venv-live Python. Follow existing local dev setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P1_Upload_Staging_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P1 import staging checks passed.) else (echo P1 import staging failed; share the diagnostics ZIP.)
pause
exit /b %RESULT%
