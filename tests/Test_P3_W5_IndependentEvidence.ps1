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
 Write-Host 'W5 SPLIT RUNNER SELF-TEST PASS: known-good, known-bad, and incomplete scenarios.'
} finally {
 Remove-Item -LiteralPath $path -ErrorAction SilentlyContinue
 Remove-Item -LiteralPath $root -Force -ErrorAction SilentlyContinue
}
