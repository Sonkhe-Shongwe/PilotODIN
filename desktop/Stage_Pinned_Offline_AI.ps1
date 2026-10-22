# Compile-time acquisition of publicly redistributed Qwen3 GGUF + llama.cpp CPU runtime.
# Only this script uses the network; the installed desktop application never does.
# Exact revisions and independent upstream SHA-256 digests are pinned below.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProgressPreference = 'SilentlyContinue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cache = Join-Path $root 'build\verified-upstream-ai'
$runtimeZip = Join-Path $cache 'llama-b10344-bin-win-cpu-x64.zip'
$modelFile = Join-Path $cache 'Qwen3-1.7B-Q4_K_M.gguf'
$runtimeSha = 'c0cec8825843957cae6620f927eb6eb9f7f4680da3206910932ea9075f91b405'
$modelSha = 'd2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5'
$llamaCommit = '7a20b417f4526cae073bd997af5020cea3e7ccbe'
$modelRevision = 'daeb8e2d528a760970442092f6bf1e55c3b659eb'

function Get-VerifiedFile([string]$uri,[string]$path,[string]$sha) {
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Force $parent | Out-Null
    if ((Test-Path -LiteralPath $path -PathType Leaf) -and
        ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $sha)) {
        Write-Host "Using pinned cached source: $(Split-Path -Leaf $path)"
        return
    }
    if (Test-Path -LiteralPath $path) {Remove-Item -LiteralPath $path -Force}
    Write-Host "Fetching verified upstream asset: $(Split-Path -Leaf $path)"
    Invoke-WebRequest -Uri $uri -OutFile $path -MaximumRedirection 10
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha) {
        Remove-Item -LiteralPath $path -Force
        throw "Source checksum mismatch: $(Split-Path -Leaf $path)"
    }
}

New-Item -ItemType Directory -Force $cache | Out-Null
Get-VerifiedFile `
  "https://github.com/ggml-org/llama.cpp/releases/download/b10344/llama-b10344-bin-win-cpu-x64.zip" `
  $runtimeZip $runtimeSha
Get-VerifiedFile `
  "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/$modelRevision/Qwen3-1.7B-Q4_K_M.gguf?download=true" `
  $modelFile $modelSha
if ((Get-Item -LiteralPath $modelFile).Length -lt 1GB) {throw 'Model is unexpectedly small'}
$modelStream = [System.IO.File]::OpenRead($modelFile)
try {
    $signature = New-Object byte[] 4
    if ($modelStream.Read($signature, 0, 4) -ne 4 -or
        [System.Text.Encoding]::ASCII.GetString($signature) -ne 'GGUF') {
        throw 'GGUF signature missing'
    }
}
finally {$modelStream.Dispose()}

$expanded = Join-Path $cache 'llama-b10344-extracted'
if (Test-Path $expanded) {Remove-Item -Recurse -Force $expanded}
Expand-Archive -LiteralPath $runtimeZip -DestinationPath $expanded -Force
$servers = @(Get-ChildItem -LiteralPath $expanded -Recurse -File -Filter 'llama-server.exe')
if ($servers.Count -ne 1) {throw "Expected exactly one llama-server.exe, found $($servers.Count)"}
$server = $servers[0]
$dlls = @(Get-ChildItem -LiteralPath $server.DirectoryName -File -Filter '*.dll')
if ($dlls.Count -lt 1) {throw 'Pinned llama.cpp archive contains no colocated runtime DLLs'}

# Notices ship inside the finished installer. Do not treat MIT/Apache identifiers
# alone as a complete third-party redistribution review.
$licenses = Join-Path $root 'frontend\src-tauri\resources\licenses'
New-Item -ItemType Directory -Force $licenses | Out-Null
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/ggml-org/llama.cpp/$llamaCommit/LICENSE" `
   -OutFile (Join-Path $licenses 'llama.cpp-MIT-LICENSE.txt')
Invoke-WebRequest -Uri 'https://www.apache.org/licenses/LICENSE-2.0.txt' `
   -OutFile (Join-Path $licenses 'Qwen3-Apache-2.0-LICENSE.txt')
@"
PilotODIN bundled offline AI source notices
Qwen3-1.7B Q4_K_M model: ggml-org/Qwen3-1.7B-GGUF
Pinned Hugging Face revision: $modelRevision
Source model SHA256: $modelSha
Model is based on Qwen/Qwen3-1.7B (Apache-2.0).
CPU runtime: ggml-org/llama.cpp b10344 ($llamaCommit), MIT.
Pinned release ZIP SHA256: $runtimeSha
Additional bundled runtime dependencies must be reviewed before public distribution.
"@ | Set-Content -LiteralPath (Join-Path $licenses 'THIRD-PARTY-SOURCES.txt') -Encoding utf8

$env:PILOTODIN_GGUF_FILE = $modelFile
$env:PILOTODIN_LLAMA_SERVER_EXE = $server.FullName
$env:PILOTODIN_LLAMA_DLL_DIR = $server.DirectoryName
$env:PILOTODIN_EXPECTED_MODEL_SHA256 = $modelSha
$env:PILOTODIN_EXPECTED_SERVER_SHA256 = (Get-FileHash -LiteralPath $server.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
& (Join-Path $PSScriptRoot 'Stage_Bundled_Inference.ps1')
& python (Join-Path $PSScriptRoot 'verify_inference_assets.py')
if ($LASTEXITCODE -ne 0) {throw 'Pinned offline AI package failed final integrity verification'}
Write-Host 'Pinned Windows CPU runtime and Qwen3 model staged. Next: runtime inference and installer smoke checks.'
