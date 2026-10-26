@echo off
setlocal
cd /d "%~dp0"
title PilotODIN P2 - Actual Synthetic Unicode Report Acceptance
echo ONE new meaningful milestone: actual reports.render_pdf with Unicode Paragraph,
echo evidence table, footer and saved chart vector labels, using synthetic evidence.
echo All original P2 U2d/U2f/U2g gates remain ACCEPTED and are NOT repeated.
echo This is DEVQA only. NO release-approved fonts, no real user datasets,
echo no pip, network, PyInstaller, Qwen, Tauri or installer.
echo Previously reviewed font files are READ ONLY. A local synthetic PDF with
echo embedded glyph subsets will be written in a NEW ignored build folder.
echo It is NOT APPROVED FOR DISTRIBUTION. Do not upload or share the PDF itself.
echo Share only the final JSON and a screenshot of the synthetic PDF as needed.
echo Prefer normal NON-ADMIN Windows. Do not use existing user project home.
echo.
if not exist "%~dp0.venv-live\Scripts\python.exe" (
  echo BLOCKED: Existing Python environment missing.
  pause
  exit /b 2
)
echo Running ONLY the newly affected ten synthetic renderer seam tests...
"%~dp0.venv-live\Scripts\python.exe" -B -m unittest discover -s "%~dp0tests" -p "test_p2_unicode_renderer_seam.py" -v
if errorlevel 1 (
 echo BLOCKED: New source tests failed. No report or proof files created.
 pause
 exit /b 2
)
echo.
echo This will run only the real REPORT renderer with disposable project home.
echo It saves one synthetic PDF inside the ignored build/p2-unicode-real-report-devqa folder.
choice /C YN /N /M "Approve ONE synthetic developer report PDF generation? [Y/N] "
if errorlevel 2 (
 echo Declined; no new report generated.
 exit /b 2
)
if not errorlevel 1 (
 echo No affirmative consent; exiting.
 exit /b 2
)
echo.
"%~dp0.venv-live\Scripts\python.exe" -B "%~dp0tools\p2_actual_unicode_report_devqa.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
 echo Scoped actual report SOURCE experiment succeeded.
 echo Inspect ONLY the generated synthetic PDF locally for glyphs, clipping,
 echo tables, numeric labels and footer. Its licence status is DEVQA ONLY.
 echo Production Unicode and installed PilotODIN remain UNACCEPTED.
) else (
 echo BLOCKED: retain previous accepted results, do not rebuild or reinstall.
 echo Share only the safe JSON state/failure class, not source fonts or PDFs.
)
pause
exit /b %RC%
