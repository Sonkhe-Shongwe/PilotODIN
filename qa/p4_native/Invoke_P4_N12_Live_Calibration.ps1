# Run only on the approved disposable GitHub-hosted Windows image.
[CmdletBinding()]
param(
    [switch]$WithEtw,
    [switch]$CollectorRundown,
    [switch]$InitialJourneyFixture,
    [switch]$AppJourney,
    [switch]$AppLifetime,
    [switch]$NoCdp,
    [switch]$NoCdpFileIO,
    [switch]$WebViewStorage,
    [ValidateSet('debug-netlog', 'debug-only')]
    [string]$StorageVariant = 'debug-netlog',
    [switch]$ProcmonEnvironmentControl,
    [switch]$ProcmonTimingControl,
    [switch]$LifetimeControl,
    [switch]$LifetimeEtwControl,
    [switch]$SocketLifetimeControl,
    [string]$SourceSha,
    [string]$ExecutableSha256,
    [string]$WebViewRuntimeDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows' -or
    $env:GITHUB_RUN_ATTEMPT -ne '1') {
    throw 'Live calibration requires the first run on disposable hosted Windows.'
}

# The no-CDP full FileIO path is diagnostic-only. The historic lifetime
# workflow does not request it, and --fileio requires fresh separate one-use
# consent. Fail BEFORE staging, importing collector helpers or installing
# Sysmon. This source path is NOT native execution authorization.
if ($NoCdpFileIO -and (
        -not $NoCdp -or -not $AppLifetime -or -not $WithEtw -or
        $AppJourney -or $WebViewStorage -or $InitialJourneyFixture -or
        $CollectorRundown -or $ProcmonEnvironmentControl -or
        $ProcmonTimingControl -or $LifetimeControl -or $LifetimeEtwControl -or
        $SocketLifetimeControl -or $WebViewRuntimeDirectory -or
        $PSBoundParameters.ContainsKey('StorageVariant') -or
        $env:GITHUB_EVENT_NAME -cne 'push' -or
        $env:GITHUB_REF_NAME -cne 'feature/live-dev-workspace-20261023' -or
        $env:PILOTODIN_N12_NO_CDP_FILEIO_CONSENT -cne 'I_APPROVE_ONE_N12_NO_CDP_FILEIO' -or
        $env:PILOTODIN_N12_CHILD_HANDLE_CONSENT -cne 'I_APPROVE_ONE_N12_QA_CHILD_HANDLES' -or
        $env:PILOTODIN_N12_APP_LIFETIME_CONSENT -cne 'I_APPROVE_ONE_N12_APP_LIFETIME' -or
        $env:PILOTODIN_N12_NO_CDP_STORAGE_CONSENT -cne 'I_APPROVE_ONE_N12_NO_CDP_STORAGE' -or
        $env:PILOTODIN_N12_QA_AMBIENT_LOCAL_VARIANT -or
        $SourceSha -cnotmatch '^[0-9a-f]{40} (-not $WithEtw -or $AppJourney -or $AppLifetime -or $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl)) {
    throw 'The FileIO rundown comparison requires the collector-only ETW rehearsal.'
}

# This optional entry is exclusively for a separately approved one-use,
# source-pinned hosted-Windows app lifetime/profile smoke. Other modes cannot
# inherit it, and the backend CLI independently verifies both consents.
if ($NoCdp -and (-not $AppLifetime -or -not $WithEtw -or $AppJourney -or
        $WebViewStorage -or $InitialJourneyFixture -or $CollectorRundown -or
        $ProcmonEnvironmentControl -or $ProcmonTimingControl -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or
        $WebViewRuntimeDirectory -or
        $env:PILOTODIN_N12_NO_CDP_STORAGE_CONSENT -cne 'I_APPROVE_ONE_N12_NO_CDP_STORAGE')) {
    throw 'A no-CDP profile smoke requires its distinct one-use, hosted app lifetime/ETW approval.'
}

if ($WebViewRuntimeDirectory -and -not $AppJourney) {
    throw 'A WebView2 runtime directory requires the approved app journey.'
}
if ($PSBoundParameters.ContainsKey('StorageVariant') -and -not $WebViewStorage) {
    throw 'Storage variant is only valid for an approved WebView storage capture.'
}

if ($WebViewStorage -and ($WithEtw -or $AppJourney -or $AppLifetime -or $LifetimeControl -or
        $LifetimeEtwControl -or $SocketLifetimeControl -or $InitialJourneyFixture -or $CollectorRundown)) {
    throw 'WebView storage requires its own Process Monitor capture mode.'
}

$procmonControl = $ProcmonEnvironmentControl -or $ProcmonTimingControl
if ($procmonControl) {
    $controlSource = if ($ProcmonTimingControl) {
        $env:PILOTODIN_N12_PROCMON_TIMING_SOURCE
    } else { $env:PILOTODIN_N12_PROCMON_ENVIRONMENT_SOURCE }
    $controlApproved = if ($ProcmonTimingControl) {
        $env:PILOTODIN_N12_PROCMON_TIMING_CONSENT -ceq 'I_APPROVE_ONE_N12_PROCMON_TIMING_CONTROL'
    } else {
        $env:PILOTODIN_N12_PROCMON_ENVIRONMENT_CONSENT -ceq 'I_APPROVE_ONE_N12_PROCMON_ENVIRONMENT_CONTROL'
    }
    if (($ProcmonEnvironmentControl -and $ProcmonTimingControl) -or
        $WithEtw -or $AppJourney -or $AppLifetime -or $WebViewStorage -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or $InitialJourneyFixture -or
        $CollectorRundown -or $SourceSha -or $ExecutableSha256 -or
        $env:GITHUB_EVENT_NAME -cne 'push' -or $env:GITHUB_REF_NAME -cne 'feature/live-dev-workspace-20261023' -or
        $env:GITHUB_RUN_ID -cnotmatch '^[0-9]+$' -or -not $controlApproved -or
        $controlSource -cnotmatch '^[0-9a-f]{40}$' -or (git rev-parse HEAD) -cne $controlSource) {
        throw 'Each Process Monitor control requires its own source-pinned run.'
    }
}

if ($InitialJourneyFixture -and (-not $WithEtw -or $CollectorRundown -or $AppJourney -or $AppLifetime -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or $SourceSha -or $ExecutableSha256 -or
        $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE)) {
    throw 'The initial journey fixture requires its own source-pinned collector-only run.'
}

if ($SocketLifetimeControl) {
    if ($LifetimeControl -or $LifetimeEtwControl -or $AppJourney -or $AppLifetime -or
        $SourceSha -or $ExecutableSha256 -or
        $env:PILOTODIN_N12_SOCKET_LIFETIME_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_SOCKET_LIFETIME_SOURCE) {
        throw 'The socket lifetime comparison requires a source-pinned collector-only run.'
    }
} elseif ($LifetimeControl -or $LifetimeEtwControl) {
    $consent = if ($LifetimeEtwControl) {
        'I_APPROVE_ONE_N12_LIFETIME_ETW_CONTROL'
    } else {
        'I_APPROVE_ONE_N12_LIFETIME_CONTROL'
    }
    if (($LifetimeControl -and $LifetimeEtwControl) -or $AppJourney -or $AppLifetime -or $WithEtw -or $SourceSha -or
        $ExecutableSha256 -or $env:PILOTODIN_N12_LIFETIME_CONTROL_CONSENT -cne $consent -or
        $env:PILOTODIN_N12_LIFETIME_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_LIFETIME_SOURCE) {
        throw 'The collector lifetime control requires its own source-pinned approval.'
    }
} elseif ($AppJourney -or $AppLifetime -or $WebViewStorage) {
    $captureApproved = if ($WebViewStorage) {
        $env:PILOTODIN_N12_WEBVIEW_STORAGE_CONSENT -ceq 'I_APPROVE_ONE_N12_WEBVIEW_STORAGE'
    } elseif ($AppLifetime) {
        $env:PILOTODIN_N12_APP_LIFETIME_CONSENT -ceq 'I_APPROVE_ONE_N12_APP_LIFETIME'
    } else {
        $env:PILOTODIN_N12_APP_JOURNEY_CONSENT -ceq 'I_APPROVE_ONE_N12_APP_JOURNEY'
    }
    if (($AppJourney -and $AppLifetime) -or (-not $WebViewStorage -and -not $WithEtw) -or -not $captureApproved -or
        $env:PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT -cne 'I_APPROVE_UNPACKAGED_P4_NATIVE_DEV' -or
        $SourceSha -cnotmatch '^[0-9a-f]{40}$' -or $SourceSha -cne $env:PILOTODIN_N12_APPROVED_SOURCE -or
        $ExecutableSha256 -cnotmatch '^[0-9a-f]{64}$') {
        throw 'The app journey requires its separate approval and staged binary identity.'
    }
    python -B -m qa.p4_research.n12_app_build verify --source $SourceSha --expected-exe-sha256 $ExecutableSha256
    if ($LASTEXITCODE -ne 0) { throw 'Staged build verification failed before Sysmon provisioning.' }
} elseif ($SourceSha -or $ExecutableSha256) {
    throw 'A staged build identity requires an approved app capture.'
} elseif ($WithEtw -and
    $env:PILOTODIN_N12_COLLECTOR_REHEARSAL_CONSENT -cne 'I_APPROVE_ONE_N12_COLLECTOR_REHEARSAL') {
    throw 'The collector-only rehearsal requires separate approval before provisioning Sysmon.'
}

. (Join-Path $PSScriptRoot 'P4_N12_Collector_Process.ps1')

function Start-CollectorCommand($Executable, $Arguments, $Description) {
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -PassThru
    try {
        $result = Wait-P4N12CollectorExit -Process $process -TimeoutMs 45000
        if ($result.Status -eq 'TIMEOUT') { throw "$Description timed out." }
        if ($result.Status -ne 'EXITED') { throw "$Description exited with code $($result.ExitCode)." }
    } finally {
        $process.Dispose()
    }
}

function Get-MicrosoftCollector($Name, $Executable, $Publisher, $ExpectedHash) {
    $archive = Join-Path $root "$Name.zip"
    $directory = Join-Path $root $Name
    Invoke-WebRequest -Uri "https://download.sysinternals.com/files/$Name.zip" -OutFile $archive -TimeoutSec 60
    Expand-Archive -LiteralPath $archive -DestinationPath $directory
    $binary = Get-Item -LiteralPath (Join-Path $directory $Executable)
    $signature = Get-AuthenticodeSignature -LiteralPath $binary.FullName
    $signer = if ($signature.SignerCertificate) {
        $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
    }
    if ($signature.Status -ne 'Valid' -or
        $signer -ne $Publisher) {
        throw "$Name failed Microsoft signature validation (status $($signature.Status), signer '$signer')."
    }
    $hash = (Get-FileHash -LiteralPath $binary.FullName -Algorithm SHA256).Hash
    if ($hash -ne $ExpectedHash) { throw "$Name differs from the reviewed binary SHA-256." }
    Write-Host "$Name version $($binary.VersionInfo.FileVersion), SHA-256 $hash"
    return $binary.FullName
}

if ((-not $procmonControl -and
        @(Get-Service -Name Sysmon,Sysmon64 -ErrorAction SilentlyContinue).Count -gt 0) -or
    @(Get-Process -Name Procmon,Procmon64 -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Collector already present or running on the disposable image.'
}

$root = Join-Path $env:RUNNER_TEMP "pilotodin-n12-live-$env:GITHUB_RUN_ID"
New-Item -ItemType Directory -Path $root | Out-Null
$channel = 'Microsoft-Windows-Sysmon/Operational'
$clock = Get-TimeZone
$sysmon = if (-not $procmonControl) {
    Get-MicrosoftCollector 'Sysmon' 'Sysmon64.exe' 'Microsoft Windows Publisher' '83d31f2478dc6716cfdbf69e5c384bf043072b5f0d8d7b2eea365f709fda4352'
}
$procmon = $null
if (-not $WithEtw -and -not $LifetimeControl -and -not $LifetimeEtwControl -and -not $SocketLifetimeControl) {
    $procmon = Get-MicrosoftCollector 'ProcessMonitor' 'Procmon64.exe' 'Microsoft Corporation' 'aa0b10e936feea464348695f8a85a2dcafd2cb3dabd1d47d8a57e7594783b27b'
}
$config = Join-Path $root 'sysmon-config.xml'
$pml = Join-Path $root 'capture.pml'
$csv = Join-Path $root 'capture.csv'
$normalized = Join-Path $root 'capture-utf8.csv'
$xml = Join-Path $root 'sysmon.xml'
$manifest = Join-Path $root 'manifest.json'
$summary = Join-Path $root 'summary.json'

$definition = @'
<Sysmon schemaversion="4.50">
  <HashAlgorithms>SHA256</HashAlgorithms>
  <EventFiltering>
    <ProcessCreate onmatch="exclude" />
    <ProcessTerminate onmatch="exclude" />
    <NetworkConnect onmatch="exclude" />
  </EventFiltering>
</Sysmon>
'@
if ($LifetimeEtwControl -or $AppLifetime) {
    $definition = $definition.Replace('<NetworkConnect onmatch="exclude" />', '<NetworkConnect onmatch="include" />')
}
$definition | Set-Content -LiteralPath $config -Encoding ascii

$installStarted = $false
$capture = $null
try {
    if ($null -ne $procmon -and $clock.Id -ne 'UTC') { Set-TimeZone -Id 'UTC' }
    if ($null -ne $sysmon) {
        $installStarted = $true
        Start-CollectorCommand $sysmon "-accepteula -i `"$config`"" 'Sysmon setup'
    }
    if ($SocketLifetimeControl) {
        $socketOptions = @()
        if ($WithEtw) { $socketOptions += '--etw-boundary' }
        python -B -m qa.p4_research.n12_socket_lifetime_control $root @socketOptions
        if ($LASTEXITCODE -ne 0) { throw 'The socket lifetime comparison could not complete.' }
        return
    }
    if ($LifetimeControl -or $LifetimeEtwControl) {
        $captureMode = if ($LifetimeEtwControl) { '--capture-etw' } else { '--capture' }
        python -B -m qa.p4_native.n12_lifetime_control $captureMode $root
        if ($LASTEXITCODE -ne 0) { throw 'The collector lifetime control did not pass.' }
        return
    }
    if ($AppLifetime) {
        $lifetimeArgs = @('--source', $SourceSha, '--expected-exe-sha256', $ExecutableSha256)
        if ($NoCdp) { $lifetimeArgs += '--no-cdp' }
        if ($NoCdpFileIO) { $lifetimeArgs += '--fileio' }
        python -B -m qa.p4_research.n12_app_lifetime @lifetimeArgs
        if ($LASTEXITCODE -ne 0) { throw 'The hosted app lifetime capture failed or returned blocked evidence.' }
        return
    }
    if ($AppJourney) {
        $journeyArgs = @('--source', $SourceSha, '--expected-exe-sha256', $ExecutableSha256)
        if ($WebViewRuntimeDirectory) { $journeyArgs += @('--webview-runtime-directory', $WebViewRuntimeDirectory) }
        python -B -m qa.p4_research.n12_app_journey @journeyArgs
        if ($LASTEXITCODE -ne 0) { throw 'The hosted app journey failed or returned blocked coverage.' }
        return
    }
    if ($InitialJourneyFixture) {
        python -B -m qa.p4_research.n12_app_journey --initial-fixture-only --source $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE
        if ($LASTEXITCODE -ne 0) { throw 'The initial journey fixture was blocked.' }
        return
    }
    if ($WithEtw) {
        & (Join-Path $PSScriptRoot 'Test_P4_N12_ETW_Fixture.ps1') -WithSysmon -Rundown:$CollectorRundown
        return
    }
    if (-not $procmonControl) {
        $latest = Get-WinEvent -LogName $channel -MaxEvents 1
        $firstRecord = $latest.RecordId + 1
    }

    $capture = Start-Process -FilePath $procmon -ArgumentList "/AcceptEula /Quiet /Minimized /NoFilter /BackingFile `"$pml`"" -PassThru
    Start-CollectorCommand $procmon '/WaitForIdle' 'Process Monitor readiness'
    $capture.Refresh()
    if ($capture.HasExited) {
        throw "Process Monitor capture exited with code $($capture.ExitCode) before readiness."
    }
    if (-not (Test-Path -LiteralPath $pml -PathType Leaf)) {
        throw 'Process Monitor backing file was absent after readiness.'
    }
    Write-Host 'Process Monitor capture process is running and its backing file is present.'

    $start = [DateTimeOffset]::UtcNow
    if ($ProcmonTimingControl) {
        python -B -m qa.p4_research.n12_procmon_timing_control capture $root
        if ($LASTEXITCODE -ne 0) { throw 'Same-session timing fixture or ETW export failed.' }
    } elseif ($ProcmonEnvironmentControl) {
        python -B -m qa.p4_research.n12_procmon_environment_control capture $root
        if ($LASTEXITCODE -ne 0) { throw 'Generated Process Monitor environment child failed.' }
    } elseif ($WebViewStorage) {
        python -B -m qa.p4_research.n12_webview_storage_probe capture $root --source $SourceSha --expected-exe-sha256 $ExecutableSha256 --diagnostic-variant $StorageVariant
        if ($LASTEXITCODE -ne 0) { throw 'Focused WebView storage launch or control failed.' }
    } else {
        $fixtureJson = python (Join-Path $PSScriptRoot 'n12_calibration.py') (Join-Path $root 'fixture')
        if ($LASTEXITCODE -ne 0) { throw 'Generated N12 fixture failed.' }
        $fixture = $fixtureJson | ConvertFrom-Json
    }
    Start-Sleep -Seconds 5
    $end = [DateTimeOffset]::UtcNow
    if (-not $procmonControl) {
        $lastRecord = (Get-WinEvent -LogName $channel -MaxEvents 1).RecordId
    }

    $stopError = $null
    $stopCommandVerified = $false
    if ($procmonControl) {
        # Exercise a normal window close on the captured process. The finally
        # block can request termination for cleanup after a failed close.
        Request-P4N12CollectorWindowClose -Process $capture
        $stopCommandVerified = $true
        Write-Host 'Process Monitor main-window close requested.'
    } else {
        try {
            Start-CollectorCommand $procmon '-terminate -quiet' 'Process Monitor stop command'
            $stopCommandVerified = $true
        } catch {
            $stopError = $_.Exception.Message
            Write-Warning $stopError
        }
    }
    $captureExit = Wait-P4N12CollectorExit -Process $capture -TimeoutMs 30000
    if ($captureExit.Status -eq 'TIMEOUT') {
        throw 'Process Monitor capture process was still running 30 seconds after the stop request.'
    }
    Write-Host "Process Monitor capture process exited with code $($captureExit.ExitCode)."
    if ($captureExit.Status -ne 'EXITED') {
        $stopError = 'Process Monitor capture process returned a nonzero exit code.'
        Write-Warning $stopError
    }
    Confirm-P4N12ClosedCapture -Path $pml -Description 'Process Monitor backing file'
    Start-CollectorCommand $procmon "/AcceptEula /Quiet /Minimized /NoFilter /OpenLog `"$pml`" /SaveAs `"$csv`"" 'Process Monitor export'
    Confirm-P4N12ClosedCapture -Path $csv -Description 'Process Monitor CSV'

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

    if ($procmonControl) {
        $controlWindow = @{
            start_utc = $start.ToString('o')
            end_utc = $end.ToString('o')
            clock_utc = (Get-TimeZone).Id -eq 'UTC'
            shutdown_verified = ($null -eq $stopError)
        }
        $controlModule = 'qa.p4_research.n12_procmon_environment_control'
        if ($ProcmonTimingControl) {
            $controlWindow.run = @{
                source_sha = $controlSource
                run_id = $env:GITHUB_RUN_ID
                run_attempt = $env:GITHUB_RUN_ATTEMPT
            }
            $controlWindow.csv_sha256 = (Get-FileHash -LiteralPath $normalized -Algorithm SHA256).Hash.ToLowerInvariant()
            $controlModule = 'qa.p4_research.n12_procmon_timing_control'
        }
        $controlWindow | ConvertTo-Json -Depth 3 |
            Set-Content -LiteralPath (Join-Path $root 'environment-window.json') -Encoding utf8
        python -B -m $controlModule reduce $root
        if ($LASTEXITCODE -ne 0) { throw 'Process Monitor control evidence was blocked.' }
        return
    }
    & (Join-Path $PSScriptRoot 'Export_P4_N12_Sysmon_Trace.ps1') -FirstRecord $firstRecord -LastRecord $lastRecord -OutputFile $xml
    $window = @{
        schema_version = 1
        disposable = $true
        start_utc = $start.ToString('o')
        end_utc = $end.ToString('o')
        sysmon_first_record = $firstRecord
        sysmon_last_record = $lastRecord
        procmon_all_events = $true
        procmon_loss_reviewed = $false
        procmon_clock_utc = (Get-TimeZone).Id -eq 'UTC'
    }
    if ($WebViewStorage) {
        # Keep the exported observations while making shutdown health part of the verdict.
        $window.procmon_shutdown_verified = ($null -eq $stopError)
        $window.procmon_stop_command_verified = $stopCommandVerified
        $window.procmon_capture_exit_status = $captureExit.Status
        $window | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'storage-window.json') -Encoding utf8
        python -B -m qa.p4_research.n12_webview_storage_probe reduce $root --source $SourceSha --expected-exe-sha256 $ExecutableSha256 --diagnostic-variant $StorageVariant
        if ($LASTEXITCODE -ne 0) { throw 'Focused WebView storage evidence was blocked.' }
        return
    }
    $window.calibration = $fixture
    $window | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifest -Encoding utf8

    # Clean stop and export do not establish a collector loss review. Keep
    # that flag false and use the summary to assess the known fixture events.
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration $manifest $xml $normalized $summary
    $result = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
        throw "Live collector calibration produced no summary (reducer exit $result)."
    }
    $report = Get-Content -LiteralPath $summary -Raw
    $report | Tee-Object -FilePath $env:GITHUB_STEP_SUMMARY -Append | Write-Host
    if ($null -ne $stopError) {
        throw 'Process Monitor shutdown was abnormal. The reduced capture is diagnostic only.'
    }
    $evidence = $report | ConvertFrom-Json
    if ($result -eq 2 -and $evidence.coverage_issues.Count -eq 1 -and
        $evidence.coverage_issues[0] -eq 'procmon-coverage-not-confirmed') {
        Write-Host 'Live fixture markers: PASS. Capture-loss review: BLOCKED.'
        return
    }
    if ($result -ne 0) { throw "Live collector calibration did not pass (exit $result)." }
} finally {
    if ($null -ne $capture) {
        try {
            if (-not $capture.HasExited) {
                Start-CollectorCommand $procmon '-terminate -quiet' 'Process Monitor cleanup command'
                $cleanup = Wait-P4N12CollectorExit -Process $capture -TimeoutMs 30000
                if ($cleanup.Status -ne 'EXITED') {
                    Write-Warning "Process Monitor cleanup result: $($cleanup.Status), exit code $($cleanup.ExitCode)."
                }
            }
        } catch {
            Write-Warning "Process Monitor cleanup: $($_.Exception.Message)"
        } finally {
            $capture.Dispose()
        }
    }
    if ($installStarted -and @(Get-Service -Name Sysmon,Sysmon64 -ErrorAction SilentlyContinue).Count -gt 0) {
        try { Start-CollectorCommand $sysmon '-u' 'Sysmon cleanup' }
        catch { Write-Warning 'Sysmon cleanup did not complete.' }
    }
    if ($null -ne $procmon -and $clock.Id -ne 'UTC') { Set-TimeZone -Id $clock.Id }
}
 -or
        $env:PILOTODIN_N12_APPROVED_SOURCE -cne $SourceSha -or
        $ExecutableSha256 -cnotmatch '^[0-9a-f]{64} (-not $WithEtw -or $AppJourney -or $AppLifetime -or $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl)) {
    throw 'The FileIO rundown comparison requires the collector-only ETW rehearsal.'
}

