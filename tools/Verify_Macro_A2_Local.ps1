# Verify Macro A2 on Windows without GitHub Actions or a native installer.
# This script is intentionally opt-in. It never touches production PilotODIN data.
param([switch]$BackendOnly,[switch]$FrontendOnly)

$ErrorActionPreference='Stop'
if ($BackendOnly -and $FrontendOnly) { throw 'Choose only one test mode.' }
$root=Split-Path -Parent $PSScriptRoot
$originalHome=$env:PILOTODIN_HOME
$originalLocation=Get-Location
$isSuccessful=$false
$isolatedData=Join-Path ([System.IO.Path]::GetTempPath()) ("pilotodin-a2-validation-"+[guid]::NewGuid().ToString('N'))
$start=Get-Date

function Invoke-Checked([string]$name,[scriptblock]$command){
  Write-Host ""
  Write-Host ("== "+$name+" ==") -ForegroundColor Cyan
  & $command
  if ($LASTEXITCODE -ne 0) {throw "$name failed with exit code $LASTEXITCODE. Stop here; do not treat A2 as accepted."}
}

try {
  $env:PILOTODIN_HOME=$isolatedData
  New-Item -Path $isolatedData -ItemType Directory -Force | Out-Null
  Write-Host 'PilotODIN Macro A2 local regression' -ForegroundColor Cyan
  Write-Host ("Repository: "+$root)
  Write-Host ("Isolated test data: "+$isolatedData)
  Write-Host 'No network calls or GitHub Actions are made by this validation script.'
  if (-not $BackendOnly) {
    Push-Location (Join-Path $root 'frontend')
    try {
      if (-not (Get-Command npm -ErrorAction SilentlyContinue)){throw 'Node.js/npm is missing. Install Node.js or launch from your existing PilotODIN dev terminal.'}
      if (-not (Test-Path node_modules)){throw 'Frontend node_modules missing. Run npm install manually before this test; this script will not install anything automatically.'}
      Invoke-Checked 'Frontend behavioural tests' {npm run test:workspace}
      Invoke-Checked 'Frontend TypeScript and Vite build' {npm run build}
    } finally {Pop-Location}
  }
  if (-not $FrontendOnly) {
    Push-Location $root
    try {
      if (-not (Get-Command python -ErrorAction SilentlyContinue)){throw 'Python is missing from PATH. Use your existing PilotODIN Python environment.'}
      $cases=@(
        'tests/test_non_ai_correctness_gates.py',
        'tests/test_explore_chart_quality.py',
        'tests/test_scatter_interactions.py',
        'tests/test_explore_linked_filters.py',
        'tests/test_explore_record_inspector.py',
        'tests/test_explore_line_box_inspection.py',
        'tests/test_column_intelligence.py',
        'tests/test_saved_explore_analyses.py',
        'tests/test_explore_to_report_evidence.py',
        'tests/test_correlation_matrix.py',
        'tests/test_chart_counts_semantics.py',
        'tests/test_quality_increment1.py',
        'tests/test_quality_deep_investigations.py',
        'tests/test_report_exhibit_render.py',
        'tests/test_build_e_persistent_reports.py'
      )
      Invoke-Checked 'Backend syntax compilation' {python -m compileall -q backend}
      Invoke-Checked 'Backend analytics/quality/reporting regressions' {python -m pytest -q @cases}
    } finally {Pop-Location}
  }
  $isSuccessful=$true
  Write-Host ""
  Write-Host ("A2 LOCAL VALIDATION PASSED in "+[math]::Round(((Get-Date)-$start).TotalMinutes,1)+" minutes") -ForegroundColor Green
} catch {
  Write-Host ""
  Write-Host ("A2 LOCAL VALIDATION FAILED: "+$_) -ForegroundColor Red
  Write-Host 'Do not merge, release, or build the final installer until failures are reviewed.' -ForegroundColor Yellow
} finally {
  $env:PILOTODIN_HOME=$originalHome
  Set-Location $originalLocation
  Write-Host ("Temporary test data retained for investigation at "+$isolatedData)
}
if (-not $isSuccessful) {exit 1}
exit 0
