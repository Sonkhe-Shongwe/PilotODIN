@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Native Export Saved-File Recovery
echo PilotODIN P2: repair-only verification of already-saved synthetic files.
echo No Tauri/Rust build, no new saves, no broad search, no model/installer.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Verify_P2_Native_Existing_Files.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P2 native previously saved file hashes VERIFIED.) else (echo P2 native saved-file verification incomplete or FAIL. Share the diagnostic ZIP.)
pause
exit /b %RESULT%
