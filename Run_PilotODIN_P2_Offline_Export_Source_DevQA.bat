@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 - Consolidated Offline PDF Export Source QA
echo This is ONE future integrated API/source acceptance, not another font audit.
echo It executes 19 release/packager and 9 in-process authenticated HTTP
echo export contracts, with a brand NEW temporary disposable SQLite home.
echo Already accepted frozen sidecar, font, CMap and visual PDF milestones
echo are NOT repeated. No real user projects, fonts, PDFs or model assets.
echo No pip/network, PyInstaller, installer, Qwen or package modification.
echo Source-level only: release approval remains NOT_GRANTED.
echo Prefer normal NON-ADMIN Windows. No elevation needed.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
  echo BLOCKED: Existing live interpreter is missing. No modifications made.
  pause
  exit /b 2
)
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_export_source_route_devqa.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo SOURCE integration QA passed. It does NOT authorize font release,
  echo production Unicode PDFs or native installer distribution.
) else (
  echo BLOCKED: preserve prior accepted checkpoints.
  echo Do not rerun old gates, rebuild or reinstall dependencies.
)
echo Share only the SAFE final JSON and stage, not local test logs.
pause
exit /b %RC%
