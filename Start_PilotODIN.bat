@echo off
setlocal
cd /d "%~dp0"
title PilotODIN Legacy Launcher

echo =====================================================
echo   Legacy checkout-data launcher retired
echo =====================================================
echo The original data directory is preserved and not migrated.
echo For the isolated development preview, explicitly open
echo Start_PilotODIN_Live_Dev.bat.
echo Existing legacy projects require a separately reviewed migration.
echo No backend, installer, dependency installation or migration started.
pause
exit /b 2
