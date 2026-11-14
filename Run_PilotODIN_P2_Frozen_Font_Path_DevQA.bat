@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Future Frozen Font Resource Path DevQA
echo PilotODIN P2: inspect six already staged build-review font/licence files.
echo Verify future frozen-sidecar package-relative resource lookup.
echo No download, font installation, backend server, installer or PyInstaller build.
echo Eight isolated tests create disposable tiny synthetic files only.
echo NOT full frozen engine, installed native app or Unicode PDF acceptance.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python missing. No installation attempted.
 pause
 exit /b 2
)
echo Testing eight synthetic font resource layout and integrity contracts...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_font_resources.py" -v
if errorlevel 1 (
 echo P2 FONT RESOURCE PATH CONTRACT: FAIL OR BLOCKED.
 pause
 exit /b 2
)
echo.
echo Checking one completed build-review receipt and its six pinned assets...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_font_resource_path_devqa.py"
if errorlevel 1 (
 echo P2 FONT RESOURCE PATH CONTRACT: BLOCKED. No production change.
 pause
 exit /b 2
)
echo.
echo FUTURE RESOURCE PATH CONTRACT PASS. Frozen Python sidecar still NOT BUILT.
echo Share console result only; do not share font files.
pause
exit /b 0
