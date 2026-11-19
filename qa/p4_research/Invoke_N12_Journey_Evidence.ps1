# Windows-only operations for the source-pinned N12 app journey.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('sysmon-tail','etw-export','etw-process-export','etw-app-lifetime-export','close','profile-active','webview-children','process-bookend','backend-tcp')][string]$Operation,
    [string]$CaptureRoot,
    [int]$AppProcessId,
    [string]$AppPath,
    [string]$AppTitle,
    [switch]$ReportCloseStatus,
    [string]$ProfilePath,
    [int]$BackendProcessId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'N12 journey operations require disposable hosted Windows.'
}
$lifetimeEtw = $Operation -cin 'sysmon-tail','etw-process-export' -and
    $env:GITHUB_RUN_ATTEMPT -ceq '1' -and
    $env:PILOTODIN_N12_LIFETIME_CONTROL_CONSENT -ceq 'I_APPROVE_ONE_N12_LIFETIME_ETW_CONTROL'
$rehearsalRead = $Operation -ceq 'sysmon-tail' -and $env:GITHUB_RUN_ATTEMPT -ceq '1' -and
    ($env:PILOTODIN_N12_COLLECTOR_REHEARSAL_CONSENT -ceq 'I_APPROVE_ONE_N12_COLLECTOR_REHEARSAL' -or
     $env:PILOTODIN_N12_LIFETIME_CONTROL_CONSENT -ceq 'I_APPROVE_ONE_N12_LIFETIME_CONTROL')
$socketLifetimeRead = $Operation -ceq 'sysmon-tail' -and $env:GITHUB_RUN_ATTEMPT -ceq '1' -and
    $env:PILOTODIN_N12_SOCKET_LIFETIME_SOURCE -cmatch '^[0-9a-f]{40}$' -and
    (git rev-parse HEAD) -ceq $env:PILOTODIN_N12_SOCKET_LIFETIME_SOURCE
if (-not $rehearsalRead -and -not $lifetimeEtw -and -not $socketLifetimeRead -and
    $env:PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT -cne 'I_APPROVE_UNPACKAGED_P4_NATIVE_DEV') {
    throw 'N12 journey operations require an approved disposable hosted Windows run.'
}

