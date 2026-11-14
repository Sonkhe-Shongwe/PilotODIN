@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Native Chain Final File Verification
echo PilotODIN P2: READ-ONLY recovery of previous native Save As files.
echo No Tauri compilation, no API, no new saves, no installer.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Verify_P2_Native_Chain_Existing_Files.ps1" -SessionId 292199a81c44
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 previous native full-chain file verification: PASS) else (echo Native full-chain file evidence incomplete. Share printed ZIP and DO NOT rename or move files to force a PASS.)
pause
exit /b %RESULT%
