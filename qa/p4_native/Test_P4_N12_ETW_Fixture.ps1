# A disposable fixture probe. The ETL and raw event payloads stay in runner temp.
[CmdletBinding()]
param([switch]$WithSysmon, [switch]$CalibrationOnly)

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
if ($WithSysmon) {
    $log = Get-WinEvent -ListLog $channel -ErrorAction SilentlyContinue
    if ($null -eq $log -or -not $log.IsEnabled) {
        throw 'Combined rehearsal blocked: a configured Sysmon operational channel is required.'
    }
    $firstRecord = (Get-WinEvent -LogName $channel -MaxEvents 1).RecordId + 1
}
if ($WithSysmon -or $CalibrationOnly) { $probeArgs += '--calibration-only' }
$result = python (Join-Path $PSScriptRoot 'n12_etw_probe.py') @probeArgs
if ($LASTEXITCODE -ne 0) { throw 'The ETW fixture did not complete.' }
$capture = $result | ConvertFrom-Json
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
        $isLifecycleEvent = $event.ProviderId -eq $processProvider -and $eventId -in 1,2
        if ($isFileEvent) {
            $ids[$eventId] = 1 + [int]$ids[$eventId]
        }
        if ($isLifecycleEvent -or ($isFileEvent -and $eventId -in 10,11,12,14,16,17,18,19,23,24,27,29,34)) {
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
$devices[$drive] = $capture.device
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
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-etw-preflight $reducerManifest $manifestPath $eventsPath
    if ($LASTEXITCODE -ne 0) { throw 'The strict ETW diagnostic preflight failed.' }
}
