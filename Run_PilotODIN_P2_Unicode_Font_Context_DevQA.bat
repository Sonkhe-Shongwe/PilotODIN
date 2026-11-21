@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 U2f - Unicode In-Memory Font Context DevQA
echo P2-U2f: real previously verified development fonts in an isolated process.
echo New scope ONLY: 10 synthetic contracts plus ONE small in-memory ReportLab PDF.
echo Uses original reviewed 6 font/OFL files read-only, ReportLab 4.5.1,
echo document-scoped ToUnicode and vector chart font runs. It writes NO PDF.
echo No network, pip, venv modification, PyInstaller, Tauri, installer, models,
echo actual projects, saved reports or production renderer changes.
echo This is NOT release font permission or product Unicode visual acceptance.
echo Previous 13-case planner, CMap, frozen scientific sidecar and P2 suites
echo are ALREADY ACCEPTED in their separate scope and will NOT be repeated.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
 echo BLOCKED: Existing .venv-live Python missing. No changes attempted.
 pause
 exit /b 2
)
echo Executing 10 NEW pure synthetic font-context safety tests...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_pdf_unicode_context_devqa.py" -v
if errorlevel 1 (
 echo BLOCKED: New context safety contracts failed. No real font probe permitted.
 pause
 exit /b 2
)
echo.
echo Inspecting the previously pinned source review and generating a
echo synthetic ONE-PAGE PDF in memory only. No persistent PDF or font copying.
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_pdf_unicode_context_devqa.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo Scoped context/Paragraph/vector-label extraction validated on Windows.
 echo The production PDF, release licences and installer remain NOT ACCEPTED.
) else (
 echo BLOCKED: Preserve accepted prior milestones. Share only final safe JSON.
 echo No reinstall, font download, old gate rerun or PDF renderer promotion.
)
echo Never share font binaries or local private font review folder.
pause
exit /b %RC%
