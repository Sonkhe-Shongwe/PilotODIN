# Disposable Windows CI only: no installed apps, real projects, models or installer.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ($env:RUNNER_OS -ne 'Windows' -or -not $env:RUNNER_TEMP) {
 throw 'Refusing non-disposable Windows GitHub runner.'
}
$probe=Join-Path $PSScriptRoot 'Measure_P4_Native_Readiness.ps1'
$root=Join-Path $env:RUNNER_TEMP ('p4-readonly-' + [guid]::NewGuid().ToString('N'))
[void](New-Item -Path $root -ItemType Directory -ErrorAction Stop)
try {
 $old=Join-Path $root 'old-app'
 $qa=Join-Path $root 'qa-app'
 $data=Join-Path $root 'original-data'
 $out=Join-Path $root 'evidence'
 foreach ($path in @($old,$qa,$data,$out)) {[void](New-Item -ItemType Directory -Path $path)}
 $oldExe=Join-Path $old 'pilotodin-desktop.exe'
 $qaExe=Join-Path $qa 'pilotodin-desktop.exe'
 $first=Join-Path $data 'synthetic-private.csv'
 Set-Content -LiteralPath $oldExe -Value 'FAKE-OLD-EXE' -NoNewline
 Set-Content -LiteralPath $qaExe -Value 'FAKE-QA-EXE' -NoNewline
 Set-Content -LiteralPath $first -Value 'SYNTHETIC-ONLY-DATA' -NoNewline
 $nested=Join-Path $data 'nested'
 [void](New-Item -Path $nested -ItemType Directory)
 Set-Content -LiteralPath (Join-Path $nested 'other-private.txt') -Value 'INVENTED' -NoNewline
 $sha=(Get-FileHash -LiteralPath $qaExe -Algorithm SHA256).Hash.ToLowerInvariant()
 & $probe -Stage Baseline -OriginalExe $oldExe -OriginalData $data -EvidenceDir $out
 & $probe -Stage Verify -OriginalExe $oldExe -OriginalData $data -EvidenceDir $out -QaExe $qaExe -ExpectedQaSha256 $sha
 $report=Get-Content -LiteralPath (Join-Path $out 'verification.json') -Raw | ConvertFrom-Json
 if ($report.original_exe_and_data_unchanged -ne $true -or
     $report.qa_exe_matches_supplied_sha256 -ne $true -or
     $report.ram.status -ne 'NOT_TESTED' -or
     $report.offline_8gb_acceptance -ne 'NOT_TESTED' -or
     $report.model_training_performed_by_script -ne $false) {throw 'Positive integrity evidence misclassified'}
 $raw=Get-Content -LiteralPath (Join-Path $out 'verification.json') -Raw
 if ($raw.Contains('synthetic-private.csv') -or $raw.Contains('other-private.txt') -or
     $raw.Contains('SYNTHETIC-ONLY-DATA')) {throw 'Private file name or value escaped'}
 $baseline=Join-Path $out 'baseline.json'
 function CheckReject([scriptblock]$mutation,[string]$label) {
  $folder=Join-Path $root ('case-' + $label)
  [void](New-Item -ItemType Directory -Path $folder)
  Copy-Item -LiteralPath $baseline -Destination (Join-Path $folder 'baseline.json')
  & $mutation
  $didFail=$false
  try {
   & $probe -Stage Verify -OriginalExe $oldExe -OriginalData $data -EvidenceDir $folder -QaExe $qaExe -ExpectedQaSha256 $sha
  } catch {$didFail=$true}
  if (-not $didFail) {throw "Expected $label to fail"}
  $failed=Get-Content -LiteralPath (Join-Path $folder 'verification.json') -Raw | ConvertFrom-Json
  if ($failed.status -ne 'FAIL') {throw "Unexpected $label acceptance"}
 }
 CheckReject {Set-Content -LiteralPath $first -Value 'CHANGED' -NoNewline} 'data-changed'
 Set-Content -LiteralPath $first -Value 'SYNTHETIC-ONLY-DATA' -NoNewline
 CheckReject {Set-Content -LiteralPath $oldExe -Value 'CHANGED-OLD-EXE' -NoNewline} 'original-exe-changed'
 Set-Content -LiteralPath $oldExe -Value 'FAKE-OLD-EXE' -NoNewline
 CheckReject {Set-Content -LiteralPath $qaExe -Value 'BAD-QA' -NoNewline} 'qa-hash-mismatch'
 Write-Host 'PASS: disposable baseline, verification, original dataset mutation, old EXE mutation and QA hash mismatch fail-closed.'
 Write-Host 'NOT TESTED: owner hardware, real installed app, model fitting, sustained 8 GB, offline and business suitability.'
} finally {
 Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
