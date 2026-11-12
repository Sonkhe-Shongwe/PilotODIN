param([switch]$PreflightOnly, [switch]$ValidateRuntime)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$base = 'fc20659e5fced50f046fee56a3b35334caa96fa3'
$branch = 'feature/live-dev-workspace-20261023'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$frontend = Join-Path $root 'frontend'
function Fail([string]$message) { throw "P4-71 FAIL-CLOSED: $message" }
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or
    $env:RUNNER_OS -ne 'Windows' -or $env:GITHUB_EVENT_NAME -ne 'push' -or
    $env:GITHUB_REF_NAME -ne $branch) { Fail 'Requires one trusted disposable GitHub-hosted Windows push run, never owner Windows' }
$actual = (& git -C $root rev-parse HEAD).Trim()
$parent = (& git -C $root rev-parse 'HEAD~4').Trim()
if ($LASTEXITCODE -ne 0 -or $actual -ne $env:GITHUB_SHA -or $parent -ne $base) { Fail 'Approved exact source/parent SHA mismatch' }
$allowed = @(
 '.github/workflows/p4-71-one-approved-native-dev.yml',
 'qa/p4_native/P4_71_OWNER_APPROVED_ONE_USE_TRIGGER_20261112.txt',
 'qa/p4_native/Run_P4_71_Disposable_Windows.ps1',
 'frontend/e2e/p4-71-native-webview-qa.mjs'
)
$changed = @(& git -C $root diff --name-only 'HEAD~4' 'HEAD')
foreach ($path in $changed) { if ($path -notin $allowed) { Fail 'Unapproved application/source change in the one-shot commit' } }
if ($changed.Count -ne 4) { Fail 'One-shot commit must contain only four reviewed QA/trigger files' }
$production = Get-Content (Join-Path $frontend 'src-tauri/tauri.conf.json') -Raw | ConvertFrom-Json
$oldQA = Get-Content (Join-Path $frontend 'src-tauri/tauri.p4-native-qa.conf.json') -Raw | ConvertFrom-Json
$isolated = Get-Content (Join-Path $frontend 'src-tauri/tauri.p4-isolated-native-dev.conf.json') -Raw | ConvertFrom-Json
$package = Get-Content (Join-Path $frontend 'package.json') -Raw | ConvertFrom-Json
if ($production.identifier -ne 'com.pilotodin.studio' -or
    $oldQA.identifier -ne 'com.pilotodin.p4nativeqa' -or
    $isolated.identifier -ne 'com.pilotodin.p4isolatednativedev' -or
    (@($production.identifier,$oldQA.identifier,$isolated.identifier) | Sort-Object -Unique).Count -ne 3 -or
    $isolated.bundle.active -ne $false -or
    @($isolated.bundle.externalBin).Count -ne 0 -or
    @($isolated.bundle.resources).Count -ne 0 -or
    $null -ne $isolated.app.PSObject.Properties['appDirectoriesOverride'] -or
    $null -ne $production.app.PSObject.Properties['appDirectoriesOverride'] -or
    $package.scripts.'desktop:dev' -ne 'node scripts/p4-isolated-native-dev.mjs' -or
    $package.scripts.'desktop:build' -ne 'node scripts/deny-intermediate-installer.mjs' -or
    $production.build.beforeDevCommand -ne 'node scripts/deny-unsafe-default-tauri-dev.mjs' -or
    $production.build.beforeBuildCommand -ne 'node scripts/deny-intermediate-installer.mjs') { Fail 'Production/QA/dev identities, bundles or default-deny hooks differ from reviewed source' }
