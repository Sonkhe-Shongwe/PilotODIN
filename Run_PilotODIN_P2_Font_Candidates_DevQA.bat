@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Font Candidate DevQA (Developer Only)
echo PilotODIN P2: verify pinned public OFL fonts for PDF Unicode research.
echo Downloads only six official candidates / license notices (~21 MB).
echo Uses isolated LOCALAPPDATA\PilotODIN\DevQA\font-candidates folder.
echo Does not install fonts, run PilotODIN, train models or change user projects.
echo Does NOT establish production Unicode or installer acceptance.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python missing. Nothing installed.
 pause
 exit /b 2
)
if "%LOCALAPPDATA%"=="" (
 echo BLOCKED: Windows LOCALAPPDATA is missing.
 pause
 exit /b 2
)
choice /C YN /N /M "Download and verify only the pinned public fonts and licenses? [Y/N] "
if errorlevel 2 (
 echo Cancelled. No download was requested.
 exit /b 2
)
if errorlevel 1 (
 "%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_font_stage_candidates.py" --download
 set "EXIT_CODE=%ERRORLEVEL%"
 echo.
 if "%EXIT_CODE%"=="0" (
  echo Candidate byte/license/cmap gate complete. Fonts are NOT production-approved.
 ) else (
  echo Candidate staging BLOCKED or requires engineering review. Do not install these assets.
 )
 echo Share the final console output for focused review. Never send font binaries.
 pause
 exit /b %EXIT_CODE%
)
echo BLOCKED: Consent choice could not be determined.
pause
exit /b 2
