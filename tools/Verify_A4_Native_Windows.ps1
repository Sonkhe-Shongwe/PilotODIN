# A4 development-only Windows native Save As validation.
# Does not build an installer, stage AI, modify the real Tauri config,
# run hosted Actions, or copy user datasets into diagnostics.
[CmdletBinding()]
param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend = Join-Path $root 'frontend'
$manifest = Join-Path $frontend 'src-tauri\tauri.native-a4-smoke.conf.json'
$report = Join-Path ([IO.Path]::GetTempPath()) ('pilotodin-a4-native-' + [guid]::NewGuid().ToString('N').Substring(0,12))
New-Item -ItemType Directory -Path $report -Force | Out-Null
$log = Join-Path $report 'a4-native-run.log'
$resultPath = Join-Path $report 'result.json'
$zip = "$report.zip"
$results = [ordered]@{
    purpose = 'A4 Rust/Tauri real-window native Save As development smoke'
    created_utc = [datetime]::UtcNow.ToString('o')
    branch = $null
    commit = $null
    checks = [ordered]@{}
    native_compilation = 'NOT_RUN'
    native_window = 'NOT_VERIFIED'
    native_pdf_save = 'NOT_VERIFIED'
    native_html_save = 'NOT_VERIFIED'
    native_cancel = 'NOT_VERIFIED'
    consolidated_regressions = 'NOT_RUN'
    browser_mode = 'NOT_TESTED'
    installer = 'NOT_BUILT'
    native_ai_8gb = 'NOT_TESTED'
    message = ''
}
function Save-Result {
    $results | ConvertTo-Json -Depth 8 | Set-Content -Path $resultPath -Encoding UTF8
    $includes = @($resultPath)
    if(Test-Path $log){ $includes += $log }
    $regressionLog = Join-Path $report 'p0-a4-regression.log'
    if(Test-Path $regressionLog){ $includes += $regressionLog }
    $otherZip = Join-Path $report 'p0-a4-regression-diagnostics.zip'
    if(Test-Path $otherZip){ $includes += $otherZip }
    Compress-Archive -LiteralPath $includes -DestinationPath $zip -Force
    Write-Host ("Diagnostics ZIP (no project files): " + $zip)
}
function Stop-With([string]$message) {
    $results.message = $message
    Write-Host ("BLOCKED: " + $message) -ForegroundColor Red
    Save-Result
    exit 1
}
function Find-Exe([string]$name) {
    $cmd=Get-Command $name -ErrorAction SilentlyContinue
    if($null -eq $cmd){return $null}
    return $cmd.Source
}
function Port-Open([int]$port) {
    $tcp = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $tcp.ConnectAsync('127.0.0.1',$port)
        return $task.Wait(750) -and $tcp.Connected
    } catch {return $false}
    finally {$tcp.Close()}
}
function Ask-Result([string]$question){
    $reply = Read-Host "$question [yes/no/skip]"
    switch -Regex ($reply.Trim().ToLowerInvariant()) {
        '^(y|yes)$' {return 'OBSERVED_PASS'}
        '^(n|no)$' {return 'OBSERVED_FAIL'}
        default {return 'NOT_VERIFIED'}
    }
}
Write-Host ''
Write-Host 'PilotODIN A4 - Native desktop source and Save As acceptance'
Write-Host '-----------------------------------------------------------'
Write-Host 'The current browser at 127.0.0.1:5173 is NOT the native window.'
Write-Host 'This runs a separate Tauri development window on localhost:5174.'
Write-Host 'Tauri Rust dependencies may need download on their first build.'
Write-Host 'No installer, model, or release asset is created.'
Write-Host ("Result directory: " + $report)
if(-not $env:OS -or $env:OS -ne 'Windows_NT'){Stop-With 'Run on the owners Windows computer, not WSL or Linux.'}
if(-not (Test-Path $manifest)){Stop-With 'Native dev-only overlay configuration not found.'}
if(-not (Test-Path (Join-Path $frontend 'node_modules'))){Stop-With 'Existing frontend dependencies are missing. Start Live Dev once first.'}
$git = Find-Exe 'git.exe'
if($git){
    $results.branch = (& $git -C $root branch --show-current).Trim()
    $results.commit = (& $git -C $root rev-parse HEAD).Trim()
    if($results.branch -ne 'feature/live-dev-workspace-20261023'){
        Stop-With ('Select the development branch first. Current branch: ' + $results.branch)
    }
    $dirty = & $git -C $root status --porcelain
    $results.checks['clean_checkout'] = [string]::IsNullOrWhiteSpace(($dirty -join ''))
    if($dirty){Write-Host 'WARNING: Your checkout has local edits. Do not discard these edits.' -ForegroundColor Yellow}
}else{
    $results.checks['git'] = 'unavailable'
}
$rustc=Find-Exe 'rustc.exe'; $cargo=Find-Exe 'cargo.exe'
$npm=Find-Exe 'npm.cmd'
$results.checks['rustc_found']=[bool]$rustc
$results.checks['cargo_found']=[bool]$cargo
$results.checks['npm_found']=[bool]$npm
if(-not $rustc -or -not $cargo) {
    Stop-With 'Rust MSVC development toolchain is missing. See the official Tauri Windows prerequisites (Rust, MSVC C++ tools, WebView2).'
}
if(-not $npm){Stop-With 'npm.cmd is unavailable. Install Node.js as already required by Live Dev.'}
$rustVersion = (& $rustc --version)
$results.checks['rustc_version']=$rustVersion
if($rustVersion -match 'rustc\s+(\d+)\.(\d+)\.'){
    $major=[int]$Matches[1];$minor=[int]$Matches[2]
    if($major -lt 1 -or ($major -eq 1 -and $minor -lt 90)){
        Stop-With 'Current Tauri dialog plugin requires Rust 1.90+. Update the local stable MSVC toolchain.'
    }
}
$hostLine=(& $rustc -vV | Select-String '^host:' | Select-Object -First 1)
$results.checks['rust_host']=("$hostLine").Trim()
if(-not $results.checks['rust_host'].Contains('pc-windows-msvc')) {
    Stop-With 'The active Rust toolchain is not a Windows MSVC target.'
}
$results.checks['backend_8000_running']=Port-Open 8000
$results.checks['vite_5174_free']=-not (Port-Open 5174)
if(-not $results.checks['backend_8000_running']){
    Stop-With 'The normal local Python backend is not listening on 127.0.0.1:8000. Start PilotODIN Live Dev first.'
}
try {
    $health=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 5
    $results.checks['backend_healthy']=($health.status -eq 'ok')
} catch {
    $results.checks['backend_healthy']=$false
}
if(-not $results.checks['backend_healthy']){
    Stop-With 'A process uses port 8000, but it is not a healthy PilotODIN API.'
}
if(-not $results.checks['vite_5174_free']){
    Stop-With 'Temporary native smoke frontend port 5174 is already in use. Close the old A4 native smoke window.'
}
$results.checks['dev_overlay_found']=Test-Path $manifest
$results.checks['no_release_assets_required']=$true
Write-Host 'Preflight checks passed. Current source branch and local backend are ready.' -ForegroundColor Green
if($PreflightOnly){
    $results.message='Preflight only; regressions and native compilation/window not run.'
    Save-Result
    exit 0
}
$regressionPython = Join-Path $root '.venv-live\Scripts\python.exe'
if(-not (Test-Path $regressionPython)){
    Stop-With 'The existing .venv-live Python for A2/A3/A4 regression tests is missing.'
}
Write-Host ''
Write-Host 'Running the ONE consolidated A2/A3/A4 regression gate first...'
$regLog=Join-Path $report 'p0-a4-regression.log'
Push-Location $root
try {
    & $regressionPython 'tools\Verify_P0_A4_Readiness.py' 2>&1 | Tee-Object -FilePath $regLog
    $regressionCode=$LASTEXITCODE
} catch {
    $regressionCode=1
    Add-Content -Path $regLog -Value ('Regression runner exception: ' + $_.Exception.Message)
} finally {Pop-Location}
$results.checks['p0_a4_regression_exit_code']=$regressionCode
if($regressionCode -ne 0){
    $results.consolidated_regressions='FAIL'
    Stop-With 'The consolidated frontend/backend regression gate failed. Fix that first; no native window was launched.'
}
$results.consolidated_regressions='PASS'
# The Python gate writes its own isolated ZIP; nest those diagnostics once in
# this native ZIP so there is still only ONE owner attachment to share.
$regText = Get-Content -Path $regLog -Raw -ErrorAction SilentlyContinue
$pattern='Shareable diagnostics ZIP:\s*(.+?\.zip)'
if($regText -match $pattern){
    $nested=$Matches[1].Trim()
    if(Test-Path $nested){
        Copy-Item -LiteralPath $nested -Destination (Join-Path $report 'p0-a4-regression-diagnostics.zip') -Force
    }
}
Write-Host 'All source regressions passed. Proceeding to actual Tauri development compilation.' -ForegroundColor Green
Write-Host ''
Write-Host 'WHEN THE SEPARATE NATIVE WINDOW OPENS:'
Write-Host '  1. Open the saved Deliver report in the Tauri window (not in Chrome).'
Write-Host '  2. Export PDF using Windows Save As. Open the file and check figures/pages.'
Write-Host '  3. Export HTML using Windows Save As. Open the file.'
Write-Host '  4. Click export again and CANCEL. Confirm no new file appeared.'
Write-Host '  5. Close the native PilotODIN window to return here.'
Write-Host 'You can leave the normal Live Dev Chrome/browser/backend open.'
Write-Host ''
$priorSmoke=$env:VITE_PILOTODIN_NATIVE_SMOKE
$env:VITE_PILOTODIN_NATIVE_SMOKE='1'
$exitCode=1
$previousErrorActionPreference=$ErrorActionPreference
Push-Location $frontend
try {
    # Tauri prints routine status messages such as "Running BeforeDevCommand"
    # to STDERR. In Windows PowerShell 5.1, redirecting native STDERR with
    # 2>&1 while ErrorActionPreference=Stop converts the very first status
    # line to a terminating NativeCommandError. That falsely aborted startup
    # BEFORE Cargo could compile and discarded the useful remaining log.
    # Treat native STDERR as diagnostic output only during the npm/Tauri
    # process; decide success by its real exit code, not its output stream.
    $ErrorActionPreference='Continue'
    & $npm run desktop:dev -- --config src-tauri/tauri.native-a4-smoke.conf.json 2>&1 | Tee-Object -FilePath $log
    $exitCode=if($null -eq $LASTEXITCODE){1}else{[int]$LASTEXITCODE}
} catch {
    Add-Content -Path $log -Value ("Launcher exception: " + $_.Exception.ToString())
} finally {
    $ErrorActionPreference=$previousErrorActionPreference
    Pop-Location
    if($null -eq $priorSmoke){Remove-Item Env:\VITE_PILOTODIN_NATIVE_SMOKE -ErrorAction SilentlyContinue}
    else {$env:VITE_PILOTODIN_NATIVE_SMOKE=$priorSmoke}
}
$results.checks['tauri_dev_exit_code']=$exitCode
if($exitCode -ne 0){
    Stop-With 'Native Tauri debug build/window returned a nonzero exit. Share ZIP diagnostics for code/toolchain fixes; no runtime pass claimed.'
}
$results.native_compilation='PASS'
Write-Host ''
Write-Host 'Desktop process completed. Record only what you actually observed:'
$results.native_window=Ask-Result 'Did a SEPARATE native PilotODIN window open?'
$results.native_pdf_save=Ask-Result 'Did PDF Save As open and write a readable file?'
$results.native_html_save=Ask-Result 'Did HTML Save As open and write a readable file?'
$results.native_cancel=Ask-Result 'Did Cancel leave the destination unchanged?'
$manual=@($results.native_window,$results.native_pdf_save,$results.native_html_save,$results.native_cancel)
if($manual -contains 'OBSERVED_FAIL'){$results.message='Native compilation completed; one or more owner-observed acceptance checks FAILED.'}
elseif($manual -contains 'NOT_VERIFIED'){$results.message='Native compilation completed; some manual observations remain unverified.'}
else {$results.message='Native compilation succeeded and all four owner-observed Save As checks reported PASS. Installer/release not tested.'}
Write-Host $results.message
Save-Result
if($manual -contains 'OBSERVED_FAIL'){exit 1}
exit 0
