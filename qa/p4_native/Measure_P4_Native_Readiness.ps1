# P4-22: strictly opt-in, READ-ONLY Windows evidence. No installer, launch, train or network.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('Baseline','Verify')][string]$Stage,
 [Parameter(Mandatory=$true)][string]$OriginalExe,
 [Parameter(Mandatory=$true)][string]$OriginalData,
 [Parameter(Mandatory=$true)][string]$EvidenceDir,
 [string]$QaExe = '',
 [string]$ExpectedQaSha256 = '',
 [ValidateRange(0,30)][int]$Samples = 0,
 [ValidateRange(1,30)][int]$IntervalSeconds = 2
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Existing([string]$name,[string]$kind) {
 if (-not (Test-Path -LiteralPath $name -PathType $kind)) {
  throw "Required $kind input missing; no source data was modified."
 }
 return (Resolve-Path -LiteralPath $name).Path
}
function Inside([string]$name,[string]$base) {
 $a=[IO.Path]::GetFullPath($name).TrimEnd([char]'\',[char]'/')
 $b=[IO.Path]::GetFullPath($base).TrimEnd([char]'\',[char]'/')
 return ($a.Equals($b,[StringComparison]::OrdinalIgnoreCase) -or
  $a.StartsWith(($b+'\'),[StringComparison]::OrdinalIgnoreCase))
}
function NewJson([string]$destination,[object]$value) {
 # New-file-only: never rewrite or erase previously recorded evidence.
 $content=[Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 8))
 $stream=[IO.File]::Open($destination,[IO.FileMode]::CreateNew,
  [IO.FileAccess]::Write,[IO.FileShare]::None)
 try { $stream.Write($content,0,$content.Length) } finally { $stream.Dispose() }
}
function HashFile([string]$path) {
 return (Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
}
function SnapshotTree([string]$source) {
 $root=[IO.Path]::GetFullPath($source).TrimEnd([char]'\',[char]'/')
 $queue=New-Object 'System.Collections.Generic.Queue[string]'
 $entries=New-Object 'System.Collections.Generic.List[object]'
 $queue.Enqueue($root)
 [long]$size=0
 while ($queue.Count -gt 0) {
  $folder=$queue.Dequeue()
  foreach ($item in @(Get-ChildItem -LiteralPath $folder -Force -ErrorAction Stop)) {
   if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Unexpected reparse point: complete original-data snapshot cannot be established.'
   }
   if ($item.PSIsContainer) {
    $queue.Enqueue($item.FullName)
    continue
   }
   $relative=$item.FullName.Substring($root.Length).TrimStart([char]'\',[char]'/').Replace('\','/')
   $hasher=[Security.Cryptography.SHA256]::Create()
   try {
    $label=[BitConverter]::ToString(
     $hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($relative))
    ).Replace('-','').ToLowerInvariant()
   } finally { $hasher.Dispose() }
   [long]$length=$item.Length
   $size += $length
   $entries.Add([pscustomobject]@{name_digest=$label;bytes=$length;content_digest=(HashFile $item.FullName)})
  }
 }
 $list=New-Object Text.StringBuilder
 foreach ($entry in @($entries | Sort-Object name_digest)) {
  [void]$list.Append($entry.name_digest).Append('|').Append($entry.bytes).Append('|').Append($entry.content_digest).AppendLine()
 }
 $sha=[Security.Cryptography.SHA256]::Create()
 try {
  $combined=[BitConverter]::ToString(
   $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($list.ToString()))
  ).Replace('-','').ToLowerInvariant()
 } finally { $sha.Dispose() }
 return [ordered]@{
  file_count=$entries.Count
  total_bytes=$size
  content_and_relative_path_tree_sha256=$combined
 }
}
function ObserveRam([string]$qa,[int]$count,[int]$pause) {
 if ($count -eq 0) {
  return [ordered]@{status='NOT_TESTED';reason='No samples requested';offline_certified=$false}
 }
 $readings=New-Object 'System.Collections.Generic.List[object]'
 for ($n=0;$n -lt $count;$n++) {
  $all=@(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop)
  $roots=@($all | Where-Object {
   $_.ExecutablePath -and $_.ExecutablePath.Equals($qa,[StringComparison]::OrdinalIgnoreCase)
  } | ForEach-Object { [int]$_.ProcessId })
  $found=@{}
  foreach ($rootId in $roots) { $found[[string]$rootId]=$true }
  $changed=$true
  while ($changed) {
   $changed=$false
   foreach ($process in $all) {
    $pidKey=[string]$process.ProcessId
    if (-not $found.ContainsKey($pidKey) -and
        $found.ContainsKey([string]$process.ParentProcessId)) {
     $found[$pidKey]=$true
     $changed=$true
    }
   }
  }
  [long]$private=0
  [long]$working=0
  $live=0
  foreach ($key in $found.Keys) {
   try {
    $p=Get-Process -Id ([int]$key) -ErrorAction Stop
    $private += [long]$p.PrivateMemorySize64
    $working += [long]$p.WorkingSet64
    $live++
   } catch {
    # An exiting child can disappear between the process list and measurement.
   }
  }
  $os=Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
  $readings.Add([pscustomobject]@{
   processes=$live
   private_mib=[Math]::Round($private/1MB,2)
   working_set_mib=[Math]::Round($working/1MB,2)
   available_gib=[Math]::Round([double]$os.FreePhysicalMemory/1MB,3)
   total_gib=[Math]::Round([double]$os.TotalVisibleMemorySize/1MB,3)
  })
  if ($n -lt $count-1) { Start-Sleep -Seconds $pause }
 }
 $active=@($readings | Where-Object {$_.processes -gt 0})
 if ($active.Count -eq 0) {
  return [ordered]@{status='NOT_TESTED';reason='QA desktop process not observed';offline_certified=$false}
 }
 return [ordered]@{
  status='PARTIAL_OBSERVATION'
  requested_samples=$count
  samples_with_qa_process=$active.Count
  max_tracked_private_mib=($active | Measure-Object -Property private_mib -Maximum).Maximum
  max_tracked_working_set_mib=($active | Measure-Object -Property working_set_mib -Maximum).Maximum
  minimum_system_available_gib=($active | Measure-Object -Property available_gib -Minimum).Minimum
  observed_total_system_gib=$active[0].total_gib
  note='Observed process tree can miss reparented or exited processes; no proof of peak RAM, sustained 8 GB operation or offline isolation.'
  offline_certified=$false
 }
}
if ($env:OS -ne 'Windows_NT') { throw 'Windows-only source-readiness evidence collector.' }
$oldExe=Existing $OriginalExe 'Leaf'
$source=Existing $OriginalData 'Container'
$qa=$null
if ($Stage -eq 'Verify') {
 if (-not $QaExe -or $ExpectedQaSha256 -notmatch '^[a-fA-F0-9]{64}$') {
  throw 'Verify requires QA EXE and independently verified expected SHA256.'
 }
 $qa=Existing $QaExe 'Leaf'
} elseif ($Samples -gt 0) {
 throw 'Memory sampling is only allowed in Verify stage.'
}
$dest=[IO.Path]::GetFullPath($EvidenceDir)
$parents=@($source,[IO.Path]::GetDirectoryName($oldExe))
if ($qa) { $parents += [IO.Path]::GetDirectoryName($qa) }
foreach ($parent in $parents) {
 if (Inside $dest $parent) {throw 'Evidence directory must be outside app data and both app installation roots.'}
}
if (Test-Path -LiteralPath $dest) {
 $existing=Get-Item -LiteralPath $dest -Force
 if (-not $existing.PSIsContainer -or ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
  throw 'Evidence output is not a regular directory.'
 }
} else {
 [void](New-Item -ItemType Directory -Path $dest -ErrorAction Stop)
}
$now=[ordered]@{old_exe_sha256=(HashFile $oldExe);original_data=(SnapshotTree $source)}
if ($Stage -eq 'Baseline') {
 NewJson (Join-Path $dest 'baseline.json') ([ordered]@{
  schema_version=1
  purpose='ORIGINAL_PRESERVATION_BASELINE_NOT_ACCEPTANCE'
  original=$now
  source_file_names_or_contents_exported=$false
 })
 Write-Host 'BASELINE ONLY: original EXE and aggregate original-data integrity digest captured.'
 return
}
$baselineFile=Join-Path $dest 'baseline.json'
if (-not (Test-Path -LiteralPath $baselineFile -PathType Leaf)) {
 throw 'Missing independent pre-test baseline; acceptance cannot be inferred.'
}
$before=Get-Content -LiteralPath $baselineFile -Raw -Encoding UTF8 | ConvertFrom-Json
if ($before.schema_version -ne 1 -or $before.purpose -ne 'ORIGINAL_PRESERVATION_BASELINE_NOT_ACCEPTANCE') {
 throw 'Unknown original-app baseline; refusing comparison.'
}
$preserved=(
 $now.old_exe_sha256 -eq $before.original.old_exe_sha256 -and
 $now.original_data.file_count -eq $before.original.original_data.file_count -and
 $now.original_data.total_bytes -eq $before.original.original_data.total_bytes -and
 $now.original_data.content_and_relative_path_tree_sha256 -eq $before.original.original_data.content_and_relative_path_tree_sha256
)
$qaGood=(HashFile $qa) -eq $ExpectedQaSha256.ToLowerInvariant()
$ram=if ($preserved -and $qaGood) { ObserveRam $qa $Samples $IntervalSeconds } else {
 [ordered]@{status='NOT_TESTED';reason='Integrity preflight failed';offline_certified=$false}
}
$report=[ordered]@{
 schema_version=1
 purpose='OWNER_OPT_IN_READ_ONLY_NATIVE_EVIDENCE'
 status=if ($preserved -and $qaGood) {'INTEGRITY_PASS_NOT_NATIVE_CERTIFICATION'} else {'FAIL'}
 original_exe_and_data_unchanged=$preserved
 qa_exe_matches_supplied_sha256=$qaGood
 original_data_file_count=$now.original_data.file_count
 original_data_total_bytes=$now.original_data.total_bytes
 original_data_aggregate_sha256=$now.original_data.content_and_relative_path_tree_sha256
 ram=$ram
 offline_8gb_acceptance='NOT_TESTED'
 target_business_gate_c='UNVERIFIED'
 owner_native_acceptance='NOT_CERTIFIED_BY_THIS_SCRIPT'
 model_training_performed_by_script=$false
 app_launched_by_script=$false
 source_file_names_or_contents_exported=$false
}
NewJson (Join-Path $dest 'verification.json') $report
if (-not $preserved -or -not $qaGood) {
 throw 'FAIL: original installation/data fingerprint changed or QA EXE hash differs. Do not claim acceptance.'
}
Write-Host 'INTEGRITY PASS only: old EXE+data unchanged and QA EXE hash matches. Native, offline, peak RAM and business acceptance remain open.'
