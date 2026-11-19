# A disposable fixture probe. The ETL and raw event payloads stay in runner temp.
[CmdletBinding()]
param([switch]$WithSysmon, [switch]$CalibrationOnly, [switch]$PreopenedControl,
    [switch]$Rundown, [switch]$SystemTiming, [switch]$ProtectedRestore, [switch]$BackgroundThread)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'The ETW fixture requires disposable GitHub-hosted Windows.'
}
$env:PYTHONDONTWRITEBYTECODE = '1'
$root = Join-Path $env:RUNNER_TEMP "pilotodin-n12-etw-$([guid]::NewGuid().ToString('N'))"
$probeArgs = @($root)
if ($ProtectedRestore -and ($WithSysmon -or $CalibrationOnly -or $PreopenedControl -or $Rundown -or $SystemTiming)) {
    throw 'The protected write and restore uses its own approved ETW fixture.'
}
if ($BackgroundThread -and ($WithSysmon -or $CalibrationOnly -or $PreopenedControl -or
        $Rundown -or $SystemTiming -or $ProtectedRestore)) {
    throw 'The background writer uses its own approved ETW fixture.'
}
if ($PreopenedControl -and ($WithSysmon -or $CalibrationOnly)) {
    throw 'The pre-opened control uses its own ETW-only fixture.'
}
if ($PreopenedControl) { $probeArgs += '--preopened-control' }
if ($Rundown) {
    if (-not ($PreopenedControl -or $WithSysmon)) { throw 'Rundown requires a supported fixture.' }
    if ($PreopenedControl) { $probeArgs += '--rundown' }
}
if ($SystemTiming) {
    if (-not ($Rundown -and $PreopenedControl)) { throw 'System timing requires the pre-opened rundown fixture.' }
    $probeArgs += '--system-timing'
}
if ($Rundown) { . (Join-Path $PSScriptRoot 'Export_N12_FileIo_Rundown.ps1') }

