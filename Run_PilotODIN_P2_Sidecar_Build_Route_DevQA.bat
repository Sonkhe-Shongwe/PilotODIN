@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Sidecar Build Route Decision - READ ONLY
echo PilotODIN P2-U2b: choose a safe build-environment ROUTE, not a build.
echo The prior six-case readiness audit and standalone frozen font PASS stay accepted.
echo Runs only SIX NEW build-route policy tests, not prior tests.
echo Re-reads bounded metadata only from three already existing Python venvs.
echo No downloads, pip, package imports, fonts, projects, app or installer.
echo Never creates/changes .venv, .venv-live, the private tooling venv or binary outputs.
echo Any route is a DESIGN ONLY recommendation, not permission to freeze.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python absent. No setup attempted.
 pause
 exit /b 2
)
echo Running six NEW synthetic build-route decision contracts...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_sidecar_build_route.py" -v
if errorlevel 1 (
 echo BLOCKED: Build-route contracts failed. No environment changes made.
 pause
 exit /b 2
)
echo.
echo Inspecting minimal existing environment metadata for compact build-route decision...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_sidecar_build_route.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo P2 BUILD-ROUTE DESIGN COMPLETED. Actual sidecar and Unicode PDF remain NOT TESTED.
) else (
 echo P2 BUILD-ROUTE BLOCKED. Do not attempt a heavy sidecar freeze.
)
echo Send the compact output only. No binaries, font files or archives needed.
pause
exit /b %RC%
