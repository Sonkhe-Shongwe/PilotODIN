@echo off
setlocal
cd /d "%~dp0"
title PilotODIN Live Development Launcher
echo.
echo  PilotODIN Live Development
echo  ==========================
echo  This starts a safe, isolated development preview, not an installer.
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0tools\live_dev.py"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python 3.11+ is required. Install it once, then try again.
    pause
    exit /b 1
  )
  python "%~dp0tools\live_dev.py"
)
if errorlevel 1 (
  echo.
  echo Startup was not successful. Review the message above.
  pause
  exit /b 1
)
exit /b 0
