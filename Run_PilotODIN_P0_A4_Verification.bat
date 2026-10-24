@echo off
setlocal
cd /d "%~dp0"
set "PILOTODIN_PYTHON=%CD%\.venv-live\Scripts\python.exe"
if not exist "%PILOTODIN_PYTHON%" (
  echo ERROR: Isolated development Python not found.
  echo Launch Start_PilotODIN_Live_Dev.bat once to configure the development environment.
  exit /b 1
)
"%PILOTODIN_PYTHON%" tools\Verify_P0_A4_Readiness.py
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Automated P0/A4 readiness checks PASSED. Manual Windows acceptance remains pending.
) else (
  echo Automated P0/A4 readiness checks FAILED. Review the isolated summary and logs.
)
exit /b %RESULT%
