# Run only on the approved disposable GitHub-hosted Windows image.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows' -or
    $env:GITHUB_RUN_ATTEMPT -ne '1') {
    throw 'Live calibration requires the first run on disposable hosted Windows.'
}

function Start-CollectorCommand($Executable, $Arguments, $Description) {
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -PassThru
    if (-not $process.WaitForExit(45000)) { throw "$Description timed out." }
    if ($process.ExitCode -ne 0) { throw "$Description exited with code $($process.ExitCode)." }
}

function Get-MicrosoftCollector($Name, $Executable) {
    $archive = Join-Path $root "$Name.zip"
    $directory = Join-Path $root $Name
    Invoke-WebRequest -Uri "https://download.sysinternals.com/files/$Name.zip" -OutFile $archive -TimeoutSec 60
    Expand-Archive -LiteralPath $archive -DestinationPath $directory
    $binary = Get-Item -LiteralPath (Join-Path $directory $Executable)
    $signature = Get-AuthenticodeSignature -LiteralPath $binary.FullName
    if ($signature.Status -ne 'Valid' -or
        $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -ne 'Microsoft Corporation') {
        throw "$Name failed Microsoft signature validation."
    }
    $hash = (Get-FileHash -LiteralPath $binary.FullName -Algorithm SHA256).Hash
    Write-Host "$Name version $($binary.VersionInfo.FileVersion), SHA-256 $hash"
    return $binary.FullName
}

