# P2 synthetic two-native-window consent test only. No releases, original data or AI.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend=Join-Path $root 'frontend'
$pythonExe=Join-Path $root '.venv-live\Scripts\python.exe'
$qaTool=Join-Path $PSScriptRoot 'qa_foundation.py'
$seeder=Join-Path $PSScriptRoot 'Seed_P2_Native_Two_Window_Local.py'
$config=Join-Path $frontend 'src-tauri\tauri.p2-native-two-window.conf.json'
$phase='P2-NATIVE-TWO-WINDOW-DELIVER'
$runDir=$null
$backend=$null
$exitCode=1
$record=[ordered]@{
 phase=$phase
 state='BLOCKED'
 product_acceptance='NOT_TESTED'
 native_two_window='NOT_TESTED'
 scope='OWNER_VISUAL_SYNTHETIC_ONLY'
 observations=[ordered]@{}
 source_integrity='NOT_TESTED'
 backend_writes='NOT_CHECKED'
 installer='NOT_BUILT'
 models='NOT_LAUNCHED'
 source_head='NOT_ATTESTED'
 worktree='NOT_CHECKED'
 failure_category=''
}
$oldEnv=@{}
foreach($name in @('PILOTODIN_HOME','PILOTODIN_DESKTOP_SESSION','PILOTODIN_DESKTOP_ALLOW_DEV',
 'VITE_PILOTODIN_NATIVE_SMOKE','VITE_P2_NATIVE_DELIVER_QA',
 'VITE_P2_NATIVE_DELIVER_PROJECT_ID','VITE_P2_NATIVE_TWO_WINDOW_PROJECT_B',
 'VITE_P2_NATIVE_TWO_WINDOW_QA','CARGO_NET_OFFLINE')){
 $oldEnv[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
function Port-Occupied([int]$number){
 $client=New-Object Net.Sockets.TcpClient
 try{
  $task=$client.ConnectAsync('127.0.0.1',$number)
  return ($task.Wait(350) -and $client.Connected)
 }catch{return $false}
 finally{$client.Close()}
}
function Wait-Project([string]$id){
 for($i=0;$i -lt 100;$i++){
  try{
   $response=Invoke-RestMethod -Uri ('http://127.0.0.1:8000/api/projects/'+$id) -TimeoutSec 2
   if($response.id -eq $id){return $true}
  }catch{}
  Start-Sleep -Milliseconds 200
 }
 return $false
}
function Owner-Check([string]$key,[string]$message){
 Write-Host ''
 Write-Host $message -ForegroundColor Cyan
 $answer=(Read-Host 'Did this happen in the ACTUAL Windows windows? [yes/no]').Trim().ToLowerInvariant()
 $pass=$answer -in @('yes','y')
 $record.observations[$key]=$(if($pass){'OWNER_REPORTED_PASS'}else{'FAIL_OR_NOT_OBSERVED'})
 Write-Host ($key+': '+$record.observations[$key]) -ForegroundColor $(if($pass){'Green'}else{'Red'})
 return $pass
}
try{
 if($env:OS -ne 'Windows_NT'){throw 'Native Windows is required.'}
 foreach($file in @($pythonExe,$qaTool,$seeder,$config,
  (Join-Path $frontend 'p2_native_deliver_consent_qa.html'),
  (Join-Path $frontend 'p2_native_two_window_peer.html'),
  (Join-Path $frontend 'src\p2NativeDeliverConsentQa.tsx'),
  (Join-Path $frontend 'src\p2NativeTwoWindowPeer.ts'))){
  if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw ('Missing pre-existing QA source/runtime: '+$file)}
 }
 if(-not(Test-Path -LiteralPath (Join-Path $frontend 'node_modules') -PathType Container)){
  throw 'Existing node_modules required; this launcher installs nothing.'
 }
 $npm=(Get-Command npm.cmd -ErrorAction Stop).Source
 $null=Get-Command cargo.exe -ErrorAction Stop
 if(Port-Occupied 8000 -or Port-Occupied 5177){throw 'Port 8000 or 5177 already in use; refusing to disturb it.'}
 $git=Get-Command git.exe -ErrorAction SilentlyContinue
 if($git){
  $branch=(& $git.Source -C $root branch --show-current).Trim()
  if($branch -ne 'feature/live-dev-workspace-20261023'){throw ('Incorrect branch: '+$branch)}
  $record.source_head=(& $git.Source -C $root rev-parse HEAD).Trim()
  $dirty=@(& $git.Source -C $root status --porcelain)
  $record.worktree=$(if($dirty.Count -gt 0){'UNCOMMITTED_CHANGES_PRESENT'}else{'CLEAN'})
  if($dirty.Count -gt 0){Write-Warning 'Uncommitted owner changes exist; they will not be changed.'}
 }else{Write-Warning 'Git unavailable; source commit cannot be attested.'}
 $tokens=$null
 $errors=$null
 [System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath,[ref]$tokens,[ref]$errors) | Out-Null
 if($errors -and $errors.Count){throw 'PowerShell runner AST parse failed.'}
 Push-Location $root
 try{
  $allocation=@(& $pythonExe -B $qaTool init --phase $phase --json)
  $allocationExit=$LASTEXITCODE
 }finally{Pop-Location}
 if($allocationExit -ne 0){throw 'DevQA run allocator refused the request.'}
 $allocated=($allocation | Out-String | ConvertFrom-Json)
 if($allocated.status -ne 'READY_NOT_TESTED' -or $allocated.product_acceptance -ne 'NOT_TESTED'){
  throw 'Unexpected new QA allocation status.'
 }
 $runDir=[string]$allocated.run_dir
 if(-not [IO.Path]::IsPathRooted($runDir) -or
    (Split-Path $runDir -Leaf) -notmatch '^P2-NATIVE-TWO-WINDOW-DELIVER-[0-9TZ]+-[a-f0-9]{10}$'){
  throw 'Unrecognised isolated QA run identity.'
 }
 $isolatedWorkspaceHome=Join-Path $runDir 'workspace'
 $fixture=Join-Path $runDir 'fixtures\two-window-manifest.json'
 $logDir=Join-Path $runDir 'logs'
 $backendLog=Join-Path $logDir 'backend-stdout.log'
 $backendErr=Join-Path $logDir 'backend-stderr.log'
 $frontendLog=Join-Path $logDir 'frontend-build.log'
 $nativeLog=Join-Path $logDir 'native-two-window.log'
 Write-Host ('Isolated P2 two-window QA: '+$runDir) -ForegroundColor Cyan
 $env:PILOTODIN_HOME=$isolatedWorkspaceHome
 Remove-Item Env:\PILOTODIN_DESKTOP_SESSION -ErrorAction SilentlyContinue
 Remove-Item Env:\PILOTODIN_DESKTOP_ALLOW_DEV -ErrorAction SilentlyContinue
 $env:VITE_PILOTODIN_NATIVE_SMOKE='1'
 $env:VITE_P2_NATIVE_DELIVER_QA='1'
 $env:VITE_P2_NATIVE_TWO_WINDOW_QA='1'
 $env:CARGO_NET_OFFLINE='true'
 Push-Location $root
 try{
  & $pythonExe -B $seeder $fixture
  $seedExit=$LASTEXITCODE
 }finally{Pop-Location}
 if($seedExit -ne 0 -or -not(Test-Path -LiteralPath $fixture -PathType Leaf)){
  throw 'Two synthetic projects could not be created safely.'
 }
 $manifest=Get-Content -LiteralPath $fixture -Raw -Encoding UTF8 | ConvertFrom-Json
 if($manifest.phase -ne $phase -or $manifest.run_id -ne (Split-Path $runDir -Leaf) -or
    $manifest.projects.Count -ne 2){throw 'Invalid two-project QA manifest.'}
 $ids=@($manifest.projects | ForEach-Object { [string]$_.id })
 if($ids[0] -notmatch '^[a-f0-9]{32}$' -or $ids[1] -notmatch '^[a-f0-9]{32}$' -or $ids[0] -eq $ids[1]){
  throw 'Synthetic A/B project identities invalid.'
 }
 $env:VITE_P2_NATIVE_DELIVER_PROJECT_ID=$ids[0]
 $env:VITE_P2_NATIVE_TWO_WINDOW_PROJECT_B=$ids[1]
 $backend=Start-Process -FilePath $pythonExe -WorkingDirectory $root -ArgumentList @(
  '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--lifespan','off'
 ) -PassThru -NoNewWindow -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr
 foreach($id in $ids){if(-not(Wait-Project $id)){throw 'Isolated FastAPI project GET readiness failed.'}}
 Write-Host 'read-only-isolated-backend-two-projects: PASS' -ForegroundColor Green
 Push-Location $frontend
 try{
  $previousPreference=$ErrorActionPreference
  $ErrorActionPreference='Continue'
  & $npm run build 2>&1 | Tee-Object -FilePath $frontendLog
  $buildCode=$LASTEXITCODE
 }finally{$ErrorActionPreference=$previousPreference;Pop-Location}
 if($buildCode -ne 0){throw 'Current TypeScript/Vite build failed; no windows launched.'}
 Write-Host 'typescript-vite-build: PASS' -ForegroundColor Green
 Write-Host 'Window A = real native full-shell synthetic Deliver; window B = NO-WRITES project selector peer.'
 Write-Host 'Only edit a disposable note in A and click the button in B. Do not import, save, export or train.'
 Write-Host 'Test A dirty draft when B selects project B, then deliberate switch from A to B.'
 Write-Host 'If A changes project unexpectedly, loses text or displays the wrong prompt, record NO.'
 Write-Host 'Close the peer window first, then close A. The final owner questions follow.'
 Push-Location $frontend
 try{
  $previousPreference=$ErrorActionPreference
  $ErrorActionPreference='Continue'
  & $npm run desktop:dev -- --config src-tauri/tauri.p2-native-two-window.conf.json 2>&1 | Tee-Object -FilePath $nativeLog
  $nativeCode=$LASTEXITCODE
 }finally{$ErrorActionPreference=$previousPreference;Pop-Location}
 if($nativeCode -ne 0){throw 'Native test process exited with an error.'}
 $record.native_two_window='OWNER_WINDOW_SESSION_CLOSED_WITH_ZERO_PROCESS_EXIT'
 $results=@(
  (Owner-Check 'dirty_external_veto' 'A: Edit a report note in window A. Click Select synthetic project B in peer window B. A must show another-tab warning, keep original project, route and identical note. No browser/native modal appeared automatically.'),
  (Owner-Check 'explicit_switch_stay' 'B: In A use the project dropdown to deliberately select synthetic project B. The native Switch project / Stay dialog appeared. Stay kept the old project and the edited note.'),
  (Owner-Check 'explicit_switch_approve' 'C: Deliberately choose B again in A, approve native Switch project and verify B opens only after consent; the intentionally discarded A note is no longer mounted.')
 )
 if($results -contains $false){throw 'At least one native two-window observation failed or was not performed.'}
 foreach($item in $manifest.projects){
  $relative=[string]$item.source_relative
  $path=[IO.Path]::GetFullPath((Join-Path $isolatedWorkspaceHome $relative))
  $homePrefix=[IO.Path]::GetFullPath($isolatedWorkspaceHome).TrimEnd('\')+'\'
  if(-not $path.StartsWith($homePrefix,[StringComparison]::OrdinalIgnoreCase)){
   throw 'Synthetic source path escaped the QA workspace.'
  }
  if(-not(Test-Path -LiteralPath $path -PathType Leaf) -or
   (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ine $item.sha256){
   throw 'Synthetic source hash changed or source missing.'
  }
 }
 $record.source_integrity='PASS'
 $access=if(Test-Path -LiteralPath $backendLog -PathType Leaf){
  Get-Content -LiteralPath $backendLog -Raw -ErrorAction SilentlyContinue
 }else{''}
 if($access -match '(POST|PUT|PATCH|DELETE) /api/'){
  $record.backend_writes='UNEXPECTED_WRITE_REQUEST'
  throw 'An unexpected mutation request reached the backend.'
 }
 $record.backend_writes='NO_MUTATION_REQUESTS_OBSERVED'
 $record.state='REVIEW_REQUIRED'
 $exitCode=0
 Write-Host 'P2 native two-window Deliver: OWNER-REPORTED OBSERVATIONS COMPLETE (REVIEW REQUIRED).' -ForegroundColor Green
}catch{
 $record.state='FAIL_OR_BLOCKED'
 $record.failure_category=$_.Exception.Message
 Write-Host ('P2 native two-window QA NOT ACCEPTED: '+$record.failure_category) -ForegroundColor Red
 $exitCode=1
}finally{
 if($backend -and -not $backend.HasExited){
  try{Stop-Process -Id $backend.Id -Force -ErrorAction Stop}
  catch{Write-Warning 'Could not stop owned QA FastAPI; inspect the printed PID without stopping unrelated processes.'}
 }
 foreach($name in $oldEnv.Keys){
  [Environment]::SetEnvironmentVariable($name,$oldEnv[$name],'Process')
 }
 if($runDir -and (Test-Path -LiteralPath $runDir -PathType Container)){
  try{
   $resultFile=Join-Path $runDir 'diagnostics\result.json'
   $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resultFile -Encoding UTF8
   $qaManifest=Join-Path $runDir 'manifest.json'
   $fixture=Join-Path $runDir 'fixtures\two-window-manifest.json'
   $archiveDir=Join-Path (Split-Path (Split-Path $runDir -Parent) -Parent) 'archive'
   $archive=Join-Path $archiveDir ((Split-Path $runDir -Leaf)+'-two-window-status.zip')
   Compress-Archive -LiteralPath @($resultFile,$qaManifest,$fixture) -DestinationPath $archive -ErrorAction Stop
   Write-Host ('P2 status-only ZIP, no source CSV, report text or native logs: '+$archive) -ForegroundColor Cyan
  }catch{Write-Warning ('Could not create status-only archive: '+$_.Exception.Message)}
 }
}
exit $exitCode
