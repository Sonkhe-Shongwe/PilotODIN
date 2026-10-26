@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Unicode Font Resource Preflight
echo PilotODIN P2-U1: test font resource staging contracts and inspect pinned candidates.
echo Uses existing .venv-live, six already staged local DevQA files, no downloads.
echo This launcher is READ ONLY. It creates no build staging directory.
echo Does NOT install fonts, launch PilotODIN, train models or build an installer.
echo A PASS here is NOT frozen sidecar or product Unicode acceptance.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python missing. No dependency installation.
 pause
 exit /b 2
)
if "%LOCALAPPDATA%"=="" (
 echo BLOCKED: Windows LOCALAPPDATA missing.
 pause
 exit /b 2
)
echo Checking seven pure synthetic build-resource contracts...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_font_build_preflight.py" -v
if errorlevel 1 (
 echo FONT BUILD PREFLIGHT: FAIL OR BLOCKED. Do not stage or bundle.
 pause
 exit /b 2
)
echo.
echo Verifying staged candidate byte identities and license notices, without copying...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_font_build_preflight.py"
if errorlevel 1 (
 echo FONT BUILD PREFLIGHT: BLOCKED. Do not stage or bundle.
 pause
 exit /b 2
)
echo.
echo FONT BUILD PREFLIGHT: SOURCE CHECK PASS; BUILD STAGING NOT PERFORMED.
echo The separate explicit --stage operation is not invoked by this launcher.
echo Send final console output. Do not upload or share font binaries.
pause
exit /b 0
