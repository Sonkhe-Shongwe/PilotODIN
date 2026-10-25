# E2 EARLY FEASIBILITY PROBE — READ-ONLY, NOT AN OFFLINE / 8 GB CERTIFICATE
# Collects only system memory totals, narrowly scoped runtime process counts
# and optional user-selected local model/runtime file sizes. No network calls,
# installers, process launches, model inference or application data access.
[CmdletBinding()]
param(
    [string]$ModelPath = '',
    [string]$RuntimePath = '',
    [string]$OutputPath = ''
)
$ErrorActionPreference = 'Stop'
if($env:OS -ne 'Windows_NT'){
    throw 'This first-pass E2 hardware inventory is for Windows only.'
}
function Round-GiB([double]$bytes){
    return [math]::Round($bytes / 1GB, 3)
}
$os = Get-CimInstance -ClassName Win32_OperatingSystem
$machine = Get-CimInstance -ClassName Win32_ComputerSystem
$totalBytes = [double]$os.TotalVisibleMemorySize * 1024
$freeBytes = [double]$os.FreePhysicalMemory * 1024
if($totalBytes -le 0){
    throw 'Could not read installed physical memory. No hardware result was inferred.'
}
$probe = [ordered]@{
    probe = 'PilotODIN early E2 feasibility inventory'
    generated_utc = [datetime]::UtcNow.ToString('o')
    evidence_level = 'READ_ONLY_INVENTORY_NOT_8GB_STRESS_OR_OFFLINE_AI'
    os_caption = [string]$os.Caption
    os_architecture = [string]$os.OSArchitecture
    physical_memory_gib = Round-GiB $totalBytes
    free_memory_gib_at_probe = Round-GiB $freeBytes
    available_fraction_at_probe = [math]::Round($freeBytes / $totalBytes,3)
    computer_is_8gb_class = ($totalBytes -ge 7.0GB -and $totalBytes -le 9.5GB)
    process_memory_gib_at_probe = [ordered]@{}
    model_file = [ordered]@{specified = $false; found = $false; size_gib = $null}
    inference_runtime = [ordered]@{specified = $false; found = $false}
    read_only = $true
    internet_disconnected = 'NOT_TESTED'
    ai_inference = 'NOT_TESTED'
    simultaneous_ai_ml_load = 'NOT_TESTED'
    cold_install = 'NOT_TESTED'
    local_model_license = 'NOT_VERIFIED'
    final_e2_decision = 'UNDETERMINED'
}
# Record only counts/aggregate memory for PilotODIN's relevant runtime
# families, never process command lines, usernames or file paths.
$families = @('python','pythonw','node','pilotodin-desktop','ollama','llama-server','llama-cli')
$processes = @(Get-Process -ErrorAction SilentlyContinue)
foreach($family in $families){
    $familyProcesses = @($processes | Where-Object { $_.ProcessName -ieq $family })
    $bytes = ($familyProcesses | Measure-Object -Property WorkingSet64 -Sum).Sum
    $probe.process_memory_gib_at_probe[$family] = [ordered]@{
        count = $familyProcesses.Count
        working_set_gib = Round-GiB ([double]$bytes)
    }
}
if(-not [string]::IsNullOrWhiteSpace($ModelPath)){
    $probe.model_file.specified = $true
    if(Test-Path -LiteralPath $ModelPath -PathType Leaf){
        $info = Get-Item -LiteralPath $ModelPath
        $probe.model_file.found = $true
        $probe.model_file.size_gib = Round-GiB $info.Length
    }
}
if(-not [string]::IsNullOrWhiteSpace($RuntimePath)){
    $probe.inference_runtime.specified = $true
    $probe.inference_runtime.found = (Test-Path -LiteralPath $RuntimePath -PathType Leaf)
}
# File locations, users, project names, models' filenames, local ports,
# startup flags, and data records are intentionally absent from the JSON.
$out = if([string]::IsNullOrWhiteSpace($OutputPath)){
    Join-Path $env:TEMP ('pilotodin-e2-inventory-' + [guid]::NewGuid().ToString('N').Substring(0,12) + '.json')
} else { $OutputPath }
$parent = Split-Path -Parent $out
if(-not (Test-Path -LiteralPath $parent -PathType Container)){
    throw 'Requested inventory output directory does not exist.'
}
$probe | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ''
Write-Host 'PilotODIN — Early E2 hardware inventory (NOT an offline or 8 GB pass)'
Write-Host ('Installed RAM (GiB): ' + $probe.physical_memory_gib)
Write-Host ('Available RAM now (GiB): ' + $probe.free_memory_gib_at_probe)
Write-Host ('8 GB-class test hardware: ' + $probe.computer_is_8gb_class)
Write-Host ('Selected local model exists: ' + $probe.model_file.found)
Write-Host ('Selected local runtime exists: ' + $probe.inference_runtime.found)
Write-Host 'Offline execution, sustained RAM/peak memory, generated tokens and real model license: NOT TESTED'
Write-Host ('Shareable read-only JSON: ' + $out)
