# P3 owner-only native WebView2 acceptance. Disposable two-project QA; no installers.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$phase='P3-NATIVE-SEMANTIC-CONTEXT'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend=Join-Path $root 'frontend'
$pythonExe=Join-Path $root '.venv-live\Scripts\python.exe'
$allocator=Join-Path $PSScriptRoot 'qa_foundation.py'
$seeder=Join-Path $PSScriptRoot 'Seed_P3_Native_Semantic_Context_Local.py'
$config=Join-Path $frontend 'src-tauri\tauri.p3-native-semantic-qa.conf.json'
$runDir=$null
$backendProcess=$null
$exitCode=1
$record=[ordered]@{
 phase=$phase
 state='BLOCKED'
 product_acceptance='NOT_TESTED'
 native_mode='NOT_TESTED'
 source_head='NOT_ATTESTED'
 source_worktree='NOT_CHECKED'
 source_integrity='NOT_CHECKED'
 semantic_save_requests='NOT_CHECKED'
 observations=[ordered]@{}
 installer='NOT_BUILT'
 model_or_ai='NOT_LAUNCHED'
 scope='P3_OWNER_NATIVE_WEBVIEW2_SYNTHETIC_TWO_PROJECTS_ONLY'
 failure_category=''
}
$ownedNames=@('PILOTODIN_HOME','PILOTODIN_DESKTOP_SESSION','PILOTODIN_DESKTOP_ALLOW_DEV',
 'VITE_PILOTODIN_NATIVE_SMOKE','VITE_P3_NATIVE_SEMANTIC_QA',
 'VITE_P3_NATIVE_QA_PROJECT_A','VITE_P3_NATIVE_QA_PROJECT_B','CARGO_NET_OFFLINE')
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
function Owner-Check([string]$key,[string]$prompt){
 Write-Host ''
 Write-Host $prompt -ForegroundColor Cyan
 $answer=(Read-Host 'Observed in the ACTUAL native WebView2 window? [yes/no]').Trim().ToLowerInvariant()
 $ok=$answer -in @('yes','y')
 $record.observations[$key]=$(if($ok){'OWNER_REPORTED_PASS'}else{'FAIL_OR_NOT_OBSERVED'})
 return $ok
}
try{
 if($env:OS -ne 'Windows_NT'){throw 'Requires Windows; native WebView2 was not tested.'}
 foreach($file in @($pythonExe,$allocator,$seeder,$config,
   (Join-Path $frontend 'p3_native_semantic_qa.html'),
   (Join-Path $frontend 'src\p3NativeSemanticQa.tsx'))){
  if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
   throw ('Required existing source/runtime is missing: '+$file)
  }
 }
 if(-not(Test-Path -LiteralPath (Join-Path $frontend 'node_modules') -PathType Container)){
  throw 'Pre-existing node_modules required. The runner does not install dependencies.'
 }
 $npm=(Get-Command npm.cmd -ErrorAction Stop).Source
 $null=Get-Command cargo.exe -ErrorAction Stop
 $git=(Get-Command git.exe -ErrorAction Stop).Source
 $branch=(& $git -C $root branch --show-current).Trim()
 if($branch -ne 'feature/live-dev-workspace-20261023'){
  throw ('Unexpected source branch: '+$branch)
 }
 $record.source_head=(& $git -C $root rev-parse HEAD).Trim()
 if($record.source_head -notmatch '^[a-f0-9]{40}$'){throw 'Cannot attest exact Git SHA.'}
 $changes=@(& $git -C $root status --porcelain)
 if($changes.Count -gt 0){
  $record.source_worktree='UNCOMMITTED_OWNER_FILES_PRESENT'
  throw 'Source checkout is dirty; no owner work was modified. Use a clean QA checkout.'
 }
 $record.source_worktree='CLEAN'
 if(Port-Occupied 8000 -or Port-Occupied 5178){
  throw 'Ports 8000 or 5178 already in use. Refusing to stop another process.'
 }
 $tokens=$null
 $parserErrors=$null
 [System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath,[ref]$tokens,[ref]$parserErrors)|Out-Null
 if($parserErrors -and $parserErrors.Count){throw 'PowerShell runner syntax preflight failed.'}
 Push-Location $root
 try{
  $raw=@(& $pythonExe -B $allocator init --phase $phase --json)
  $allocationCode=$LASTEXITCODE
 }finally{Pop-Location}
 if($allocationCode -ne 0){throw 'DevQA allocator did not create a new run.'}
 $allocation=($raw | Out-String | ConvertFrom-Json)
 if($allocation.status -ne 'READY_NOT_TESTED' -or $allocation.product_acceptance -ne 'NOT_TESTED'){
  throw 'DevQA allocator returned an unexpected status.'
 }
 $runDir=[string]$allocation.run_dir
 if(-not [IO.Path]::IsPathRooted($runDir) -or
    (Split-Path $runDir -Leaf) -notmatch '^P3-NATIVE-SEMANTIC-CONTEXT-[0-9TZ]+-[a-f0-9]{10}$'){
  throw 'DevQA run identity is not recognised.'
 }
 $workspaceDir=Join-Path $runDir 'workspace'
 $manifestFile=Join-Path $runDir 'fixtures\p3-native-semantic-manifest.json'
 $backendStdout=Join-Path $runDir 'logs\backend-stdout.log'
 $backendStderr=Join-Path $runDir 'logs\backend-stderr.log'
 $frontendLog=Join-Path $runDir 'logs\frontend-build.log'
 $nativeLog=Join-Path $runDir 'logs\native-shell.log'
 Write-Host ('Isolated P3 native QA run: '+$runDir) -ForegroundColor Cyan
 $env:PILOTODIN_HOME=$workspaceDir
 Remove-Item Env:\PILOTODIN_DESKTOP_SESSION -ErrorAction SilentlyContinue
 Remove-Item Env:\PILOTODIN_DESKTOP_ALLOW_DEV -ErrorAction SilentlyContinue
 $env:VITE_PILOTODIN_NATIVE_SMOKE='1'
 $env:VITE_P3_NATIVE_SEMANTIC_QA='1'
 $env:CARGO_NET_OFFLINE='true'
 Push-Location $root
 try{
  & $pythonExe -B $seeder $manifestFile
  $seedCode=$LASTEXITCODE
 }finally{Pop-Location}
 if($seedCode -ne 0 -or -not(Test-Path -LiteralPath $manifestFile -PathType Leaf)){
  throw 'Synthetic project seeding failed.'
 }
 $manifest=Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
 if($manifest.phase -ne $phase -or $manifest.run_id -ne (Split-Path $runDir -Leaf) -or
    @($manifest.projects).Count -ne 2){throw 'Synthetic two-project manifest is invalid.'}
 $ids=@($manifest.projects | ForEach-Object {[string]$_.id})
 if($ids[0] -notmatch '^[a-f0-9]{32}$' -or $ids[1] -notmatch '^[a-f0-9]{32}$' -or $ids[0] -eq $ids[1]){
  throw 'Expected distinct synthetic A/B project IDs.'
 }
 $env:VITE_P3_NATIVE_QA_PROJECT_A=$ids[0]
 $env:VITE_P3_NATIVE_QA_PROJECT_B=$ids[1]
 $backendProcess=Start-Process -FilePath $pythonExe -WorkingDirectory $root -ArgumentList @(
  '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--lifespan','off'
 ) -PassThru -NoNewWindow -RedirectStandardOutput $backendStdout -RedirectStandardError $backendStderr
 foreach($id in $ids){
  if(-not(Wait-Project $id)){throw 'Synthetic local FastAPI backend failed to start.'}
 }
 Push-Location $frontend
 try{
  $oldPreference=$ErrorActionPreference
  $ErrorActionPreference='Continue'
  & $npm run build 2>&1 | Tee-Object -FilePath $frontendLog
  $buildCode=$LASTEXITCODE
 }finally{$ErrorActionPreference=$oldPreference;Pop-Location}
 if($buildCode -ne 0){throw 'TypeScript/Vite build failed; native window not launched.'}
 Write-Host ''
 Write-Host 'NATIVE WINDOWS TEST ONLY. Synthetic A and B, never installed projects.' -ForegroundColor Cyan
 Write-Host 'W1: In Your data > Data dictionary > Business meaning, enter the synthetic domain, row meaning and claim_amount field meaning.'
 Write-Host '     BEFORE Save, attempt Switch project B. Choose Stay. Confirm A typed text remains.'
 Write-Host '     Save business descriptions for A, and verify user-described/unverified labels.'
 Write-Host 'W2: Reload/reopen A, check saved fields, edit the domain and Save a second time.'
 Write-Host 'W3: Switch to B. Its user descriptions must be empty. Switch back to A to see only A notes.'
 Write-Host 'W4: Use keyboard Tab/Enter/Space in the real window. Short descriptions must disable Save.'
 Write-Host 'DO NOT use any other Save, upload, Quality edit, training, ODIN, export, or original project.'
 Write-Host 'Close the native QA window after testing; then answer the five owner questions.'
 Push-Location $frontend
 try{
  $oldPreference=$ErrorActionPreference
  $ErrorActionPreference='Continue'
  & $npm run desktop:dev -- --config src-tauri/tauri.p3-native-semantic-qa.conf.json 2>&1 |
    Tee-Object -FilePath $nativeLog
  $nativeCode=$LASTEXITCODE
 }finally{$ErrorActionPreference=$oldPreference;Pop-Location}
 if($nativeCode -ne 0){throw 'Native Tauri development shell failed or exited with an error.'}
 $record.native_mode='OWNER_WINDOW_CLOSED_WITH_ZERO_TAURI_EXIT'
 $observations=@(
  (Owner-Check 'w1_dirty_switch_stay' 'W1a: Native Switch project / Stay prevented discarding unsaved descriptions and kept A open.'),
  (Owner-Check 'w1_save' 'W1b: Explicit Save A persisted synthetic business descriptions and labelled them unverified.'),
  (Owner-Check 'w2_reload_edit' 'W2: Reload/reopen A restored notes; edited domain saved successfully a second time.'),
  (Owner-Check 'w3_project_isolation' 'W3: Project B never displayed A owner notes; returning to A restored A notes.'),
  (Owner-Check 'w4_keyboard_validation' 'W4: Keyboard navigation and native controls were usable; invalid short text disabled Save.')
 )
 if($observations -contains $false){throw 'One or more native observations failed or were not completed.'}
 foreach($entry in $manifest.projects){
  $datasetPath=[IO.Path]::GetFullPath((Join-Path $workspaceDir ([string]$entry.source_relative)))
  $workspacePrefix=[IO.Path]::GetFullPath($workspaceDir).TrimEnd('\')+'\'
  if(-not $datasetPath.StartsWith($workspacePrefix,[StringComparison]::OrdinalIgnoreCase)){
   throw 'Synthetic source path escaped isolated workspace.'
  }
  if(-not(Test-Path -LiteralPath $datasetPath -PathType Leaf) -or
     (Get-FileHash -LiteralPath $datasetPath -Algorithm SHA256).Hash -ine $entry.sha256){
   throw 'Original synthetic source changed or is missing.'
  }
 }
 $record.source_integrity='PASS'
 $access=if(Test-Path -LiteralPath $backendStdout -PathType Leaf){
  Get-Content -LiteralPath $backendStdout -Raw -ErrorAction SilentlyContinue
 }else{''}
 $mutations=@([regex]::Matches($access,'(?m)"(?:POST|PUT|PATCH|DELETE) /api/[^\r\n]+'))
 $expected='POST /api/projects/'+$ids[0]+'/semantic-business-context HTTP/1.1" 200'
 if($mutations.Count -ne 2 -or @($mutations | Where-Object {$_.Value -notlike ('*'+$expected+'*')}).Count -gt 0){
  $record.semantic_save_requests='UNEXPECTED_OR_MISSING_WRITE_REQUESTS'
  throw 'Expected exactly two successful synthetic A semantic POSTs and no other mutation requests.'
 }
 $record.semantic_save_requests='TWO_APPROVED_SYNTHETIC_A_SAVES_ONLY'
 $record.state='REVIEW_REQUIRED'
 $record.product_acceptance='NOT_TESTED'
 $exitCode=0
 Write-Host 'Owner-reported synthetic native observations recorded. QA review is still required.' -ForegroundColor Green
}catch{
 $record.state='FAIL_OR_BLOCKED'
 $record.failure_category=$_.Exception.Message
 Write-Host ('P3 native semantic QA NOT ACCEPTED: '+$record.failure_category) -ForegroundColor Red
 $exitCode=1
}finally{
 if($backendProcess -and -not $backendProcess.HasExited){
  try{Stop-Process -Id $backendProcess.Id -Force -ErrorAction Stop}
  catch{Write-Warning 'Could not stop the test-owned backend PID; do not stop other processes.'}
 }
 foreach($name in $ownedNames){
  [Environment]::SetEnvironmentVariable($name,$previousEnvironment[$name],'Process')
 }
 if($runDir -and (Test-Path -LiteralPath $runDir -PathType Container)){
  try{
   $recordFile=Join-Path $runDir 'diagnostics\result.json'
   $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $recordFile -Encoding UTF8
   $archiveDir=Join-Path (Split-Path (Split-Path $runDir -Parent) -Parent) 'archive'
   $archive=Join-Path $archiveDir ((Split-Path $runDir -Leaf)+'-p3-native-status.zip')
   $files=@($recordFile,(Join-Path $runDir 'manifest.json'),
     (Join-Path $runDir 'fixtures\p3-native-semantic-manifest.json')) |
      Where-Object {Test-Path -LiteralPath $_ -PathType Leaf}
   Compress-Archive -LiteralPath $files -DestinationPath $archive -ErrorAction Stop
   Write-Host ('Status-only QA ZIP; no CSVs, draft text or logs: '+$archive) -ForegroundColor Cyan
  }catch{Write-Warning ('Could not save safe QA status archive: '+$_.Exception.Message)}
 }
}
exit $exitCode
