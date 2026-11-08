# Automated, disposable P3 W5 Windows Tauri acceptance. One owner UI observation.
# No installer, model, user datasets or unapproved transformations.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$phase='P3-NATIVE-QUALITY-W5'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend=Join-Path $root 'frontend'
$pythonExe=Join-Path $root '.venv-live\Scripts\python.exe'
$allocator=Join-Path $PSScriptRoot 'qa_foundation.py'
$seeder=Join-Path $PSScriptRoot 'Seed_P3_Native_Quality_W5_Local.py'
$historyVerifier=Join-Path $PSScriptRoot 'Verify_P3_Native_Quality_W5_History_Local.py'
$statusVerifier=Join-Path $PSScriptRoot 'Verify_P3_Native_Quality_W5_Status.py'
$config=Join-Path $frontend 'src-tauri\tauri.p3-native-quality-w5-qa.conf.json'
$runDir=$null
$backendProcess=$null
$exitCode=1
$record=[ordered]@{
 phase=$phase
 state='BLOCKED'
 product_acceptance='NOT_TESTED'
 source_head='NOT_ATTESTED'
 source_worktree='NOT_CHECKED'
 native_mode='NOT_TESTED'
 original_sha256='NOT_CHECKED'
 quality_version='NOT_CHECKED'
 version_history='NOT_CHECKED'
 stale_semantic_get='NOT_CHECKED'
 stale_semantic_post='NOT_CHECKED'
 current_semantic_context='NOT_CHECKED'
 historical_semantic_context='NOT_CHECKED'
 request_audit='NOT_CHECKED'
 owner_native_ui='NOT_OBSERVED'
 installer='NOT_BUILT'
 model_or_ai='NOT_LAUNCHED'
 scope='SYNTHETIC_NATIVE_P3_W5_ONLY'
 failure_category=''
}
$ownedNames=@('PILOTODIN_HOME','PILOTODIN_DESKTOP_SESSION','PILOTODIN_DESKTOP_ALLOW_DEV',
 'VITE_PILOTODIN_NATIVE_SMOKE','VITE_P3_NATIVE_QUALITY_W5_QA',
 'VITE_P3_NATIVE_W5_PROJECT','VITE_P3_NATIVE_W5_ISSUE','CARGO_NET_OFFLINE')
