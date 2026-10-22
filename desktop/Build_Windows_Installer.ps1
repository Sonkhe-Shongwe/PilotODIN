# Run on Windows PowerShell from any working directory.
# Requires Python 3.11+, Node.js LTS, Rust stable MSVC, Visual Studio C++ build tools.
# Bundles the entire Python analytics runtime as one signed-by-nobody prototype
# binary, then builds a Tauri/NSIS installer. This does NOT sign the release.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        Write-Host 'Creating build-only Python virtual environment...'
        py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
    }
    $python = Join-Path $root '.venv\Scripts\python.exe'
    Write-Host 'Validating mandatory self-contained offline AI assets...'
    & $python 'desktop\verify_inference_assets.py'
    if ($LASTEXITCODE -ne 0) { throw 'Offline AI assets missing or invalid; refusing to create a misleading installer' }
    # The same frozen-engine builder and real startup check is used by Windows CI.
    # Failed loopback/readiness/auth verification MUST block any installer.
    & (Join-Path $PSScriptRoot 'Build_Python_Sidecar.ps1')

    Push-Location (Join-Path $root 'frontend')
    try {
        Write-Host 'Installing frontend build dependencies...'
        if (Test-Path 'package-lock.json') { npm ci }
        else { npm install }
        if ($LASTEXITCODE -ne 0) { throw 'npm dependency installation failed' }
        Write-Host 'Compiling the desktop application and installer...'
        npm run desktop:build
        if ($LASTEXITCODE -ne 0) { throw 'Tauri Windows build failed' }
    }
    finally { Pop-Location }
    Write-Host 'Build finished. Installer should be under frontend\src-tauri\target\release\bundle\nsis\'
    Write-Host 'This is an unsigned development preview. Do not publicly distribute without testing/signing.'
}
finally { Pop-Location }