function Get-ProcessBookend {
    Get-CimInstance -ClassName Win32_Process -Property ProcessId,CreationDate,Name |
        Where-Object CreationDate |
        ForEach-Object {
            @{ pid = $_.ProcessId; birth_ticks = $_.CreationDate.ToUniversalTime().Ticks; name = $_.Name }
        }
}
function Get-ThreadBookend {
    foreach ($process in [Diagnostics.Process]::GetProcesses()) {
        try {
            foreach ($thread in $process.Threads) {
                try {
                    $birth = $thread.StartTime.ToUniversalTime().Ticks
                    if ($thread.Id -gt 0) {
                        @{ pid = $process.Id; tid = $thread.Id; birth_ticks = $birth }
                    }
                } catch {
                    # A thread can exit during enumeration or deny time queries.
                }
            }
        } catch {
            # A process can exit during enumeration.
        } finally {
            $process.Dispose()
        }
    }
}
if ($WithSysmon) {
    $probeArgs += '--collector-rehearsal'
    if ($Rundown) { $probeArgs += '--rundown' }
} elseif ($CalibrationOnly) {
    $probeArgs += '--calibration-only'
}
$bookends = $null
$withThreadBookends = ($CalibrationOnly -and -not $WithSysmon) -or $PreopenedControl
if ($WithSysmon -or $withThreadBookends) {
    # Win32_Process and thread snapshots supply stable identity for processes
    # that predate ETW. Collect names only, never command lines or full paths.
    $bookends = Join-Path $root 'process-bookends.json'
    $before = @(Get-ProcessBookend)
}
if ($withThreadBookends) {
    $threadsBefore = @(Get-ThreadBookend)
    if ($CalibrationOnly) { $probeArgs += '--thread-context' }
}
if ($WithSysmon) {
    $PSNativeCommandUseErrorActionPreference = $false
    $output = @(python -B -m qa.p4_native.n12_etw_probe @probeArgs)
    $probeExit = $LASTEXITCODE
    foreach ($line in $output) {
        if ($line.StartsWith('N12 initial Sysmon calibration ', [StringComparison]::Ordinal)) {
            Write-Host $line
        }
    }
    if ($probeExit -ne 0 -or $output.Count -eq 0) { throw 'The collector-only fixture did not complete.' }
    $result = $output[-1]
} elseif ($ProtectedRestore) {
    $result = python -B -m qa.p4_native.n12_protected_restore capture $root
    if ($LASTEXITCODE -ne 0) { throw 'The protected write and restore fixture did not complete.' }
} elseif ($BackgroundThread) {
    $result = python -B -m qa.p4_native.n12_background_thread capture $root
    if ($LASTEXITCODE -ne 0) { throw 'The background writer fixture did not complete.' }
} else {
    $result = python (Join-Path $PSScriptRoot 'n12_etw_probe.py') @probeArgs
    if ($LASTEXITCODE -ne 0) { throw 'The ETW fixture did not complete.' }
}
$capture = $result | ConvertFrom-Json
if ($bookends) {
    $after = @(Get-ProcessBookend)
    $snapshots = @{ before = $before; after = $after }
    if ($withThreadBookends) {
        $snapshots.threads_before = $threadsBefore
        $snapshots.threads_after = @(Get-ThreadBookend)
    }
    $snapshots | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $bookends -Encoding utf8
}
$manifestPath = Join-Path $root 'fixture.json'
$eventsPath = Join-Path $root 'events.jsonl'
$result | Set-Content -LiteralPath $manifestPath -Encoding utf8
$provider = [guid]'edd08927-9cc4-4e65-b970-c2560fb5c289'
$processProvider = [guid]'22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716'
$ids = @{}
$captureStart = [long]$capture.start_ticks
$captureEnd = [long]$capture.end_ticks
$outside = @{}
$stream = [IO.StreamWriter]::new($eventsPath, $false, [Text.UTF8Encoding]::new($false))
try {
    Get-WinEvent -Path (Join-Path $root 'fixture.etl') -Oldest | ForEach-Object {
        $event = $_
        $eventId = $event.Id
        $isFileEvent = $event.ProviderId -eq $provider
        $isLifecycleEvent = $event.ProviderId -eq $processProvider -and
            ($eventId -in 1,2 -or (($withThreadBookends -or $ProtectedRestore -or $BackgroundThread) -and
                $eventId -in 3,4))
        if ($isFileEvent) {
            $ids[$eventId] = 1 + [int]$ids[$eventId]
        }
        if ($isLifecycleEvent -or ($isFileEvent -and
                ($eventId -in 10,11,12,13,14,16,17,18,19,23,24,26,27,28,29,34 -or
                    ($SystemTiming -and $eventId -in 15,21)))) {
            $ticks = $event.TimeCreated.ToUniversalTime().Ticks
            if ($ticks -lt $captureStart -or $ticks -gt $captureEnd) {
                $side = if ($ticks -lt $captureStart) { 'before' } else { 'after' }
                $offset = if ($side -eq 'before') { $captureStart - $ticks } else { $ticks - $captureEnd }
                $kind = if ($isLifecycleEvent) { 'process' } else { 'file' }
                $key = "$side-$kind-$eventId"
                if (-not $outside.ContainsKey($key)) { $outside[$key] = @{ count = 0; max_ticks = 0 } }
                $outside[$key].count++
                $outside[$key].max_ticks = [Math]::Max([long]$outside[$key].max_ticks, $offset)
            }
            $xml = [xml]$event.ToXml()
            $fields = @{}
            foreach ($field in $xml.SelectNodes("//*[local-name()='EventData']/*[local-name()='Data']")) {
                $fields[$field.GetAttribute('Name')] = $field.InnerText
            }
            $stream.WriteLine((@{
                id = $eventId
                pid = $event.ProcessId
                ticks = $ticks
                lifecycle = $isLifecycleEvent
                data = $fields
            } | ConvertTo-Json -Compress -Depth 4))
        }
    }
} finally {
    $stream.Dispose()
}
if ($outside.Count) {
    Write-Host ('ETW events outside capture bounds by event ID: ' +
        ($outside | ConvertTo-Json -Compress))
}
$drive = [IO.Path]::GetPathRoot($root).TrimEnd('\')
$devices = @{}
if ($capture.volume_devices) {
    foreach ($entry in $capture.volume_devices.PSObject.Properties) {
        $devices[$entry.Name] = $entry.Value
    }
}
if (-not $devices.ContainsKey($drive)) {
    $devices[$drive] = $capture.device
}
$startUtc = [datetime]::new([long]$capture.start_ticks, [DateTimeKind]::Utc).ToString('o')
$endUtc = [datetime]::new([long]$capture.end_ticks, [DateTimeKind]::Utc).ToString('o')
$manifest = @{
    schema_version = 1
    disposable = $true
    start_utc = $startUtc
    end_utc = $endUtc
    calibration = $capture.fixture
    protected_roots = @{ synthetic = $capture.protected_root }
    etw = @{
        schema_version = 1
        start_utc = $startUtc
        end_utc = $endUtc
        events_sha256 = (Get-FileHash -LiteralPath $eventsPath -Algorithm SHA256).Hash.ToLowerInvariant()
        volume_devices = $devices
        counters = $capture.counters
    }
}
$rundownStopTicks = $null
if ($capture.PSObject.Properties.Name -contains 'rundown_stop_ticks') {
    $rundownStopTicks = $capture.rundown_stop_ticks
}
if ($null -ne $rundownStopTicks) {
    $manifest.etw.rundown_stop_utc = [datetime]::new([long]$rundownStopTicks, [DateTimeKind]::Utc).ToString('o')
}
if ($Rundown -and $null -eq $rundownStopTicks) {
    throw 'The native rundown stop timestamp was not captured inside the ETW window.'
}
if ($Rundown) {
    if ($capture.PSObject.Properties.Name -notcontains 'rundown_start_ticks') {
        throw 'The native rundown start timestamp was not captured inside the ETW window.'
    }
    $rundownStart = [datetime]::new([long]$capture.rundown_start_ticks, [DateTimeKind]::Utc)
    $rundownStop = [datetime]::Parse($manifest.etw.rundown_stop_utc).ToUniversalTime()
    $captureStart = [datetime]::Parse($startUtc).ToUniversalTime()
    $captureEnd = [datetime]::Parse($endUtc).ToUniversalTime()
    if ($rundownStart -lt $captureStart -or $rundownStop -lt $rundownStart -or $rundownStop -gt $captureEnd) {
        throw 'The native rundown timestamps fall outside the companion ETW capture window.'
    }
    $manifest.etw.rundown_start_utc = $rundownStart.ToString('o')
    Write-Host 'Native rundown stop timestamp is inside the companion ETW capture window.'
}
$reducerManifest = Join-Path $root 'capture-manifest.json'
if ($WithSysmon) {
    Start-Sleep -Seconds 3
    $lastRecord = (Get-WinEvent -LogName 'Microsoft-Windows-Sysmon/Operational' -MaxEvents 1).RecordId
    if ($lastRecord -lt $capture.sysmon.prelaunch_last_record) {
        throw 'The Sysmon record ID regressed after the shared prelaunch check.'
    }
    $sysmonXml = Join-Path $root 'sysmon.xml'
    & (Join-Path $PSScriptRoot 'Export_P4_N12_Sysmon_Trace.ps1') -FirstRecord $capture.sysmon.first_record -LastRecord $lastRecord -OutputFile $sysmonXml
    $manifest.sysmon_first_record = $capture.sysmon.first_record
    $manifest.sysmon_last_record = $lastRecord
    $manifest.collector_fixture_precision = $true
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reducerManifest -Encoding utf8
if ($WithSysmon) {
    $baselinePath = Join-Path $root 'summary-without-bookends.json'
    $summaryPath = Join-Path $root 'summary.json'
    $PSNativeCommandUseErrorActionPreference = $false
    Write-Host 'Combined rehearsal exported ETW and bounded Sysmon evidence. Starting reducer.'
    Write-Host 'Baseline summary without process snapshots:'
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration-etw $reducerManifest $sysmonXml $eventsPath $baselinePath
    if ($LASTEXITCODE -notin 0,2 -or -not (Test-Path -LiteralPath $baselinePath -PathType Leaf)) {
        throw 'Combined rehearsal could not produce the baseline summary.'
    }
    Get-Content -LiteralPath $baselinePath -Raw | Write-Host
    Write-Host 'Summary with process snapshots from the same capture:'
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration-etw $reducerManifest $sysmonXml $eventsPath $summaryPath --process-bookends $bookends
    $auditExit = $LASTEXITCODE
    if (Test-Path -LiteralPath $summaryPath -PathType Leaf) {
        Get-Content -LiteralPath $summaryPath -Raw | Write-Host
    }
    if ($Rundown -and $auditExit -in 0,2 -and (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
        $rundownPath = Export-N12FileIoRundown $root
        $manifest.etw.rundown_sha256 = (Get-FileHash -LiteralPath $rundownPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reducerManifest -Encoding utf8
        $comparisonPath = Join-Path $root 'summary-with-rundown-candidates.json'
        Write-Host 'Summary with process snapshots and native rundown candidates from the same capture:'
        python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration-etw $reducerManifest $sysmonXml $eventsPath $comparisonPath --process-bookends $bookends --rundown $rundownPath
        if ($LASTEXITCODE -ne $auditExit -or -not (Test-Path -LiteralPath $comparisonPath -PathType Leaf)) {
            throw 'The rundown comparison failed or disagreed with the strict calibration verdict.'
        }
        Get-Content -LiteralPath $comparisonPath -Raw | Write-Host

        $creditPath = Join-Path $root 'summary-with-verified-rundown-credit.json'
        Write-Host 'Strict comparison with verified background paths credited from the same capture:'
        python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration-etw $reducerManifest $sysmonXml $eventsPath $creditPath --process-bookends $bookends --rundown $rundownPath --credit-verified-rundown
        if (($LASTEXITCODE -notin 0,2) -or -not (Test-Path -LiteralPath $creditPath -PathType Leaf)) {
            throw 'The verified rundown credit comparison failed to produce a report.'
        }
        Get-Content -LiteralPath $creditPath -Raw | Write-Host
    }
    if ($auditExit -ne 0) { throw "Combined rehearsal did not calibrate (exit $auditExit)." }
    return
}
python (Join-Path $PSScriptRoot 'n12_trace.py') check-etw-export $reducerManifest $eventsPath
if ($LASTEXITCODE -ne 0) { throw 'The Windows ETW export failed reducer validation.' }
if ($ProtectedRestore) {
    python -B -m qa.p4_native.n12_protected_restore reduce $reducerManifest $manifestPath $eventsPath
    if ($LASTEXITCODE -ne 0) { throw 'The protected write and restore evidence was blocked.' }
    return
}
if ($BackgroundThread) {
    python -B -m qa.p4_native.n12_background_thread reduce $reducerManifest $manifestPath $eventsPath
    if ($LASTEXITCODE -ne 0) { throw 'The background thread evidence was blocked.' }
    return
}
if ($PreopenedControl) {
    $controlArgs = @($manifestPath, $eventsPath, '--preopened-control')
    if ($Rundown) {
        $rundownPath = Export-N12FileIoRundown $root
        $manifest.etw.rundown_sha256 = (Get-FileHash -LiteralPath $rundownPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reducerManifest -Encoding utf8
        $controlArgs += $rundownPath
    }
    $controlOutput = @(python (Join-Path $PSScriptRoot 'n12_etw_correlate.py') @controlArgs)
    $controlExit = $LASTEXITCODE
    if ($controlExit -ne 0) {
        foreach ($line in $controlOutput) { Write-Host $line }
        throw 'The pre-opened control could not validate both write completions.'
    }
    $controlText = ($controlOutput -join "`n").Trim()
    try {
        $controlReport = $controlText | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw 'The pre-opened control did not return a valid redacted report.'
    }
    Write-Host ('Pre-opened control summary: ' + ($controlReport | ConvertTo-Json -Compress -Depth 8))
    if (-not $Rundown) {
        $known = $controlReport.known_write
        Write-Host ('Known file opened during capture: ' + ($known | ConvertTo-Json -Compress))
        if ($known.status -ne 'PASS' -or $known.matched_file -cne 'known-write.bin') {
            throw 'The single-write control could not verify its expected filename.'
        }
        $resize = $controlReport.known_resize
        Write-Host ('Known file resize: ' + ($resize | ConvertTo-Json -Compress))
        if ($resize.status -ne 'PASS' -or $resize.matched_file -cne 'known-resize.bin' -or
            $resize.before_bytes -ne 96 -or $resize.after_bytes -ne 37) {
            throw 'The single-resize control could not verify its expected filename and size change.'
        }
        $named = $controlReport.in_capture_name_control
        Write-Host ('In-capture name control: ' + ($named | ConvertTo-Json -Compress -Depth 5))
        $requestTime = $named.PSObject.Properties['request_time_path']
        if ($null -ne $requestTime -and $requestTime.Value -eq 'different-from-handle-path') {
            throw 'The in-capture name control disagreed with the verified handle path.'
        }
    }
    if ($Rundown) {
        if ([long]$controlReport.rundown_keys -le 0) {
            throw 'The native rundown did not produce any file-key mappings.'
        }
        foreach ($label in @('protected', 'outside')) {
            $target = $controlReport.targets.PSObject.Properties[$label].Value
            if ($null -eq $target -or $target.request_candidates -ne 1 -or
                $target.completion -ne 'success' -or $target.issuing_thread -ne 'matches' -or
                $target.rundown_name -ne 'matches-target') {
                throw "Native rundown did not independently establish the $label control target."
            }
        }
        Write-Host ('Pre-opened path validation: ' +
            ($controlReport.preopened_path_validation | ConvertTo-Json -Compress))
        if ($SystemTiming) {
            $timing = $controlReport.control_write_timing
            if ($timing.protected.identity -ne 'file-key-and-object' -or
                $timing.protected.explicit_flush_trace -ne 'confirmed') {
                throw 'The System timing fixture could not verify the protected control flush.'
            }
            Write-Host ('System timing control summary: ' + ($timing | ConvertTo-Json -Compress -Depth 8))
            return
        }
        $reducerOutput = @(python (Join-Path $PSScriptRoot 'n12_trace.py') check-etw-preopened-rundown $reducerManifest $manifestPath $eventsPath --rundown $rundownPath --process-bookends $bookends)
        $reducerExit = $LASTEXITCODE
        if ($reducerExit -ne 0) {
            foreach ($line in $reducerOutput) { Write-Host $line }
            throw 'The strict ETW reducer did not classify both pre-opened controls.'
        }
        $reducerText = ($reducerOutput -join [Environment]::NewLine).Trim()
        try {
            $reducerReport = $reducerText | ConvertFrom-Json -ErrorAction Stop
        } catch {
            throw 'The strict ETW reducer did not return a valid redacted report.'
        }
        Write-Host ('Strict reducer pre-opened rundown summary: ' + ($reducerReport | ConvertTo-Json -Compress))
        $known = $reducerReport.known_preopened_write
        Write-Host ('Known file opened before capture: ' + ($known | ConvertTo-Json -Compress))
        $resize = $reducerReport.known_preopened_resize
        Write-Host ('Known resize on a pre-opened file: ' + ($resize | ConvertTo-Json -Compress))
        if ($resize.status -ne 'PASS' -or $resize.without_rundown -ne 'path-unresolved' -or
            $resize.matched_file -cne 'known-resize.bin' -or
            $resize.before_bytes -ne 96 -or $resize.after_bytes -ne 37) {
            throw 'The pre-opened resize comparison did not verify its expected filename and size change.'
        }
        if ($reducerReport.control_status -ne 'PASS' -or
            $known.status -ne 'PASS' -or $known.matched_file -cne 'outside.bin' -or
            $reducerReport.rundown_control_keys_recovered -ne 2 -or
            $reducerReport.strict_coverage -ne 'BLOCKED' -or
            $reducerReport.protected_control_classification -ne 'PROTECTED_WRITE_DETECTED' -or
            $reducerReport.outside_control_classification -ne 'OUTSIDE_PROTECTED_ROOTS') {
            throw 'The strict ETW reducer did not preserve the protected/outside control distinction.'
        }
    }
    return
}
$report = python (Join-Path $PSScriptRoot 'n12_etw_correlate.py') $manifestPath $eventsPath
if ($LASTEXITCODE -ne 0) { throw 'The ETW correlation did not complete.' }
$summary = @{
    scope = 'ETW synthetic fixture correlation'
    counters = $capture.counters
    observed_event_ids = @($ids.Keys | Sort-Object)
    correlation = $report | ConvertFrom-Json -AsHashtable
}
$summary | ConvertTo-Json -Depth 6 | Write-Host
$expected = @(
    'fixture:create:original', 'fixture:write:original', 'fixture:resize:original',
    'fixture:rename:original:renamed', 'fixture:delete:renamed'
)
if (-not $CalibrationOnly) {
    $expected += @('second-writer:rename:source:destination',
        'other:create:protected', 'other:write:protected', 'other:delete:protected')
    if ($summary.correlation.operations.Contains('second-writer:create:source') -or
        -not $summary.correlation.failed.Contains('second-writer:open:source') -or
        $summary.correlation.protected_writes -lt 1) {
        throw 'ETW fixture failed the second-writer or protected-directory control.'
    }
} elseif ($summary.correlation.protected_writes -ne 0) {
    throw 'The calibration-only fixture observed an unexpected protected-directory mutation.'
}
$missing = @($expected | Where-Object { -not $summary.correlation.operations.Contains($_) })
if ($missing.Count -or $summary.correlation.unresolved.Count) {
    throw "ETW fixture correlation incomplete. Missing: $($missing -join ', ')."
}
if ($CalibrationOnly) {
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-etw-preflight $reducerManifest $manifestPath $eventsPath --process-bookends $bookends
    if ($LASTEXITCODE -ne 0) { throw 'The strict ETW diagnostic preflight failed.' }
}
