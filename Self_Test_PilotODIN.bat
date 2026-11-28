@echo off
setlocal
cd /d "%~dp0"
title PilotODIN Self Test
rem Source-test prerequisites must already exist. No dependency setup here.
if not exist ".venv\Scripts\python.exe" (
 echo Existing source-test environment missing. Separate reviewed setup required.
 exit /b 2
)
node frontend\scripts\verify-npm-lock.mjs --installed
if errorlevel 1 exit /b 2
set PIP_CONFIG_FILE=NUL
set PIP_NO_INDEX=1
set npm_config_offline=true
set npm_config_audit=false
".venv\Scripts\python.exe" -I -B -m pip --isolated --disable-pip-version-check --no-input check
if errorlevel 1 exit /b 2
".venv\Scripts\python.exe" -I -B -c "import importlib.metadata as m; m.version('pytest'); m.version('httpx'); m.version('httpx2'); m.version('PyMuPDF')"
if errorlevel 1 exit /b 2
echo Checking Python tests...
".venv\Scripts\python.exe" -B -m pytest -q
if errorlevel 1 (
 echo Tests failed. No packages installed.
 exit /b 1
)
echo Checking React/TypeScript build...
pushd frontend
call npm.cmd run build
if errorlevel 1 (
 popd
 echo Frontend build FAILED. Capture the output for troubleshooting.
 exit /b 1
)
popd
echo Both backend tests and frontend source bundle succeeded.
exit /b 0
