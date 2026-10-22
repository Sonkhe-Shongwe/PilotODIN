@echo off
setlocal
cd /d "%~dp0"
title PilotODIN Local Diagnostics
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0diagnostics\Check_Local_API.ps1"
echo.
pause
