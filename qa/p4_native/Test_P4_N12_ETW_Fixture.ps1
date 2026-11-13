# A disposable fixture probe. The ETL and raw event payloads stay in runner temp.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'
$root = Join-Path $env:RUNNER_TEMP "pilotodin-n12-etw-$([guid]::NewGuid().ToString('N'))"
$result = python (Join-Path $PSScriptRoot 'n12_etw_probe.py') $root
if ($LASTEXITCODE -ne 0) { throw 'The ETW fixture did not complete.' }
$capture = $result | ConvertFrom-Json
$manifestPath = Join-Path $root 'fixture.json'
$eventsPath = Join-Path $root 'events.jsonl'
$result | Set-Content -LiteralPath $manifestPath -Encoding utf8
$provider = [guid]'edd08927-9cc4-4e65-b970-c2560fb5c289'
$processProvider = [guid]'22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716'
$ids = @{}
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
        if ($isLifecycleEvent -or ($isFileEvent -and $eventId -in 12,14,16,17,18,19,23,24,27,29,34)) {
            $xml = [xml]$event.ToXml()
            $fields = @{}
            foreach ($field in $xml.SelectNodes("//*[local-name()='EventData']/*[local-name()='Data']")) {
                $fields[$field.GetAttribute('Name')] = $field.InnerText
            }
            $stream.WriteLine((@{
                id = $eventId
                pid = $event.ProcessId
                ticks = $event.TimeCreated.ToUniversalTime().Ticks
                lifecycle = $isLifecycleEvent
                data = $fields
            } | ConvertTo-Json -Compress -Depth 4))
        }
    }
} finally {
    $stream.Dispose()
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
if ($capture.counters.events_lost -ne 0 -or $capture.counters.log_buffers_lost -ne 0 -or
    $capture.counters.realtime_buffers_lost -ne 0) {
    throw 'Windows reported ETW event or buffer loss.'
}
$expected = @(
    'fixture:create:original', 'fixture:write:original', 'fixture:resize:original',
    'fixture:rename:original:renamed', 'fixture:delete:renamed',
    'second-writer:rename:source:destination',
    'other:create:protected', 'other:write:protected', 'other:delete:protected'
)
$missing = @($expected | Where-Object { -not $summary.correlation.operations.Contains($_) })
if ($missing.Count -or $summary.correlation.unresolved.Count -or
    $summary.correlation.operations.Contains('second-writer:create:source') -or
    -not $summary.correlation.failed.Contains('second-writer:open:source') -or
    $summary.correlation.protected_writes -lt 1) {
    throw "ETW fixture correlation incomplete. Missing: $($missing -join ', ')."
}