if (@(Get-Service -Name Sysmon,Sysmon64 -ErrorAction SilentlyContinue).Count -gt 0 -or
    @(Get-Process -Name Procmon,Procmon64 -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Collector already present or running on the disposable image.'
}

$root = Join-Path $env:RUNNER_TEMP "pilotodin-n12-live-$env:GITHUB_RUN_ID"
New-Item -ItemType Directory -Path $root | Out-Null
$channel = 'Microsoft-Windows-Sysmon/Operational'
$clock = Get-TimeZone
$sysmon = Get-MicrosoftCollector 'Sysmon' 'Sysmon64.exe'
$procmon = Get-MicrosoftCollector 'ProcessMonitor' 'Procmon64.exe'
$config = Join-Path $root 'sysmon-config.xml'
$pml = Join-Path $root 'capture.pml'
$csv = Join-Path $root 'capture.csv'
$normalized = Join-Path $root 'capture-utf8.csv'
$xml = Join-Path $root 'sysmon.xml'
$manifest = Join-Path $root 'manifest.json'
$summary = Join-Path $root 'summary.json'

@'
<Sysmon schemaversion="4.50">
  <HashAlgorithms>SHA256</HashAlgorithms>
  <EventFiltering>
    <ProcessCreate onmatch="exclude" />
    <ProcessTerminate onmatch="exclude" />
    <NetworkConnect onmatch="exclude" />
  </EventFiltering>
</Sysmon>
'@ | Set-Content -LiteralPath $config -Encoding ascii

$installStarted = $false
$captureActive = $false
try {
    if ($clock.Id -ne 'UTC') { Set-TimeZone -Id 'UTC' }
    $installStarted = $true
    Start-CollectorCommand $sysmon "-accepteula -i `"$config`"" 'Sysmon setup'
    $latest = Get-WinEvent -LogName $channel -MaxEvents 1
    $firstRecord = $latest.RecordId + 1

    $capture = Start-Process -FilePath $procmon -ArgumentList "/AcceptEula /Quiet /Minimized /NoFilter /BackingFile `"$pml`"" -PassThru
    $captureActive = $true
    Start-CollectorCommand $procmon '/WaitForIdle' 'Process Monitor readiness'
    $capture.Refresh()
    if ($capture.HasExited -or -not (Test-Path -LiteralPath $pml -PathType Leaf)) {
        throw 'Process Monitor capture did not start.'
    }

    $start = [DateTimeOffset]::UtcNow
    $fixtureJson = python (Join-Path $PSScriptRoot 'n12_calibration.py') (Join-Path $root 'fixture')
    if ($LASTEXITCODE -ne 0) { throw 'Generated N12 fixture failed.' }
    $fixture = $fixtureJson | ConvertFrom-Json
    Start-Sleep -Seconds 5
    $end = [DateTimeOffset]::UtcNow
    $lastRecord = (Get-WinEvent -LogName $channel -MaxEvents 1).RecordId

    Start-CollectorCommand $procmon '/Terminate' 'Process Monitor stop'
    if (-not $capture.WaitForExit(30000) -or $capture.ExitCode -ne 0) {
        throw 'Process Monitor capture did not exit cleanly.'
    }
    $captureActive = $false
    Start-CollectorCommand $procmon "/AcceptEula /Quiet /Minimized /NoFilter /OpenLog `"$pml`" /SaveAs `"$csv`"" 'Process Monitor export'
    if (-not (Test-Path -LiteralPath $csv -PathType Leaf)) { throw 'Process Monitor CSV is missing.' }

    # Normalize English 12-hour timestamps if Procmon exported them. The
    # host clock is UTC. Preserve fractional seconds and the rest of each row.
    $reader = [IO.StreamReader]::new($csv, $true)
    try {
        $writer = [IO.StreamWriter]::new($normalized, $false, [Text.UTF8Encoding]::new($false))
        try {
            $writer.WriteLine($reader.ReadLine())
            while ($null -ne ($line = $reader.ReadLine())) {
                if ($line -match '^"(?<hour>0?[1-9]|1[0-2])(?<rest>:\d{2}:\d{2}(?:\.\d{1,7})?) (?<period>AM|PM)"(?<fields>,.*)$') {
                    $hour = [int]$Matches.hour % 12
                    if ($Matches.period -eq 'PM') { $hour += 12 }
                    $line = '"{0:00}{1}"{2}' -f $hour, $Matches.rest, $Matches.fields
                }
                $writer.WriteLine($line)
            }
        } finally { $writer.Dispose() }
    } finally { $reader.Dispose() }

    & (Join-Path $PSScriptRoot 'Export_P4_N12_Sysmon_Trace.ps1') -FirstRecord $firstRecord -LastRecord $lastRecord -OutputFile $xml
    @{
        schema_version = 1
        disposable = $true
        start_utc = $start.ToString('o')
        end_utc = $end.ToString('o')
        sysmon_first_record = $firstRecord
        sysmon_last_record = $lastRecord
        procmon_all_events = $true
        procmon_loss_reviewed = $false
        procmon_clock_utc = (Get-TimeZone).Id -eq 'UTC'
        calibration = $fixture
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifest -Encoding utf8

    # Clean stop and export do not establish a collector loss review. Keep
    # that flag false and use the summary to assess the known fixture events.
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration $manifest $xml $normalized $summary
    $result = $LASTEXITCODE
    if (Test-Path -LiteralPath $summary -PathType Leaf) {
        $report = Get-Content -LiteralPath $summary -Raw
        $report | Tee-Object -FilePath $env:GITHUB_STEP_SUMMARY -Append | Write-Host
        $evidence = $report | ConvertFrom-Json
        if ($result -eq 2 -and $evidence.coverage_issues.Count -eq 1 -and
            $evidence.coverage_issues[0] -eq 'procmon-coverage-not-confirmed') {
            Write-Host 'Live fixture markers: PASS. Capture-loss review: BLOCKED.'
            return
        }
    }
    if ($result -ne 0) { throw "Live collector calibration did not pass (exit $result)." }
} finally {
    if ($captureActive) {
        try { Start-CollectorCommand $procmon '/Terminate' 'Process Monitor cleanup' }
        catch { Write-Warning 'Process Monitor cleanup did not complete.' }
    }
    if ($installStarted -and @(Get-Service -Name Sysmon,Sysmon64 -ErrorAction SilentlyContinue).Count -gt 0) {
        try { Start-CollectorCommand $sysmon '-u' 'Sysmon cleanup' }
        catch { Write-Warning 'Sysmon cleanup did not complete.' }
    }
    if ($clock.Id -ne 'UTC') { Set-TimeZone -Id $clock.Id }
}
