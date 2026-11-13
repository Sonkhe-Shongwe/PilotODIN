param([switch]$PreflightOnly, [switch]$ValidateRuntime)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$base = 'a9ccf9ebcb3fd41caa994af1eaa8a7b15942c0d1'
$branch = 'feature/live-dev-workspace-20261023'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$frontend = Join-Path $root 'frontend'
function Fail([string]$message) { throw "P4-71 FAIL-CLOSED: $message" }
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or
    $env:RUNNER_OS -ne 'Windows' -or $env:GITHUB_EVENT_NAME -ne 'push' -or
    $env:GITHUB_REF_NAME -ne $branch) { Fail 'Requires one trusted disposable GitHub-hosted Windows push run, never owner Windows' }
$actual = (& git -C $root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actual -ne $env:GITHUB_SHA) { Fail 'Checked-out source differs from the workflow SHA' }
$commitAndParents = (& git -C $root rev-list --parents -n 1 HEAD).Trim() -split ' '
if ($LASTEXITCODE -ne 0 -or $commitAndParents.Count -ne 2 -or $commitAndParents[1] -ne $base) {
 Fail 'One-shot run must be a direct child of the reviewed source'
}
if ($env:GITHUB_RUN_ATTEMPT -ne '1') { Fail 'One-shot approval excludes re-runs' }
$allowed = @(
 '.github/workflows/p4-native-quality-relaunch-20261113.yml',
 'qa/p4_native/P4_WINDOWS_QUALITY_RELAUNCH_APPROVAL_20261113.txt',
 'qa/p4_native/Run_P4_71_Disposable_Windows.ps1',
 'frontend/e2e/p4-71-native-webview-qa.mjs',
 'frontend/e2e/p4-quality-version-transition.mjs'
)
$changed = @(& git -C $root diff --name-only $base $actual)
if ($LASTEXITCODE -ne 0 -or $changed.Count -ne $allowed.Count) { Fail 'One-shot launch must contain exactly the reviewed QA setup changes' }
foreach ($path in $changed) { if ($path -cnotin $allowed) { Fail 'Unapproved path in the one-shot launch' } }
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
if (-not (Test-Path -LiteralPath (Join-Path $root 'qa/p4_native/P4_WINDOWS_QUALITY_RELAUNCH_APPROVAL_20261113.txt') -PathType Leaf)) { Fail 'One-shot owner approval marker absent' }
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
. (Join-Path $PSScriptRoot 'Close_P4_Verified_Window.ps1')
$backend = $null
$native = $null
$reopened = $null
$devServer = $null
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
 Write-Host 'STARTING ONE APPROVED NATIVE DEVELOPER BUILD.'
 $native = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c','npm run desktop:dev') -WorkingDirectory $frontend -PassThru
 $binary = Join-Path $frontend 'src-tauri/target/debug/pilotodin-desktop.exe'
 $compiled = $false
 for($i=0; $i -lt 540; $i++) {
   Start-Sleep -Seconds 5
   if ($native.HasExited) { Fail 'Native developer build/launcher exited; do not repeat this one-shot build' }
   if (Test-Path -LiteralPath $binary -PathType Leaf) {
     $nativeProcess = @(Get-CimInstance Win32_Process -Filter "Name = 'pilotodin-desktop.exe'" -ErrorAction SilentlyContinue |
       Where-Object { [string]::Equals($_.ExecutablePath, $binary, [StringComparison]::OrdinalIgnoreCase) })
     if ($nativeProcess.Count -gt 1) { Fail 'More than one isolated QA desktop process was found' }
     if ($nativeProcess.Count -eq 1) {
       $env:P4_NATIVE_QA_APP_PID = [string]$nativeProcess[0].ProcessId
       $compiled = $true
       break
     }
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
 # Collect probe diagnostics even if the readiness poll found no debugger.
 Push-Location $frontend
 try {
   node e2e/p4-71-native-webview-qa.mjs
   if ($LASTEXITCODE -eq 2) { Fail 'Native startup verified; N2-N12 BLOCKED before fixture creation. See loopback diagnostics.' }
   if ($LASTEXITCODE -eq 3) { Fail 'Native project switch BLOCKED at the Windows confirmation. See the per-case probe output.' }
   if ($LASTEXITCODE -ne 0) { Fail 'Native WebView2 synthetic QA failed: preserve failure evidence, no repeat compilation under this approval' }
 } finally { Pop-Location }
 $closedAppPid = [int]$env:P4_NATIVE_QA_APP_PID
 Close-P4VerifiedWindow -AppProcessId $closedAppPid -ExpectedPath $binary -ExpectedTitle $isolated.app.windows[0].title
 Write-Host 'N11 isolated app accepted its Windows close request and exited normally.'
 if (-not $native.WaitForExit(10000)) {
   & taskkill.exe /PID $native.Id /T /F | Out-Null
   if (-not $native.WaitForExit(5000)) { Fail 'The original development launcher did not stop' }
 }
 # Use the same Vite app on the same origin so the restarted WebView can read
 # its persisted project selection. The Tauri dev launcher may have stopped Vite.
 $ui = 'http://127.0.0.1:5173/'
 try { $viteReady = (Invoke-WebRequest -Uri $ui -TimeoutSec 3).StatusCode -eq 200 } catch { $viteReady = $false }
 if (-not $viteReady) {
   $devServer = Start-Process -FilePath 'node.exe' -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--strictPort') -WorkingDirectory $frontend -PassThru
   for ($i=0; $i -lt 20; $i++) {
     if ($devServer.HasExited) { Fail 'Vite exited before the relaunch readiness check' }
     try { $viteReady = (Invoke-WebRequest -Uri $ui -TimeoutSec 2).StatusCode -eq 200; if ($viteReady) { break } } catch { }
     Start-Sleep -Milliseconds 500
   }
 }
 if (-not $viteReady) { Fail 'Vite did not become ready for relaunch' }
 if ((Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha) {
   Fail 'The app binary changed after the first launch'
 }
 $oldDebuggerReady = $true
 for ($i=0; $i -lt 12; $i++) {
   try { $oldDebuggerReady = [bool](Invoke-RestMethod -Uri 'http://127.0.0.1:9331/json/version' -TimeoutSec 1).webSocketDebuggerUrl }
   catch { $oldDebuggerReady = $false }
   if (-not $oldDebuggerReady) { break }
   Start-Sleep -Milliseconds 500
 }
 if ($oldDebuggerReady) { Fail 'The previous WebView debugger remained reachable after closing the app' }
 $reopened = Start-Process -FilePath $binary -WorkingDirectory (Split-Path $binary) -PassThru
 if ($reopened.Id -eq $closedAppPid) { Fail 'Could not establish a distinct relaunched app process' }
 $env:P4_NATIVE_QA_APP_PID = [string]$reopened.Id
 Write-Host 'N11 started a new Windows app process from the same verified binary.'
 $relaunchCdp = $false
 for ($i=0; $i -lt 25; $i++) {
   if ($reopened.HasExited) { Fail 'The relaunched QA app exited before the WebView was ready' }
   try { $v = Invoke-RestMethod -Uri 'http://127.0.0.1:9331/json/version' -TimeoutSec 2; if ($v.webSocketDebuggerUrl) { $relaunchCdp = $true; break } } catch { }
   Start-Sleep -Seconds 1
 }
 if (-not $relaunchCdp) { Fail 'The relaunched WebView debugger did not become ready' }
 Push-Location $frontend
 try {
   node e2e/p4-71-native-webview-qa.mjs --verify-relaunch
   if ($LASTEXITCODE -ne 0) { Fail 'N11 post-relaunch version and Prepare plan were not verified' }
 } finally { Pop-Location }
 # Do not count this hosted runner as a physical 8 GB/Qwen/offline acceptance.
 Write-Host 'R03 PHYSICAL 8GB + QWEN OFFLINE: NOT TESTED. No model fitted. No original owner files touched.'
} finally {
 if ($reopened -and -not $reopened.HasExited) { & taskkill.exe /PID $reopened.Id /T /F 2>$null | Out-Null }
 if ($devServer -and -not $devServer.HasExited) { Stop-Process -Id $devServer.Id -Force -ErrorAction SilentlyContinue }
 if ($native -and -not $native.HasExited) { & taskkill.exe /PID $native.Id /T /F 2>$null | Out-Null }
 if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
 foreach($name in @('com.pilotodin.studio','com.pilotodin.p4nativeqa')) {
  foreach($baseDir in @($env:LOCALAPPDATA,$env:APPDATA)) {
   if (Test-Path -LiteralPath (Join-Path $baseDir $name)) { Fail 'Unexpected protected profile path created: STOP/FAIL' }
  }
 }
 Write-Host 'POSTRUN PROTECTED IDENTITIES ABSENT on disposable hosted runner. Historical owner R06 FAIL unchanged.'
}
