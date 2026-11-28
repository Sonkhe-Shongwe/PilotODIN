@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Read Safety Repair
echo PilotODIN P2: repair-only navigation source contract check
echo Previous 24 Node passes and frontend build PASS retained from uploaded ZIP.
echo No Vite rebuild, user data writes, Qwen, installer or older-suite replay.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing .venv-live Python. Use existing local dev setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P2_Report_Read_Repair_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 read-safety focused repair checks passed.) else (echo P2 repair failed; share the printed diagnostics ZIP.)
pause
exit /b %RESULT%
