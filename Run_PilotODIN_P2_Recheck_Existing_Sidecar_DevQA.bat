@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 - Recheck Existing REAL Scientific Sidecar DevQA
set "RUN_ID=run-b029a70aeb1e41efb575a60afbbd6fb6"
echo P2-U2d targeted follow-up: REUSE the existing frozen scientific engine.
echo The screenshot shows a ValueError after actual frozen smoke was entered.
echo The old final executable hash used a 32 MiB FONT-only helper.
echo This launcher makes NO new executable or sidecar build.
echo.
echo Original ignored run: %RUN_ID%
echo Use normal NON-ADMIN Windows wherever permissions allow.
echo The earlier build, original nine-case test run and prior P2 suites
echo are NOT repeated. This recheck runs seven NEW focused safety cases.
echo Only a new tiny ignored attestation folder may be created after consent.
echo NO pip/downloads, PyInstaller, Tauri/NSIS, Qwen, user datasets or installer.
echo No raw fonts, executables or logs should be shared.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing live development interpreter is missing.
 pause
 exit /b 2
)
echo Running seven NEW reusable-engine safety contracts...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_recheck_real_sidecar_devqa.py" -v
if errorlevel 1 (
 echo BLOCKED: New scoped safety checks failed. No frozen engine launched.
 pause
 exit /b 2
)
echo.
echo Reviewing original frozen executable, six staged bytes and ORIGINAL hook
echo receipt without executing anything or changing prior ignored build...
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_recheck_real_sidecar_devqa.py" --run-id "%RUN_ID%" --inspect
if errorlevel 1 (
 echo BLOCKED: Previous saved DevQA artifact cannot be confirmed.
 echo Do not rebuild, remove prior run, reinstall or open production builder.
 pause
 exit /b 2
)
echo.
echo Approval launches this EXISTING original frozen exe ONCE with new
echo disposable random API token, loopback port and isolated SQLite.
echo This will create only a NEW ignored hook-receipt proof folder.
echo No executable reconstruction, font copying or production changes.
choice /C YN /N /M "Approve a single runtime-only old sidecar recheck? [Y/N] "
if errorlevel 2 (
 echo Declined. Existing exe not executed.
 exit /b 2
)
if not errorlevel 1 (
 echo BLOCKED: No affirmative runtime approval.
 pause
 exit /b 2
)
echo.
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_recheck_real_sidecar_devqa.py" --run-id "%RUN_ID%" --recheck
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo SCOPED previous frozen engine verified. Production Unicode PDF and installer remain NOT ACCEPTED.
) else (
 echo BLOCKED or FAILED. Preserve old build and share only safe final state/stage JSON.
)
echo DevQA-only proof. Never distribute prior exe, fonts or private logs.
pause
exit /b %RC%
