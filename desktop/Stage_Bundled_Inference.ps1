# Development-machine staging only. Nothing is downloaded or installed for end users.
# Supply redistributable llama.cpp Windows CPU runtime + pinned Qwen3 GGUF.
# Example (paths point to files already obtained and license-reviewed):
# $env:PILOTODIN_LLAMA_SERVER_EXE='C:\vendor\llama-server.exe'
# $env:PILOTODIN_LLAMA_DLL_DIR='C:\vendor'
# $env:PILOTODIN_GGUF_FILE='C:\vendor\qwen3-1.7b-q4_k_m.gguf'
# $env:PILOTODIN_EXPECTED_SERVER_SHA256='<independently verified digest>'
# $env:PILOTODIN_EXPECTED_MODEL_SHA256='<independently verified digest>'
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$srcModel=$env:PILOTODIN_GGUF_FILE
$srcServer=$env:PILOTODIN_LLAMA_SERVER_EXE
$srcDlls=$env:PILOTODIN_LLAMA_DLL_DIR
$expectedModel=$env:PILOTODIN_EXPECTED_MODEL_SHA256
$expectedServer=$env:PILOTODIN_EXPECTED_SERVER_SHA256
foreach ($pair in @(@('PILOTODIN_GGUF_FILE',$srcModel),@('PILOTODIN_LLAMA_SERVER_EXE',$srcServer),
                  @('PILOTODIN_LLAMA_DLL_DIR',$srcDlls),@('PILOTODIN_EXPECTED_MODEL_SHA256',$expectedModel),
                  @('PILOTODIN_EXPECTED_SERVER_SHA256',$expectedServer))) {
    if ([string]::IsNullOrWhiteSpace($pair[1])) {throw "Required build input missing: $($pair[0])"}
}
if (-not (Test-Path -LiteralPath $srcModel -PathType Leaf)) {throw 'Model file does not exist'}
if (-not (Test-Path -LiteralPath $srcServer -PathType Leaf)) {throw 'llama-server.exe not found'}
if (-not (Test-Path -LiteralPath $srcDlls -PathType Container)) {throw 'DLL directory not found'}
if ($expectedModel -notmatch '^[a-fA-F0-9]{64}$' -or $expectedServer -notmatch '^[a-fA-F0-9]{64}$') {
    throw 'Expected model and inference executable checksums must be 64-character SHA-256 values'
}
$modelHash=(Get-FileHash -LiteralPath $srcModel -Algorithm SHA256).Hash.ToLowerInvariant()
$serverHash=(Get-FileHash -LiteralPath $srcServer -Algorithm SHA256).Hash.ToLowerInvariant()
if ($modelHash -ne $expectedModel.ToLowerInvariant()) {throw 'Model failed independent SHA-256 verification'}
if ($serverHash -ne $expectedServer.ToLowerInvariant()) {throw 'Runtime failed independent SHA-256 verification'}
$modelDst=Join-Path $root 'frontend\src-tauri\resources\models'
$dllDst=Join-Path $root 'frontend\src-tauri\resources\llama-runtime'
$binDst=Join-Path $root 'frontend\src-tauri\binaries'
New-Item -ItemType Directory -Force -Path $modelDst,$dllDst,$binDst | Out-Null
$stagedModel=Join-Path $modelDst 'qwen3-1.7b-q4_k_m.gguf'
$stagedServer=Join-Path $binDst 'pilotodin-inference-x86_64-pc-windows-msvc.exe'
Copy-Item -LiteralPath $srcModel -Destination $stagedModel -Force
Copy-Item -LiteralPath $srcServer -Destination $stagedServer -Force
$items=@{}
# No executable DLL plugins or extra models are accepted from project folders.
Get-ChildItem -LiteralPath $srcDlls -Filter '*.dll' -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $dllDst $_.Name) -Force
    $items[$_.Name]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest=@{
    schema_version=1
    model_file='qwen3-1.7b-q4_k_m.gguf'
    model_sha256=$modelHash
    server_sha256=$serverHash
    runtime_dll_sha256=$items
    model_alias='pilotodin-qwen3-1.7b'
    # This manifest records exact bytes; license clearance must be reviewed separately.
} | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText((Join-Path $modelDst 'model-manifest.json'), $manifest, (New-Object System.Text.UTF8Encoding($false)))
Write-Host 'Model and runtime staged with verified input hashes. License clearance and Windows execution still required.'
