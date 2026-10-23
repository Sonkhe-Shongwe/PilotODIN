$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$env:PILOTODIN_HOME = Join-Path $root '.pilotodin-dev-data'
$env:PILOTODIN_DESKTOP_SESSION = ''
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = Join-Path $root '.venv-live\Scripts\python.exe'
Write-Host '[PilotODIN DEV / Backend] Isolated data: ' $env:PILOTODIN_HOME
Write-Host '[PilotODIN DEV / Backend] File edits trigger an automatic restart.'
& $python -m uvicorn backend.main:app --reload --reload-dir backend --host 127.0.0.1 --port 8000
Write-Host '[PilotODIN DEV / Backend] Process exited. Inspect the last error above.' -ForegroundColor Yellow
