# A3 local acceptance preflight: isolated data, pinned live Python environment,
# serial frontend and backend checks; no GitHub Actions, installer or model download.
param([switch]$FrontendOnly,[switch]$BackendOnly)

$ErrorActionPreference='Stop'
if($FrontendOnly -and $BackendOnly){throw 'Select one test mode only.'}
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$oldHome=$env:PILOTODIN_HOME
$success=$false
$testHome=Join-Path ([System.IO.Path]::GetTempPath()) ("pilotodin-a3-validation-"+[guid]::NewGuid().ToString('N'))
$start=Get-Date

function Checked([string]$label,[scriptblock]$action){
  Write-Host ("== "+$label+" ==") -ForegroundColor Cyan
  & $action
  if($LASTEXITCODE -ne 0){throw "$label failed with exit code $LASTEXITCODE"}
}

try {
  $env:PILOTODIN_HOME=$testHome
  New-Item -ItemType Directory -Force -Path $testHome|Out-Null
  if(-not $BackendOnly){
    Push-Location (Join-Path $root 'frontend')
    try{
      if(-not (Get-Command npm -ErrorAction SilentlyContinue)){throw 'npm not installed'}
      if(-not (Test-Path 'node_modules')){throw 'Install frontend dependencies in your dev environment first'}
      Checked 'A3 frontend behavioural tests' {npm run test:workspace}
      Checked 'A3 TypeScript and Vite compilation' {npm run build}
    }finally{Pop-Location}
  }
  if(-not $FrontendOnly){
    Push-Location $root
    try {
      $python=Join-Path $root '.venv-live\Scripts\python.exe'
      if(-not (Test-Path $python)){throw 'Missing .venv-live; start the normal live-development launcher once'}
      & $python -m pytest --version
      if($LASTEXITCODE -ne 0){throw 'Install test dependencies in .venv-live using: & ".\.venv-live\Scripts\python.exe" -m pip install -r backend\requirements-test.txt'}
      Checked 'A3 backend syntax checks' {& $python -m compileall -q backend}
      $cases=@(
        'tests/test_ml_a3_preparation_and_split_safety.py',
        'tests/test_ml_a3_baseline_and_prediction_warnings.py',
        'tests/test_ml_a3_memory_and_explainability.py',
        'tests/test_model_library_expansion.py',
        'tests/test_non_ai_correctness_gates.py',
        'tests/test_build_d_unified_journey.py'
      )
      Checked 'A3 ML and existing workflow regression' {& $python -m pytest -q @cases}
    }finally{Pop-Location}
  }
  $success=$true
  Write-Host ("A3 LOCAL CHECKS PASSED in "+[math]::Round(((Get-Date)-$start).TotalSeconds,1)+" seconds") -ForegroundColor Green
}catch{
  Write-Host ("A3 LOCAL CHECKS FAILED: "+$_) -ForegroundColor Red
}finally{
  $env:PILOTODIN_HOME=$oldHome
  Write-Host ("Isolated test data retained at "+$testHome)
}
if(-not $success){exit 1}
exit 0