if (-not (Select-String -Path (Join-Path $frontend 'src-tauri/src/lib.rs') -Pattern 'app_local_data_dir' -SimpleMatch -Quiet)) { Fail 'Native backend storage derivation changed' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'qa/p4_native/P4_71_OWNER_APPROVED_ONE_USE_TRIGGER_20261112.txt') -PathType Leaf)) { Fail 'One-shot owner approval marker absent' }
if ($env:PILOTODIN_HOME) { Fail 'Inherited PILOTODIN_HOME is not permitted' }
foreach ($item in @('com.pilotodin.studio','com.pilotodin.p4nativeqa')) {
 foreach($appdata in @($env:LOCALAPPDATA,$env:APPDATA)) {
   if (Test-Path -LiteralPath (Join-Path $appdata $item)) { Fail 'Protected production or old-QA appdata unexpectedly present on disposable runner' }
 }
}
$qaHome = Join-Path $env:RUNNER_TEMP ('P4-71-only-home-' + $env:GITHUB_RUN_ID)
if (Test-Path -LiteralPath $qaHome) { Fail 'Disposable test home unexpectedly exists; refusing reuse' }
if ($PreflightOnly -or $ValidateRuntime) {
 Write-Host "P4-71 HOSTED WINDOWS PREFLIGHT + RUNTIME PATH PASS: exact HEAD=$actual approved_base=$base; distinct IDs; original roots absent; reserved variable avoided; bundle forbidden; no native compilation."
 exit 0
}
New-Item -ItemType Directory -Path $qaHome | Out-Null
$env:PILOTODIN_HOME = $qaHome
$env:PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT = 'I_APPROVE_UNPACKAGED_P4_NATIVE_DEV'
$env:VITE_PILOTODIN_NATIVE_SMOKE = '1'
# Remote debugger applies to disposable hosted WebView2 only. No other host is exposed.
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = '--remote-debugging-port=9331'
$backend = $null
$native = $null
try {
 $backend = Start-Process -FilePath 'python.exe' -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--no-access-log') -WorkingDirectory $root -PassThru
 $ready = $false
 for ($i=0; $i -lt 60; $i++) {
   Start-Sleep -Seconds 2
   if ($backend.HasExited) { Fail 'Disposable Python backend exited before health check' }
   try {
     $status = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
     if ($status.status -eq 'ok') { $ready = $true; break }
   } catch { }
 }
 if (-not $ready) { Fail 'Disposable Python backend unavailable; compile NOT started' }
 Write-Host 'DISPOSABLE LOOPBACK BACKEND READY: 127.0.0.1:8000 (no sidecar/Qwen).'
 # Exactly one approved Tauri dev compile; do NOT retry if it fails.
 $native = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c','npm run desktop:dev') -WorkingDirectory $frontend -PassThru
 $binary = Join-Path $frontend 'src-tauri/target/debug/pilotodin-desktop.exe'
 $compiled = $false
 for($i=0; $i -lt 540; $i++) {
   Start-Sleep -Seconds 5
   if ($native.HasExited) { Fail 'Native developer build/launcher exited; do not repeat this one-shot build' }
   if (Test-Path -LiteralPath $binary -PathType Leaf) {
     $nativeProcess = @(Get-CimInstance Win32_Process -Filter "Name = 'pilotodin-desktop.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.ExecutablePath -and $_.ExecutablePath.EndsWith('src-tauri\target\debug\pilotodin-desktop.exe',[System.StringComparison]::OrdinalIgnoreCase) })
     if ($nativeProcess.Count -gt 0) { $compiled = $true; break }
   }
 }
 if (-not $compiled) { Fail 'Single native developer compilation/runtime failed to start inside time budget' }
 $sha = (Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLowerInvariant()
 $bytes = (Get-Item -LiteralPath $binary).Length
 Write-Host "ONE NATIVE DEV COMPILATION: exact source $actual ; executable SHA256=$sha ; bytes=$bytes ; no installer."
 $cdp = $false
 for($i=0; $i -lt 20; $i++) {
   Start-Sleep -Seconds 2
   try { $v = Invoke-RestMethod -Uri 'http://127.0.0.1:9331/json/version' -TimeoutSec 2; if ($v.webSocketDebuggerUrl) { $cdp=$true; break } } catch { }
 }
 $isolatedRoot=Join-Path $env:LOCALAPPDATA 'com.pilotodin.p4isolatednativedev'
 $webviews=@(Get-CimInstance Win32_Process -Filter "Name = 'msedgewebview2.exe'" -ErrorAction SilentlyContinue |
  Where-Object {$_.CommandLine -and $_.CommandLine.Contains('com.pilotodin.p4isolatednativedev')})
 Write-Host "NATIVE WEBVIEW SMOKE: isolated_app_root_present=$(Test-Path $isolatedRoot); isolated_WebView2_processes=$($webviews.Count); debugger_ready=$cdp"
 if (-not (Test-Path $isolatedRoot) -or $webviews.Count -lt 1) { Fail 'Actual native WebView2 profile isolation/startup not proven' }
 if ($cdp) {
   Push-Location $frontend
   try {
     node e2e/p4-71-native-webview-qa.mjs
     if ($LASTEXITCODE -ne 0) { Fail 'Native WebView2 synthetic QA failed: preserve failure evidence, no repeat compilation under this approval' }
   } finally { Pop-Location }
 } else {
   Write-Host 'NATIVE INTERACTIONS BLOCKED: WebView2 CDP unavailable. N2-N11 NOT TESTED; native startup isolation only.'
 }
 # Do not count this hosted runner as a physical 8 GB/Qwen/offline acceptance.
 Write-Host 'R03 PHYSICAL 8GB + QWEN OFFLINE: NOT TESTED. No model fitted. No original owner files touched.'
} finally {
 if ($native -and -not $native.HasExited) { & taskkill.exe /PID $native.Id /T /F 2>$null | Out-Null }
 if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
 foreach($name in @('com.pilotodin.studio','com.pilotodin.p4nativeqa')) {
  foreach($baseDir in @($env:LOCALAPPDATA,$env:APPDATA)) {
   if (Test-Path -LiteralPath (Join-Path $baseDir $name)) { Fail 'Unexpected protected profile path created: STOP/FAIL' }
  }
 }
 Write-Host 'POSTRUN PROTECTED IDENTITIES ABSENT on disposable hosted runner. Historical owner R06 FAIL unchanged.'
}
