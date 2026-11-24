$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$env:PILOTODIN_HOME = Join-Path $root '.pilotodin-dev-data'
$env:PILOTODIN_DESKTOP_SESSION = ''
$env:PILOTODIN_SERVER_MODE = 'dev'
if ($env:PILOTODIN_DEV_CAPABILITY -cnotmatch '^[0-9a-f]{64}$' -or $env:PILOTODIN_DEV_ORIGIN -cne 'http://127.0.0.1:5173' -or $env:PILOTODIN_DEV_PORT -cne '8000') { throw 'Start Live Dev using the paired launcher.' }
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = Join-Path $root '.venv-live\Scripts\python.exe'
Write-Host '[PilotODIN DEV / Backend] Isolated data: ' $env:PILOTODIN_HOME
Write-Host '[PilotODIN DEV / Backend] File edits trigger an automatic restart.'
& $python -m uvicorn backend.server_entry:owned_app --factory --reload --reload-dir backend --host 127.0.0.1 --port 8000 --no-proxy-headers --ws none --no-access-log
Write-Host '[PilotODIN DEV / Backend] Process exited. Inspect the last error above.' -ForegroundColor Yellow
