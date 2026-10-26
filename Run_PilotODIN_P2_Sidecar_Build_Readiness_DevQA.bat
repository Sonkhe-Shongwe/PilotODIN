@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Actual Sidecar Build Readiness - READ ONLY
echo PilotODIN P2-U2b: inspect the three EXISTING local Python environments.
echo The prior real standalone frozen resource PASS is accepted, not repeated.
echo Runs ONLY six new synthetic metadata-isolation contracts.
echo Checks Python/package metadata and available build disk WITHOUT changing files.
echo No pip, installs, downloads, model training, Tauri, actual sidecar, or installer.
echo No user projects, database, PDF exports or staged font binaries accessed.
echo A green audit does NOT authorise an actual sidecar freeze or Unicode acceptance.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python missing. No setup attempted.
 pause
 exit /b 2
)
echo Testing six synthetic sidecar-build readiness safety contracts...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_sidecar_build_readiness.py" -v
if errorlevel 1 (
 echo BLOCKED: New readiness contract tests failed. Nothing was installed.
 pause
 exit /b 2
)
echo.
echo Collecting read-only package version metadata from fixed local venv paths...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_sidecar_build_readiness.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo P2 SIDECAR READINESS AUDIT COMPLETED, not a build or release PASS.
) else (
 echo P2 SIDECAR READINESS BLOCKED. Share only safe metadata shown above.
)
echo Do not rerun accepted font or frozen probe gates.
pause
exit /b %RC%
