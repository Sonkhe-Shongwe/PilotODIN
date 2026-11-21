@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Verified Font Build-Review Staging
echo PilotODIN P2-U1: stage verified public OFL fonts for BUILD REVIEW only.
echo Reads six previously verified local DevQA font and license files.
echo With your consent, copies about 21 MB to an ignored build-only review folder.
echo Does NOT download, install fonts, build an engine/installer, or open projects.
echo Does NOT modify production PDFs, models, report revisions or app resources.
echo Output is NOT approved for release or final Unicode acceptance.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python is missing. No installation attempted.
 pause
 exit /b 2
)
if "%LOCALAPPDATA%"=="" (
 echo BLOCKED: Windows LOCALAPPDATA is missing.
 pause
 exit /b 2
)
choice /C YN /N /M "Stage six pinned files into ignored BUILD-ONLY review folder? [Y/N] "
if errorlevel 2 (
 echo Cancelled. No font staging was requested.
 exit /b 2
)
if not errorlevel 1 (
 echo BLOCKED: Consent not established.
 pause
 exit /b 2
)
echo.
echo Rechecking pinned source bytes, licenses and copied file hashes...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_font_build_preflight.py" --stage
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo STAGING REVIEW: Six files copied and individually verified.
 echo The receipt is NOT release approval. Frozen sidecar and product remain UNTESTED.
) else (
 echo STAGING BLOCKED: No successful review is accepted. Inspect the error above.
 echo Existing completed review folders are not deliberately overwritten or deleted.
)
echo Share the console result and receipt metadata only, NOT font binaries.
pause
exit /b %RC%
