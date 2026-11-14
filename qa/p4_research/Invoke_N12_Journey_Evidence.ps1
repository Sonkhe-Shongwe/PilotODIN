# Windows-only operations for the source-pinned N12 app journey.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('sysmon-tail','etw-export','close','profile-active')][string]$Operation,
    [string]$CaptureRoot,
    [int]$AppProcessId,
    [string]$AppPath,
    [string]$AppTitle,
    [string]$ProfilePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows' -or
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
        Close-P4VerifiedWindow -AppProcessId $AppProcessId -ExpectedPath $AppPath -ExpectedTitle $AppTitle
    }
    'profile-active' {
        if ([string]::IsNullOrWhiteSpace($ProfilePath)) { throw 'The disposable profile path is required.' }
        $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'msedgewebview2.exe'" |
            Where-Object { $_.CommandLine -and
                $_.CommandLine.IndexOf($ProfilePath, [StringComparison]::OrdinalIgnoreCase) -ge 0 })
        $processes.Count
    }
    'etw-export' {
        $file = [IO.File]::Open((Join-Path $CaptureRoot 'etw.jsonl'), [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream = [IO.StreamWriter]::new($file, [Text.UTF8Encoding]::new($false))
        $fileProvider = [guid]'edd08927-9cc4-4e65-b970-c2560fb5c289'
        $processProvider = [guid]'22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716'
        try {
            Get-WinEvent -Path (Join-Path $CaptureRoot 'journey.etl') -Oldest | ForEach-Object {
                $event = $_
                $lifecycle = $event.ProviderId -eq $processProvider -and $event.Id -in 1,2,3,4
                if ($lifecycle -or ($event.ProviderId -eq $fileProvider -and
                    $event.Id -in 10,11,12,13,14,15,16,17,18,19,21,23,24,26,27,28,29,34)) {
                    $xml = [xml]$event.ToXml()
                    $fields = @{}
                    foreach ($field in $xml.SelectNodes("//*[local-name()='EventData']/*[local-name()='Data']")) {
                        $fields[$field.GetAttribute('Name')] = $field.InnerText
                    }
                    $stream.WriteLine((@{
                        id = $event.Id
                        pid = $event.ProcessId
                        ticks = $event.TimeCreated.ToUniversalTime().Ticks
                        lifecycle = $lifecycle
                        data = $fields
                    } | ConvertTo-Json -Compress -Depth 4))
                }
            }
        } finally {
            $stream.Dispose()
        }
    }
}