# This optional entry is exclusively for a separately approved one-use,
# source-pinned hosted-Windows app lifetime/profile smoke. Other modes cannot
# inherit it, and the backend CLI independently verifies both consents.
if ($NoCdp -and (-not $AppLifetime -or -not $WithEtw -or $AppJourney -or
        $WebViewStorage -or $InitialJourneyFixture -or $CollectorRundown -or
        $ProcmonEnvironmentControl -or $ProcmonTimingControl -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or
        $WebViewRuntimeDirectory -or
        $env:PILOTODIN_N12_NO_CDP_STORAGE_CONSENT -cne 'I_APPROVE_ONE_N12_NO_CDP_STORAGE')) {
    throw 'A no-CDP profile smoke requires its distinct one-use, hosted app lifetime/ETW approval.'
}

if ($WebViewRuntimeDirectory -and -not $AppJourney) {
    throw 'A WebView2 runtime directory requires the approved app journey.'
}
if ($PSBoundParameters.ContainsKey('StorageVariant') -and -not $WebViewStorage) {
    throw 'Storage variant is only valid for an approved WebView storage capture.'
}

if ($WebViewStorage -and ($WithEtw -or $AppJourney -or $AppLifetime -or $LifetimeControl -or
        $LifetimeEtwControl -or $SocketLifetimeControl -or $InitialJourneyFixture -or $CollectorRundown)) {
    throw 'WebView storage requires its own Process Monitor capture mode.'
}

