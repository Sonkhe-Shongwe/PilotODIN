# Read-only E2 memory triage. No model starts, network, API calls or installers.
# Reports executable BASENAMES only for the 12 largest process families:
# no file paths, command lines, PIDs, window titles or user/project data.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Windows-only diagnostic.'}
function GiB([double]$bytes){[math]::Round($bytes / 1GB,3)}
$os=Get-CimInstance -ClassName Win32_OperatingSystem
$total=[double]$os.TotalVisibleMemorySize * 1024
$free=[double]$os.FreePhysicalMemory * 1024
if($total -le 0){throw 'Cannot establish installed physical RAM.'}
# CIM WorkingSetSize is current mapped physical pages and includes shared
# pages; adding it across processes double-counts shared memory. PrivatePageCount
# is private committed pages, not necessarily pages resident in RAM.
$processes=@(Get-CimInstance -ClassName Win32_Process -Property Name,WorkingSetSize,PrivatePageCount |
  Where-Object { -not [string]::IsNullOrWhiteSpace($_.Name) })
$rows=@(foreach($group in @($processes | Group-Object -Property Name)){
    $working=0.0
    $private=0.0
    foreach($process in $group.Group){
        $working += [double]$process.WorkingSetSize
        $private += [double]$process.PrivatePageCount
    }
    [pscustomobject]@{
        executable_name = [string]$group.Name
        process_count = @($group.Group).Count
        working_set_gib_sum = GiB $working
        private_committed_gib_sum = GiB $private
    }
})
$top=@($rows | Sort-Object -Property working_set_gib_sum -Descending | Select-Object -First 12)
$allWorking=0.0
$allPrivate=0.0
foreach($row in $rows){
    $allWorking += $row.working_set_gib_sum
    $allPrivate += $row.private_committed_gib_sum
}
$report=[ordered]@{
  probe='PilotODIN early E2 low-RAM triage, read-only'
  generated_utc=[datetime]::UtcNow.ToString('o')
  physical_memory_gib=GiB $total
  free_physical_memory_gib=GiB $free
  available_fraction=[math]::Round($free/$total,3)
  eight_gib_class=($total -ge (7 * 1GB) -and $total -le (9.5 * 1GB))
  process_count=$processes.Count
  top_twelve_executable_families=$top
  # These group sums are diagnostic comparisons ONLY; not system RAM usage,
  # since shared pages appear in multiple processes, and committed memory
  # can be resident, paged out, or compressed by Windows.
  all_family_working_set_gib_sum_approx=[math]::Round($allWorking,3)
  all_family_private_committed_gib_sum_approx=[math]::Round($allPrivate,3)
  contains_executable_names=$true
  omitted_fields=@('process_id','username','process_command_line','executable_path','window_title','project_data')
  ollama_processes=@($processes | Where-Object { $_.Name -ieq 'ollama.exe' }).Count
  ollama_model_loaded='NOT_CHECKED'
  model_inference='NOT_RUN'
  actual_offline_generation='NOT_TESTED'
  actual_8gb_concurrent_stress='NOT_TESTED'
  result='UNDETERMINED'
}
$out=Join-Path $env:TEMP ('pilotodin-e2-memory-triage-'+[guid]::NewGuid().ToString('N').Substring(0,12)+'.json')
$zip=[IO.Path]::ChangeExtension($out,'.zip')
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $out -Encoding UTF8
Compress-Archive -LiteralPath $out -DestinationPath $zip -Force
Write-Host ''
Write-Host 'PilotODIN E2 read-only low-RAM triage (NOT an offline AI benchmark)'
Write-Host ('Physical RAM: '+$report.physical_memory_gib+' GiB')
Write-Host ('Free RAM now: '+$report.free_physical_memory_gib+' GiB')
Write-Host '12 largest process families (working sets; summed, may double-count shared pages):'
$top | Format-Table -Property executable_name,process_count,working_set_gib_sum,private_committed_gib_sum -AutoSize
Write-Host ('Ollama processes detected: '+$report.ollama_processes+' (loaded-model status NOT CHECKED)')
Write-Host 'No processes stopped; no models started/downloaded; no user file paths or commands captured.'
Write-Host ('Diagnostic ZIP (contains executable basenames only): '+$zip)
