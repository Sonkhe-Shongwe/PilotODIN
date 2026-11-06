@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 PDF Visual DevQA (Synthetic Only)
echo PilotODIN P2: render isolated synthetic PDFs for actual visual inspection.
echo Uses no existing projects, app windows, model training, Qwen or installer.
echo Previously accepted 12-case mixed and 5-case display suites are NOT rerun.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCK: Existing .venv-live Python missing. No installation attempted.
 pause
 exit /b 2
)
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_visual_devqa.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
 echo Generated synthetic previews. Upload the VISUAL PREVIEW ZIP for review.
 echo A successful generator does NOT establish visual PDF acceptance.
) else (
 echo P2 PDF visual DevQA FAILED/BLOCKED. Share the STATUS-ONLY ZIP or screenshot.
)
pause
exit /b %EXIT_CODE%