$procmonControl = $ProcmonEnvironmentControl -or $ProcmonTimingControl
if ($procmonControl) {
    $controlSource = if ($ProcmonTimingControl) {
        $env:PILOTODIN_N12_PROCMON_TIMING_SOURCE
    } else { $env:PILOTODIN_N12_PROCMON_ENVIRONMENT_SOURCE }
    $controlApproved = if ($ProcmonTimingControl) {
        $env:PILOTODIN_N12_PROCMON_TIMING_CONSENT -ceq 'I_APPROVE_ONE_N12_PROCMON_TIMING_CONTROL'
    } else {
        $env:PILOTODIN_N12_PROCMON_ENVIRONMENT_CONSENT -ceq 'I_APPROVE_ONE_N12_PROCMON_ENVIRONMENT_CONTROL'
    }
    if (($ProcmonEnvironmentControl -and $ProcmonTimingControl) -or
        $WithEtw -or $AppJourney -or $AppLifetime -or $WebViewStorage -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or $InitialJourneyFixture -or
        $CollectorRundown -or $SourceSha -or $ExecutableSha256 -or
        $env:GITHUB_EVENT_NAME -cne 'push' -or $env:GITHUB_REF_NAME -cne 'feature/live-dev-workspace-20261023' -or
        $env:GITHUB_RUN_ID -cnotmatch '^[0-9]+$' -or -not $controlApproved -or
        $controlSource -cnotmatch '^[0-9a-f]{40}$' -or (git rev-parse HEAD) -cne $controlSource) {
        throw 'Each Process Monitor control requires its own source-pinned run.'
    }
}

