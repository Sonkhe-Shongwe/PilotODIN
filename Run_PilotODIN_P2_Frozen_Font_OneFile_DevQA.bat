@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Actual Onefile Font Resources - Isolated DevQA
echo PilotODIN P2-U2a: REAL isolated PyInstaller ONEFILE font resource proof.
echo Uses ONLY the previously staged six verified font/OFL review files.
echo Runs eight disposable synthetic contracts first.
echo This creates a separate ignored probe executable, NOT the PilotODIN sidecar.
echo No downloads, pip installs, Tauri app, model training or customer projects.
echo The font license and hash receipt remain build-review-only, NOT for release.
echo This does NOT test the production Unicode PDF renderer or installer.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python is missing. No installation attempted.
 pause
 exit /b 2
)
echo Running eight synthetic isolation, integrity and failure-contract tests...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_frozen_font_onefile.py" -v
if errorlevel 1 (
 echo BLOCKED OR FAIL: Synthetic safety contracts were not all green.
 pause
 exit /b 2
)
echo.
echo Checking existing build environments for PyInstaller 6, WITHOUT installing it...
set "FREEZER="
"%~dp0.venv-live\Scripts\python.exe" -c "from importlib.metadata import version; assert version('pyinstaller').split('.')[0] == '6'" >nul 2>&1
if not errorlevel 1 set "FREEZER=%~dp0.venv-live\Scripts\python.exe"
if not defined FREEZER if exist "%~dp0.venv\Scripts\python.exe" (
 "%~dp0.venv\Scripts\python.exe" -c "from importlib.metadata import version; assert version('pyinstaller').split('.')[0] == '6'" >nul 2>&1
 if not errorlevel 1 set "FREEZER=%~dp0.venv\Scripts\python.exe"
)
if not defined FREEZER (
 echo BLOCKED: PyInstaller 6 not found in existing .venv-live or .venv.
 echo No dependency installation or other environment modification attempted.
 pause
 exit /b 2
)
echo Existing PyInstaller 6 found. Only the selected local build Python is used.
echo Consent: build one isolated frozen proof with the existing PyInstaller?
echo It will use around 21 MB of verified font data in a new ignored build folder.
choice /C YN /N /M "Create and execute the isolated ONEFILE font probe? [Y/N] "
if errorlevel 2 (
 echo Cancelled. No frozen probe build authorized.
 exit /b 2
)
if not errorlevel 1 (
 echo BLOCKED: Consent not established.
 pause
 exit /b 2
)
echo.
echo Building and verifying only the DEVQA font probe; no installer or sidecar.
"%FREEZER%" -B "%~dp0tools\p2_pdf_frozen_font_onefile_devqa.py" --build
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo Scoped frozen font resource experiment passed. Actual PilotODIN sidecar still OPEN.
) else (
 echo Frozen resource experiment FAILED OR BLOCKED; do not promote build assets.
 echo Share the safe console outcome. Do not upload any font binaries or executables.
)
pause
exit /b %RC%
