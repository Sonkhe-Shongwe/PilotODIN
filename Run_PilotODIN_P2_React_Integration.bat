@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Mounted React Integration
echo PilotODIN P2: actual mounted React reporting interactions
echo Uses synthetic mocked API, isolated loopback Vite and disposable Chrome/Edge profile.
echo Never connects to actual backend or reads user datasets/reports.
echo No new npm packages, cloud Actions, installer or AI.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing existing .venv-live Python. Use established development setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P2_React_Integration_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 mounted React integration checks passed.) else (echo P2 React integration failed. Share one printed diagnostic ZIP.)
pause
exit /b %RESULT%
