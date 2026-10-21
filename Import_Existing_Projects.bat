@echo off
setlocal
cd /d "%~dp0"
title PilotODIN Studio - Import Previous Projects
echo =====================================================
echo   Import projects from your PREVIOUS PilotODIN folder
 echo   Close both PilotODIN applications first.
echo   Your OLD data will NOT be changed.
echo =====================================================
echo.
set /p "OLD=Paste the FULL PATH to your old inner PilotODIN folder: "
if "%OLD%"=="" (
 echo No folder selected.
 pause
 exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
 echo Please install Python or use python Migrate_From_Old_PilotODIN.py "OLD_FOLDER"
 pause
 exit /b 1
)
py Migrate_From_Old_PilotODIN.py "%OLD%"
if errorlevel 1 (
 echo Migration was NOT completed. Check the error above before trying again.
 pause
 exit /b 1
)
echo.
echo Ready. Now open Start_PilotODIN.bat
pause
