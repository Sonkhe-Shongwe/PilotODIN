# Merges a bounded, isolated functional-probe report into W5 runner status.
# A native-window exit error must not erase independently verified data checks.
# This file defines functions only: safe to dot-source in synthetic CI fixtures.
function Import-P3W5FunctionalReport {
 param(
  [Parameter(Mandatory=$true)][string]$Path,
  [Parameter(Mandatory=$true)][System.Collections.IDictionary]$Record
 )
 $expected=@{
  quality_version='PASS_V0_TO_V1'
  version_history='PASS_EXACTLY_V0_V1'
  current_semantic_context='PASS_EMPTY_V1'
  historical_semantic_context='PASS_V0_RETAINED_V1_ABSENT'
  stale_semantic_get='PASS_HTTP_409'
  stale_semantic_post='PASS_HTTP_409'
  original_sha256='PASS_UNCHANGED'
  request_audit='PASS_ONE_PROPOSAL_ONE_UI_COMMIT_ONE_REJECTED_STALE_POST'
 }
 if(-not(Test-Path -LiteralPath $Path -PathType Leaf)){
  $Record.functional_state='NOT_REPORTED'
  return 'NOT_REPORTED'
 }
 try{
  $report=Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
  if($report.phase -ne 'P3-NATIVE-QUALITY-W5' -or
     $report.product_acceptance -ne 'NOT_TESTED' -or
     $report.native_shutdown -ne 'INDEPENDENT_NOT_TESTED' -or
     $report.functional_state -notin @('PASS','VERIFYING','WAITING_FOR_REVIEWED_CORRECTION','FAIL_OR_INCOMPLETE')){
   throw 'Invalid probe identity or unsupported state'
  }
  if($null -eq $report.checks){throw 'Missing probe checks'}
  $proposed=[ordered]@{}
  foreach($name in $expected.Keys){
   $value=[string]$report.checks.$name
   if($value -ne 'NOT_CHECKED' -and $value -ne $expected[$name]){
    throw ('Out-of-scope probe check: '+$name)
   }
   if($report.functional_state -eq 'PASS' -and $value -ne $expected[$name]){
    throw ('Probe falsely claimed PASS: '+$name)
   }
   $proposed[$name]=$value
  }
  foreach($name in $proposed.Keys){$Record[$name]=$proposed[$name]}
  $Record.functional_state=[string]$report.functional_state
  if($report.failure_category){
   $Record.functional_failure_category=([string]$report.failure_category).Substring(
    0,[Math]::Min(120,([string]$report.failure_category).Length)
   )
  }
  return $Record.functional_state
 }catch{
  $Record.functional_state='INVALID_PROBE_REPORT'
  $Record.functional_failure_category='PROBE_REPORT_VALIDATION_FAILED'
  return 'INVALID_PROBE_REPORT'
 }
}