if ($InitialJourneyFixture -and (-not $WithEtw -or $CollectorRundown -or $AppJourney -or $AppLifetime -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or $SourceSha -or $ExecutableSha256 -or
        $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE)) {
    throw 'The initial journey fixture requires its own source-pinned collector-only run.'
}

if ($SocketLifetimeControl) {
    if ($LifetimeControl -or $LifetimeEtwControl -or $AppJourney -or $AppLifetime -or
        $SourceSha -or $ExecutableSha256 -or
        $env:PILOTODIN_N12_SOCKET_LIFETIME_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_SOCKET_LIFETIME_SOURCE) {
        throw 'The socket lifetime comparison requires a source-pinned collector-only run.'
    }
} elseif ($LifetimeControl -or $LifetimeEtwControl) {
    $consent = if ($LifetimeEtwControl) {
        'I_APPROVE_ONE_N12_LIFETIME_ETW_CONTROL'
    } else {
        'I_APPROVE_ONE_N12_LIFETIME_CONTROL'
    }
    if (($LifetimeControl -and $LifetimeEtwControl) -or $AppJourney -or $AppLifetime -or $WithEtw -or $SourceSha -or
        $ExecutableSha256 -or $env:PILOTODIN_N12_LIFETIME_CONTROL_CONSENT -cne $consent -or
        $env:PILOTODIN_N12_LIFETIME_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_LIFETIME_SOURCE) {
        throw 'The collector lifetime control requires its own source-pinned approval.'
    }
} elseif ($AppJourney -or $AppLifetime -or $WebViewStorage) {
    $captureApproved = if ($WebViewStorage) {
        $env:PILOTODIN_N12_WEBVIEW_STORAGE_CONSENT -ceq 'I_APPROVE_ONE_N12_WEBVIEW_STORAGE'
    } elseif ($AppLifetime) {
        $env:PILOTODIN_N12_APP_LIFETIME_CONSENT -ceq 'I_APPROVE_ONE_N12_APP_LIFETIME'
    } else {
        $env:PILOTODIN_N12_APP_JOURNEY_CONSENT -ceq 'I_APPROVE_ONE_N12_APP_JOURNEY'
    }
    if (($AppJourney -and $AppLifetime) -or (-not $WebViewStorage -and -not $WithEtw) -or -not $captureApproved -or
        $env:PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT -cne 'I_APPROVE_UNPACKAGED_P4_NATIVE_DEV' -or
        $SourceSha -cnotmatch '^[0-9a-f]{40}$' -or $SourceSha -cne $env:PILOTODIN_N12_APPROVED_SOURCE -or
        $ExecutableSha256 -cnotmatch '^[0-9a-f]{64}$') {
        throw 'The app journey requires its separate approval and staged binary identity.'
    }
    python -B -m qa.p4_research.n12_app_build verify --source $SourceSha --expected-exe-sha256 $ExecutableSha256
    if ($LASTEXITCODE -ne 0) { throw 'Staged build verification failed before Sysmon provisioning.' }
} elseif ($SourceSha -or $ExecutableSha256) {
    throw 'A staged build identity requires an approved app capture.'
} elseif ($WithEtw -and
    $env:PILOTODIN_N12_COLLECTOR_REHEARSAL_CONSENT -cne 'I_APPROVE_ONE_N12_COLLECTOR_REHEARSAL') {
    throw 'The collector-only rehearsal requires separate approval before provisioning Sysmon.'
}

. (Join-Path $PSScriptRoot 'P4_N12_Collector_Process.ps1')

function Start-CollectorCommand($Executable, $Arguments, $Description) {
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -PassThru
    try {
        $result = Wait-P4N12CollectorExit -Process $process -TimeoutMs 45000
        if ($result.Status -eq 'TIMEOUT') { throw "$Description timed out." }
        if ($result.Status -ne 'EXITED') { throw "$Description exited with code $($result.ExitCode)." }
    } finally {
        $process.Dispose()
    }
}

function Get-MicrosoftCollector($Name, $Executable, $Publisher, $ExpectedHash) {
    $archive = Join-Path $root "$Name.zip"
    $directory = Join-Path $root $Name
    Invoke-WebRequest -Uri "https://download.sysinternals.com/files/$Name.zip" -OutFile $archive -TimeoutSec 60
    Expand-Archive -LiteralPath $archive -DestinationPath $directory
    $binary = Get-Item -LiteralPath (Join-Path $directory $Executable)
    $signature = Get-AuthenticodeSignature -LiteralPath $binary.FullName
    $signer = if ($signature.SignerCertificate) {
        $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
    }
    if ($signature.Status -ne 'Valid' -or
        $signer -ne $Publisher) {
        throw "$Name failed Microsoft signature validation (status $($signature.Status), signer '$signer')."
    }
    $hash = (Get-FileHash -LiteralPath $binary.FullName -Algorithm SHA256).Hash
    if ($hash -ne $ExpectedHash) { throw "$Name differs from the reviewed binary SHA-256." }
    Write-Host "$Name version $($binary.VersionInfo.FileVersion), SHA-256 $hash"
    return $binary.FullName
}

