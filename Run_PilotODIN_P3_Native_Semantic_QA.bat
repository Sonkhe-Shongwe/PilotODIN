@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P3 Semantic Business Context Native Windows QA
echo P3 native WebView2 semantic-description acceptance with two isolated synthetic projects.
echo This does not install software, use installed project data, launch AI, or make a release.
echo Only two approved semantic-description saves to synthetic project A are allowed.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Run_P3_Native_Semantic_QA_Local.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo P3 owner observations recorded for REVIEW, not automatic release acceptance.) else (echo P3 NATIVE QA BLOCKED OR FAILED. Review the displayed status-only archive.)
pause
exit /b %RESULT%
