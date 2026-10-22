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
    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Could not update pip' }
    & $python -m pip install -r 'backend\requirements.txt' 'pyinstaller>=6,<7'
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Python build dependencies' }

    Write-Host 'Packaging the scientific Python runtime for Windows...'
    & $python -m PyInstaller --noconfirm --clean --onefile --name pilotodin-engine `
      --paths $root --collect-all sklearn --collect-all scipy `
      --collect-submodules sklearn --hidden-import uvicorn.logging `
      --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto `
      --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on `
      --distpath (Join-Path $root 'build\py-dist') `
      --workpath (Join-Path $root 'build\py-work') `
      --specpath (Join-Path $root 'build') `
      'backend\desktop_runner.py'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
    $binary = Join-Path $root 'build\py-dist\pilotodin-engine.exe'
    if (-not (Test-Path $binary)) { throw "Missing packaged Python engine: $binary" }
    Copy-Item -Force $binary 'frontend\src-tauri\binaries\pilotodin-engine-x86_64-pc-windows-msvc.exe'


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