if ((-not $procmonControl -and
        @(Get-Service -Name Sysmon,Sysmon64 -ErrorAction SilentlyContinue).Count -gt 0) -or
    @(Get-Process -Name Procmon,Procmon64 -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Collector already present or running on the disposable image.'
}

$root = Join-Path $env:RUNNER_TEMP "pilotodin-n12-live-$env:GITHUB_RUN_ID"
New-Item -ItemType Directory -Path $root | Out-Null
$channel = 'Microsoft-Windows-Sysmon/Operational'
$clock = Get-TimeZone
$sysmon = if (-not $procmonControl) {
    Get-MicrosoftCollector 'Sysmon' 'Sysmon64.exe' 'Microsoft Windows Publisher' '83d31f2478dc6716cfdbf69e5c384bf043072b5f0d8d7b2eea365f709fda4352'
}
$procmon = $null
if (-not $WithEtw -and -not $LifetimeControl -and -not $LifetimeEtwControl -and -not $SocketLifetimeControl) {
    $procmon = Get-MicrosoftCollector 'ProcessMonitor' 'Procmon64.exe' 'Microsoft Corporation' 'aa0b10e936feea464348695f8a85a2dcafd2cb3dabd1d47d8a57e7594783b27b'
}
$config = Join-Path $root 'sysmon-config.xml'
$pml = Join-Path $root 'capture.pml'
$csv = Join-Path $root 'capture.csv'
$normalized = Join-Path $root 'capture-utf8.csv'
$xml = Join-Path $root 'sysmon.xml'
$manifest = Join-Path $root 'manifest.json'
$summary = Join-Path $root 'summary.json'

$definition = @'
<Sysmon schemaversion="4.50">
  <HashAlgorithms>SHA256</HashAlgorithms>
  <EventFiltering>
    <ProcessCreate onmatch="exclude" />
    <ProcessTerminate onmatch="exclude" />
    <NetworkConnect onmatch="exclude" />
  </EventFiltering>
</Sysmon>
'@
if ($LifetimeEtwControl -or $AppLifetime) {
    $definition = $definition.Replace('<NetworkConnect onmatch="exclude" />', '<NetworkConnect onmatch="include" />')
}
$definition | Set-Content -LiteralPath $config -Encoding ascii

$installStarted = $false
$capture = $null
try {
    if ($null -ne $procmon -and $clock.Id -ne 'UTC') { Set-TimeZone -Id 'UTC' }
    if ($null -ne $sysmon) {
        $installStarted = $true
        Start-CollectorCommand $sysmon "-accepteula -i `"$config`"" 'Sysmon setup'
    }
    if ($SocketLifetimeControl) {
        $socketOptions = @()
        if ($WithEtw) { $socketOptions += '--etw-boundary' }
        python -B -m qa.p4_research.n12_socket_lifetime_control $root @socketOptions
        if ($LASTEXITCODE -ne 0) { throw 'The socket lifetime comparison could not complete.' }
        return
    }
    if ($LifetimeControl -or $LifetimeEtwControl) {
        $captureMode = if ($LifetimeEtwControl) { '--capture-etw' } else { '--capture' }
        python -B -m qa.p4_native.n12_lifetime_control $captureMode $root
        if ($LASTEXITCODE -ne 0) { throw 'The collector lifetime control did not pass.' }
        return
    }
    if ($AppLifetime) {
        $lifetimeArgs = @('--source', $SourceSha, '--expected-exe-sha256', $ExecutableSha256)
        if ($NoCdp) { $lifetimeArgs += '--no-cdp' }
        python -B -m qa.p4_research.n12_app_lifetime @lifetimeArgs
        if ($LASTEXITCODE -ne 0) { throw 'The hosted app lifetime capture failed or returned blocked evidence.' }
        return
    }
    if ($AppJourney) {
        $journeyArgs = @('--source', $SourceSha, '--expected-exe-sha256', $ExecutableSha256)
        if ($WebViewRuntimeDirectory) { $journeyArgs += @('--webview-runtime-directory', $WebViewRuntimeDirectory) }
        python -B -m qa.p4_research.n12_app_journey @journeyArgs
        if ($LASTEXITCODE -ne 0) { throw 'The hosted app journey failed or returned blocked coverage.' }
        return
    }
    if ($InitialJourneyFixture) {
        python -B -m qa.p4_research.n12_app_journey --initial-fixture-only --source $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE
        if ($LASTEXITCODE -ne 0) { throw 'The initial journey fixture was blocked.' }
        return
    }
    if ($WithEtw) {
        & (Join-Path $PSScriptRoot 'Test_P4_N12_ETW_Fixture.ps1') -WithSysmon -Rundown:$CollectorRundown
        return
    }
    if (-not $procmonControl) {
        $latest = Get-WinEvent -LogName $channel -MaxEvents 1
        $firstRecord = $latest.RecordId + 1
    }

    $capture = Start-Process -FilePath $procmon -ArgumentList "/AcceptEula /Quiet /Minimized /NoFilter /BackingFile `"$pml`"" -PassThru
    Start-CollectorCommand $procmon '/WaitForIdle' 'Process Monitor readiness'
    $capture.Refresh()
    if ($capture.HasExited) {
        throw "Process Monitor capture exited with code $($capture.ExitCode) before readiness."
    }
    if (-not (Test-Path -LiteralPath $pml -PathType Leaf)) {
        throw 'Process Monitor backing file was absent after readiness.'
    }
    Write-Host 'Process Monitor capture process is running and its backing file is present.'

    $start = [DateTimeOffset]::UtcNow
    if ($ProcmonTimingControl) {
        python -B -m qa.p4_research.n12_procmon_timing_control capture $root
        if ($LASTEXITCODE -ne 0) { throw 'Same-session timing fixture or ETW export failed.' }
    } elseif ($ProcmonEnvironmentControl) {
        python -B -m qa.p4_research.n12_procmon_environment_control capture $root
        if ($LASTEXITCODE -ne 0) { throw 'Generated Process Monitor environment child failed.' }
    } elseif ($WebViewStorage) {
        python -B -m qa.p4_research.n12_webview_storage_probe capture $root --source $SourceSha --expected-exe-sha256 $ExecutableSha256 --diagnostic-variant $StorageVariant
        if ($LASTEXITCODE -ne 0) { throw 'Focused WebView storage launch or control failed.' }
    } else {
        $fixtureJson = python (Join-Path $PSScriptRoot 'n12_calibration.py') (Join-Path $root 'fixture')
        if ($LASTEXITCODE -ne 0) { throw 'Generated N12 fixture failed.' }
        $fixture = $fixtureJson | ConvertFrom-Json
    }
    Start-Sleep -Seconds 5
    $end = [DateTimeOffset]::UtcNow
    if (-not $procmonControl) {
        $lastRecord = (Get-WinEvent -LogName $channel -MaxEvents 1).RecordId
    }

    $stopError = $null
    $stopCommandVerified = $false
    if ($procmonControl) {
        # Exercise a normal window close on the captured process. The finally
        # block can request termination for cleanup after a failed close.
        Request-P4N12CollectorWindowClose -Process $capture
        $stopCommandVerified = $true
        Write-Host 'Process Monitor main-window close requested.'
    } else {
        try {
            Start-CollectorCommand $procmon '-terminate -quiet' 'Process Monitor stop command'
            $stopCommandVerified = $true
        } catch {
            $stopError = $_.Exception.Message
            Write-Warning $stopError
        }
    }
    $captureExit = Wait-P4N12CollectorExit -Process $capture -TimeoutMs 30000
    if ($captureExit.Status -eq 'TIMEOUT') {
        throw 'Process Monitor capture process was still running 30 seconds after the stop request.'
    }
    Write-Host "Process Monitor capture process exited with code $($captureExit.ExitCode)."
    if ($captureExit.Status -ne 'EXITED') {
        $stopError = 'Process Monitor capture process returned a nonzero exit code.'
        Write-Warning $stopError
    }
    Confirm-P4N12ClosedCapture -Path $pml -Description 'Process Monitor backing file'
    Start-CollectorCommand $procmon "/AcceptEula /Quiet /Minimized /NoFilter /OpenLog `"$pml`" /SaveAs `"$csv`"" 'Process Monitor export'
    Confirm-P4N12ClosedCapture -Path $csv -Description 'Process Monitor CSV'

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

    if ($procmonControl) {
        $controlWindow = @{
            start_utc = $start.ToString('o')
            end_utc = $end.ToString('o')
            clock_utc = (Get-TimeZone).Id -eq 'UTC'
            shutdown_verified = ($null -eq $stopError)
        }
        $controlModule = 'qa.p4_research.n12_procmon_environment_control'
        if ($ProcmonTimingControl) {
            $controlWindow.run = @{
                source_sha = $controlSource
                run_id = $env:GITHUB_RUN_ID
                run_attempt = $env:GITHUB_RUN_ATTEMPT
            }
            $controlWindow.csv_sha256 = (Get-FileHash -LiteralPath $normalized -Algorithm SHA256).Hash.ToLowerInvariant()
            $controlModule = 'qa.p4_research.n12_procmon_timing_control'
        }
        $controlWindow | ConvertTo-Json -Depth 3 |
            Set-Content -LiteralPath (Join-Path $root 'environment-window.json') -Encoding utf8
        python -B -m $controlModule reduce $root
        if ($LASTEXITCODE -ne 0) { throw 'Process Monitor control evidence was blocked.' }
        return
    }
    & (Join-Path $PSScriptRoot 'Export_P4_N12_Sysmon_Trace.ps1') -FirstRecord $firstRecord -LastRecord $lastRecord -OutputFile $xml
    $window = @{
        schema_version = 1
        disposable = $true
        start_utc = $start.ToString('o')
        end_utc = $end.ToString('o')
        sysmon_first_record = $firstRecord
        sysmon_last_record = $lastRecord
        procmon_all_events = $true
        procmon_loss_reviewed = $false
        procmon_clock_utc = (Get-TimeZone).Id -eq 'UTC'
    }
    if ($WebViewStorage) {
        # Keep the exported observations while making shutdown health part of the verdict.
        $window.procmon_shutdown_verified = ($null -eq $stopError)
        $window.procmon_stop_command_verified = $stopCommandVerified
        $window.procmon_capture_exit_status = $captureExit.Status
        $window | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'storage-window.json') -Encoding utf8
        python -B -m qa.p4_research.n12_webview_storage_probe reduce $root --source $SourceSha --expected-exe-sha256 $ExecutableSha256 --diagnostic-variant $StorageVariant
        if ($LASTEXITCODE -ne 0) { throw 'Focused WebView storage evidence was blocked.' }
        return
    }
    $window.calibration = $fixture
    $window | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifest -Encoding utf8

    # Clean stop and export do not establish a collector loss review. Keep
    # that flag false and use the summary to assess the known fixture events.
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration $manifest $xml $normalized $summary
    $result = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
        throw "Live collector calibration produced no summary (reducer exit $result)."
    }
    $report = Get-Content -LiteralPath $summary -Raw
    $report | Tee-Object -FilePath $env:GITHUB_STEP_SUMMARY -Append | Write-Host
    if ($null -ne $stopError) {
        throw 'Process Monitor shutdown was abnormal. The reduced capture is diagnostic only.'
    }
    $evidence = $report | ConvertFrom-Json
    if ($result -eq 2 -and $evidence.coverage_issues.Count -eq 1 -and
        $evidence.coverage_issues[0] -eq 'procmon-coverage-not-confirmed') {
        Write-Host 'Live fixture markers: PASS. Capture-loss review: BLOCKED.'
        return
    }
    if ($result -ne 0) { throw "Live collector calibration did not pass (exit $result)." }
} finally {
    if ($null -ne $capture) {
        try {
            if (-not $capture.HasExited) {
                Start-CollectorCommand $procmon '-terminate -quiet' 'Process Monitor cleanup command'
                $cleanup = Wait-P4N12CollectorExit -Process $capture -TimeoutMs 30000
                if ($cleanup.Status -ne 'EXITED') {
                    Write-Warning "Process Monitor cleanup result: $($cleanup.Status), exit code $($cleanup.ExitCode)."
                }
            }
        } catch {
            Write-Warning "Process Monitor cleanup: $($_.Exception.Message)"
        } finally {
            $capture.Dispose()
        }
    }
    if ($installStarted -and @(Get-Service -Name Sysmon,Sysmon64 -ErrorAction SilentlyContinue).Count -gt 0) {
        try { Start-CollectorCommand $sysmon '-u' 'Sysmon cleanup' }
        catch { Write-Warning 'Sysmon cleanup did not complete.' }
    }
    if ($null -ne $procmon -and $clock.Id -ne 'UTC') { Set-TimeZone -Id $clock.Id }
}
)) {
    throw 'Full no-CDP FileIO requires a new source-pinned, separately consented, baseline-only app capture.'
}

