# P4 native investigation: READ ONLY. Never repairs, copies, deletes or accepts a changed tree.
# Uses a separately captured P4-22 baseline AND the independent pre-QA backup.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$BaselineFile,
 [Parameter(Mandatory=$true)][string]$BackupData,
 [Parameter(Mandatory=$true)][string]$OriginalData,
 [Parameter(Mandatory=$true)][string]$OriginalExe
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Existing([string]$value,[string]$kind) {
 if (-not (Test-Path -LiteralPath $value -PathType $kind)) {
  throw 'A required evidence or source path is missing; refusing comparison.'
 }
 $item=Get-Item -LiteralPath $value -Force -ErrorAction Stop
 if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
  throw 'Reparse-point input refused; no integrity result.'
 }
 return [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $value).Path).TrimEnd([char]'\',[char]'/')
}
function Inside([string]$value,[string]$root) {
 return ($value.Equals($root,[StringComparison]::OrdinalIgnoreCase) -or
  $value.StartsWith(($root+'\'),[StringComparison]::OrdinalIgnoreCase))
}
function ShaFile([string]$path) {
 return (Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
}
function ShaText([string]$text) {
 $sha=[Security.Cryptography.SHA256]::Create()
 try {
  return [BitConverter]::ToString(
   $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text))
  ).Replace('-','').ToLowerInvariant()
 } finally { $sha.Dispose() }
}
function Tree([string]$source) {
 # Exactly the P4-22 Baseline relative-path/content/byte hashing algorithm.
 $queue=New-Object 'System.Collections.Generic.Queue[string]'
 $entries=New-Object 'System.Collections.Generic.List[object]'
 $files=@{}
 # Directory paths must be compared independently of file hashes: empty
 # directories have no file entry in the historical P4-22 baseline.
 $directories=@{}
 $queue.Enqueue($source)
 [long]$total=0
 while ($queue.Count -gt 0) {
  $folder=$queue.Dequeue()
  foreach ($item in @(Get-ChildItem -LiteralPath $folder -Force -ErrorAction Stop)) {
   if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Reparse point inside source refused; snapshot incomplete.'
   }
   if ($item.PSIsContainer) {
    $relativeDir=$item.FullName.Substring($source.Length).TrimStart([char]'\',[char]'/').Replace('\','/')
    if ($directories.ContainsKey($relativeDir)) {
     throw 'Ambiguous case-insensitive directory name; snapshot refused.'
    }
    $directories[$relativeDir]=$true
    $queue.Enqueue($item.FullName)
    continue
   }
   $relative=$item.FullName.Substring($source.Length).TrimStart([char]'\',[char]'/').Replace('\','/')
   if ($files.ContainsKey($relative)) { throw 'Ambiguous case-insensitive file name; snapshot refused.' }
   [long]$bytes=$item.Length
   $digest=ShaFile $item.FullName
   $entry=[pscustomobject]@{name_digest=(ShaText $relative);bytes=$bytes;content_digest=$digest}
   $files[$relative]=$entry
   $entries.Add($entry)
   $total += $bytes
  }
 }
 $builder=New-Object Text.StringBuilder
 foreach ($entry in @($entries | Sort-Object name_digest)) {
  [void]$builder.Append($entry.name_digest).Append('|').Append($entry.bytes).Append('|').Append($entry.content_digest).AppendLine()
 }
 return @{
  file_count=$entries.Count
  total_bytes=$total
  content_and_relative_path_tree_sha256=(ShaText $builder.ToString())
  files=$files
  directories=$directories
  directory_count=$directories.Count
 }
}
function SameTree([hashtable]$left,[hashtable]$right) {
 # The v1 file fingerprint is compared separately from the complete
 # directory path set, which also includes empty directories.
 if ($left.file_count -ne $right.file_count -or
     $left.total_bytes -ne $right.total_bytes -or
     $left.content_and_relative_path_tree_sha256 -ne $right.content_and_relative_path_tree_sha256 -or
     $left.directory_count -ne $right.directory_count) { return $false }
 foreach ($name in $left.directories.Keys) {
  if (-not $right.directories.ContainsKey($name)) { return $false }
 }
 return $true
}
function Category([string]$relative) {
 # The native launcher explicitly uses app_local_data_dir()/data as
 # PILOTODIN_HOME. backend/storage.py stores SQLite and artifacts there.
 # Classifying this as critical is NOT a relaxation of full-tree integrity.
 if ($relative -match '(?i)^data/') { return 'critical_project_store' }
 # Only candidates for WebView/browser-generated state; none are excluded
 # from the full preservation check, even when category resembles a cache.
 if ($relative -match '(?i)(^|/)(WebView2|EBWebView|IndexedDB|Local Storage|Session Storage|Service Worker|GPUCache|Code Cache|Cache|CacheStorage|DawnCache|Crashpad|blob_storage)(/|$)') {
  return 'browser_cache_candidate'
 }
 return 'unclassified'
}
if ($env:OS -ne 'Windows_NT') {throw 'Windows-only read-only diagnostic.'}
$baselinePath=Existing $BaselineFile 'Leaf'
$backup=Existing $BackupData 'Container'
$current=Existing $OriginalData 'Container'
$oldExe=Existing $OriginalExe 'Leaf'
if ((Inside $backup $current) -or (Inside $current $backup) -or
    (Inside $baselinePath $current) -or (Inside $baselinePath $backup) -or
    (Inside $oldExe $current) -or (Inside $oldExe $backup)) {
 throw 'Backup, original and baseline locations must be independent.'
}
$baseline=Get-Content -LiteralPath $baselinePath -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json
if ($baseline.schema_version -ne 1 -or
    $baseline.purpose -ne 'ORIGINAL_PRESERVATION_BASELINE_NOT_ACCEPTANCE' -or
    $baseline.original.old_exe_sha256 -notmatch '^[a-fA-F0-9]{64}$' -or
    $baseline.original.original_data.content_and_relative_path_tree_sha256 -notmatch '^[a-fA-F0-9]{64}$') {
 throw 'Unrecognized P4-22 baseline; comparison refused.'
}

# Fail closed if an independently verified BACKUP is not identical to
# the original pre-QA baseline; never treat a newer backup as baseline.
$before=Tree $backup
if ($before.file_count -ne $baseline.original.original_data.file_count -or
    $before.total_bytes -ne $baseline.original.original_data.total_bytes -or
    $before.content_and_relative_path_tree_sha256 -ne $baseline.original.original_data.content_and_relative_path_tree_sha256) {
 throw 'Backup does not reproduce the original P4-22 baseline; do not interpret changes.'
}
$now=Tree $current
$firstExeSha=ShaFile $oldExe
$oldExeGood=$firstExeSha -eq $baseline.original.old_exe_sha256.ToLowerInvariant()
$allDataGood=($now.file_count -eq $baseline.original.original_data.file_count -and
 $now.total_bytes -eq $baseline.original.original_data.total_bytes -and
 $now.content_and_relative_path_tree_sha256 -eq $baseline.original.original_data.content_and_relative_path_tree_sha256)

# The P4-22 v1 baseline fingerprints FILES, not empty directories.
# Use the independently preserved backup as an additional source for
# read-only directory-layout comparison. Never rewrite or rebaseline v1.
$directoryCounts=@{
 critical_project_store=@{added=0;missing=0}
 browser_cache_candidate=@{added=0;missing=0}
 unclassified=@{added=0;missing=0}
}
foreach ($name in @(@($before.directories.Keys) + @($now.directories.Keys) | Sort-Object -Unique)) {
 $was=$before.directories.ContainsKey($name)
 $is=$now.directories.ContainsKey($name)
 if ($was -eq $is) {continue}
 $change=if ($is) {'added'} else {'missing'}
 $category=Category ($name+'/')
 $directoryCounts[$category][$change]++
}
$criticalDirectoryChanges=$directoryCounts.critical_project_store.added+$directoryCounts.critical_project_store.missing
$browserDirectoryChanges=$directoryCounts.browser_cache_candidate.added+$directoryCounts.browser_cache_candidate.missing
$otherDirectoryChanges=$directoryCounts.unclassified.added+$directoryCounts.unclassified.missing
$allDirectoryChanges=$criticalDirectoryChanges+$browserDirectoryChanges+$otherDirectoryChanges
$directoryLayoutGood=($allDirectoryChanges -eq 0 -and $before.directory_count -eq $now.directory_count)

# No raw paths, file names, record contents, per-file hashes or identifiers are
# displayed or written. Counts are inclusive: critical changes never waived.
$counts=@{
 critical_project_store=@{added=0;modified=0;missing=0}
 browser_cache_candidate=@{added=0;modified=0;missing=0}
 unclassified=@{added=0;modified=0;missing=0}
}
foreach ($name in @(@($before.files.Keys) + @($now.files.Keys) | Sort-Object -Unique)) {
 $was=$before.files.ContainsKey($name)
 $is=$now.files.ContainsKey($name)
 $change=if (-not $was) {'added'} elseif (-not $is) {'missing'} elseif (
  $before.files[$name].bytes -ne $now.files[$name].bytes -or
  $before.files[$name].content_digest -ne $now.files[$name].content_digest
 ) {'modified'} else { $null }
 if ($null -eq $change) {continue}
 $category=Category $name
 $counts[$category][$change]++
}
$core=$counts.critical_project_store
$browser=$counts.browser_cache_candidate
$other=$counts.unclassified
$criticalTotal=$core.added+$core.modified+$core.missing
$browserTotal=$browser.added+$browser.modified+$browser.missing
$otherTotal=$other.added+$other.modified+$other.missing

# P4-43: sequential filesystem enumeration is NOT an atomic snapshot.
# Re-read both trees and the original EXE after computing change categories.
# If ANY file hash, path, size, directory membership, or EXE digest differs
# between observations, fail closed without claiming a stable verdict.
$backupRecheck=Tree $backup
$currentRecheck=Tree $current
$exeRecheckSha=ShaFile $oldExe
if (-not (SameTree $before $backupRecheck) -or
    -not (SameTree $now $currentRecheck) -or
    $firstExeSha -ne $exeRecheckSha) {
 throw 'Source changed during preservation comparison; stable integrity evidence cannot be established. No cleanup, restore or rebaseline.'
}

[pscustomobject][ordered]@{
 status=if ($allDataGood -and $directoryLayoutGood -and $oldExeGood) {'FULL_FINGERPRINT_MATCH'} else {'REVIEW_REQUIRED_FULL_PRESERVATION_NOT_PASSED'}
 independent_backup_matches_baseline=$true
 original_exe_matches_baseline=$oldExeGood
 full_original_data_tree_matches_baseline=($allDataGood -and $directoryLayoutGood)
 file_fingerprint_matches_p4_22_baseline=$allDataGood
 directory_layout_matches_independent_backup=$directoryLayoutGood
 directory_layout_reference='independent_backup_only_p4_22_v1_baseline_files_only'
 baseline_file_count=$before.file_count
 current_file_count=$now.file_count
 backup_directory_count=$before.directory_count
 current_directory_count=$now.directory_count
 critical_project_store_directory_changes=$criticalDirectoryChanges
 browser_cache_candidate_directory_changes=$browserDirectoryChanges
 unclassified_directory_changes=$otherDirectoryChanges
 all_changed_directories=$allDirectoryChanges
 critical_project_store_changes=$criticalTotal
 critical_project_store_added=$core.added
 critical_project_store_modified=$core.modified
 critical_project_store_missing=$core.missing
 browser_cache_candidate_changes=$browserTotal
 unclassified_changes=$otherTotal
 all_changed_files=$criticalTotal+$browserTotal+$otherTotal
 all_changed_items=$criticalTotal+$browserTotal+$otherTotal+$allDirectoryChanges
 full_data_integrity_waived=$false
 project_data_certified=$false
 writer_process_identified=$false
 offline_8gb_certified=$false
 sequential_rescan_consistent=$true
 snapshot_is_atomic=$false
 note='Directory categories are source-derived hints, not forensic attribution. Empty-directory layout compares current against independent backup only; historic P4-22 v1 baseline never fingerprinted directories, so baseline-time directory provenance cannot be proved. Any file or directory mismatch is FAIL. A second sequential scan checks for drift but is NOT an atomic snapshot or historical attribution. No restore, cleanup, model or user data write.'
}
