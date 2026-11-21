@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P3 W5 Quality Native Windows QA
echo P3 W5: one disposable project, one reviewed native Quality correction.
echo No installer, owner data, AI model, training or prior W1-W4 QA is involved.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Run_P3_Native_Quality_W5_QA_Local.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo W5 synthetic native results saved for independent QA review, not release certification.) else (echo W5 BLOCKED or FAILED. See the diagnostic above. No product data was modified.)
pause
exit /b %RESULT%