if ($CollectorRundown -and (-not $WithEtw -or $AppJourney -or $AppLifetime -or $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl)) {
    throw 'The FileIO rundown comparison requires the collector-only ETW rehearsal.'
}

# This optional entry is exclusively for a separately approved one-use,
# source-pinned hosted-Windows app lifetime/profile smoke. Other modes cannot
# inherit it, and the backend CLI independently verifies both consents.
if ($NoCdp -and (-not $AppLifetime -or -not $WithEtw -or $AppJourney -or
        $WebViewStorage -or $InitialJourneyFixture -or $CollectorRundown -or
        $ProcmonEnvironmentControl -or $ProcmonTimingControl -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or
        $WebViewRuntimeDirectory -or
        $env:PILOTODIN_N12_NO_CDP_STORAGE_CONSENT -cne 'I_APPROVE_ONE_N12_NO_CDP_STORAGE')) {
    throw 'A no-CDP profile smoke requires its distinct one-use, hosted app lifetime/ETW approval.'
}

if ($WebViewRuntimeDirectory -and -not $AppJourney) {
    throw 'A WebView2 runtime directory requires the approved app journey.'
}
if ($PSBoundParameters.ContainsKey('StorageVariant') -and -not $WebViewStorage) {
    throw 'Storage variant is only valid for an approved WebView storage capture.'
}

if ($WebViewStorage -and ($WithEtw -or $AppJourney -or $AppLifetime -or $LifetimeControl -or
        $LifetimeEtwControl -or $SocketLifetimeControl -or $InitialJourneyFixture -or $CollectorRundown)) {
    throw 'WebView storage requires its own Process Monitor capture mode.'
}

$procmonControl = $ProcmonEnvironmentControl -or $ProcmonTimingControl
if ($procmonControl) {
    $controlSource = if ($ProcmonTimingControl) {
        $env:PILOTODIN_N12_PROCMON_TIMING_SOURCE
    } else { $env:PILOTODIN_N12_PROCMON_ENVIRONMENT_SOURCE }
    $controlApproved = if ($ProcmonTimingControl) {
        $env:PILOTODIN_N12_PROCMON_TIMING_CONSENT -ceq 'I_APPROVE_ONE_N12_PROCMON_TIMING_CONTROL'
    } else {
        $env:PILOTODIN_N12_PROCMON_ENVIRONMENT_CONSENT -ceq 'I_APPROVE_ONE_N12_PROCMON_ENVIRONMENT_CONTROL'
    }
    if (($ProcmonEnvironmentControl -and $ProcmonTimingControl) -or
        $WithEtw -or $AppJourney -or $AppLifetime -or $WebViewStorage -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or $InitialJourneyFixture -or
        $CollectorRundown -or $SourceSha -or $ExecutableSha256 -or
        $env:GITHUB_EVENT_NAME -cne 'push' -or $env:GITHUB_REF_NAME -cne 'feature/live-dev-workspace-20261023' -or
        $env:GITHUB_RUN_ID -cnotmatch '^[0-9]+$' -or -not $controlApproved -or
        $controlSource -cnotmatch '^[0-9a-f]{40}$' -or (git rev-parse HEAD) -cne $controlSource) {
        throw 'Each Process Monitor control requires its own source-pinned run.'
    }
}

if ($InitialJourneyFixture -and (-not $WithEtw -or $CollectorRundown -or $AppJourney -or $AppLifetime -or
        $LifetimeControl -or $LifetimeEtwControl -or $SocketLifetimeControl -or $SourceSha -or $ExecutableSha256 -or
        $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE)) {
    throw 'The initial journey fixture requires its own source-pinned collector-only run.'
}

