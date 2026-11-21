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
$functionalProbe=Join-Path $PSScriptRoot 'P3_W5_Functional_Probe.py'
$functionalReader=Join-Path $PSScriptRoot 'Read_P3_W5_Functional_Result.ps1'
$config=Join-Path $frontend 'src-tauri\tauri.p3-native-quality-w5-qa.conf.json'
$runDir=$null
$backendProcess=$null
$probeProcess=$null
$probeResultFile=$null
$exitCode=1
$record=[ordered]@{
 phase=$phase
 state='BLOCKED'
 product_acceptance='NOT_TESTED'
 source_head='NOT_ATTESTED'
 source_worktree='NOT_CHECKED'
 native_mode='NOT_TESTED'
 native_shutdown_status='NOT_TESTED'
 functional_state='NOT_TESTED'
 functional_failure_category=''
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
try{
 if($env:OS -ne 'Windows_NT'){throw 'Requires physical Windows Tauri/WebView2; no native test ran.'}
 foreach($file in @($pythonExe,$allocator,$seeder,$historyVerifier,$statusVerifier,$functionalProbe,$functionalReader,$config,
   (Join-Path $frontend 'p3_native_quality_w5_qa.html'),
   (Join-Path $frontend 'src\p3NativeQualityW5Qa.tsx'))){
  if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
   throw ('Missing existing native QA prerequisite: '+$file)
  }
 }
 # Shared with the real Windows known-good/bad harness classification self-test.
 . $functionalReader
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
 # Start an independent data verifier WHILE the native QA window is open.
 # Its only write is an intentionally rejected stale semantic POST (HTTP 409).
 $probeResultFile=Join-Path $runDir 'diagnostics\functional-result.json'
 $probeOut=Join-Path $runDir 'logs\functional-probe-stdout.log'
 $probeErr=Join-Path $runDir 'logs\functional-probe-stderr.log'
 $probeProcess=Start-Process -FilePath $pythonExe -WorkingDirectory $root -ArgumentList @(
  '-B','-m','tools.P3_W5_Functional_Probe'
 ) -PassThru -NoNewWindow -RedirectStandardOutput $probeOut -RedirectStandardError $probeErr
 Write-Host 'Independent W5 data probe started. Native window exit cannot overwrite data results.' -ForegroundColor Cyan
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
 # Merge isolated data evidence FIRST, independent of native window exit.
 if($probeProcess -and -not $probeProcess.HasExited){
  $null=$probeProcess.WaitForExit(15000)
 }
 $functionalState=Import-P3W5FunctionalReport -Path $probeResultFile -Record $record
 $record.native_shutdown_status=if($nativeCode -eq 0){'PASS_ZERO_EXIT'}else{'FAIL_NONZERO_EXIT'}
 if($nativeCode -ne 0){
  throw ('Native QA window exit failed (code '+$nativeCode+
   '), but independent data result is '+$functionalState)
 }
 $record.native_mode='OWNER_WINDOW_CLOSED_WITH_ZERO_TAURI_EXIT'
 if($functionalState -ne 'PASS'){
  throw ('Native QA closed but independent data verification did not pass: '+$functionalState)
 }
 Write-Host 'Independent data and native close checks passed; confirm your own observation.' -ForegroundColor Green
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
 # When native launch/exit fails, preserve already completed functional checks.
 # Stop only our test-owned probe, never arbitrary processes or user projects.
 if($probeProcess){
  try{
   if(-not $probeProcess.HasExited){$null=$probeProcess.WaitForExit(6000)}
   if(-not $probeProcess.HasExited){
    Stop-Process -Id $probeProcess.Id -ErrorAction Stop
    Write-Warning 'Isolated W5 functional probe incomplete. No data acceptance assumed.'
   }
  }catch{Write-Warning 'Could not stop only the owned probe process.'}
 }
 if($probeResultFile){
  $null=Import-P3W5FunctionalReport -Path $probeResultFile -Record $record
 }
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
