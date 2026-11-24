$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location (Join-Path $root 'frontend')
if ($env:VITE_PILOTODIN_AUTH_DEV -cne '1' -or $env:PILOTODIN_DEV_CAPABILITY -cnotmatch '^[0-9a-f]{64}$') { throw 'Start Live Dev using the paired launcher.' }
Write-Host '[PilotODIN DEV / Frontend] React/Vite live reload on http://127.0.0.1:5173'
Write-Host '[PilotODIN DEV / Frontend] Save a .tsx or .css file to see the change.'
& npm.cmd run dev
Write-Host '[PilotODIN DEV / Frontend] Process exited. Inspect the last error above.' -ForegroundColor Yellow
