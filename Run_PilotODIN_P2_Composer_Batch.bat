@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Composer Controlled Batch
echo PilotODIN P2: Save, Quality capture and truthful refresh results
echo Behavioral guard tests, affected Node regressions, TypeScript/Vite.
echo No real project/report writes, Qwen/installer or old standalone suite replay.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing .venv-live Python. Use existing developer setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P2_Composer_Batch_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 composer focused batch passed.) else (echo P2 composer batch failed; share diagnostics ZIP.)
pause
exit /b %RESULT%
