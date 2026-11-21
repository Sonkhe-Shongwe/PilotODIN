# P2 native Save As verification, dev Tauri, synthetic PDF/HTML only.
# No user project import, existing backend, Qwen, installer, CI or prior suite.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend = Join-Path $root 'frontend'
$fixtureDir = Join-Path $frontend 'public\p2-native-fixtures'
$manifest = Join-Path $frontend 'src-tauri\tauri.native-p2-smoke.conf.json'
$session = Join-Path ([IO.Path]::GetTempPath()) ('pilotodin-p2-native-' + [guid]::NewGuid().ToString('N').Substring(0,12))
$target = Join-Path $session 'save-target'
New-Item -ItemType Directory -Force -Path $target | Out-Null
$reportPath = Join-Path $session 'result.json'
$logBuild = Join-Path $session 'frontend-build.log'
$logNative = Join-Path $session 'tauri-native-dev.log'
$zipPath = $session + '.zip'
$checks = [ordered]@{}
$report = [ordered]@{
    scope = 'P2 native Rust Save As against dedicated synthetic PDF and HTML'
    created_utc = [datetime]::UtcNow.ToString('o')
    branch = $null
    head = $null
    checks = $checks
    overall = 'FAIL'
    native_ui_observation = 'NOT_TESTED'
    native_dev_only = $true
    original_data = 'NOT_ACCESSED'
    actual_backend = 'NOT_STARTED'
    cloud_or_model = 'NOT_RUN'
    installer = 'NOT_BUILT'
    message = ''
}
function Mark([string]$key,[bool]$passed){
    $checks[$key] = $(if($passed){'PASS'}else{'FAIL'})
    Write-Host ($key + ': ' + $checks[$key]) -ForegroundColor $(if($passed){'Green'}else{'Red'})
}
function Archive([string]$message){
    $report.message=$message
    $report.overall=$(if(($checks.Values -contains 'FAIL') -or ($checks.Values -contains 'NOT_TESTED')){'FAIL'}else{'PASS'})
    $report | ConvertTo-Json -Depth 8 | Set-Content -Path $reportPath -Encoding UTF8
    $parts=@($reportPath)
    if(Test-Path $logBuild){$parts += $logBuild}
    if(Test-Path $logNative){$parts += $logNative}
    Compress-Archive -LiteralPath $parts -DestinationPath $zipPath -Force
    Write-Host ('P2 native synthetic Save As gate: ' + $report.overall)
    Write-Host ('Diagnostic ZIP (may contain temporary paths): ' + $zipPath)
    return $(if($report.overall -eq 'PASS'){0}else{1})
}
function Stop-With([string]$message){
    Write-Host ('BLOCKED/FAILED: ' + $message) -ForegroundColor Red
    $script:report.overall='FAIL'
    $script:report.message=$message
    $script:report | ConvertTo-Json -Depth 8 | Set-Content -Path $reportPath -Encoding UTF8
    $parts=@($reportPath)
    if(Test-Path $logBuild){$parts += $logBuild}
    if(Test-Path $logNative){$parts += $logNative}
    Compress-Archive -LiteralPath $parts -DestinationPath $zipPath -Force
    Write-Host ('Diagnostic ZIP (may contain temporary paths): ' + $zipPath)
    exit 1
}
function Port-In-Use([int]$port){
    $tcp = New-Object Net.Sockets.TcpClient
    try {
        $task=$tcp.ConnectAsync('127.0.0.1',$port)
        return $task.Wait(350) -and $tcp.Connected
    }catch{return $false}
    finally {$tcp.Close()}
}
Write-Host 'PilotODIN P2: isolated development-only native Save As'
Write-Host '-------------------------------------------------------'
Write-Host ('TEMPORARY SAVE TARGET FOLDER: ' + $target) -ForegroundColor Cyan
Write-Host 'Save BOTH files in that exact EMPTY folder with the proposed names.'
Write-Host 'No backend connection, user project, Qwen or installer is required.'
if($env:OS -ne 'Windows_NT'){Stop-With 'Run this on the owner Windows computer.'}
$git=Get-Command git.exe -ErrorAction SilentlyContinue
if($null -eq $git){
    $report.branch='OWNER_VERIFY_IN_GITHUB_DESKTOP'
    Write-Warning 'git.exe not in PATH. Confirm feature/live-dev-workspace-20261023 is checked out in GitHub Desktop.'
}else{
    $report.branch=(& $git.Source -C $root branch --show-current).Trim()
    $report.head=(& $git.Source -C $root rev-parse HEAD).Trim()
    if($report.branch -ne 'feature/live-dev-workspace-20261023'){
        Stop-With ('Wrong active branch: ' + $report.branch)
    }
    $dirty=@(& $git.Source -C $root status --porcelain)
    if($dirty.Count -gt 0){
        Write-Warning 'Local uncommitted changes detected. This test will not discard them.'
    }
}
$npm=Get-Command npm.cmd -ErrorAction SilentlyContinue
$cargo=Get-Command cargo.exe -ErrorAction SilentlyContinue
if($null -eq $npm -or $null -eq $cargo){Stop-With 'Existing npm and Rust Cargo toolchains are required.'}
if(-not (Test-Path (Join-Path $frontend 'node_modules'))){Stop-With 'Existing frontend dependencies missing. No new packages will be installed.'}
if(-not (Test-Path $manifest)){Stop-With 'Native test-only configuration missing.'}
if(Port-In-Use 5175){Stop-With 'Test-only Vite port 5175 is occupied. Close any earlier native P2 test.'}
$pdfFixture=Join-Path $fixtureDir 'report.pdf'
$htmlFixture=Join-Path $fixtureDir 'report.html'
if(-not (Test-Path $pdfFixture) -or -not (Test-Path $htmlFixture)){
    Stop-With 'Test-only fixtures missing from the pulled feature branch.'
}
$pdfExpected=(Get-FileHash -LiteralPath $pdfFixture -Algorithm SHA256).Hash
$htmlExpected=(Get-FileHash -LiteralPath $htmlFixture -Algorithm SHA256).Hash
$report.fixture_pdf_sha256=$pdfExpected
$report.fixture_html_sha256=$htmlExpected
Write-Host ''
Write-Host 'Running only the affected TypeScript/Vite build.'
Push-Location $frontend
try {
    $prior=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    & $npm.Source run build 2>&1 | Tee-Object -FilePath $logBuild
    $buildCode=$LASTEXITCODE
}finally{
    $ErrorActionPreference=$prior
    Pop-Location
}
Mark 'frontend-typescript-vite' ($buildCode -eq 0)
if($buildCode -ne 0){Stop-With 'Frontend build failed before native launch.'}
Write-Host ''
Write-Host 'The test-only Tauri window will open. No backend or inference process is started.'
Write-Host ('SAVE BOTH REPORTS HERE: ' + $target) -ForegroundColor Cyan
Write-Host 'In the native window: PDF Save, HTML Save, Cancel PDF dialog, reject invalid PDF, reject wrong extension.'
Write-Host 'Choose the target folder above for PDF/HTML, and keep the proposed filenames.'
Write-Host 'Close the native window ONLY after completing all five checks.'
$previousOffline=$env:CARGO_NET_OFFLINE
$previousSmoke=$env:VITE_PILOTODIN_NATIVE_SMOKE
$env:CARGO_NET_OFFLINE='true'
$env:VITE_PILOTODIN_NATIVE_SMOKE='1'
$exitCode=1
Push-Location $frontend
try {
    $prior=$ErrorActionPreference
    # PowerShell 5.1 treats Tauri stderr status as a terminating error if
    # ErrorActionPreference is Stop. Trust the native process exit code.
    $ErrorActionPreference='Continue'
    & $npm.Source run desktop:dev -- --config src-tauri/tauri.native-p2-smoke.conf.json 2>&1 | Tee-Object -FilePath $logNative
    $exitCode=$(if($null -eq $LASTEXITCODE){1}else{[int]$LASTEXITCODE})
}finally{
    $ErrorActionPreference=$prior
    Pop-Location
    if($null -eq $previousOffline){Remove-Item Env:\CARGO_NET_OFFLINE -ErrorAction SilentlyContinue}
    else {$env:CARGO_NET_OFFLINE=$previousOffline}
    if($null -eq $previousSmoke){Remove-Item Env:\VITE_PILOTODIN_NATIVE_SMOKE -ErrorAction SilentlyContinue}
    else {$env:VITE_PILOTODIN_NATIVE_SMOKE=$previousSmoke}
}
Mark 'tauri-native-development-window' ($exitCode -eq 0)
if($exitCode -ne 0){Stop-With 'Tauri dev window did not exit successfully. Share ZIP log.'}
Write-Host ''
$reply=(Read-Host 'Did all FIVE test buttons in the actual native window report PASS? [yes/no]').Trim().ToLowerInvariant()
$observed=$reply -in @('y','yes')
$report.native_ui_observation=$(if($observed){'OWNER_OBSERVED_PASS'}else{'OWNER_OBSERVED_FAIL_OR_NOT_VERIFIED'})
Mark 'native-command-five-observations' $observed
$pdfTarget=Join-Path $target 'PilotODIN_P2_Synthetic.pdf'
$htmlTarget=Join-Path $target 'PilotODIN_P2_Synthetic.html'
$cancelTarget=Join-Path $target 'PilotODIN_P2_Cancel.pdf'
$pdfMatches=(Test-Path $pdfTarget) -and ((Get-FileHash -LiteralPath $pdfTarget -Algorithm SHA256).Hash -eq $pdfExpected)
$htmlMatches=(Test-Path $htmlTarget) -and ((Get-FileHash -LiteralPath $htmlTarget -Algorithm SHA256).Hash -eq $htmlExpected)
Mark 'pdf-written-byte-for-byte' $pdfMatches
Mark 'html-written-byte-for-byte' $htmlMatches
Mark 'cancel-file-absent' (-not (Test-Path $cancelTarget))
$originalsIntact=((Get-FileHash -LiteralPath $pdfFixture -Algorithm SHA256).Hash -eq $pdfExpected) -and
  ((Get-FileHash -LiteralPath $htmlFixture -Algorithm SHA256).Hash -eq $htmlExpected)
Mark 'synthetic-fixtures-unchanged' $originalsIntact
$code=Archive 'Dev-only native Save As tested with actual OS dialogs and isolated synthetic files. No native release or real API link certified.'
exit $code
