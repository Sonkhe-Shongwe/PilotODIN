@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Document-Scoped PDF Unicode DevQA
echo PilotODIN P2: test safe document-specific PDF Unicode mappings.
echo Reads previously verified local DevQA font candidates.
echo No downloads, installs, project data, app startup or native Save As replay.
echo Runs nine new unit contracts and two isolated synthetic PDF workers.
echo A PASS here is NOT full production PDF acceptance.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python missing. No installation attempted.
 pause
 exit /b 2
)
if "%LOCALAPPDATA%"=="" (
 echo BLOCKED: LOCALAPPDATA is missing.
 pause
 exit /b 2
)
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_cmap_scoped_devqa.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
 echo Isolated mapping experiment passed. Production integration still OPEN.
) else (
 echo Scoped experiment needs engineering review. Share console screenshot.
)
pause
exit /b %EXIT_CODE%
