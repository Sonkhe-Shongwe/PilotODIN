@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 - Actual Isolated Scientific Sidecar and Font Runtime DevQA
echo P2-U2d: Build and test the REAL FastAPI/SQLite scientific engine, DevQA ONLY.
echo Existing full scientific builder, six-source font review and earlier PASS gates
echo are reused. Previously accepted U2c 7/7 and standalone font 9-case suites
echo are NOT rerun. Eight new synthetic safety contracts run first.
echo.
echo Actual operation MAY require significant disk, RAM and Windows build time.
echo Needs at least 4 GiB currently free for the new isolated engine build.
echo Creates NEW ignored build/p2-sidecar-env/real-sidecar-proofs/run-*.
echo Embeds six previously reviewed fonts/OFL notices with a TEST-ONLY fail-closed
echo runtime hook. Runs temporary local API/401/403/SQLite startup and cleanup.
echo NO pip, download, package install, production installer, Tauri binary overwrite,
echo existing user projects, Qwen/model training or real reporting changes.
echo This DOES NOT approve font redistribution or production Unicode PDFs.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live is missing. No changes attempted.
 pause
 exit /b 2
)
echo Running eight NEW focused real-sidecar DevQA safety tests...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_real_sidecar_font_devqa.py" -v
if errorlevel 1 (
 echo BLOCKED: New safety tests failed. No frozen build permitted.
 pause
 exit /b 2
)
echo.
echo Checking the already prepared FULL scientific builder without installing...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_prepare_full_sidecar_builder.py"
if errorlevel 1 (
 echo BLOCKED: Existing private scientific builder cannot be validated.
 echo No pip, reinstall, venv modification or actual freeze attempted.
 pause
 exit /b 2
)
echo.
echo The upcoming build creates and executes an isolated dev-only copy
echo of backend/desktop_runner.py. It does not stage any Tauri executable.
choice /C YN /N /M "Approve this one REAL isolated scientific sidecar DEVQA build? [Y/N] "
if errorlevel 2 (
 echo Declined. No actual sidecar build authorised.
 exit /b 2
)
if not errorlevel 1 (
 echo BLOCKED: No affirmative approval.
 pause
 exit /b 2
)
echo.
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_real_sidecar_font_devqa.py" --build
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo Scoped frozen REAL scientific sidecar verified with fonts and private smoke.
 echo Production Unicode PDF and full installer remain NOT ACCEPTED.
) else (
 echo Actual sidecar gate BLOCKED or FAILED. Do NOT distribute build output.
 echo Share only safe final JSON and stage. Preserve private build log locally.
)
echo Never upload font assets, executables, wheel packages or private build logs.
pause
exit /b %RC%
