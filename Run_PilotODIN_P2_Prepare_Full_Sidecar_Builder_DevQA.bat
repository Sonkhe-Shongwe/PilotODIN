@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Isolated Full Sidecar Builder - DevQA Only
echo PilotODIN P2-U2c: prepare a SEPARATE scientific backend build environment.
echo The previously accepted six-case route and frozen font resource PASS are NOT rerun.
echo Runs seven NEW synthetic safety contracts first, then checks for an existing builder.
echo Does not touch .venv-live, .venv, Tauri binaries, accepted user projects or models.
echo This DOES NOT build PilotODIN's actual sidecar, PDF, installer or Qwen.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python missing; no setup attempted.
 pause
 exit /b 2
)
echo Running seven new isolated build-environment safety contracts...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_prepare_full_sidecar_builder.py" -v
if errorlevel 1 (
 echo BLOCKED: Synthetic safety contracts failed. No install permitted.
 pause
 exit /b 2
)
echo.
if exist "%~dp0build\p2-sidecar-env\venv" (
 echo A separate build venv already exists. Read-only validation only.
 "%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_prepare_full_sidecar_builder.py"
 set "RC=%ERRORLEVEL%"
 echo No overwrite, repair or package install was attempted.
 pause
 exit /b %RC%
)
echo The verified build route REQUIRES a separate full scientific build venv.
echo It will be created ONLY under ignored build\p2-sidecar-env\venv.
echo It will use Python 3.12.3 from existing .venv-live as the base interpreter.
echo.
echo With your approval, it will download/install packages from official PyPI:
echo - Existing live backend direct package versions, scipy, uvicorn[standard]
echo - Pinned PyInstaller 6.22.3 and hooks 2026.9
echo - Transitive wheel dependencies resolved by pip, WITHOUT a release hash lock.
echo At least 3 GiB free disk is required. This may require sizable downloads.
echo A failed partial private venv is PRESERVED, not silently deleted or repaired.
echo NO installation into .venv-live, .venv, system Python or the installer.
echo.
choice /C YN /N /M "Approve creating and downloading ONLY this private DevQA builder? [Y/N] "
if errorlevel 2 (
 echo Cancelled. No build environment creation was authorised.
 exit /b 2
)
if not errorlevel 1 (
 echo BLOCKED: Consent was not established.
 pause
 exit /b 2
)
echo.
echo Preparing private development builder; the actual sidecar is NOT being frozen...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_prepare_full_sidecar_builder.py" --prepare
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo Isolated scientific builder prepared FOR DEVELOPMENT REVIEW ONLY.
 echo No actual PilotODIN executable built; no release lockfile approved.
) else (
 echo BLOCKED: Keep the partial private build folder for focused diagnostics.
 echo Do NOT install globally or manually delete an existing build folder.
)
echo Share final safe JSON status, not wheel files, cached packages or binaries.
pause
exit /b %RC%
