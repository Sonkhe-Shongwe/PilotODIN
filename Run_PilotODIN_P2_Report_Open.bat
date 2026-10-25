@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Report Open Safety
echo PilotODIN P2: latest-request-safe report Open navigation
echo Isolated Node source contracts and TypeScript/Vite build only.
echo No user reports modified, no model/installer/Qwen and no old-suite replay.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing .venv-live Python. Follow existing dev setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P2_Report_Open_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 report Open focused checks passed.) else (echo P2 report Open failed; share ZIP printed above.)
pause
exit /b %RESULT%
