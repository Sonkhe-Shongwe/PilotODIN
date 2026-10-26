@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 - Isolated Freezer Tooling Recovery
echo PilotODIN P2-U2a: resolve missing PyInstaller 6 prerequisite safely.
echo This is NOT the application installer and does not change production reports.
echo It will never install anything into .venv-live or .venv.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python is missing. No setup performed.
 pause
 exit /b 2
)
echo Running five pure synthetic contracts for isolated tool setup...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_pyinstaller_tooling.py" -v
if errorlevel 1 (
 echo BLOCKED: Isolated tooling contracts failed. Nothing installed.
 pause
 exit /b 2
)
echo.
echo Checking existing isolated DevQA tooling (no install)...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_pyinstaller_tooling_devqa.py"
if not errorlevel 1 goto TOOL_READY
echo.
echo PyInstaller 6 is not yet available in the dedicated DevQA tooling environment.
echo With your YES, a NEW private Python venv will be created ONLY under:
echo build\p2-pdf-frozen-resource-probe\tooling-venv
echo It will use official https://pypi.org/simple to download/install:
echo pyinstaller==6.22.3 and pyinstaller-hooks-contrib==2026.9
echo plus necessary package dependencies into that private tooling venv.
echo Network access is needed. No user projects, app dependencies, fonts
echo or existing Python environments will be changed.
echo Existing incomplete tooling folders will NOT be deleted or overwritten.
echo.
choice /C YN /N /M "Approve ONLY this separate DevQA tooling installation? [Y/N] "
if errorlevel 2 (
 echo Cancelled. No dependency install authorised.
 exit /b 2
)
if not errorlevel 1 (
 echo BLOCKED: No affirmative consent.
 pause
 exit /b 2
)
echo.
echo Preparing private, pinned PyInstaller development tooling...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_pyinstaller_tooling_devqa.py" --prepare
if errorlevel 1 (
 echo BLOCKED: Private tooling preparation failed.
 echo No app environment was intentionally modified.
 echo Share this status only. Do NOT manually delete folders or install globally.
 pause
 exit /b 2
)
:TOOL_READY
echo.
echo Private PyInstaller 6 tooling ready.
echo Starting the existing scoped frozen-font DevQA launcher.
echo That launcher will ask SEPARATELY for consent to build and run the probe.
call "%~dp0Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat"
set "STATUS=%ERRORLEVEL%"
exit /b %STATUS%
