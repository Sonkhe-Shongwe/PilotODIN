# P2: test actual ReportWorkspace -> live TEMP FastAPI -> native Tauri Save As.
# All data is synthetic. No existing backend, user projects, model, cloud or installer.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend=Join-Path $root 'frontend'
$pythonExe=Join-Path $root '.venv-live\Scripts\python.exe'
$seed=Join-Path $root 'tools\Seed_P2_Native_Live_Chain_Local.py'
$cfg=Join-Path $frontend 'src-tauri\tauri.native-p2-chain.conf.json'
$session=Join-Path ([IO.Path]::GetTempPath()) ('pilotodin-p2-native-chain-'+[guid]::NewGuid().ToString('N').Substring(0,12))
$isolatedWorkspaceHome=Join-Path $session 'workspace'
$logDir=Join-Path $session 'logs'
$saveTarget=Join-Path $session 'save-target'
$manifestPath=Join-Path $isolatedWorkspaceHome 'synthetic-manifest.json'
$archive=$session+'.zip'
New-Item -ItemType Directory -Force -Path $isolatedWorkspaceHome,$logDir,$saveTarget | Out-Null
$seedLog=Join-Path $logDir 'synthetic-fixture.log'
$backendOut=Join-Path $logDir 'isolated-fastapi.log'
$backendErr=Join-Path $logDir 'isolated-fastapi-stderr.log'
$buildLog=Join-Path $logDir 'typescript-vite.log'
$nativeLog=Join-Path $logDir 'native-real-report.log'
$reportFile=Join-Path $logDir 'result.json'
$report=[ordered]@{
    scope='P2 real saved report -> isolated FastAPI -> actual Tauri ReportWorkspace Save As'
    created_utc=[datetime]::UtcNow.ToString('o')
    overall='FAIL'
    phases=[ordered]@{}
    native_observations='NOT_TESTED'
    existing_backend_8000='NOT_USED'
    synthetic_workspace='NEW_TEMP_ONLY'
    qwen_ai='NOT_RUN'
    installed_release='NOT_BUILT'
    report_outputs='NOT_VERIFIED'
    synthetic_pdf_reproducibility='REPORTLAB_INVARIANT_TEST_SCOPE_ONLY'
    message=''
}
$backend=$null
$nativeCompleted=$false
$manifest=$null
$oldEnv=@{}
foreach($name in @('RL_invariant','PILOTODIN_HOME','PILOTODIN_DESKTOP_SESSION','CARGO_NET_OFFLINE','VITE_PILOTODIN_NATIVE_SMOKE',
 'VITE_P2_CHAIN_API_PORT','VITE_P2_CHAIN_PROJECT_ID','VITE_P2_CHAIN_REPORT_ID',
 'VITE_P2_CHAIN_HTML_NAME','VITE_P2_CHAIN_PDF_NAME')){
    $oldEnv[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
function Mark([string]$name,[bool]$passed){
    $report.phases[$name]=$(if($passed){'PASS'}else{'FAIL'})
    Write-Host ($name+': '+$report.phases[$name]) -ForegroundColor $(if($passed){'Green'}else{'Red'})
}
function Free-Port {
    $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse('127.0.0.1'),0)
    $listener.Start()
    $port=$listener.LocalEndpoint.Port
    $listener.Stop()
    return $port
}
function Port-Used([int]$port){
    $c=New-Object Net.Sockets.TcpClient
    try{$t=$c.ConnectAsync('127.0.0.1',$port);return $t.Wait(300) -and $c.Connected}
    catch{return $false}
    finally{$c.Close()}
}
function File-Match([string]$path,[string]$hash,[string]$label){
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        Write-Host ($label+': ABSENT in selected folder') -ForegroundColor Red
        return $false
    }
    $got=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    $ok=($got -eq $hash)
    Write-Host ($label+': '+$(if($ok){'SHA-256 MATCH'}else{'SHA-256 MISMATCH'})) -ForegroundColor $(if($ok){'Green'}else{'Red'})
    return $ok
}
function Check-Live-Report([int]$port,[string]$reportId){
    $uri="http://127.0.0.1:$port/api/reports/$reportId"+'?revision=2'
    $last=''
    for($i=0;$i -lt 120;$i++){
        try{
            $response=Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
            if($response.StatusCode -eq 200){return $true}
        }catch{$last=$_.Exception.Message}
        Start-Sleep -Milliseconds 250
    }
    throw ('Isolated FastAPI report not available: '+$last)
}
Write-Host 'PilotODIN P2: FULL CHAIN native report export (synthetic development test)'
Write-Host '-----------------------------------------------------------------------'
Write-Host ('TEMPORARY SAVE FOLDER (recommended): '+$saveTarget) -ForegroundColor Cyan
Write-Host 'You may use a different EMPTY folder if necessary, but supply its actual location after test.'
Write-Host 'Never save these test files over a real report or modify originals.'
try{
    if($env:OS -ne 'Windows_NT'){throw 'Run this launcher on Windows only.'}
    if(-not(Test-Path -LiteralPath $pythonExe) -or -not(Test-Path -LiteralPath $cfg) -or -not(Test-Path -LiteralPath $seed)){
        throw 'Existing virtualenv, fixture seeder or test-only Tauri config unavailable.'
    }
    $npm=Get-Command npm.cmd -ErrorAction Stop
    $cargo=Get-Command cargo.exe -ErrorAction Stop
    if(-not(Test-Path (Join-Path $frontend 'node_modules'))){throw 'Existing node_modules missing; no download allowed.'}
    if(Port-Used 5176){throw 'Port 5176 occupied; close the prior isolated test first.'}
    $git=Get-Command git.exe -ErrorAction SilentlyContinue
    if($git){
        $current=(& $git.Source -C $root branch --show-current).Trim()
        if($current -ne 'feature/live-dev-workspace-20261023'){throw ('Wrong GitHub branch: '+$current)}
        $uncommitted=@(& $git.Source -C $root status --porcelain)
        if($uncommitted.Count -gt 0){
            Write-Warning 'Uncommitted files exist; they will not be discarded or reset.'
        }
    }else{Write-Warning 'Verify feature/live-dev-workspace-20261023 is checked out in GitHub Desktop.'}
    # ReportLab normally embeds render-time PDF timestamps and document IDs.
    # Limit reproducible PDF metadata to this synthetic QA process tree only.
    # This affects both the fixture seed and its child live Uvicorn process.
    $env:RL_invariant='1'
    $env:PILOTODIN_HOME=$isolatedWorkspaceHome
    Remove-Item Env:\PILOTODIN_DESKTOP_SESSION -ErrorAction SilentlyContinue
    $env:CARGO_NET_OFFLINE='true'
    $env:VITE_PILOTODIN_NATIVE_SMOKE='1'
    Push-Location $root
    try{
        & $pythonExe $seed $manifestPath 2>&1 | Tee-Object -FilePath $seedLog
        $seedCode=$LASTEXITCODE
    }finally{Pop-Location}
    Mark 'p2-synthetic-real-report-seed' ($seedCode -eq 0 -and (Test-Path $manifestPath))
    if($seedCode -ne 0 -or -not(Test-Path $manifestPath)){throw 'Synthetic fixture creation failed.'}
    $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if($manifest.revision -ne 2 -or $manifest.report_id -notmatch '^[a-f0-9]{32}$' -or
       $manifest.project_id -notmatch '^[a-f0-9]{32}$'){throw 'Synthetic report manifest invalid.'}
    $backendPort=Free-Port
    $backend=Start-Process -FilePath $pythonExe -WorkingDirectory $root -ArgumentList @(
        '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',"$backendPort",
        '--lifespan','off') -NoNewWindow -PassThru -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
    $up=Check-Live-Report $backendPort $manifest.report_id
    Mark 'p2-isolated-real-fastapi' $up
    if(-not $up){throw 'Real temporary FastAPI backend did not start.'}
    # Verify that the live isolated HTTP service is returning the exact same
    # revision-2 bytes used as the expected reference by the synthetic seeder.
    $web=New-Object System.Net.WebClient
    $web.Headers.Add('Origin','http://127.0.0.1:5176')
    Write-Host 'Comparing live exports with synthetic fixture under test-only invariant PDF metadata.'
    foreach($kind in @('html','pdf')){
        $reference=Join-Path $session ('reference-'+$kind+'.bin')
        $url="http://127.0.0.1:$backendPort/api/reports/$($manifest.report_id)/export/$kind"+'?revision=2'
        $web.DownloadFile($url,$reference)
        $referenceHash=(Get-FileHash -LiteralPath $reference -Algorithm SHA256).Hash
        $expected=($manifest.exports.$kind.sha256).ToUpperInvariant()
        if($referenceHash -ne $expected){throw ('Live HTTP '+$kind+' content differs from frozen synthetic fixture.')}
        Remove-Item -LiteralPath $reference -Force
    }
    Mark 'p2-live-export-reference-digests' $true
    $env:VITE_P2_CHAIN_API_PORT="$backendPort"
    $env:VITE_P2_CHAIN_PROJECT_ID=[string]$manifest.project_id
    $env:VITE_P2_CHAIN_REPORT_ID=[string]$manifest.report_id
    $env:VITE_P2_CHAIN_HTML_NAME=[string]$manifest.exports.html.filename
    $env:VITE_P2_CHAIN_PDF_NAME=[string]$manifest.exports.pdf.filename
    Push-Location $frontend
    try{
        $prior=$ErrorActionPreference
        $ErrorActionPreference='Continue'
        & $npm.Source run build 2>&1 | Tee-Object -FilePath $buildLog
        $buildCode=$LASTEXITCODE
    }finally{$ErrorActionPreference=$prior;Pop-Location}
    Mark 'frontend-typescript-vite' ($buildCode -eq 0)
    if($buildCode -ne 0){throw 'TypeScript/Vite build failed; native app not launched.'}
    Write-Host ''
    Write-Host ('SAVE BOTH REVISION-2 FILES INTO: '+$saveTarget) -ForegroundColor Cyan
    Write-Host ('HTML name: '+$manifest.exports.html.filename)
    Write-Host ('PDF name:  '+$manifest.exports.pdf.filename)
    Write-Host 'In the Tauri test window use the ACTUAL ReportWorkspace Export HTML and Export PDF buttons.'
    Write-Host 'Both must show PASS in the test header before closing its native window.'
    Push-Location $frontend
    try{
        $prior=$ErrorActionPreference
        $ErrorActionPreference='Continue'
        & $npm.Source run desktop:dev -- --config src-tauri/tauri.native-p2-chain.conf.json 2>&1 | Tee-Object -FilePath $nativeLog
        $nativeCode=$LASTEXITCODE
    }finally{$ErrorActionPreference=$prior;Pop-Location}
    Mark 'p2-real-report-native-tauri-window' ($nativeCode -eq 0)
    if($nativeCode -ne 0){throw 'Native Tauri development window failed or exited with an error.'}
    $answer=(Read-Host 'Did real report revision 2 load and BOTH Export HTML/PDF show PASS in the native test window? [yes/no]').Trim().ToLowerInvariant()
    $nativeCompleted=$answer -in @('y','yes')
    $report.native_observations=$(if($nativeCompleted){'OWNER_OBSERVED_BOTH_REAL_REPORT_NATIVE_SAVES'}else{'FAIL_OR_NOT_OBSERVED'})
    Mark 'p2-owner-real-report-export-observations' $nativeCompleted
    if(-not $nativeCompleted){throw 'Owner did not confirm both native export results.'}
    Write-Host ('Recommended target folder was: '+$saveTarget) -ForegroundColor Cyan
    $chosen=(Read-Host 'Paste the ACTUAL folder where the two unmodified native exports were saved').Trim().Trim('"')
    if(-not(Test-Path -LiteralPath $chosen -PathType Container)){throw 'Selected Save As folder does not exist.'}
    $chosen=(Resolve-Path -LiteralPath $chosen).Path
    $htmlFile=Join-Path $chosen $manifest.exports.html.filename
    $pdfFile=Join-Path $chosen $manifest.exports.pdf.filename
    $htmlOk=File-Match $htmlFile ([string]$manifest.exports.html.sha256) 'HTML real report saved bytes'
    $pdfOk=File-Match $pdfFile ([string]$manifest.exports.pdf.sha256) 'PDF real report saved bytes'
    $report.report_outputs=$(if($htmlOk -and $pdfOk){'BOTH_SHA256_MATCH_REAL_API'}else{'FAIL_OR_MISSING'})
    Mark 'p2-real-report-native-saved-byte-integrity' ($htmlOk -and $pdfOk)
    if(-not($htmlOk -and $pdfOk)){throw 'Actual Save As files absent or differ from the live backend export bytes.'}
    $source=Join-Path $isolatedWorkspaceHome $manifest.source_relative
    $sourceOk=(Test-Path -LiteralPath $source -PathType Leaf) -and
        ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -eq $manifest.source_sha256)
    Mark 'p2-synthetic-source-unchanged' $sourceOk
    if(-not $sourceOk){throw 'Original synthetic CSV was modified.'}
    $report.overall='PASS'
    $report.message='Actual ReportWorkspace -> real isolated FastAPI -> native Tauri Save As completed for both revision-2 formats; owner-selected paths verified by SHA.'
}catch{
    $report.message=$_.Exception.Message
    Write-Host ('P2 full-chain integration FAILED: '+$report.message) -ForegroundColor Red
}finally{
    if($backend){
        try{if(-not $backend.HasExited){Stop-Process -Id $backend.Id -Force -ErrorAction Stop; $backend.WaitForExit(5000)|Out-Null}}catch{}
    }
    foreach($key in $oldEnv.Keys){
        [Environment]::SetEnvironmentVariable($key,$oldEnv[$key],'Process')
    }
    $report | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath $reportFile -Encoding UTF8
    $files=@($reportFile,$seedLog,$backendOut,$backendErr,$buildLog,$nativeLog) | Where-Object {Test-Path $_}
    Compress-Archive -LiteralPath $files -DestinationPath $archive -Force
    Write-Host ('P2 live API-to-native export gate: '+$report.overall) -ForegroundColor $(if($report.overall -eq 'PASS'){'Green'}else{'Red'})
    Write-Host ('One diagnostic ZIP (logs may contain test-local paths): '+$archive)
}
if($report.overall -ne 'PASS'){exit 1}
exit 0
