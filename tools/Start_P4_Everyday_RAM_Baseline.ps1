# Measure the verified unpackaged QA desktop during an everyday, model-free session.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$KitDirectory,
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-VerifiedPayload([string]$Directory) {
    $kit = Get-Item -LiteralPath $Directory
    if (-not $kit.PSIsContainer -or ($kit.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Use the ordinary folder containing the extracted headroom kit.'
    }
    $expected = [ordered]@{
        'pilotodin-desktop.exe' = 'c9aac50c3299d280cb7ce4211db5b7e32402d7949a03fcf98d01e738d2c57fbf'
        'pilotodin-engine.exe' = 'b85b7a39bb863ef340a2ea420166cfa93fed1d8427b57229e75dc3724dca4f6b'
    }
    $payload = foreach ($entry in $expected.GetEnumerator()) {
        $file = Get-Item -LiteralPath (Join-Path $kit.FullName $entry.Key)
        if ($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ine $entry.Value) {
            throw "Unexpected SHA-256 or file type for $($entry.Key). Use the verified GitHub Actions kit."
        }
        [pscustomobject]@{ Name = $entry.Key; Path = $file.FullName; Sha256 = $entry.Value }
    }
    return $payload
}

function New-WideFixture([string]$Path) {
    $writer = [IO.StreamWriter]::new($Path, $false, [Text.UTF8Encoding]::new($false))
    try {
        $header = @('record_id', 'premium', 'outcome') + @(1..25 | ForEach-Object { 'text_{0:D2}' -f $_ })
        $writer.WriteLine(($header -join ','))
        for ($row = 1; $row -le 4000; $row++) {
            $outcome = if (($row % 4) -eq 2 -or ($row % 4) -eq 0) { 'No' } else { 'Yes' }
            $premium = if (($row % 4) -eq 2) { '' } else { 10 * (1 + (($row - 1) % 4)) }
            $fields = for ($column = 1; $column -le 25; $column++) {
                'category_{0:D2}_field_{1:D2}_reference_{2:D3}' -f ($row % 53), $column, ($row % 127)
            }
            $writer.WriteLine(((@($row, $premium, $outcome) + $fields) -join ','))
        }
    } finally {
        $writer.Dispose()
    }
}

function Get-OwnedProcesses($Snapshot, $App, [string]$AppPath, [hashtable]$Seen) {
    if ($null -eq $App) { return }
    $owned = @{}
    foreach ($entry in $Snapshot) {
        $key = [int]$entry.ProcessId
        if ($null -eq $entry.CreationDate) { continue }
        $birth = $entry.CreationDate.ToUniversalTime()
        $isRoot = $key -eq $App.Id -and $entry.ExecutablePath -ieq $AppPath -and
            [Math]::Abs(($birth - $App.StartTime.ToUniversalTime()).TotalMilliseconds) -le 2
        if ($isRoot -or ($Seen.ContainsKey($key) -and $Seen[$key] -eq $birth)) {
            $owned[$key] = $entry
        }
    }
    do {
        $added = $false
        foreach ($entry in $Snapshot) {
            $key = [int]$entry.ProcessId
            $parent = [int]$entry.ParentProcessId
            if ($owned.ContainsKey($key) -or -not $owned.ContainsKey($parent) -or $null -eq $entry.CreationDate) { continue }
            if ($entry.CreationDate -lt $owned[$parent].CreationDate) { continue }
            $owned[$key] = $entry
            $added = $true
        }
    } while ($added)
    foreach ($entry in $owned.Values) {
        $Seen[[int]$entry.ProcessId] = $entry.CreationDate.ToUniversalTime()
        $entry
    }
}

function Add-CsvRow([string]$Path, $Rows) {
    if (@($Rows).Count -gt 0) {
        $Rows | Export-Csv -LiteralPath $Path -Append -NoTypeInformation -Encoding UTF8
    }
}

function Write-Sample([string]$Stage, [int]$Sequence, $App, [string]$AppPath, [hashtable]$Seen, [string]$OutputRoot) {
    $sampleStarted = [DateTime]::UtcNow
    $system = Get-CimInstance -ClassName Win32_PerfFormattedData_PerfOS_Memory -OperationTimeoutSec 4
    $owned = @()
    $counters = @{}
    if ($null -ne $App) {
        $snapshot = @(Get-CimInstance -ClassName Win32_Process -OperationTimeoutSec 4 -Property ProcessId,ParentProcessId,CreationDate,Name,ExecutablePath)
        $owned = @(Get-OwnedProcesses $snapshot $App $AppPath $Seen)
        if ($owned.Count -gt 0) {
            $filter = ($owned | ForEach-Object { "IDProcess = $($_.ProcessId)" }) -join ' OR '
            foreach ($counter in @(Get-CimInstance -ClassName Win32_PerfFormattedData_PerfProc_Process -Filter $filter -OperationTimeoutSec 4)) {
                $counters[[int]$counter.IDProcess] = $counter
            }
        }
    }
    $rows = @(foreach ($entry in $owned) {
        $counter = $counters[[int]$entry.ProcessId]
        $perfName = [IO.Path]::GetFileNameWithoutExtension($entry.Name)
        $matched = $null -ne $counter -and ($counter.Name -ieq $perfName -or
            $counter.Name -match ('^' + [regex]::Escape($perfName) + '#[0-9]+$'))
        $role = switch -Wildcard ($entry.Name) {
            'pilotodin-desktop.exe' { 'desktop' }
            'pilotodin-engine*.exe' { 'engine' }
            'msedgewebview2.exe' { 'webview2' }
            'pilotodin-inference*.exe' { 'inference' }
            default { 'other-child' }
        }
        [pscustomobject][ordered]@{
            sample = $Sequence; stage = $Stage; role = $role
            pid = $entry.ProcessId; parent_pid = $entry.ParentProcessId
            started_utc = $entry.CreationDate.ToUniversalTime().ToString('o')
            working_set_bytes = if ($matched) { $counter.WorkingSet }
            private_resident_bytes = if ($matched) { $counter.WorkingSetPrivate }
            private_commit_bytes = if ($matched) { $counter.PrivateBytes }
        }
    })
    $working = @($rows | Where-Object { $null -ne $_.working_set_bytes })
    $private = @($working | Where-Object { $null -ne $_.private_resident_bytes })
    $roles = @($working | ForEach-Object { $_.role } | Sort-Object -Unique)
    $hasCore = 'desktop' -in $roles -and 'engine' -in $roles -and 'webview2' -in $roles
    $responding = if ($null -ne $App -and -not $App.HasExited) { $App.Refresh(); $App.Responding }
    Add-CsvRow (Join-Path $OutputRoot 'processes.csv') $rows
    Add-CsvRow (Join-Path $OutputRoot 'samples.csv') ([pscustomobject][ordered]@{
        sample = $Sequence; stage = $Stage; at_utc = $sampleStarted.ToString('o')
        collection_ms = [int]([DateTime]::UtcNow - $sampleStarted).TotalMilliseconds
        available_mib = $system.AvailableMBytes
        system_commit_bytes = $system.CommittedBytes
        pages_input_per_second = $system.PagesInputPersec
        owned_processes = $owned.Count; measured_processes = $working.Count
        core_roles_measured = $hasCore; desktop_responding = $responding
        working_set_bytes_sum = if ($working.Count -gt 0) { ($working | Measure-Object -Property working_set_bytes -Sum).Sum }
        private_resident_bytes_sum = if ($private.Count -gt 0) { ($private | Measure-Object -Property private_resident_bytes -Sum).Sum }
        private_resident_processes = $private.Count
    })
}

function Write-Stage([string]$Name, [string]$Event, [string]$Observation) {
    Add-CsvRow (Join-Path $result 'stages.csv') ([pscustomobject][ordered]@{
        at_utc = [DateTime]::UtcNow.ToString('o'); stage = $Name; event = $Event; observation = $Observation
    })
}

$payload = @(Get-VerifiedPayload $KitDirectory)
if ($VerifyOnly) {
    Write-Host 'Both QA executables match the pinned SHA-256 values.'
    return
}
if ($env:OS -ne 'Windows_NT' -or [Console]::IsInputRedirected) {
    throw 'Run this in an interactive Windows PowerShell window.'
}
foreach ($name in @('PILOTODIN_HOME','PILOTODIN_R03_BENCHMARK','WEBVIEW2_USER_DATA_FOLDER','WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS')) {
    if ([Environment]::GetEnvironmentVariable($name)) { throw "Open a fresh shell without $name." }
}
$profileRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'com.pilotodin.p4r03benchmark'
$profileData = Join-Path $profileRoot 'data'
$baselineProfile = Join-Path $profileData 'baseline'
foreach ($parentDirectory in @($profileRoot, $profileData)) {
    if (Test-Path -LiteralPath $parentDirectory) {
        $parentItem = Get-Item -LiteralPath $parentDirectory
        if (-not $parentItem.PSIsContainer -or ($parentItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'The QA data path is redirected. Leave the profile untouched.'
        }
    }
}
if (Test-Path -LiteralPath $baselineProfile) {
    throw 'The isolated R03 baseline profile already exists. Leave it and its evidence untouched.'
}
if (Get-Process -Name 'pilotodin-desktop','pilotodin-engine','pilotodin-inference' -ErrorAction SilentlyContinue) {
    throw 'Close the existing PilotODIN windows and stop any Live Dev test you opened. Then retry.'
}
$root = Join-Path ([IO.Path]::GetTempPath()) ('PilotODIN-Everyday-RAM-' + [Guid]::NewGuid().ToString('N'))
$result = Join-Path $root 'evidence'
$null = New-Item -ItemType Directory -Path $root, $result
foreach ($file in $payload) {
    $staged = Join-Path $root $file.Name
    Copy-Item -LiteralPath $file.Path -Destination $staged
    if ((Get-FileHash -LiteralPath $staged -Algorithm SHA256).Hash -ine $file.Sha256) {
        throw "Staging changed the SHA-256 for $($file.Name)."
    }
}
$small = Join-Path $root 'everyday_small.csv'
$wide = Join-Path $root 'everyday_wide.csv'
$html = Join-Path $root 'PilotODIN-RAM-report.html'
@('premium,outcome','10,Yes',',No','30,Yes','40,No') | Set-Content -LiteralPath $small -Encoding Ascii
New-WideFixture $wide
$os = Get-CimInstance -ClassName Win32_OperatingSystem -OperationTimeoutSec 4
[ordered]@{
    source_sha = '8966edc781128baa94354df044bfadc45d069984'
    windows_version = $os.Version; physical_memory_mib = [Math]::Round($os.TotalVisibleMemorySize / 1024, 1)
    desktop_sha256 = $payload[0].Sha256; engine_sha256 = $payload[1].Sha256
    profile = 'com.pilotodin.p4r03benchmark/data/baseline'
    inference = 'Local analytics only; model files are absent from the staged app'
    fixtures = @(@{ name = 'everyday_small.csv'; rows = 4; columns = 2 },
        @{ name = 'everyday_wide.csv'; rows = 4000; columns = 28 })
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $result 'session.json') -Encoding UTF8

$stages = [ordered]@{
    'cold_launch' = 'Wait for the Home screen and working navigation.'
    'ready_idle' = 'Leave Home visible. Sampling will advance automatically.'
    'import_small' = "Use New project to import $small as everyday_small. Confirm 4 rows."
    'import_wide' = "Use New project to import $wide as everyday_wide. Confirm 4,000 rows."
    'switch_project' = 'Use the project selector to switch to everyday_small, then back to everyday_wide.'
    'quality' = 'Open Quality on everyday_wide and confirm the premium issue shows 1,000 missing values. Leave the data as imported.'
    'explore' = 'Open Explore on everyday_wide. Select a Histogram for premium and wait for the chart.'
    'local_analytics' = 'Open Ask ODIN on everyday_wide, choose Local analytics and ask What is the dataset overview? Confirm 4,000 rows.'
    'export_html' = "In Deliver choose New report. Title it PilotODIN RAM baseline. Capture current Quality audit, select its evidence and click Save report. Click Export HTML and save to $html"
    'cooldown' = 'Return to Home and leave the app open. Sampling will advance automatically.'
}
$appPath = Join-Path $root 'pilotodin-desktop.exe'
$app = $null
$seen = @{}
$sequence = 0
$sessionOutcome = 'error'
$stage = 'system_idle'
try {
    [void][Console]::KeyAvailable
    Write-Host 'Collecting ten idle Windows memory samples before launch.'
    Write-Stage $stage 'start' ''
    for ($tick = 0; $tick -lt 10; $tick++) {
        Write-Sample $stage (++$sequence) $null $appPath $seen $result
        Start-Sleep -Seconds 1
    }
    Write-Stage $stage 'end' 'timed'
    # The staged app has no inference payload and starts with a fresh backend and WebView2 profile.
    $stage = 'cold_launch'
    Write-Stage $stage 'start' ''
    $null = [IO.Directory]::CreateDirectory($profileData)
    # Claim this path once, with no overwrite if another QA session created it.
    $null = New-Item -ItemType Directory -Path $baselineProfile
    $env:PILOTODIN_R03_BENCHMARK = 'baseline'
    $env:WEBVIEW2_USER_DATA_FOLDER = Join-Path $root 'webview'
    try {
        $app = Start-Process -FilePath $appPath -WorkingDirectory $root -PassThru
    } finally {
        Remove-Item Env:PILOTODIN_R03_BENCHMARK,Env:WEBVIEW2_USER_DATA_FOLDER
    }
    foreach ($entry in $stages.GetEnumerator()) {
        $stage = $entry.Key
        $timed = $stage -in @('ready_idle', 'cooldown')
        if ($stage -ne 'cold_launch') { Write-Stage $stage 'start' '' }
        Write-Host ""
        Write-Host $entry.Value
        if (-not $timed) { Write-Host 'Back in PowerShell, press P if complete or F if it failed. Press Q to stop.' }
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $observation = 'timeout'
        do {
            Write-Sample $stage (++$sequence) $app $appPath $seen $result
            if ($app.HasExited) { $observation = 'desktop_exited'; break }
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true).Key
                if ($key -eq 'Q') { $observation = 'stopped'; break }
                if (-not $timed -and $key -eq 'P') {
                    if ($stage -eq 'export_html' -and -not (Test-Path -LiteralPath $html -PathType Leaf)) {
                        Write-Host "Save the export to $html before pressing P."
                        continue
                    }
                    $observation = 'owner_observed'
                    break
                }
                if (-not $timed -and $key -eq 'F') { $observation = 'owner_reported_failure'; break }
            }
            Start-Sleep -Seconds 1
        } while ($timer.Elapsed.TotalSeconds -lt $(if ($timed) { 20 } else { 300 }))
        if ($timed -and $observation -eq 'timeout') { $observation = 'timed' }
        Write-Stage $stage 'end' $observation
        $sessionOutcome = $observation
        if ($observation -notin @('timed','owner_observed')) { break }
    }
    if ($stage -eq 'cooldown' -and $sessionOutcome -eq 'timed') { $sessionOutcome = 'walkthrough_complete' }
} catch {
    $sessionOutcome = 'error'
    Write-Warning $_.Exception.Message
    Write-Stage $stage 'end' $sessionOutcome
} finally {
    Write-Stage $stage 'session_end' $sessionOutcome
    $zip = Join-Path $root 'PilotODIN-Everyday-RAM-Evidence.zip'
    Compress-Archive -Path (Join-Path $result '*') -DestinationPath $zip
    Write-Host ""
    Write-Host "Walkthrough outcome: $sessionOutcome"
    Write-Host "Evidence ZIP: $zip"
    if ($null -ne $app -and -not $app.HasExited) { Write-Host 'You can now close the QA desktop normally.' }
}
