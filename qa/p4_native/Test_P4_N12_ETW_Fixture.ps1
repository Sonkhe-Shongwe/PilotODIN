# A disposable fixture probe. The ETL and raw event payloads stay in runner temp.
[CmdletBinding()]
param([switch]$WithSysmon, [switch]$CalibrationOnly, [switch]$PreopenedControl,
    [switch]$Rundown, [switch]$SystemTiming)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'The ETW fixture requires disposable GitHub-hosted Windows.'
}
$env:PYTHONDONTWRITEBYTECODE = '1'
$root = Join-Path $env:RUNNER_TEMP "pilotodin-n12-etw-$([guid]::NewGuid().ToString('N'))"
$channel = 'Microsoft-Windows-Sysmon/Operational'
$firstRecord = $null
$probeArgs = @($root)
if ($PreopenedControl -and ($WithSysmon -or $CalibrationOnly)) {
    throw 'The pre-opened control uses its own ETW-only fixture.'
}
if ($PreopenedControl) { $probeArgs += '--preopened-control' }
if ($Rundown) {
    if (-not $PreopenedControl) { throw 'Rundown requires the pre-opened control.' }
    $probeArgs += '--rundown'
}
if ($SystemTiming) {
    if (-not $Rundown) { throw 'System timing requires the native rundown fixture.' }
    $probeArgs += '--system-timing'
}
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
    $log = Get-WinEvent -ListLog $channel -ErrorAction SilentlyContinue
    if ($null -eq $log -or -not $log.IsEnabled) {
        throw 'Combined rehearsal blocked: a configured Sysmon operational channel is required.'
    }
    $firstRecord = (Get-WinEvent -LogName $channel -MaxEvents 1).RecordId + 1
}
if ($WithSysmon -or $CalibrationOnly) { $probeArgs += '--calibration-only' }
$bookends = $null
if (($CalibrationOnly -and -not $WithSysmon) -or $PreopenedControl) {
    # Win32_Process and thread snapshots supply stable identity for processes
    # that predate ETW. Collect names only, never command lines or full paths.
    $bookends = Join-Path $root 'process-bookends.json'
    $before = @(Get-ProcessBookend)
    $threadsBefore = @(Get-ThreadBookend)
    if ($CalibrationOnly -and -not $WithSysmon) { $probeArgs += '--thread-context' }
}
$result = python (Join-Path $PSScriptRoot 'n12_etw_probe.py') @probeArgs
if ($LASTEXITCODE -ne 0) { throw 'The ETW fixture did not complete.' }
$capture = $result | ConvertFrom-Json
if ($bookends) {
    $after = @(Get-ProcessBookend)
    $threadsAfter = @(Get-ThreadBookend)
    @{ before = $before; after = $after; threads_before = $threadsBefore; threads_after = $threadsAfter } |
        ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $bookends -Encoding utf8
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
            ($eventId -in 1,2 -or ($bookends -and $eventId -in 3,4))
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
    $rundownStop = [datetime]::Parse($manifest.etw.rundown_stop_utc).ToUniversalTime()
    $captureStart = [datetime]::Parse($startUtc).ToUniversalTime()
    $captureEnd = [datetime]::Parse($endUtc).ToUniversalTime()
    if ($rundownStop -lt $captureStart -or $rundownStop -gt $captureEnd) {
        throw 'The native rundown stop timestamp falls outside the companion ETW capture window.'
    }
    Write-Host 'Native rundown stop timestamp is inside the companion ETW capture window.'
}
$reducerManifest = Join-Path $root 'capture-manifest.json'
if ($WithSysmon) {
    Start-Sleep -Seconds 3
    $lastRecord = (Get-WinEvent -LogName $channel -MaxEvents 1).RecordId
    $sysmonXml = Join-Path $root 'sysmon.xml'
    $exportArgs = @{ FirstRecord = $firstRecord; LastRecord = $lastRecord; OutputFile = $sysmonXml }
    & (Join-Path $PSScriptRoot 'Export_P4_N12_Sysmon_Trace.ps1') @exportArgs
    $manifest.sysmon_first_record = $firstRecord
    $manifest.sysmon_last_record = $lastRecord
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reducerManifest -Encoding utf8
if ($WithSysmon) {
    $summaryPath = Join-Path $root 'summary.json'
    $PSNativeCommandUseErrorActionPreference = $false
    Write-Host 'Combined rehearsal exported ETW and bounded Sysmon evidence. Starting reducer.'
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration-etw $reducerManifest $sysmonXml $eventsPath $summaryPath
    $auditExit = $LASTEXITCODE
    if (Test-Path -LiteralPath $summaryPath -PathType Leaf) {
        Get-Content -LiteralPath $summaryPath -Raw | Write-Host
    }
    if ($auditExit -ne 0) { throw "Combined rehearsal did not calibrate (exit $auditExit)." }
    return
}
python (Join-Path $PSScriptRoot 'n12_trace.py') check-etw-export $reducerManifest $eventsPath
if ($LASTEXITCODE -ne 0) { throw 'The Windows ETW export failed reducer validation.' }
if ($PreopenedControl) {
    $controlArgs = @($manifestPath, $eventsPath, '--preopened-control')
    if ($Rundown) {
        # Use the native ProcessTrace consumer and TDH decoder. Decoded paths
        # are written only to the disposable runner-temp JSONL file.
        $rundownPath = Join-Path $root 'rundown.jsonl'
        $decoderSource = Join-Path $PSScriptRoot 'n12_fileio_rundown.cpp'
        $decoderExe = Join-Path $root 'n12_fileio_rundown.exe'
        $programFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
        if (-not $programFilesX86) { throw 'The Visual C++ build tools location is unavailable.' }
        $vswhere = Join-Path $programFilesX86 'Microsoft Visual Studio\Installer\vswhere.exe'
        if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) {
            throw 'The Visual Studio installation locator is unavailable.'
        }
        $vsInstall = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -ne 0 -or -not $vsInstall) {
            throw 'The native ETW decoder requires the Visual C++ x64 build tools.'
        }
        $vcvars = Join-Path $vsInstall 'VC\Auxiliary\Build\vcvars64.bat'
        if (-not (Test-Path -LiteralPath $vcvars -PathType Leaf)) {
            throw 'The Visual C++ x64 environment script is unavailable.'
        }
        $compileCommand = 'call "{0}" >nul && cl.exe /nologo /std:c++17 /EHsc /W4 /DUNICODE /D_UNICODE "{1}" /Fe:"{2}" /link tdh.lib advapi32.lib' -f $vcvars, $decoderSource, $decoderExe
        Push-Location $root
        try {
            & $env:ComSpec /d /s /c $compileCommand
            if ($LASTEXITCODE -ne 0) { throw 'The native ProcessTrace decoder did not compile.' }
        } finally {
            Pop-Location
        }
        if (-not (Test-Path -LiteralPath $decoderExe -PathType Leaf)) {
            throw 'The native ProcessTrace decoder executable was not produced.'
        }
        $decoderOutput = @(& $decoderExe (Join-Path $root 'rundown.etl') $rundownPath)
        $decoderExit = $LASTEXITCODE
        if ($decoderExit -ne 0) {
            foreach ($line in $decoderOutput) { Write-Host $line }
            throw 'The native ProcessTrace decoder could not read the rundown trace.'
        }
        $decoderText = ($decoderOutput -join "`n").Trim()
        try {
            $decoderSummary = $decoderText | ConvertFrom-Json -ErrorAction Stop
        } catch {
            throw 'The native ProcessTrace decoder did not return a valid diagnostic summary.'
        }
        Write-Host ('Native ProcessTrace decoder summary: ' + ($decoderSummary | ConvertTo-Json -Compress))
        $manifest.etw.rundown_sha256 = (Get-FileHash -LiteralPath $rundownPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reducerManifest -Encoding utf8
        if ([long]$decoderSummary.rundown_opcode_36 -le 0) {
            throw 'The native decoder observed no classic FileIO rundown records.'
        }
        $decodedRecords = [long]$decoderSummary.tdh_records_written + [long]$decoderSummary.raw_schema_records_written
        if ($decodedRecords -le 0) {
            throw 'The native decoder observed rundown records but recovered no file names.'
        }
        if ([long]$decoderSummary.callback_errors -gt 0) {
            throw 'The native decoder reported callback output errors.'
        }
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
        if ($reducerReport.control_status -ne 'PASS' -or
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