$previousEnvironment=@{}
foreach($name in $ownedNames){
 $previousEnvironment[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
function Port-Occupied([int]$number){
 $client=New-Object Net.Sockets.TcpClient
 try{
  $task=$client.ConnectAsync('127.0.0.1',$number)
  return ($task.Wait(350) -and $client.Connected)
 }catch{return $false}
 finally{$client.Close()}
}
function Wait-Project([string]$projectId){
 for($i=0;$i -lt 80;$i++){
  try{
   $result=Invoke-RestMethod -Uri ('http://127.0.0.1:8000/api/projects/'+$projectId) -TimeoutSec 2
   if($result.id -eq $projectId){return $true}
  }catch{}
  Start-Sleep -Milliseconds 250
 }
 return $false
}
function Read-Expected([string]$path){
 return Invoke-RestMethod -Uri ('http://127.0.0.1:8000/api'+$path) -Method GET -TimeoutSec 12
}
function Denied-Expected([string]$path,[string]$method,[object]$payload){
 $status=0
 try{
  $args=@{Uri=('http://127.0.0.1:8000/api'+$path);Method=$method;TimeoutSec=12;UseBasicParsing=$true}
  if($method -eq 'POST'){
   $args.ContentType='application/json'
   $args.Body=($payload | ConvertTo-Json -Depth 5 -Compress)
  }
  $res=Invoke-WebRequest @args
  $status=[int]$res.StatusCode
 }catch{
  if(-not $_.Exception.Response){throw}
  $status=[int]$_.Exception.Response.StatusCode
 }
 if($status -ne 409){throw ('Expected stale semantic HTTP 409, received '+$status)}
}
try{
 if($env:OS -ne 'Windows_NT'){throw 'Requires physical Windows Tauri/WebView2; no native test ran.'}
 foreach($file in @($pythonExe,$allocator,$seeder,$historyVerifier,$statusVerifier,$config,
   (Join-Path $frontend 'p3_native_quality_w5_qa.html'),
   (Join-Path $frontend 'src\p3NativeQualityW5Qa.tsx'))){
  if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
   throw ('Missing existing native QA prerequisite: '+$file)
  }
 }
 if(-not(Test-Path -LiteralPath (Join-Path $frontend 'node_modules') -PathType Container)){
  throw 'Pre-existing node_modules required. No dependencies will be installed.'
 }
 $npm=(Get-Command npm.cmd -ErrorAction Stop).Source
 $null=Get-Command cargo.exe -ErrorAction Stop
 $git=(Get-Command git.exe -ErrorAction Stop).Source
 $branch=(& $git -C $root branch --show-current).Trim()
 if($branch -ne 'feature/live-dev-workspace-20261023'){throw ('Unexpected branch: '+$branch)}
 $record.source_head=(& $git -C $root rev-parse HEAD).Trim()
 if($record.source_head -notmatch '^[a-f0-9]{40}$'){throw 'Cannot attest source commit.'}
 # Never ignore tracked changes. Only three exact, untracked Tauri build
 # artifacts may coexist with clean tracked source during this synthetic QA.
 # Keep Cargo.lock visible for future dependency/release review; do not globally
 # gitignore it, auto-delete it, stash it or mark it as tracked.
 $changes=@(& $git -C $root status --porcelain --untracked-files=normal)
 if($LASTEXITCODE -ne 0){throw 'Git status failed; refusing to alter owner work.'}
 $allowedTauriUntracked=@(
  '?? frontend/src-tauri/Cargo.lock',
  '?? frontend/src-tauri/gen/',
  '?? frontend/src-tauri/target/'
 )
 $unexpectedChanges=@($changes | Where-Object { $_ -notin $allowedTauriUntracked })
 if($unexpectedChanges.Count -gt 0){
  $record.source_worktree='UNCOMMITTED_OWNER_WORK'
  Write-Host 'Unreviewed source/worktree changes detected. Preserve them in GitHub Desktop.' -ForegroundColor Yellow
  @($unexpectedChanges | Select-Object -First 12) | ForEach-Object {Write-Host ('  '+$_)}
  throw 'Require clean tracked source; no files were modified.'
 }
 if($changes.Count -gt 0){
  $record.source_worktree='TRACKED_CLEAN_EXPECTED_UNTRACKED_TAURI'
  Write-Host 'Tracked source clean; only known untracked Tauri outputs remain. Preserving them.' -ForegroundColor Cyan
  @($changes | Select-Object -First 3) | ForEach-Object {Write-Host ('  '+$_)}
 }else{
  $record.source_worktree='CLEAN'
 }
 if(Port-Occupied 8000 -or Port-Occupied 5178){
  throw 'Ports 8000 or 5178 already occupied. Refusing to stop another process.'
 }
 $tokens=$null;$parserErrors=$null
 [System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath,[ref]$tokens,[ref]$parserErrors)|Out-Null
 if($parserErrors -and $parserErrors.Count){throw 'PowerShell parser failed.'}
 Push-Location $root
 try{$raw=@(& $pythonExe -B $allocator init --phase $phase --json);$allocatedCode=$LASTEXITCODE}
 finally{Pop-Location}
 if($allocatedCode -ne 0){throw 'DevQA allocation failed.'}
 $allocation=($raw | Out-String | ConvertFrom-Json)
 if($allocation.status -ne 'READY_NOT_TESTED' -or $allocation.product_acceptance -ne 'NOT_TESTED'){
  throw 'DevQA allocation did not return an unused QA run.'
 }
 $runDir=[string]$allocation.run_dir
 if(-not [IO.Path]::IsPathRooted($runDir) -or
   (Split-Path $runDir -Leaf) -notmatch '^P3-NATIVE-QUALITY-W5-[0-9TZ]+-[a-f0-9]{10}$'){
  throw 'Unexpected W5 QA run identity.'
 }
 $workspaceDir=Join-Path $runDir 'workspace'
 $manifestFile=Join-Path $runDir 'fixtures\p3-native-w5-manifest.json'
 $backendStdout=Join-Path $runDir 'logs\backend-stdout.log'
 $backendStderr=Join-Path $runDir 'logs\backend-stderr.log'
 $frontendLog=Join-Path $runDir 'logs\frontend-build.log'
 $nativeLog=Join-Path $runDir 'logs\native-shell.log'
 Write-Host ('Isolated native W5 QA: '+$runDir) -ForegroundColor Cyan
 $env:PILOTODIN_HOME=$workspaceDir
 Remove-Item Env:\PILOTODIN_DESKTOP_SESSION -ErrorAction SilentlyContinue
 Remove-Item Env:\PILOTODIN_DESKTOP_ALLOW_DEV -ErrorAction SilentlyContinue
 $env:VITE_PILOTODIN_NATIVE_SMOKE='1'
 $env:VITE_P3_NATIVE_QUALITY_W5_QA='1'
 $env:CARGO_NET_OFFLINE='true'
 Push-Location $root
 try{& $pythonExe -B $seeder $manifestFile;$seedCode=$LASTEXITCODE}
 finally{Pop-Location}
 if($seedCode -ne 0 -or -not(Test-Path -LiteralPath $manifestFile -PathType Leaf)){
  throw 'Synthetic v0 Quality seeding failed.'
 }
 $manifest=Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
 if($manifest.phase -ne $phase -or $manifest.run_id -ne (Split-Path $runDir -Leaf) -or
    $manifest.project_id -notmatch '^[a-f0-9]{32}$' -or
    [string]::IsNullOrWhiteSpace([string]$manifest.issue_id) -or
    $manifest.rows -ne 36 -or $manifest.expected_changed_cells -ne 2 -or $manifest.version -ne 0){
  throw 'Synthetic W5 fixture manifest did not match the expected scope.'
 }
 $id=[string]$manifest.project_id
 $env:VITE_P3_NATIVE_W5_PROJECT=$id
 $env:VITE_P3_NATIVE_W5_ISSUE=[string]$manifest.issue_id
 $original=[IO.Path]::GetFullPath((Join-Path $workspaceDir ([string]$manifest.source_relative)))
 $prefix=[IO.Path]::GetFullPath($workspaceDir).TrimEnd('\')+'\'
 if(-not $original.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or
    -not(Test-Path -LiteralPath $original -PathType Leaf)){throw 'Original fixture path is not isolated.'}
 if((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash -ine $manifest.original_sha256){
  throw 'Synthetic original checksum mismatch before launch.'
 }
 $backendProcess=Start-Process -FilePath $pythonExe -WorkingDirectory $root -ArgumentList @(
  '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--lifespan','off'
 ) -PassThru -NoNewWindow -RedirectStandardOutput $backendStdout -RedirectStandardError $backendStderr
 if(-not(Wait-Project $id)){throw 'Isolated FastAPI backend did not become available.'}
 Push-Location $frontend
 try{
  $oldPref=$ErrorActionPreference;$ErrorActionPreference='Continue'
  & $npm run build 2>&1 | Tee-Object -FilePath $frontendLog
  $buildCode=$LASTEXITCODE
 }finally{$ErrorActionPreference=$oldPref;Pop-Location}
 if($buildCode -ne 0){throw 'TypeScript/Vite failed. No native UI was launched.'}
 Write-Host ''
 Write-Host 'ONLY TWO NATIVE UI ACTIONS APPLY THE SYNTHETIC CORRECTION:' -ForegroundColor Cyan
 Write-Host '1. In Quality, open Region / Surrounding whitespace and click Review this correction.'
 Write-Host '2. In the exact review dialog, inspect 2 affected cells and click Approve these changes.'
 Write-Host '3. Confirm Quality says WORKING VERSION 1 and Your data has no old version-0 notes.'
 Write-Host 'In Your data, inspect empty v1 descriptions. After 12s W5 finishes automatically.'
 Write-Host 'Use Finish W5 QA and verify only as fallback; automatic audit and ZIP follow.'
 Write-Host 'Never upload, export, train, use Ask ODIN, or use a real project in this run.'
 Push-Location $frontend
 try{
  $oldPref=$ErrorActionPreference;$ErrorActionPreference='Continue'
  & $npm run desktop:dev -- --config src-tauri/tauri.p3-native-quality-w5-qa.conf.json 2>&1 |
    Tee-Object -FilePath $nativeLog
  $nativeCode=$LASTEXITCODE
 }finally{$ErrorActionPreference=$oldPref;Pop-Location}
 if($nativeCode -ne 0){throw 'Native Tauri W5 QA window exited with an error.'}
 $record.native_mode='OWNER_WINDOW_CLOSED_WITH_ZERO_TAURI_EXIT'
 $quality=Read-Expected ('/projects/'+$id+'/quality')
 if($quality.version -ne 1){throw 'Actual native UI did not complete exactly one reviewed Quality v0-to-v1 action.'}
 $record.quality_version='PASS_V0_TO_V1'
 $history=Read-Expected ('/projects/'+$id+'/quality/history')
 $versions=@($history.versions | ForEach-Object {[int]$_.version})
 if($history.current_version -ne 1 -or
    ($versions -join ',') -ne '0,1'){throw 'Unexpected Quality version history.'}
 $record.version_history='PASS_EXACTLY_V0_V1'
 $v1=Read-Expected ('/projects/'+$id+'/semantics?expected_version=1')
 if($v1.version -ne 1 -or $null -ne $v1.user_context){
  throw 'Previous unverified semantic descriptions silently transferred to version one.'
 }
 $record.current_semantic_context='PASS_EMPTY_V1'
 $preview=Read-Expected ('/projects/'+$id+'/quality/preview?offset=0&limit=10&expected_version=1')
 if($preview.version -ne 1 -or @($preview.rows).Count -lt 3 -or
    $preview.rows[1].original.Region -cne ' Mpumalanga ' -or
    $preview.rows[1].working.Region -cne 'Mpumalanga' -or
    $preview.rows[2].original.Region -cne ' Mpumalanga ' -or
    $preview.rows[2].working.Region -cne 'Mpumalanga'){
  throw 'Original versus approved working Region cells do not match expected W5 values.'
 }
 Denied-Expected ('/projects/'+$id+'/semantics?expected_version=0') 'GET' $null
 $record.stale_semantic_get='PASS_HTTP_409'
 $stale=@{
  expected_version=0
  domain_description='Synthetic old version context must not migrate'
  record_grain_description='One original synthetic insurance claim per row'
  field_definitions=@(@{column='claim_amount';meaning='Synthetic requested amount for old version'})
 }
 Denied-Expected ('/projects/'+$id+'/semantic-business-context') 'POST' $stale
 $record.stale_semantic_post='PASS_HTTP_409'
 # Existing v0 human descriptions must remain durable, not just absent on v1.
 # Verify read-only SQLite state in this isolated disposable workspace.
 Push-Location $root
 try{
  $historyOutput=@(& $pythonExe -B $historyVerifier $workspaceDir $manifestFile)
  $historyCode=$LASTEXITCODE
 }finally{Pop-Location}
 if($historyCode -ne 0){throw 'Synthetic v0 semantic history was not preserved; DB read-only gate failed.'}
 $historyResult=($historyOutput | Out-String | ConvertFrom-Json)
 if($historyResult.state -ne 'PASS_V0_RETAINED_V1_ABSENT' -or
    $historyResult.evidence -ne 'ISOLATED_SQLITE_READ_ONLY' -or
    $historyResult.product_acceptance -ne 'NOT_TESTED'){
  throw 'Synthetic v0 semantic history verifier did not prove the expected isolated state.'
 }
 $record.historical_semantic_context='PASS_V0_RETAINED_V1_ABSENT'
 if((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash -ine $manifest.original_sha256){
  throw 'Original synthetic source changed after Quality commit.'
 }
 $record.original_sha256='PASS_UNCHANGED'
 $access=if(Test-Path -LiteralPath $backendStdout -PathType Leaf){
  Get-Content -LiteralPath $backendStdout -Raw -ErrorAction SilentlyContinue
 }else{''}
 $mutations=@([regex]::Matches($access,'(?m)"(?:POST|PUT|PATCH|DELETE) /api/[^\r\n]+'))
 $expected=@(
  'POST /api/projects/'+$id+'/quality/proposals HTTP/1.1" 200',
  'POST /api/projects/'+$id+'/quality/commit HTTP/1.1" 200',
  'POST /api/projects/'+$id+'/semantic-business-context HTTP/1.1" 409'
 )
 if($mutations.Count -ne 3){throw ('Unexpected number of backend write requests: '+$mutations.Count)}
 for($i=0;$i -lt 3;$i++){
  if(-not $mutations[$i].Value.Contains($expected[$i])){
   throw ('Unexpected backend mutation request or order at audit index '+$i)
  }
 }
 $record.request_audit='PASS_ONE_PROPOSAL_ONE_UI_COMMIT_ONE_REJECTED_STALE_POST'
 $response=(Read-Host 'Observed ACTUAL native WebView2 working v1 and empty Your data v1 notes? [yes/no]').Trim().ToLowerInvariant()
 if($response -notin @('yes','y')){throw 'Owner native visual W5 observation was not confirmed.'}
 $record.owner_native_ui='OWNER_REPORTED_PASS'
 $record.state='REVIEW_REQUIRED'
 $record.product_acceptance='NOT_TESTED'
 $exitCode=0
 Write-Host 'W5 native owner observation and automated version, integrity, stale and HTTP audit passed.' -ForegroundColor Green
 Write-Host 'This is scoped QA evidence for independent review, not release certification.' -ForegroundColor Cyan
}catch{
 $record.state='FAIL_OR_BLOCKED'
 $record.failure_category=$_.Exception.Message
 Write-Host ('P3 native W5 NOT ACCEPTED: '+$record.failure_category) -ForegroundColor Red
 $exitCode=1
}finally{
 if($backendProcess -and -not $backendProcess.HasExited){
  try{Stop-Process -Id $backendProcess.Id -Force -ErrorAction Stop}
  catch{Write-Warning 'Test-owned backend PID could not be stopped; do not stop unrelated processes.'}
 }
 foreach($name in $ownedNames){
  [Environment]::SetEnvironmentVariable($name,$previousEnvironment[$name],'Process')
 }
 if($runDir -and (Test-Path -LiteralPath $runDir -PathType Container)){
  try{
   $recordFile=Join-Path $runDir 'diagnostics\result.json'
   $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $recordFile -Encoding UTF8
   $archiveDir=Join-Path (Split-Path (Split-Path $runDir -Parent) -Parent) 'archive'
   $archive=Join-Path $archiveDir ((Split-Path $runDir -Leaf)+'-p3-w5-status.zip')
   $files=@($recordFile,(Join-Path $runDir 'manifest.json'),(Join-Path $runDir 'fixtures\p3-native-w5-manifest.json')) |
     Where-Object {Test-Path -LiteralPath $_ -PathType Leaf}
   Compress-Archive -LiteralPath $files -DestinationPath $archive -ErrorAction Stop
   if($exitCode -eq 0){
    # Run the existing read-only status verifier as part of the same one-click
    # procedure. This is local self-check, NOT independent WebView2 acceptance.
    # Trust only the actual exit code AND its scoped JSON verdict.
    $inspectionText=@(& $pythonExe -B $statusVerifier $archive --expected-source ([string]$record.source_head))
    $inspectionCode=$LASTEXITCODE
    $inspected=$null
    if($inspectionCode -eq 0){
     try{$inspected=($inspectionText | Out-String | ConvertFrom-Json)}
     catch{$inspected=$null}
    }
    if($inspectionCode -ne 0 -or $null -eq $inspected -or
       $inspected.verdict -ne 'STATUS_ARCHIVE_INTEGRITY_PASS' -or
       $inspected.native_acceptance -ne 'PENDING_INDEPENDENT_REVIEW' -or
       $inspected.product_acceptance -ne 'NOT_TESTED' -or
       $inspected.source_sha_matches_supplied_expectation -ne $true){
     $record.state='FAIL_OR_BLOCKED'
     $record.failure_category='STATUS_ONLY_ZIP_SELF_CHECK_FAILED'
     $exitCode=1
     $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $recordFile -Encoding UTF8
     Compress-Archive -LiteralPath $files -DestinationPath $archive -Force -ErrorAction Stop
     Write-Warning 'P3 W5 status archive local self-check failed. Status is BLOCKED, not accepted.'
    }else{
     Write-Host 'Status-only ZIP integrity self-check PASS (native evidence still requires independent review).' -ForegroundColor Green
    }
   }
   Write-Host ('Status-only QA evidence (no datasets or logs): '+$archive) -ForegroundColor Cyan
  }catch{
   $exitCode=1
   Write-Warning ('P3 W5 evidence generation or self-check failed; result NOT accepted: '+$_.Exception.Message)
  }
 }
}
exit $exitCode
