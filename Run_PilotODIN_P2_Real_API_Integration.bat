@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Real API Integration
echo PilotODIN P2: real React + isolated FastAPI/SQLite report journey
echo Uses temporary synthetic project files, loopback API and disposable Chrome/Edge.
echo Will not use the existing 8000 backend, real projects, cloud models or installer.
if not exist ".venv-live\Scripts\python.exe" (
 echo Missing .venv-live Python. Use established development setup.
 pause
 exit /b 1
)
".venv-live\Scripts\python.exe" tools\Verify_P2_Real_API_Integration_Local.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 real API reporting integration passed.) else (echo P2 real API gate failed. Share the diagnostic ZIP printed above.)
pause
exit /b %RESULT%
