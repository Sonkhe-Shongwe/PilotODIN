# A disposable fixture probe. The ETL and raw event payloads stay in runner temp.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'
$root = Join-Path $env:RUNNER_TEMP "pilotodin-n12-etw-$([guid]::NewGuid().ToString('N'))"
$result = python (Join-Path $PSScriptRoot 'n12_etw_probe.py') $root
if ($LASTEXITCODE -ne 0) { throw 'The ETW fixture did not complete.' }
$capture = $result | ConvertFrom-Json
$fixture = $capture.fixture
$paths = @($fixture.fixture, $fixture.renamed_fixture)
$deviceSuffixes = @($paths | ForEach-Object { $_.Substring(2) })
$provider = [guid]'edd08927-9cc4-4e65-b970-c2560fb5c289'
$fixtureEvents = @{}
$childEvents = @{}
$fixtureFields = [Collections.Generic.HashSet[string]]::new()
$total = 0
Get-WinEvent -Path (Join-Path $root 'fixture.etl') -Oldest | ForEach-Object {
    $event = $_
    if ($event.ProviderId -eq $provider) {
        $total += 1
        $eventId = $event.Id
        if ($event.ProcessId -eq $fixture.child_pid) {
            $childEvents[$eventId] = 1 + [int]$childEvents[$eventId]
        }
        if ($eventId -in 10,11,12,26,27,30) {
            $xml = [xml]$event.ToXml()
            $data = @($xml.SelectNodes("//*[local-name()='EventData']/*[local-name()='Data']"))
            $matchesFixture = $false
            foreach ($field in $data) {
                if ($field.GetAttribute('Name') -notin 'FileName','FilePath') { continue }
                $value = $field.InnerText
                $devicePath = $value -replace '^\\Device\\HarddiskVolume\d+', ''
                if ($value -in $paths -or ($value -ne $devicePath -and $devicePath -in $deviceSuffixes)) {
                    $matchesFixture = $true
                    break
                }
            }
            if ($matchesFixture) {
                $fixtureEvents[$eventId] = 1 + [int]$fixtureEvents[$eventId]
                foreach ($field in $data) {
                    $name = $field.GetAttribute('Name')
                    if ($name -in 'FileName','FilePath','FileObject','FileKey','Irp','ThreadId','IssuingThreadId','InfoClass') {
                        [void]$fixtureFields.Add($name)
                    }
                }
            }
        }
    }
}
if ($total -eq 0) { throw 'No Kernel File ETW events were decoded.' }

$summary = [ordered]@{
    scope = 'ETW fixture feasibility'
    counters = $capture.counters
    kernel_file_events = $total
    fixture_path_event_ids = [ordered]@{}
    fixture_child_header_event_ids = [ordered]@{}
    fixture_path_event_fields = @($fixtureFields | Sort-Object)
}
foreach ($id in ($fixtureEvents.Keys | Sort-Object)) {
    $summary.fixture_path_event_ids[[string]$id] = $fixtureEvents[$id]
}
foreach ($id in ($childEvents.Keys | Sort-Object)) {
    $summary.fixture_child_header_event_ids[[string]$id] = $childEvents[$id]
}
$summary | ConvertTo-Json -Depth 5 | Write-Host
if ($capture.counters.events_lost -ne 0 -or $capture.counters.log_buffers_lost -ne 0 -or
    $capture.counters.realtime_buffers_lost -ne 0) {
    throw 'Windows reported ETW event or buffer loss.'
}
if ($fixtureEvents.Count -eq 0) { throw 'The ETW probe did not resolve any fixture path.' }
