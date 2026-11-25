# Read-only Live Dev diagnostics. No service startup or installation.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv-live\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-Host 'The isolated Live Dev environment is unavailable. Start the paired Live Dev launcher first.' -ForegroundColor Yellow
    exit 2
}
& $python -B (Join-Path $PSScriptRoot 'check_local_api.py')
exit $LASTEXITCODE