switch ($Operation) {
    'sysmon-tail' {
        $channel = 'Microsoft-Windows-Sysmon/Operational'
        if (-not (Get-WinEvent -ListLog $channel).IsEnabled) { throw 'Sysmon channel is disabled.' }
        (Get-WinEvent -LogName $channel -MaxEvents 1).RecordId
    }
    'close' {
        . (Join-Path $PSScriptRoot '../p4_native/Close_P4_Verified_Window.ps1')
        Close-P4VerifiedWindow -AppProcessId $AppProcessId -ExpectedPath $AppPath -ExpectedTitle $AppTitle `
            -ReportCloseStatus:$ReportCloseStatus
    }
    'profile-active' {
        if ([string]::IsNullOrWhiteSpace($ProfilePath)) { throw 'The disposable profile path is required.' }
        $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'msedgewebview2.exe'" |
            Where-Object { $_.CommandLine -and
                $_.CommandLine.IndexOf($ProfilePath, [StringComparison]::OrdinalIgnoreCase) -ge 0 })
        $processes.Count
    }
    'webview-children' {
        if ($env:PILOTODIN_N12_APP_JOURNEY_CONSENT -cne 'I_APPROVE_ONE_N12_APP_JOURNEY' -or
            $AppProcessId -le 0) { throw 'N12 child process evidence requires an approved journey.' }
        $descendants = [System.Collections.Generic.HashSet[int]]::new()
        [void]$descendants.Add($AppProcessId)
        $rows = @(Get-CimInstance Win32_Process -Filter "Name = 'msedgewebview2.exe'" |
            Where-Object CreationDate | Sort-Object CreationDate | ForEach-Object {
                if ($descendants.Contains([int]$_.ParentProcessId) -and $descendants.Add([int]$_.ProcessId)) {
                    @{ pid = [int]$_.ProcessId; birth_ticks = $_.CreationDate.ToUniversalTime().Ticks }
                }
            })
        ConvertTo-Json -InputObject $rows -Compress
    }
    'process-bookend' {
        $processRows = @(Get-CimInstance -ClassName Win32_Process -Property ProcessId,CreationDate |
            Where-Object CreationDate | ForEach-Object {
                @{ pid = $_.ProcessId; birth_ticks = $_.CreationDate.ToUniversalTime().Ticks }
            })
        $threadRows = $null
        try {
            $threadRows = @(foreach ($process in [Diagnostics.Process]::GetProcesses()) {
                try {
                    foreach ($thread in $process.Threads) {
                        try {
                            if ($thread.Id -gt 0) {
                                @{ pid = $process.Id; tid = $thread.Id; birth_ticks = $thread.StartTime.ToUniversalTime().Ticks }
                            }
                        } catch {
                            # Windows may deny the read or the thread may have exited.
                        }
                    }
                } catch {
                    # A process can exit during enumeration.
                } finally {
                    $process.Dispose()
                }
            })
        } catch {
            # Preserve process evidence if optional thread enumeration fails.
        }
        ConvertTo-Json -InputObject @{ processes = $processRows; threads = $threadRows } -Compress -Depth 4
    }
    'backend-tcp' {
        if ($env:PILOTODIN_N12_APP_JOURNEY_CONSENT -cne 'I_APPROVE_ONE_N12_APP_JOURNEY' -or
            $BackendProcessId -le 0) { throw 'N12 backend socket evidence requires an approved journey.' }
        $backend = Get-Process -Id $BackendProcessId
        try {
            $birth = $backend.StartTime.ToUniversalTime().Ticks
            $rows = @(Get-NetTCPConnection -OwningProcess $BackendProcessId -State Established |
                ForEach-Object {
                    @{ local_address = $_.LocalAddress; local_port = [int]$_.LocalPort
                       remote_address = $_.RemoteAddress; remote_port = [int]$_.RemotePort }
                })
            $sample = [DateTime]::UtcNow.Ticks
            if ($backend.HasExited) { throw 'Backend exited during the socket snapshot.' }
            ConvertTo-Json -InputObject @{ pid = $BackendProcessId; birth_ticks = $birth
                observed_ticks = $sample; sockets = $rows } -Compress -Depth 4
        } finally {
            $backend.Dispose()
        }
    }
    { $_ -in 'etw-export','etw-process-export','etw-app-lifetime-export' } {
        $appLifetime = $_ -ceq 'etw-app-lifetime-export'
        $imagePathControl = $lifetimeEtw -and $env:PILOTODIN_N12_IMAGE_PATH_CONTROL -ceq '1'
        $processOnly = $_ -cne 'etw-export'
        if ($processOnly) {
            $expected = if ($appLifetime) {
                Join-Path $env:RUNNER_TEMP "pilotodin-n12-build-$env:GITHUB_RUN_ID-lifetime"
            } else {
                Join-Path $env:RUNNER_TEMP "pilotodin-n12-live-$env:GITHUB_RUN_ID"
            }
            $approved = if ($appLifetime) {
                $env:GITHUB_RUN_ATTEMPT -ceq '1' -and
                    $env:PILOTODIN_N12_APP_LIFETIME_CONSENT -ceq 'I_APPROVE_ONE_N12_APP_LIFETIME'
            } else { $lifetimeEtw }
            if (-not $approved -or $env:GITHUB_RUN_ID -cnotmatch '^[0-9]+$' -or
                [IO.Path]::GetFullPath($CaptureRoot) -ne [IO.Path]::GetFullPath($expected)) {
                throw 'Process-only ETW export requires its approved hosted capture root.'
            }
        }
        $inputFile = if ($processOnly) { 'lifetime.etl' } else { 'journey.etl' }
        $outputFile = if ($processOnly) { 'lifetime-etw.jsonl' } else { 'etw.jsonl' }
        $file = [IO.File]::Open((Join-Path $CaptureRoot $outputFile), [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream = [IO.StreamWriter]::new($file, [Text.UTF8Encoding]::new($false))
        $fileProvider = [guid]'edd08927-9cc4-4e65-b970-c2560fb5c289'
        $processProvider = [guid]'22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716'
        try {
            Get-WinEvent -Path (Join-Path $CaptureRoot $inputFile) -Oldest | ForEach-Object {
                $event = $_
                $lifecycle = $event.ProviderId -eq $processProvider -and
                    ($event.Id -in 1,2 -or (-not $processOnly -and $event.Id -in 3,4))
                if ($lifecycle -or (-not $processOnly -and $event.ProviderId -eq $fileProvider -and
                    $event.Id -in 10,11,12,13,14,15,16,17,18,19,21,23,24,26,27,28,29,34)) {
                    $xml = [xml]$event.ToXml()
                    $fields = @{}
                    $duplicateLifecycleField = $false
                    foreach ($field in $xml.SelectNodes("//*[local-name()='EventData']/*[local-name()='Data']")) {
                        $name = $field.GetAttribute('Name')
                        if ($processOnly) {
                            if ($name -cnotin 'ProcessID','ProcessSequenceNumber','ParentProcessID',
                                'ParentProcessSequenceNumber','CreateTime','ExitTime' -and
                                -not (($appLifetime -or $imagePathControl) -and $name -ceq 'ImageName')) { continue }
                            if ($fields.ContainsKey($name)) {
                                throw 'Process-only ETW event fields are ambiguous.'
                            }
                        }
                        if ($lifecycle -and $fields.ContainsKey($name)) {
                            $duplicateLifecycleField = $true
                        }
                        $fields[$name] = $field.InnerText
                    }
                    $row = @{
                        id = $event.Id
                        pid = $event.ProcessId
                        ticks = $event.TimeCreated.ToUniversalTime().Ticks
                        lifecycle = $lifecycle
                        data = $fields
                    }
                    if ($lifecycle -and $event.Id -in 1,2) {
                        $row.version = $event.Version
                        if ($duplicateLifecycleField) { $row.lifecycle_fields_ambiguous = $true }
                    }
                    $stream.WriteLine(($row | ConvertTo-Json -Compress -Depth 4))
                }
            }
        } finally {
            $stream.Dispose()
        }
    }
}
