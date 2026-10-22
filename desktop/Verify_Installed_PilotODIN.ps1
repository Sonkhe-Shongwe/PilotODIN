# Verify that the actual NSIS artifact installs with all offline dependencies.
# This intentionally runs on a clean Windows CI runner and never needs Ollama.
param(
    [Parameter(Mandatory=$true)][string]$InstallerPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$destination = Join-Path $env:RUNNER_TEMP 'PilotODIN-CI-NSIS-Install'
if (Test-Path -LiteralPath $destination) {
    throw 'Refusing to install over existing CI target'
}
Write-Host 'Performing isolated Windows NSIS install without Python, Node or Ollama on the target.'
# /D must be the last NSIS argument. GitHub Windows runner is disposable.
$job = Start-Process -FilePath $installer -ArgumentList @('/S',("/D=" + $destination)) -PassThru
if (-not $job.WaitForExit(480000)) {
    try {$job.Kill()} catch {}
    throw 'NSIS installer did not finish within the verification limit'
}
if ($job.ExitCode -ne 0) {throw "NSIS installer failed with exit code $($job.ExitCode)"}
if (-not (Test-Path -LiteralPath $destination -PathType Container)) {
    throw 'NSIS did not create the designated isolated install directory'
}
$files = @(Get-ChildItem -LiteralPath $destination -Recurse -File)
function RequireOne([string]$name) {
    $found = @($files | Where-Object {$_.Name -ieq $name})
    if ($found.Count -ne 1) {
        throw "Installer payload missing or ambiguous: $name ($($found.Count) matching files)"
    }
    return $found[0]
}
# Cargo package names the executable pilotodin-desktop.exe; productName may
# influence the displayed application name but not always the binary name.
$desktop = @($files | Where-Object {$_.Name -in @('pilotodin-desktop.exe','pilotODIN.exe')})
if ($desktop.Count -ne 1) {throw "Application executable is missing or ambiguous ($($desktop.Count) matches)"}
$desktop = $desktop[0]
$engine = RequireOne 'pilotodin-engine.exe'
$inference = RequireOne 'pilotodin-inference.exe'
$model = RequireOne 'qwen3-1.7b-q4_k_m.gguf'
$manifest = RequireOne 'model-manifest.json'
$licenseOne = RequireOne 'llama.cpp-MIT-LICENSE.txt'
$licenseTwo = RequireOne 'Qwen3-Apache-2.0-LICENSE.txt'
if ($model.Length -lt 1GB) {throw 'Installed GGUF model is unexpectedly small'}
foreach ($exe in @($desktop, $engine, $inference)) {
    Write-Host ("Installed binary {0}: {1:N0} bytes" -f $exe.Name, $exe.Length)
    # A Windows PE executable can be small when it delegates to adjacent DLLs.
    # Require a real PE header, then cryptographically validate the inference
    # server instead of inventing a minimum file-size policy for that binary.
    # The pinned llama.cpp CPU launcher is 9,216 bytes; most of its code is
    # shipped as separately manifested ggml DLLs. Its exact SHA-256 is checked
    # against the staged release manifest below.
    $minimum = if ($exe.FullName -eq $inference.FullName) {4KB} else {64KB}
    if ($exe.Length -lt $minimum) {throw "Executable is unexpectedly small: $($exe.Name)"}
    $stream = [System.IO.File]::OpenRead($exe.FullName)
    try {
        $head = New-Object byte[] 2
        if ($stream.Read($head,0,2) -ne 2 -or $head[0] -ne 77 -or $head[1] -ne 90) {
            throw "Installed executable is missing the Windows PE MZ signature: $($exe.Name)"
        }
    } finally {$stream.Dispose()}
}
$expected = Get-Content -LiteralPath $manifest.FullName -Raw | ConvertFrom-Json
$actual = (Get-FileHash -LiteralPath $model.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected.model_sha256) {throw 'Installed GGUF differs from the verified staged model'}
$inferenceHash = (Get-FileHash -LiteralPath $inference.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
if ($inferenceHash -ne $expected.server_sha256) {
    throw 'Installed inference executable differs from the verified staged binary'
}
$dlls = @($files | Where-Object {$_.Extension -ieq '.dll' -and $_.DirectoryName -like '*llama-runtime*'})
if ($dlls.Count -lt 1) {throw 'Bundled CPU runtime DLL directory is empty'}
Write-Host 'Now verifying the actual INSTALLED Python engine can serve authenticated local API requests...'
$smoke = Join-Path $root 'desktop\verify_packaged_engine.py'
& python $smoke --exe $engine.FullName --startup-seconds 120 `
    --result-json (Join-Path $root 'build\installed-engine-smoke-result.json')
if ($LASTEXITCODE -ne 0) {throw 'Installed Python engine did not start securely'}
Write-Host 'WINDOWS INSTALLATION CHECK PASSED: offline payload installed and installed engine booted.'
