# Build the Windows analytics executable and prove it boots before installer packaging.
# This script does not stage Qwen3 assets and does not build an installer.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Write-Host 'Creating isolated Python build environment...'
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not initialise Python build environment' }
    }
    & $python -m pip install -r 'backend\requirements.txt' 'pyinstaller>=6,<7'
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Python engine build requirements' }
    Write-Host 'Freezing the REAL Python/FastAPI analytical engine...'
    & $python -m PyInstaller --noconfirm --clean --onefile --name pilotodin-engine `
      --paths $root --collect-all sklearn --collect-all scipy `
      --collect-submodules sklearn --hidden-import uvicorn.logging `
      --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto `
      --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on `
      --distpath (Join-Path $root 'build\py-dist') `
      --workpath (Join-Path $root 'build\py-work') `
      --specpath (Join-Path $root 'build') `
      'backend\desktop_runner.py'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller could not package the scientific Python runtime' }
    $engine = Join-Path $root 'build\py-dist\pilotodin-engine.exe'
    if (-not (Test-Path -LiteralPath $engine -PathType Leaf)) { throw 'Frozen analytical engine missing' }
    Write-Host 'Starting the frozen EXE with temporary local data and a private session token...'
    & $python 'desktop\verify_packaged_engine.py' --exe $engine `
      --startup-seconds 100 --result-json 'build\engine-smoke-result.json'
    if ($LASTEXITCODE -ne 0) { throw 'Frozen analytical engine failed runtime smoke test' }
    $target = Join-Path $root 'frontend\src-tauri\binaries\pilotodin-engine-x86_64-pc-windows-msvc.exe'
    New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $engine -Destination $target -Force
    Write-Host 'Packaged Python engine verified and staged for native bundling. Qwen3 runtime remains a separate gate.'
}
finally { Pop-Location }