if ($SocketLifetimeControl) {
    if ($LifetimeControl -or $LifetimeEtwControl -or $AppJourney -or $AppLifetime -or
        $SourceSha -or $ExecutableSha256 -or
        $env:PILOTODIN_N12_SOCKET_LIFETIME_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_SOCKET_LIFETIME_SOURCE) {
        throw 'The socket lifetime comparison requires a source-pinned collector-only run.'
    }
} elseif ($LifetimeControl -or $LifetimeEtwControl) {
    $consent = if ($LifetimeEtwControl) {
        'I_APPROVE_ONE_N12_LIFETIME_ETW_CONTROL'
    } else {
        'I_APPROVE_ONE_N12_LIFETIME_CONTROL'
    }
    if (($LifetimeControl -and $LifetimeEtwControl) -or $AppJourney -or $AppLifetime -or $WithEtw -or $SourceSha -or
        $ExecutableSha256 -or $env:PILOTODIN_N12_LIFETIME_CONTROL_CONSENT -cne $consent -or
        $env:PILOTODIN_N12_LIFETIME_SOURCE -cnotmatch '^[0-9a-f]{40}$' -or
        (git rev-parse HEAD) -cne $env:PILOTODIN_N12_LIFETIME_SOURCE) {
        throw 'The collector lifetime control requires its own source-pinned approval.'
    }
} elseif ($AppJourney -or $AppLifetime -or $WebViewStorage) {
    $captureApproved = if ($WebViewStorage) {
        $env:PILOTODIN_N12_WEBVIEW_STORAGE_CONSENT -ceq 'I_APPROVE_ONE_N12_WEBVIEW_STORAGE'
    } elseif ($AppLifetime) {
        $env:PILOTODIN_N12_APP_LIFETIME_CONSENT -ceq 'I_APPROVE_ONE_N12_APP_LIFETIME'
    } else {
        $env:PILOTODIN_N12_APP_JOURNEY_CONSENT -ceq 'I_APPROVE_ONE_N12_APP_JOURNEY'
    }
    if (($AppJourney -and $AppLifetime) -or (-not $WebViewStorage -and -not $WithEtw) -or -not $captureApproved -or
        $env:PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT -cne 'I_APPROVE_UNPACKAGED_P4_NATIVE_DEV' -or
        $SourceSha -cnotmatch '^[0-9a-f]{40}$' -or $SourceSha -cne $env:PILOTODIN_N12_APPROVED_SOURCE -or
        $ExecutableSha256 -cnotmatch '^[0-9a-f]{64}$') {
        throw 'The app journey requires its separate approval and staged binary identity.'
    }
    python -B -m qa.p4_research.n12_app_build verify --source $SourceSha --expected-exe-sha256 $ExecutableSha256
    if ($LASTEXITCODE -ne 0) { throw 'Staged build verification failed before Sysmon provisioning.' }
} elseif ($SourceSha -or $ExecutableSha256) {
    throw 'A staged build identity requires an approved app capture.'
} elseif ($WithEtw -and
    $env:PILOTODIN_N12_COLLECTOR_REHEARSAL_CONSENT -cne 'I_APPROVE_ONE_N12_COLLECTOR_REHEARSAL') {
    throw 'The collector-only rehearsal requires separate approval before provisioning Sysmon.'
}

. (Join-Path $PSScriptRoot 'P4_N12_Collector_Process.ps1')

function Start-CollectorCommand($Executable, $Arguments, $Description) {
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -PassThru
    try {
        $result = Wait-P4N12CollectorExit -Process $process -TimeoutMs 45000
        if ($result.Status -eq 'TIMEOUT') { throw "$Description timed out." }
        if ($result.Status -ne 'EXITED') { throw "$Description exited with code $($result.ExitCode)." }
    } finally {
        $process.Dispose()
    }
}

function Get-MicrosoftCollector($Name, $Executable, $Publisher, $ExpectedHash) {
    $archive = Join-Path $root "$Name.zip"
    $directory = Join-Path $root $Name
    Invoke-WebRequest -Uri "https://download.sysinternals.com/files/$Name.zip" -OutFile $archive -TimeoutSec 60
    Expand-Archive -LiteralPath $archive -DestinationPath $directory
    $binary = Get-Item -LiteralPath (Join-Path $directory $Executable)
    $signature = Get-AuthenticodeSignature -LiteralPath $binary.FullName
    $signer = if ($signature.SignerCertificate) {
        $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
    }
    if ($signature.Status -ne 'Valid' -or
        $signer -ne $Publisher) {
        throw "$Name failed Microsoft signature validation (status $($signature.Status), signer '$signer')."
    }
    $hash = (Get-FileHash -LiteralPath $binary.FullName -Algorithm SHA256).Hash
    if ($hash -ne $ExpectedHash) { throw "$Name differs from the reviewed binary SHA-256." }
    Write-Host "$Name version $($binary.VersionInfo.FileVersion), SHA-256 $hash"
    return $binary.FullName
}

