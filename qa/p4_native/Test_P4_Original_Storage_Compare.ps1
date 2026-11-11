# Synthetic Windows-only test of read-only P4 classification (not owner evidence).
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ($env:RUNNER_OS -ne 'Windows' -or -not $env:RUNNER_TEMP) {
 throw 'Refusing non-disposable Windows GitHub runner.'
}
$probe=Join-Path $PSScriptRoot 'Measure_P4_Native_Readiness.ps1'
$compare=Join-Path $PSScriptRoot 'Compare_P4_Original_Storage.ps1'
$root=Join-Path $env:RUNNER_TEMP ('p4-storage-compare-' + [guid]::NewGuid().ToString('N'))
[void](New-Item -Path $root -ItemType Directory -ErrorAction Stop)
try {
 $backup=Join-Path $root 'backup'
 $current=Join-Path $root 'current'
 $exeRoot=Join-Path $root 'original-app'
 $evidence=Join-Path $root 'evidence'
 foreach ($p in @($backup,$exeRoot,$evidence)) {
  [void](New-Item -Path $p -ItemType Directory -ErrorAction Stop)
 }
 $exe=Join-Path $exeRoot 'pilotodin-desktop.exe'
 Set-Content -LiteralPath $exe -Value 'DISPOSABLE-EXE' -NoNewline
 foreach ($p in @('data','data\datasets','WebView2\IndexedDB','WebView2\Cache','other')) {
  [void](New-Item -Path (Join-Path $backup $p) -ItemType Directory -Force)
 }
 Set-Content -LiteralPath (Join-Path $backup 'data\pilotodin.sqlite3') -Value 'SYNTHETIC-PROJECT-METADATA' -NoNewline
 Set-Content -LiteralPath (Join-Path $backup 'data\datasets\example.csv') -Value 'SYNTHETIC-CSV' -NoNewline
 Set-Content -LiteralPath (Join-Path $backup 'WebView2\IndexedDB\000001.log') -Value 'BROWSER-CACHE' -NoNewline
 Set-Content -LiteralPath (Join-Path $backup 'other\unknown.txt') -Value 'UNCLASSIFIED' -NoNewline
 # Compare against independent original baseline, not a regenerated current-state baseline.
 & $probe -Stage Baseline -OriginalExe $exe -OriginalData $backup -EvidenceDir $evidence
 Copy-Item -LiteralPath $backup -Destination $current -Recurse -ErrorAction Stop
 $params=@{
  BaselineFile=(Join-Path $evidence 'baseline.json')
  BackupData=$backup
  OriginalData=$current
  OriginalExe=$exe
 }
 $initial=& $compare @params
 if ($initial.status -ne 'FULL_FINGERPRINT_MATCH' -or
     $initial.all_changed_files -ne 0 -or
     $initial.critical_project_store_changes -ne 0 -or
     $initial.original_exe_matches_baseline -ne $true) {
  throw 'Unmodified synthetic original incorrectly rejected'
 }
 $backupHash=(Get-FileHash -LiteralPath (Join-Path $backup 'data\pilotodin.sqlite3') -Algorithm SHA256).Hash
 Set-Content -LiteralPath (Join-Path $current 'WebView2\IndexedDB\000001.log') -Value 'NEW-BROWSER-CACHE' -NoNewline
 Set-Content -LiteralPath (Join-Path $current 'WebView2\Cache\index') -Value 'FAKE' -NoNewline
 $browser=& $compare @params
 if ($browser.status -ne 'REVIEW_REQUIRED_FULL_PRESERVATION_NOT_PASSED' -or
     $browser.critical_project_store_changes -ne 0 -or
     $browser.browser_cache_candidate_changes -ne 2 -or
     $browser.all_changed_files -ne 2 -or
     $browser.project_data_certified -ne $false -or
     $browser.full_data_integrity_waived -ne $false) {
  throw 'Cache-only drift was improperly accepted or classified'
 }
 Set-Content -LiteralPath (Join-Path $current 'data\pilotodin.sqlite3') -Value 'CHANGED-SYNTHETIC-PROJECT' -NoNewline
 Remove-Item -LiteralPath (Join-Path $current 'data\datasets\example.csv') -ErrorAction Stop
 Set-Content -LiteralPath (Join-Path $current 'other\unknown.txt') -Value 'UNKNOWN-CHANGED' -NoNewline
 $critical=& $compare @params
 if ($critical.critical_project_store_changes -ne 2 -or
     $critical.critical_project_store_modified -ne 1 -or
     $critical.critical_project_store_missing -ne 1 -or
     $critical.unclassified_changes -ne 1 -or
     $critical.all_changed_files -ne 5) {
  throw 'Critical store or unclassified changes were hidden'
 }
 Set-Content -LiteralPath $exe -Value 'CHANGED-EXE' -NoNewline
 $exeDrift=& $compare @params
 if ($exeDrift.original_exe_matches_baseline -ne $false -or
     $exeDrift.status -ne 'REVIEW_REQUIRED_FULL_PRESERVATION_NOT_PASSED') {
  throw 'Standalone production executable hash drift was ignored'
 }
 if ((Get-FileHash -LiteralPath (Join-Path $backup 'data\pilotodin.sqlite3') -Algorithm SHA256).Hash -ne $backupHash) {
  throw 'Comparator unexpectedly changed backup project file'
 }
 Set-Content -LiteralPath (Join-Path $backup 'data\pilotodin.sqlite3') -Value 'TAMPERED-BACKUP' -NoNewline
 $stopped=$false
 try { $null=& $compare @params } catch { $stopped=$true }
 if (-not $stopped) {throw 'Comparator accepted an unverified altered backup'}
 $baseline=Get-Content -LiteralPath (Join-Path $evidence 'baseline.json') -Raw | ConvertFrom-Json
 if ($baseline.purpose -ne 'ORIGINAL_PRESERVATION_BASELINE_NOT_ACCEPTANCE') {
  throw 'Baseline overwritten during read-only comparison'
 }
 Write-Host 'PASS: synthetic full match, WebView-only drift still FAIL, protected SQLite/dataset drift blocked, unknown changes retained, EXE drift, backup tamper fail-closed.'
 Write-Host 'NOT TESTED: owner real files, writer attribution, critical store preservation on Windows, physical offline/8GB or P4 release acceptance.'
} finally {
 Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
