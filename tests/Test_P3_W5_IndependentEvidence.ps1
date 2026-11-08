# No GUI or user datasets. Verify W5 classification with deliberately good/bad reports.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\tools\Read_P3_W5_Functional_Result.ps1')
$root=Join-Path ([IO.Path]::GetTempPath()) ('pilotodin-w5-split-selftest-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
try {
 $path=Join-Path $root 'functional.json'
 $checks=[ordered]@{
  quality_version='PASS_V0_TO_V1'
  version_history='PASS_EXACTLY_V0_V1'
  current_semantic_context='PASS_EMPTY_V1'
  historical_semantic_context='PASS_V0_RETAINED_V1_ABSENT'
  stale_semantic_get='PASS_HTTP_409'
  stale_semantic_post='PASS_HTTP_409'
  original_sha256='PASS_UNCHANGED'
  request_audit='PASS_ONE_PROPOSAL_ONE_UI_COMMIT_ONE_REJECTED_STALE_POST'
 }
 $good=@{
  phase='P3-NATIVE-QUALITY-W5'
  functional_state='PASS'
  checks=$checks
  failure_category=''
  native_shutdown='INDEPENDENT_NOT_TESTED'
  product_acceptance='NOT_TESTED'
 }
 $good | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $path -Encoding UTF8
 # A failed native close cannot invalidate a real and independently checked v1.
 $record=[ordered]@{native_shutdown_status='FAIL_NONZERO_EXIT'; functional_state='NOT_TESTED'}
 $state=Import-P3W5FunctionalReport -Path $path -Record $record
 if($state -ne 'PASS' -or $record.native_shutdown_status -ne 'FAIL_NONZERO_EXIT' -or
    $record.quality_version -ne 'PASS_V0_TO_V1' -or
    $record.historical_semantic_context -ne 'PASS_V0_RETAINED_V1_ABSENT'){
  throw 'Known-good functional/failed-window independent verdict did not survive'
 }
 # A report that says PASS but does not prove the precise two-cell transformation
 # must be rejected even when all other positive result fields are populated.
 $bad=@{}+$good
 $badChecks=[ordered]@{}+$checks
 $badChecks.quality_version='NOT_CHECKED'
 $bad.checks=$badChecks
 $bad | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $path -Encoding UTF8
 $rejected=[ordered]@{functional_state='NOT_TESTED'}
 $state=Import-P3W5FunctionalReport -Path $path -Record $rejected
 if($state -ne 'INVALID_PROBE_REPORT' -or $rejected.quality_version){
  throw 'Deliberately invalid functional PASS was not refused'
 }
 # An incomplete operation is neither a clean pass nor grounds to relabel a
 # different check as a failure.
 $waiting=@{}+$good
 $waiting.functional_state='WAITING_FOR_REVIEWED_CORRECTION'
 $pending=[ordered]@{}
 foreach($k in $checks.Keys){$pending[$k]='NOT_CHECKED'}
 $waiting.checks=$pending
 $waiting | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $path -Encoding UTF8
 $record=[ordered]@{native_shutdown_status='FAIL_NONZERO_EXIT'}
 $state=Import-P3W5FunctionalReport -Path $path -Record $record
 if($state -ne 'WAITING_FOR_REVIEWED_CORRECTION' -or
    $record.quality_version -ne 'NOT_CHECKED'){
  throw 'Known-incomplete result incorrectly labelled'
 }
 # Verify the runner's real Start-Process invocation on physical Windows CI.
 # This one deliberately lacks a manifest, so the probe MUST return failure
 # without contacting any owner project or starting a native desktop window.
 $workspace=Join-Path $root 'workspace'
 New-Item -ItemType Directory -Path $workspace | Out-Null
 New-Item -ItemType Directory -Path (Join-Path $root 'diagnostics') | Out-Null
 $probeOut=Join-Path $root 'probe-stdout.log'
 $probeErr=Join-Path $root 'probe-stderr.log'
 $previousHome=$env:PILOTODIN_HOME
 try {
  $env:PILOTODIN_HOME=$workspace
  $python=(Get-Command python.exe -ErrorAction Stop).Source
  $repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
  $probe=Start-Process -FilePath $python -WorkingDirectory $repoRoot -ArgumentList @(
   '-B','-m','tools.P3_W5_Functional_Probe'
  ) -PassThru -NoNewWindow -RedirectStandardOutput $probeOut -RedirectStandardError $probeErr
  if(-not $probe.WaitForExit(20000)){throw 'Actual Windows background probe did not exit'}
  # Windows PowerShell 5.1 can leave Start-Process -PassThru ExitCode
  # unset even after WaitForExit. The durable synthetic report is authoritative.
  if($null -ne $probe.ExitCode -and $probe.ExitCode -ne 2){
   $errorDetail=if(Test-Path -LiteralPath $probeErr){
    (Get-Content -LiteralPath $probeErr -Tail 12 | Out-String)
   }else{'No stderr file.'}
   Write-Host ('Isolated probe stderr diagnostic: '+$errorDetail)
   throw ('Deliberately invalid probe exited '+$probe.ExitCode+' instead of safe code 2')
  }
  $probeStatus=Get-Content -LiteralPath (Join-Path $root 'diagnostics\functional-result.json') -Raw | ConvertFrom-Json
  if($probeStatus.functional_state -ne 'FAIL_OR_INCOMPLETE' -or
     $probeStatus.product_acceptance -ne 'NOT_TESTED' -or
     $probeStatus.native_shutdown -ne 'INDEPENDENT_NOT_TESTED'){
   throw 'Actual Windows background probe process was not isolated and fail closed'
  }
 }finally{
  [Environment]::SetEnvironmentVariable('PILOTODIN_HOME',$previousHome,'Process')
 }
 Write-Host 'W5 SPLIT RUNNER SELF-TEST PASS: known-good, known-bad, incomplete and actual Windows probe launch.'
} finally {
 # Temporary CI-only directory. Do not let PowerShell 5.1 Remove-Item
 # errors mask a legitimate known-good/bad harness result.
 if($root -and $root.StartsWith([IO.Path]::GetTempPath(),[StringComparison]::OrdinalIgnoreCase) -and
    (Test-Path -LiteralPath $root -PathType Container)){
  try{[IO.Directory]::Delete($root,$true)}
  catch{Write-Warning 'Could not tidy the isolated W5 self-test directory.'}
 }
}
