@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Cached Font Review - Read Only
echo PilotODIN P2: review already staged public font candidates OFFLINE.
echo Reads only the existing isolated DevQA font-candidates folder.
echo No download, fonts installed, project access, model training, or installer.
echo Does NOT establish final Unicode visual or product acceptance.
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
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_font_local_review.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo Candidate extraction checks passed, but PDF visual acceptance remains OPEN.
) else (
 echo Check each font and TEXT result above. No changes were made.
)
pause
exit /b %RC%
