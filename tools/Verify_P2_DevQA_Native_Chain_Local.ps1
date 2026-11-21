# DevQA P2: isolated real saved-report -> FastAPI -> Tauri native Save As.
# This test-only runner uses ONE new DevQA run allocated by qa_foundation.py.
# Historic Verify_P2_Native_Live_Report_Local.ps1 remains untouched.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$QaRunDir)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend=Join-Path $root 'frontend'
$pythonExe=Join-Path $root '.venv-live\Scripts\python.exe'
$seed=Join-Path $root 'tools\Seed_P2_Native_Live_Chain_Local.py'
$cfg=Join-Path $frontend 'src-tauri\tauri.native-p2-chain.conf.json'
if(-not $env:LOCALAPPDATA -or -not [IO.Path]::IsPathRooted($env:LOCALAPPDATA)){
    throw 'Windows LOCALAPPDATA missing. DevQA runner will not infer a directory.'
}
$qaRoot=Join-Path $env:LOCALAPPDATA 'PilotODIN\DevQA'
$expectedParent=Join-Path $qaRoot 'runs'
if(-not [IO.Path]::IsPathRooted($QaRunDir)){throw 'DevQA run must be an absolute path.'}
$session=(Resolve-Path -LiteralPath $QaRunDir -ErrorAction Stop).Path
$expectedRuns=(Resolve-Path -LiteralPath $expectedParent -ErrorAction Stop).Path
if((Split-Path -Parent $session) -ine $expectedRuns){throw 'Refusing a run outside the managed DevQA runs folder.'}
foreach($path in @($qaRoot,$expectedParent,$session,(Join-Path $session 'exports'),(Join-Path $session 'workspace'),(Join-Path $session 'logs'))){
    $item=Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Refusing a linked or redirected DevQA workspace.'}
}
$qaManifestPath=Join-Path $session 'manifest.json'
$qaManifest=Get-Content -LiteralPath $qaManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if($qaManifest.phase -ne 'P2-NATIVE-CHAIN' -or $qaManifest.state -ne 'READY_NOT_TESTED' -or
   $qaManifest.product_acceptance -ne 'NOT_TESTED'){
    throw 'QA run manifest does not identify a fresh P2 native-chain test.'
}
$isolatedWorkspaceHome=Join-Path $session 'workspace'
$logDir=Join-Path $session 'logs'
$saveTarget=Join-Path $session 'exports'
$manifestPath=Join-Path $isolatedWorkspaceHome 'synthetic-manifest.json'
$archive=Join-Path (Join-Path $qaRoot 'archive') ((Split-Path $session -Leaf)+'.zip')
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
    synthetic_workspace='DEVQA_UNIQUE_RUN_ONLY'
    qa_run_id=(Split-Path $session -Leaf)
    save_verification='NOT_TESTED'
    alternate_location='NOT_USED'
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
 'VITE_P2_CHAIN_HTML_NAME','VITE_P2_CHAIN_PDF_NAME','VITE_P2_CHAIN_SAVE_FOLDER')){
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
        Write-Host ($label+': MISSING exact required file '+[IO.Path]::GetFileName($path)) -ForegroundColor Red
        return $false
    }
    $fileItem=Get-Item -LiteralPath $path -Force
    if(($fileItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        Write-Host ($label+': Refusing linked export file') -ForegroundColor Red
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
Write-Host ('DEVQA EXPORTS FOLDER (USE THIS FOR BOTH WINDOWS SAVE AS DIALOGS): '+$saveTarget) -ForegroundColor Cyan
Write-Host 'In the Save As dialog, paste this EXACT directory in the address bar. Keep both filenames.'
Write-Host 'After the test we verify this directory automatically. No Downloads/relative folder prompts.'
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
    $env:VITE_P2_CHAIN_SAVE_FOLDER=$saveTarget
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
    Write-Host ('SAVE BOTH REVISION-2 FILES INTO THIS DEVQA EXPORT FOLDER: '+$saveTarget) -ForegroundColor Cyan
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
    # Never guess a Downloads path or search arbitrary personal folders.
    # The new DevQA run has ONE exact empty exports folder at test start.
    $chosen=$saveTarget
    $htmlFile=Join-Path $chosen $manifest.exports.html.filename
    $pdfFile=Join-Path $chosen $manifest.exports.pdf.filename
    if((-not (Test-Path -LiteralPath $htmlFile -PathType Leaf)) -or
       (-not (Test-Path -LiteralPath $pdfFile -PathType Leaf))){
        Write-Host 'One or both EXACT filenames are missing in DevQA exports.' -ForegroundColor Yellow
        Write-Host ('Expected HTML: '+$manifest.exports.html.filename)
        Write-Host ('Expected PDF:  '+$manifest.exports.pdf.filename)
        Write-Host 'Different browser-download names do NOT establish native file acceptance.'
        $alternate=(Read-Host 'Did you deliberately choose a DIFFERENT folder in both Windows Save As dialogs? [yes/no]').Trim().ToLowerInvariant()
        if($alternate -in @('yes','y')){
            $inputFolder=(Read-Host 'Paste the FULL ABSOLUTE path to that original folder (NOT Downloads)').Trim().Trim('"')
            # IsPathRooted alone accepts drive-relative forms such as '\folder' on Windows.
            $driveAbsolute=($inputFolder -match '^[A-Za-z]:[\\/]')
            $uncAbsolute=($inputFolder -match '^\\\\[^\\]+\\[^\\]+(?:\\|$)')
            if((-not [IO.Path]::IsPathRooted($inputFolder)) -or (-not($driveAbsolute -or $uncAbsolute))){
                throw 'Alternate Save As folder must be a fully qualified Windows path, not Downloads or a drive-relative path.'
            }
            if(-not (Test-Path -LiteralPath $inputFolder -PathType Container)){throw 'Owner-supplied absolute Save As folder does not exist.'}
            $chosen=(Resolve-Path -LiteralPath $inputFolder).Path
            $chosenItem=Get-Item -LiteralPath $chosen -Force
            if(($chosenItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
                throw 'Refusing linked or redirected alternate export folder.'
            }
            $report.alternate_location='OWNER_CONFIRMED_ABSOLUTE_FOLDER'
        }else{
            $report.alternate_location='NOT_SUPPLIED_OR_NOT_USED'
        }
    }
    $htmlFile=Join-Path $chosen $manifest.exports.html.filename
    $pdfFile=Join-Path $chosen $manifest.exports.pdf.filename
    $htmlOk=File-Match $htmlFile ([string]$manifest.exports.html.sha256) 'HTML real report saved bytes'
    $pdfOk=File-Match $pdfFile ([string]$manifest.exports.pdf.sha256) 'PDF real report saved bytes'
    $report.report_outputs=$(if($htmlOk -and $pdfOk){'BOTH_SHA256_MATCH_REAL_API'}else{'MISSING_OR_SHA_MISMATCH'})
    $report.save_verification=$(if($chosen -ieq $saveTarget){'DEFAULT_DEVQA_EXPORTS'}else{'OWNER_ABSOLUTE_ALTERNATE'})
    Mark 'p2-real-report-native-saved-byte-integrity' ($htmlOk -and $pdfOk)
    # Source immutability must be checked even when an export is missing.
    $source=Join-Path $isolatedWorkspaceHome $manifest.source_relative
    $sourceOk=(Test-Path -LiteralPath $source -PathType Leaf) -and
        ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -eq $manifest.source_sha256)
    Mark 'p2-synthetic-source-unchanged' $sourceOk
    if(-not $sourceOk){throw 'Original synthetic CSV was modified.'}
    if(-not($htmlOk -and $pdfOk)){throw 'Native Save As content not verified: expected file missing or SHA mismatch. No files were renamed or moved.'}
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
    $qaManifest.state=$(if($report.overall -eq 'PASS'){'P2_SYNTHETIC_DEV_PASS'}else{'P2_SYNTHETIC_DEV_FAIL'})
    $qaManifest | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath $qaManifestPath -Encoding UTF8
    $report | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath $reportFile -Encoding UTF8
    # The synthetic-only reference manifest allows independent SHA verification of a red gate.
    # Never bundle the source CSV, actual saved exports or user datasets.
    $files=@($reportFile,$manifestPath,$qaManifestPath,$seedLog,$backendOut,$backendErr,$buildLog,$nativeLog,
        (Join-Path $logDir 'devqa-preflight.json'),(Join-Path $logDir 'devqa-selftests.log')) | Where-Object {Test-Path $_}
    Compress-Archive -LiteralPath $files -DestinationPath $archive -Force
    Write-Host ('P2 live API-to-native export gate: '+$report.overall) -ForegroundColor $(if($report.overall -eq 'PASS'){'Green'}else{'Red'})
    Write-Host ('One diagnostic ZIP (logs may contain test-local paths): '+$archive)
}
if($report.overall -ne 'PASS'){exit 1}
exit 0
