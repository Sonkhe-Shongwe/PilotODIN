# P2 synthetic full UnifiedShell native consent observation only.
# One new DevQA home, backend on owned :8000 and Vite :5177, no installer/AI.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend=Join-Path $root 'frontend'
$pythonExe=Join-Path $root '.venv-live\Scripts\python.exe'
$qaTool=Join-Path $PSScriptRoot 'qa_foundation.py'
$seeder=Join-Path $PSScriptRoot 'Seed_P2_Native_Deliver_Consent_Local.py'
$nativeConfig=Join-Path $frontend 'src-tauri\tauri.p2-native-deliver-consent.conf.json'
$runDir=$null
$backend=$null
$record=[ordered]@{
  phase='P2-NATIVE-DELIVER-CONSENT'
  state='BLOCKED'
  product_acceptance='NOT_TESTED'
  owner_native_observations='NOT_TESTED'
  native_tauri_full_shell='NOT_TESTED'
  source_unchanged='NOT_TESTED'
  backend_writes='NOT_CHECKED'
  installer='NOT_BUILT'
  models='NOT_LAUNCHED'
  scope='DISPOSABLE_SYNTHETIC_OWNER_VISUAL_ONLY'
  observations=[ordered]@{}
  failure_category=''
}
$exitCode=1
$oldEnv=@{}
foreach($name in @('PILOTODIN_HOME','PILOTODIN_DESKTOP_SESSION','PILOTODIN_DESKTOP_ALLOW_DEV',
    'VITE_PILOTODIN_NATIVE_SMOKE','VITE_P2_NATIVE_DELIVER_QA',
    'VITE_P2_NATIVE_DELIVER_PROJECT_ID','CARGO_NET_OFFLINE')){
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
function Wait-SyntheticProject([string]$projectId){
  for($i=0;$i -lt 100;$i++){
    try{
      $answer=Invoke-RestMethod -Uri ('http://127.0.0.1:8000/api/projects/'+$projectId) -TimeoutSec 2
      if($answer.id -eq $projectId){return $true}
    }catch{}
    Start-Sleep -Milliseconds 200
  }
  return $false
}
function Owner-Check([string]$key,[string]$message){
  Write-Host ''
  Write-Host $message -ForegroundColor Cyan
  $answer=(Read-Host 'Did the ACTUAL Windows native main-window test behave exactly as described? [yes/no]').Trim().ToLowerInvariant()
  $ok=$answer -in @('yes','y')
  $record.observations[$key]=$(if($ok){'OWNER_REPORTED_PASS'}else{'FAIL_OR_NOT_OBSERVED'})
  Write-Host ($key+': '+$record.observations[$key]) -ForegroundColor $(if($ok){'Green'}else{'Red'})
  return $ok
}
try {
  if($env:OS -ne 'Windows_NT'){throw 'Windows is required; no native UI was run.'}
  foreach($file in @($pythonExe,$qaTool,$seeder,$nativeConfig,
    (Join-Path $frontend 'p2_native_deliver_consent_qa.html'),
    (Join-Path $frontend 'src\p2NativeDeliverConsentQa.tsx'))){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw ('Required source or existing Python runtime missing: '+$file)}
  }
  if(-not(Test-Path -LiteralPath (Join-Path $frontend 'node_modules') -PathType Container)){
    throw 'Missing pre-existing node_modules. This test does not install packages.'
  }
  $npm=(Get-Command npm.cmd -ErrorAction Stop).Source
  $cargo=(Get-Command cargo.exe -ErrorAction Stop).Source
  if(Port-Occupied 8000 -or Port-Occupied 5177){
    throw 'An existing service owns port 8000 or 5177. Refusing to interrupt an unrelated process.'
  }
  $git=Get-Command git.exe -ErrorAction SilentlyContinue
  if($git){
    $branch=(& $git.Source -C $root branch --show-current).Trim()
    if($branch -ne 'feature/live-dev-workspace-20261023'){
      throw ('Incorrect branch: '+$branch)
    }
    $changes=@(& $git.Source -C $root status --porcelain)
    if(@($changes).Count -gt 0){Write-Warning 'Uncommitted source exists. It will not be reset or deleted.'}
  }else{Write-Warning 'Git CLI unavailable; verify feature/live-dev-workspace-20261023 is checked out.'}
  $parseTokens=$null
  $parseErrors=$null
  [System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath,[ref]$parseTokens,[ref]$parseErrors) | Out-Null
  if($parseErrors -and $parseErrors.Count){throw 'PowerShell runner failed its own parser preflight.'}
  Push-Location $root
  try{
    $raw=@(& $pythonExe -B $qaTool init --phase P2-NATIVE-DELIVER-CONSENT --json)
    $allocStatus=$LASTEXITCODE
  }finally{Pop-Location}
  if($allocStatus -ne 0){throw 'DevQA allocator rejected the isolated run.'}
  $allocated=($raw | Out-String | ConvertFrom-Json)
  if($allocated.status -ne 'READY_NOT_TESTED' -or $allocated.product_acceptance -ne 'NOT_TESTED'){
    throw 'DevQA allocator did not return a new test-only run.'
  }
  $runDir=[string]$allocated.run_dir
  if(-not [IO.Path]::IsPathRooted($runDir)){throw 'DevQA run is not an absolute directory.'}
  $runName=Split-Path $runDir -Leaf
  if($runName -notmatch '^P2-NATIVE-DELIVER-CONSENT-[0-9TZ]+-[a-f0-9]{10}$'){
    throw 'Allocated synthetic run has an unexpected identity.'
  }
  $home=Join-Path $runDir 'workspace'
  $fixture=Join-Path $runDir 'fixtures\synthetic-consent-manifest.json'
  $logDir=Join-Path $runDir 'logs'
  $backendLog=Join-Path $logDir 'backend-stdout.log'
  $backendErr=Join-Path $logDir 'backend-stderr.log'
  $frontendLog=Join-Path $logDir 'typescript-vite.log'
  $nativeLog=Join-Path $logDir 'native-shell-build.log'
  Write-Host ('P2 NATIVE CONSENT QA RUN: '+$runDir) -ForegroundColor Cyan
  Write-Host 'This is NOT the normal PilotODIN installed desktop or your real project catalogue.'
  $env:PILOTODIN_HOME=$home
  Remove-Item Env:\PILOTODIN_DESKTOP_SESSION -ErrorAction SilentlyContinue
  Remove-Item Env:\PILOTODIN_DESKTOP_ALLOW_DEV -ErrorAction SilentlyContinue
  $env:VITE_PILOTODIN_NATIVE_SMOKE='1'
  $env:VITE_P2_NATIVE_DELIVER_QA='1'
  $env:CARGO_NET_OFFLINE='true'
  Push-Location $root
  try{
    & $pythonExe -B $seeder $fixture
    $seedCode=$LASTEXITCODE
  }finally{Pop-Location}
  if($seedCode -ne 0 -or -not(Test-Path -LiteralPath $fixture -PathType Leaf)){
    throw 'Could not create only the isolated synthetic CSV project.'
  }
  $manifest=Get-Content -LiteralPath $fixture -Raw -Encoding UTF8 | ConvertFrom-Json
  if($manifest.phase -ne 'P2-NATIVE-DELIVER-CONSENT' -or
    $manifest.run_id -ne $runName -or
    $manifest.project_id -notmatch '^[a-f0-9]{32}$'){
    throw 'Synthetic seed manifest could not be verified.'
  }
  $env:VITE_P2_NATIVE_DELIVER_PROJECT_ID=[string]$manifest.project_id
  $backend=Start-Process -FilePath $pythonExe -WorkingDirectory $root -ArgumentList @(
    '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--lifespan','off'
  ) -PassThru -NoNewWindow -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr
  if(-not(Wait-SyntheticProject $manifest.project_id)){
    throw 'Owned isolated FastAPI failed its synthetic project health gate.'
  }
  Write-Host 'isolated-real-FastAPI/synthetic-project: PASS' -ForegroundColor Green
  Push-Location $frontend
  try{
    $previousPreference=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    & $npm run build 2>&1 | Tee-Object -FilePath $frontendLog
    $buildCode=$LASTEXITCODE
  }finally{$ErrorActionPreference=$previousPreference;Pop-Location}
  if($buildCode -ne 0){throw 'Frontend TypeScript/Vite build failed; native window NOT started.'}
  Write-Host 'typescript-vite-build: PASS' -ForegroundColor Green
  Write-Host ''
  Write-Host 'The native test window will open the REAL main UnifiedShell in Deliver.'
  Write-Host 'Use ONLY the four-row SYNTHETIC project, report text, main rail and New project actions.'
  Write-Host 'Do not use Save, import, exports, Quality edits, models, ODIN or any original projects.'
  Write-Host 'Observe the actual Windows system dialog: Leave Deliver / Keep editing.'
  Write-Host 'After completing the interactions, close the test window and answer the prompts.'
  Push-Location $frontend
  try{
    $previousPreference=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    & $npm run desktop:dev -- --config src-tauri/tauri.p2-native-deliver-consent.conf.json 2>&1 | Tee-Object -FilePath $nativeLog
    $nativeCode=$LASTEXITCODE
  }finally{$ErrorActionPreference=$previousPreference;Pop-Location}
  if($nativeCode -ne 0){throw 'Full shell Tauri development process failed or closed with an error.'}
  $record.native_tauri_full_shell='OWNER_WINDOW_CLOSED_WITH_ZERO_PROCESS_EXIT'
  $results=@(
    (Owner-Check 'dirty_warning' 'A: Deliver showed the unsaved report warning after you typed a short synthetic note.'),
    (Owner-Check 'explore_keep' 'B: Clicking shell Explore showed native Leave Deliver / Keep editing. You chose Keep editing, and Deliver, the note and route stayed unchanged.'),
    (Owner-Check 'new_project_keep' 'C: Clicking shell New project showed the native dialog. Keep editing left the report visible and did NOT open an importer, immediately or later.'),
    (Owner-Check 'explore_leave' 'D: A fresh native dialog appeared when you retried Explore. Choosing Leave Deliver opened Explore; keyboard focus stayed usable.'),
    (Owner-Check 'new_project_leave' 'E: After returning to Deliver and typing a new note, choosing Leave Deliver on New project opened only the synthetic importer.')
  )
  if($results -contains $false){throw 'One or more actual native observation steps failed or were not performed.'}
  $record.owner_native_observations='OWNER_REPORTED_PASS_REVIEW_REQUIRED'
  $sourceRel=[string]$manifest.source_relative
  $dataset=[IO.Path]::GetFullPath((Join-Path $home $sourceRel))
  $homeFull=[IO.Path]::GetFullPath($home).TrimEnd('\')+'\'
  if(-not $dataset.StartsWith($homeFull,[StringComparison]::OrdinalIgnoreCase)){
    throw 'Synthetic manifest source resolved outside the QA workspace.'
  }
  if(-not(Test-Path -LiteralPath $dataset -PathType Leaf) -or
     (Get-FileHash -LiteralPath $dataset -Algorithm SHA256).Hash -ine $manifest.synthetic_csv_sha256){
    throw 'Synthetic source file is missing or changed.'
  }
  $record.source_unchanged='PASS'
  # Browser API mutations are blocked in QA. Uvicorn log independently audits
  # any attempted HTTP POST/PUT/PATCH/DELETE reaching the owned backend.
  $access=(Get-Content -LiteralPath $backendLog -Raw -ErrorAction SilentlyContinue)
  if($access -match '(POST|PUT|PATCH|DELETE) /api/'){
    $record.backend_writes='UNEXPECTED_WRITE_REQUEST'
    throw 'Unexpected mutation reached the isolated backend; do not accept.'
  }
  $record.backend_writes='NO_MUTATION_REQUESTS_OBSERVED'
  $record.state='REVIEW_REQUIRED'
  $record.product_acceptance='NOT_TESTED'
  $exitCode=0
  Write-Host 'P2 native Deliver consent: OWNER-REPORTED SCOPED OBSERVATION COMPLETE (REVIEW REQUIRED).' -ForegroundColor Green
}catch{
  $record.state='FAIL_OR_BLOCKED'
  $record.failure_category=$_.Exception.Message
  Write-Host ('P2 native Deliver consent NOT ACCEPTED: '+$record.failure_category) -ForegroundColor Red
  $exitCode=1
}finally{
  if($backend -and -not $backend.HasExited){
    try{Stop-Process -Id $backend.Id -Force -ErrorAction Stop}
    catch{Write-Warning 'Could not stop owned synthetic FastAPI. Inspect its PID, do not stop unrelated services.'}
  }
  foreach($name in $oldEnv.Keys){
    [Environment]::SetEnvironmentVariable($name,$oldEnv[$name],'Process')
  }
  if($runDir -and (Test-Path -LiteralPath $runDir -PathType Container)){
    try{
      $recordFile=Join-Path $runDir 'diagnostics\result.json'
      $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $recordFile -Encoding UTF8
      $qaManifest=Join-Path $runDir 'manifest.json'
      $archiveDir=Join-Path (Split-Path (Split-Path $runDir -Parent) -Parent) 'archive'
      $zip=Join-Path $archiveDir ((Split-Path $runDir -Leaf)+'-native-consent-status.zip')
      $statusSources=@($recordFile,$qaManifest)
      if(Test-Path -LiteralPath (Join-Path $runDir 'fixtures\synthetic-consent-manifest.json') -PathType Leaf){
        $statusSources+=Join-Path $runDir 'fixtures\synthetic-consent-manifest.json'
      }
      Compress-Archive -LiteralPath $statusSources -DestinationPath $zip -ErrorAction Stop
      Write-Host ('P2 status-only QA ZIP (no source CSV, report text or native logs): '+$zip) -ForegroundColor Cyan
    }catch{Write-Warning ('Could not write status-only QA archive: '+$_.Exception.Message)}
  }
}
exit $exitCode
