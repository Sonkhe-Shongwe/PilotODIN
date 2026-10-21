@echo off
setlocal
cd /d "%~dp0"
title PilotODIN Self Test
if not exist ".venv\Scripts\python.exe" (
 echo Run Start_PilotODIN.bat first to set up your Python environment.
 pause
 exit /b 1
)
echo Checking Python tests...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (
 echo Tests failed, or pytest is not installed.
 echo If pytest is missing: .venv\Scripts\python.exe -m pip install pytest httpx
 pause
 exit /b 1
)
echo Checking React/TypeScript build...
pushd frontend
call npm.cmd run build
if errorlevel 1 (
 popd
 echo Frontend build FAILED. Capture the output for troubleshooting.
 pause
 exit /b 1
)
popd
echo Both backend tests and frontend production build succeeded on your machine.
pause
exit /b 0
