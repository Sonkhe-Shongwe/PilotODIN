@echo off
setlocal
cd /d "%~dp0"
title PilotODIN Launcher

echo =====================================================
echo   PilotODIN  -  one-click local development launcher

echo =====================================================
if not exist "backend\main.py" (
  echo ERROR: Open this launcher from inside the PilotODIN project folder.
  pause
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher 'py' is missing. Install Python 3.11 or newer.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo First launch: creating the permanent Python environment...
  py -m venv .venv || goto :failed
)
".venv\Scripts\python.exe" -c "import uvicorn, fastapi, sklearn, pandas, openpyxl" >nul 2>&1
if errorlevel 1 (
  echo Installing backend dependencies one time or after a requirements update...
  ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt || goto :failed
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo Node.js and npm are required. Install Node.js 20+ once.
  pause
  exit /b 1
)
if not exist "frontend\node_modules\vite\bin\vite.js" (
  echo First launch: installing React frontend dependencies...
  pushd frontend
  call npm.cmd install
  if errorlevel 1 (
    popd
    goto :failed
  )
  popd
)
echo Checking that no other PilotODIN copy is using the required ports...
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul
if not errorlevel 1 (
  echo ERROR: Port 8000 is already in use by another process.
  echo Close the old PilotODIN backend window before launching Studio v0.8.
  pause
  exit /b 1
)
netstat -ano | findstr /r /c:":5173 .*LISTENING" >nul
if not errorlevel 1 (
  echo ERROR: Port 5173 is already in use by another process.
  echo Close the old PilotODIN frontend window before launching Studio v0.8.
  pause
  exit /b 1
)
echo Starting backend and frontend in separate windows...
start "PilotODIN Backend" cmd /k ""%CD%\.venv\Scripts\python.exe" -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
start "PilotODIN Frontend" cmd /k "cd /d ""%CD%\frontend"" && npm.cmd run dev"
echo Waiting briefly, then opening PilotODIN in your browser...
timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"
echo To stop PilotODIN, close the two runtime windows.
exit /b 0
:failed
echo Setup did not complete. Read the error above and try again.
pause
exit /b 1
