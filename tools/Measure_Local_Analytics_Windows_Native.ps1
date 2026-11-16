param(
    [Parameter(Mandatory=$true)][string]$ProfilePath,
    [int]$BackendId = 0,
    [int]$AppId = 0
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Read-Processes([int[]]$ProcessIds) {
    $processes = @()
    foreach ($processId in $ProcessIds) {
        if ($processId -gt 0) {
            try { $processes += Get-Process -Id $processId -ErrorAction Stop } catch { }
        }
    }
    [long]$working = 0
    [long]$private = 0
    foreach ($process in $processes) {
        $working += $process.WorkingSet64
        $private += $process.PrivateMemorySize64
    }
    return [ordered]@{
        processes = $processes.Count
        working_set_mib = [Math]::Round($working / 1MB, 2)
        private_mib = [Math]::Round($private / 1MB, 2)
    }
}

$webviews = @(Get-CimInstance Win32_Process -Filter "Name = 'msedgewebview2.exe'")
$webviewIds = @($webviews |
    Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($ProfilePath, [StringComparison]::OrdinalIgnoreCase) -ge 0 } |
    ForEach-Object { [int]$_.ProcessId })
for ($pass = 0; $pass -lt $webviews.Count; $pass++) {
    $children = @($webviews | Where-Object { $_.ParentProcessId -in $webviewIds -and $_.ProcessId -notin $webviewIds } |
        ForEach-Object { [int]$_.ProcessId })
    if ($children.Count -eq 0) { break }
    $webviewIds += $children
}
$debuggers = @(Get-NetTCPConnection -LocalPort 9331 -State Listen -ErrorAction SilentlyContinue)
$unexpected = @($debuggers | Where-Object {
    $_.LocalAddress -notin @('127.0.0.1','::1') -or
    ($_.OwningProcess -ne $AppId -and $_.OwningProcess -notin $webviewIds)
})
$os = Get-CimInstance Win32_OperatingSystem
$mem = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
[ordered]@{
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    total_gib = [Math]::Round([double]$os.TotalVisibleMemorySize / 1MB, 3)
    available_mib = [int]$mem.AvailableMBytes
    system_commit_mib = [Math]::Round([double]$mem.CommittedBytes / 1MB, 2)
    system_pages_input_per_sec = [long]$mem.PagesInputPersec
    backend = Read-Processes @($BackendId)
    desktop = Read-Processes @($AppId)
    webview = Read-Processes $webviewIds
    debugger_isolated = ($debuggers.Count -gt 0 -and $unexpected.Count -eq 0)
} | ConvertTo-Json -Depth 4 -Compress
