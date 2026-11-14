@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 U2g - Read-Only Font Release Readiness
echo P2-U2g: read-only existing six-file font/OFL candidate provenance review.
echo This is NOT font redistribution approval or a release manifest.
echo It DOES NOT install, edit, convert, download, stage or publish font files.
echo No report rendering, saved user data, PyInstaller, Tauri, installer, models.
echo Existing successful U2c/U2d/U2f and earlier font/PDF gates are NOT rerun.
echo Prefer a normal, NON-ADMIN Windows session. No elevation needed.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing app/test Python missing; no environment changes made.
 pause
 exit /b 2
)
echo Running ONLY 10 NEW pure synthetic dossier safety tests...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_release_readiness_devqa.py" -v
if errorlevel 1 (
 echo BLOCKED: New dossier safety contracts failed. No real source audit attempted.
 pause
 exit /b 2
)
echo.
echo Read-only rehash of the single previously reviewed six candidate files...
echo Original OFL headings and Reserved Font Name indicators reviewed safely.
echo No copies, release pins or production report changes.
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_release_readiness_devqa.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo DevQA candidate DOSSIER ONLY. Actual release font approval is NOT_GRANTED.
 echo No actual product Unicode PDF or installer has been accepted.
) else (
 echo BLOCKED: Stop; retain old accepted evidence and share only safe final JSON.
 echo Do not reinstall, rebuild, mutate font files or rerun old tests.
)
echo Share only safe console JSON, never fonts, OFL files or private folders.
pause
exit /b %RC%
