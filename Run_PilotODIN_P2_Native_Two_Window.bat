@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 Two-Window External Project Guard (Synthetic DevQA)
echo Isolated A/B synthetic projects. Real Tauri window A has Deliver; window B only changes the QA selection key.
echo No installs, source edits, real datasets, model training, uploads, exports or report saves.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Run_P2_Native_Two_Window_Local.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo Two-window native observations recorded; QA review remains required.) else (echo NOT ACCEPTED. Report the status-only QA ZIP.)
pause
exit /b %RESULT%