if ((-not $procmonControl -and
        @(Get-Service -Name Sysmon,Sysmon64 -ErrorAction SilentlyContinue).Count -gt 0) -or
    @(Get-Process -Name Procmon,Procmon64 -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Collector already present or running on the disposable image.'
}

$root = Join-Path $env:RUNNER_TEMP "pilotodin-n12-live-$env:GITHUB_RUN_ID"
New-Item -ItemType Directory -Path $root | Out-Null
$channel = 'Microsoft-Windows-Sysmon/Operational'
$clock = Get-TimeZone
$sysmon = if (-not $procmonControl) {
    Get-MicrosoftCollector 'Sysmon' 'Sysmon64.exe' 'Microsoft Windows Publisher' '83d31f2478dc6716cfdbf69e5c384bf043072b5f0d8d7b2eea365f709fda4352'
}
$procmon = $null
if (-not $WithEtw -and -not $LifetimeControl -and -not $LifetimeEtwControl -and -not $SocketLifetimeControl) {
    $procmon = Get-MicrosoftCollector 'ProcessMonitor' 'Procmon64.exe' 'Microsoft Corporation' 'aa0b10e936feea464348695f8a85a2dcafd2cb3dabd1d47d8a57e7594783b27b'
}
$config = Join-Path $root 'sysmon-config.xml'
$pml = Join-Path $root 'capture.pml'
$csv = Join-Path $root 'capture.csv'
$normalized = Join-Path $root 'capture-utf8.csv'
$xml = Join-Path $root 'sysmon.xml'
$manifest = Join-Path $root 'manifest.json'
$summary = Join-Path $root 'summary.json'

$definition = @'
<Sysmon schemaversion="4.50">
  <HashAlgorithms>SHA256</HashAlgorithms>
  <EventFiltering>
    <ProcessCreate onmatch="exclude" />
    <ProcessTerminate onmatch="exclude" />
    <NetworkConnect onmatch="exclude" />
  </EventFiltering>
</Sysmon>
'@
if ($LifetimeEtwControl -or $AppLifetime) {
    $definition = $definition.Replace('<NetworkConnect onmatch="exclude" />', '<NetworkConnect onmatch="include" />')
}
$definition | Set-Content -LiteralPath $config -Encoding ascii

$installStarted = $false
$capture = $null
try {
    if ($null -ne $procmon -and $clock.Id -ne 'UTC') { Set-TimeZone -Id 'UTC' }
    if ($null -ne $sysmon) {
        $installStarted = $true
        Start-CollectorCommand $sysmon "-accepteula -i `"$config`"" 'Sysmon setup'
    }
    if ($SocketLifetimeControl) {
        $socketOptions = @()
        if ($WithEtw) { $socketOptions += '--etw-boundary' }
        python -B -m qa.p4_research.n12_socket_lifetime_control $root @socketOptions
        if ($LASTEXITCODE -ne 0) { throw 'The socket lifetime comparison could not complete.' }
        return
    }
    if ($LifetimeControl -or $LifetimeEtwControl) {
        $captureMode = if ($LifetimeEtwControl) { '--capture-etw' } else { '--capture' }
        python -B -m qa.p4_native.n12_lifetime_control $captureMode $root
        if ($LASTEXITCODE -ne 0) { throw 'The collector lifetime control did not pass.' }
        return
    }
    if ($AppLifetime) {
        $lifetimeArgs = @('--source', $SourceSha, '--expected-exe-sha256', $ExecutableSha256)
        if ($NoCdp) { $lifetimeArgs += '--no-cdp' }
        python -B -m qa.p4_research.n12_app_lifetime @lifetimeArgs
        if ($LASTEXITCODE -ne 0) { throw 'The hosted app lifetime capture failed or returned blocked evidence.' }
        return
    }
    if ($AppJourney) {
        $journeyArgs = @('--source', $SourceSha, '--expected-exe-sha256', $ExecutableSha256)
        if ($WebViewRuntimeDirectory) { $journeyArgs += @('--webview-runtime-directory', $WebViewRuntimeDirectory) }
        python -B -m qa.p4_research.n12_app_journey @journeyArgs
        if ($LASTEXITCODE -ne 0) { throw 'The hosted app journey failed or returned blocked coverage.' }
        return
    }
    if ($InitialJourneyFixture) {
        python -B -m qa.p4_research.n12_app_journey --initial-fixture-only --source $env:PILOTODIN_N12_INITIAL_FIXTURE_SOURCE
        if ($LASTEXITCODE -ne 0) { throw 'The initial journey fixture was blocked.' }
        return
    }
    if ($WithEtw) {
        & (Join-Path $PSScriptRoot 'Test_P4_N12_ETW_Fixture.ps1') -WithSysmon -Rundown:$CollectorRundown
        return
    }
    if (-not $procmonControl) {
        $latest = Get-WinEvent -LogName $channel -MaxEvents 1
        $firstRecord = $latest.RecordId + 1
    }

    $capture = Start-Process -FilePath $procmon -ArgumentList "/AcceptEula /Quiet /Minimized /NoFilter /BackingFile `"$pml`"" -PassThru
    Start-CollectorCommand $procmon '/WaitForIdle' 'Process Monitor readiness'
    $capture.Refresh()
    if ($capture.HasExited) {
        throw "Process Monitor capture exited with code $($capture.ExitCode) before readiness."
    }
    if (-not (Test-Path -LiteralPath $pml -PathType Leaf)) {
        throw 'Process Monitor backing file was absent after readiness.'
    }
    Write-Host 'Process Monitor capture process is running and its backing file is present.'

    $start = [DateTimeOffset]::UtcNow
    if ($ProcmonTimingControl) {
        python -B -m qa.p4_research.n12_procmon_timing_control capture $root
        if ($LASTEXITCODE -ne 0) { throw 'Same-session timing fixture or ETW export failed.' }
    } elseif ($ProcmonEnvironmentControl) {
        python -B -m qa.p4_research.n12_procmon_environment_control capture $root
        if ($LASTEXITCODE -ne 0) { throw 'Generated Process Monitor environment child failed.' }
    } elseif ($WebViewStorage) {
        python -B -m qa.p4_research.n12_webview_storage_probe capture $root --source $SourceSha --expected-exe-sha256 $ExecutableSha256 --diagnostic-variant $StorageVariant
        if ($LASTEXITCODE -ne 0) { throw 'Focused WebView storage launch or control failed.' }
    } else {
        $fixtureJson = python (Join-Path $PSScriptRoot 'n12_calibration.py') (Join-Path $root 'fixture')
        if ($LASTEXITCODE -ne 0) { throw 'Generated N12 fixture failed.' }
        $fixture = $fixtureJson | ConvertFrom-Json
    }
    Start-Sleep -Seconds 5
    $end = [DateTimeOffset]::UtcNow
    if (-not $procmonControl) {
        $lastRecord = (Get-WinEvent -LogName $channel -MaxEvents 1).RecordId
    }

    $stopError = $null
    $stopCommandVerified = $false
    if ($procmonControl) {
        # Exercise a normal window close on the captured process. The finally
        # block can request termination for cleanup after a failed close.
        Request-P4N12CollectorWindowClose -Process $capture
        $stopCommandVerified = $true
        Write-Host 'Process Monitor main-window close requested.'
    } else {
        try {
            Start-CollectorCommand $procmon '-terminate -quiet' 'Process Monitor stop command'
            $stopCommandVerified = $true
        } catch {
            $stopError = $_.Exception.Message
            Write-Warning $stopError
        }
    }
    $captureExit = Wait-P4N12CollectorExit -Process $capture -TimeoutMs 30000
    if ($captureExit.Status -eq 'TIMEOUT') {
        throw 'Process Monitor capture process was still running 30 seconds after the stop request.'
    }
    Write-Host "Process Monitor capture process exited with code $($captureExit.ExitCode)."
    if ($captureExit.Status -ne 'EXITED') {
        $stopError = 'Process Monitor capture process returned a nonzero exit code.'
        Write-Warning $stopError
    }
    Confirm-P4N12ClosedCapture -Path $pml -Description 'Process Monitor backing file'
    Start-CollectorCommand $procmon "/AcceptEula /Quiet /Minimized /NoFilter /OpenLog `"$pml`" /SaveAs `"$csv`"" 'Process Monitor export'
    Confirm-P4N12ClosedCapture -Path $csv -Description 'Process Monitor CSV'

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

    if ($procmonControl) {
        $controlWindow = @{
            start_utc = $start.ToString('o')
            end_utc = $end.ToString('o')
            clock_utc = (Get-TimeZone).Id -eq 'UTC'
            shutdown_verified = ($null -eq $stopError)
        }
        $controlModule = 'qa.p4_research.n12_procmon_environment_control'
        if ($ProcmonTimingControl) {
            $controlWindow.run = @{
                source_sha = $controlSource
                run_id = $env:GITHUB_RUN_ID
                run_attempt = $env:GITHUB_RUN_ATTEMPT
            }
            $controlWindow.csv_sha256 = (Get-FileHash -LiteralPath $normalized -Algorithm SHA256).Hash.ToLowerInvariant()
            $controlModule = 'qa.p4_research.n12_procmon_timing_control'
        }
        $controlWindow | ConvertTo-Json -Depth 3 |
            Set-Content -LiteralPath (Join-Path $root 'environment-window.json') -Encoding utf8
        python -B -m $controlModule reduce $root
        if ($LASTEXITCODE -ne 0) { throw 'Process Monitor control evidence was blocked.' }
        return
    }
    & (Join-Path $PSScriptRoot 'Export_P4_N12_Sysmon_Trace.ps1') -FirstRecord $firstRecord -LastRecord $lastRecord -OutputFile $xml
    $window = @{
        schema_version = 1
        disposable = $true
        start_utc = $start.ToString('o')
        end_utc = $end.ToString('o')
        sysmon_first_record = $firstRecord
        sysmon_last_record = $lastRecord
        procmon_all_events = $true
        procmon_loss_reviewed = $false
        procmon_clock_utc = (Get-TimeZone).Id -eq 'UTC'
    }
    if ($WebViewStorage) {
        # Keep the exported observations while making shutdown health part of the verdict.
        $window.procmon_shutdown_verified = ($null -eq $stopError)
        $window.procmon_stop_command_verified = $stopCommandVerified
        $window.procmon_capture_exit_status = $captureExit.Status
        $window | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'storage-window.json') -Encoding utf8
        python -B -m qa.p4_research.n12_webview_storage_probe reduce $root --source $SourceSha --expected-exe-sha256 $ExecutableSha256 --diagnostic-variant $StorageVariant
        if ($LASTEXITCODE -ne 0) { throw 'Focused WebView storage evidence was blocked.' }
        return
    }
    $window.calibration = $fixture
    $window | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifest -Encoding utf8

    # Clean stop and export do not establish a collector loss review. Keep
    # that flag false and use the summary to assess the known fixture events.
    python (Join-Path $PSScriptRoot 'n12_trace.py') check-calibration $manifest $xml $normalized $summary
    $result = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
        throw "Live collector calibration produced no summary (reducer exit $result)."
    }
    $report = Get-Content -LiteralPath $summary -Raw
    $report | Tee-Object -FilePath $env:GITHUB_STEP_SUMMARY -Append | Write-Host
    if ($null -ne $stopError) {
        throw 'Process Monitor shutdown was abnormal. The reduced capture is diagnostic only.'
    }
    $evidence = $report | ConvertFrom-Json
    if ($result -eq 2 -and $evidence.coverage_issues.Count -eq 1 -and
        $evidence.coverage_issues[0] -eq 'procmon-coverage-not-confirmed') {
        Write-Host 'Live fixture markers: PASS. Capture-loss review: BLOCKED.'
        return
    }
    if ($result -ne 0) { throw "Live collector calibration did not pass (exit $result)." }
} finally {
    if ($null -ne $capture) {
        try {
            if (-not $capture.HasExited) {
                Start-CollectorCommand $procmon '-terminate -quiet' 'Process Monitor cleanup command'
                $cleanup = Wait-P4N12CollectorExit -Process $capture -TimeoutMs 30000
                if ($cleanup.Status -ne 'EXITED') {
                    Write-Warning "Process Monitor cleanup result: $($cleanup.Status), exit code $($cleanup.ExitCode)."
                }
            }
        } catch {
            Write-Warning "Process Monitor cleanup: $($_.Exception.Message)"
        } finally {
            $capture.Dispose()
        }
    }
    if ($installStarted -and @(Get-Service -Name Sysmon,Sysmon64 -ErrorAction SilentlyContinue).Count -gt 0) {
        try { Start-CollectorCommand $sysmon '-u' 'Sysmon cleanup' }
        catch { Write-Warning 'Sysmon cleanup did not complete.' }
    }
    if ($null -ne $procmon -and $clock.Id -ne 'UTC') { Set-TimeZone -Id $clock.Id }
}
