$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runner = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'tools/Start_P4_Everyday_RAM_Baseline.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($runner, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors -join [Environment]::NewLine) }
# Load definitions without entering the physical laptop launcher.
foreach ($definition in $ast.EndBlock.Statements) {
    if ($definition -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
        . ([scriptblock]::Create($definition.Extent.Text))
    }
}

function Assert-Equal($Actual, $Expected, [string]$Case) {
    if ($Actual -cne $Expected) { throw "${Case}: expected $Expected, got $Actual" }
}

function New-FakeProcess([int]$Id, [int]$Parent, [datetime]$Birth, [string]$Name, [string]$Path = '') {
    [pscustomobject]@{
        ProcessId = $Id; ParentProcessId = $Parent
        CreationDate = $Birth; Name = $Name; ExecutablePath = $Path
    }
}

# Windows verifies the real CIM provider's property names before synthetic attribution.
if ($env:OS -eq 'Windows_NT') {
    $now = Get-CimInstance Win32_Process -Filter "ProcessId = $PID" -Property ProcessId,ParentProcessId,CreationDate,Name,ExecutablePath
    $perf = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -Filter "IDProcess = $PID"
    $memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    if (-not $now.ExecutablePath -or $now.CreationDate -isnot [datetime] -or -not $perf.WorkingSet -or
        $null -eq $perf.WorkingSetPrivate -or $null -eq $perf.PrivateBytes -or
        $null -eq $memory.AvailableMBytes -or $null -eq $memory.PagesInputPersec -or $null -eq $memory.CommittedBytes) {
        throw 'The Windows collector is missing an expected process or system counter.'
    }
}

$temp = Join-Path ([IO.Path]::GetTempPath()) ('PilotODIN-RAM-test-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $temp
try {
    $baseline = Get-QaKitSpec 'Baseline'
    $updated = Get-QaKitSpec 'Updated'
    Assert-Equal $baseline.SourceSha '8966edc781128baa94354df044bfadc45d069984' 'baseline source'
    Assert-Equal $updated.SourceSha '1cfeb9421a3986ec75c97d8dd9b88f831596c9eb' 'updated source'
    foreach ($filename in $baseline.Files.Keys) {
        Assert-Equal ($baseline.Files[$filename] -cmatch '^[0-9a-f]{64}$') $true 'baseline hash pinned'
        Assert-Equal ($updated.Files[$filename] -cmatch '^[0-9a-f]{64}$') $true 'updated hash pinned'
        Assert-Equal ($baseline.Files[$filename] -cne $updated.Files[$filename]) $true 'build receipts differ'
    }

    # The pinned launcher refuses an altered payload even in verify-only mode.
    'fake' | Set-Content -LiteralPath (Join-Path $temp 'pilotodin-desktop.exe')
    $rejected = $false
    try {
        $null = Get-VerifiedPayload $temp $baseline.Files
    } catch {
        $rejected = $_.Exception.Message -like '*Unexpected SHA-256*'
    }
    Assert-Equal $rejected $true 'reject changed executable'

    $profile = Join-Path $temp 'baseline'
    $candidate = New-Item -ItemType Directory -Path (Join-Path $temp 'candidate')
    Initialize-QaBaseline $profile $false
    'existing evidence' | Set-Content -LiteralPath (Join-Path $profile 'r03-benchmark.jsonl')
    $existingHash = (Get-FileHash -LiteralPath (Join-Path $profile 'r03-benchmark.jsonl')).Hash
    $rejected = $false
    try {
        Initialize-QaBaseline $profile $false
    } catch {
        $rejected = $_.Exception.Message -like '*QA baseline already exists*'
    }
    Assert-Equal $rejected $true 'require explicit archive switch'
    Initialize-QaBaseline $profile $true
    $archive = @(Get-ChildItem -LiteralPath $temp -Directory -Filter 'baseline-before-everyday-ram-*')
    Assert-Equal $archive.Count 1 'one previous profile archived'
    Assert-Equal (Get-FileHash -LiteralPath (Join-Path $archive[0].FullName 'r03-benchmark.jsonl')).Hash $existingHash 'prior evidence retained'
    Assert-Equal @(Get-ChildItem -LiteralPath $profile).Count 0 'new profile starts empty'
    Assert-Equal (Test-Path -LiteralPath $candidate.FullName -PathType Container) $true 'candidate profile still present'

    '<html>unrelated</html>' | Set-Content -LiteralPath (Join-Path $temp 'other.html')
    $report = Join-Path $temp 'pilotodin_report_26dc360189b4_rev1.html'
    $fixtureHash = 'a' * 64
    $null = New-Item -ItemType File -Path $report
    Assert-Equal (Get-VerifiedQaHtmlExport $temp $fixtureHash) $null 'reject an unrelated report or empty export'
    $rendered = @"
<!doctype html><html><head><title>PilotODIN RAM baseline</title></head><body><table><tr><td>Rows in approved dataset</td><td>4000</td></tr><tr><td>Source original SHA-256</td><td>$fixtureHash</td></tr><tr><td>Missing or blank values</td><td>Missing or blank values require domain review before imputation. | Column: premium | Affected rows: 1000 | Decision: pending</td></tr></table></body></html>
"@
    $rendered.Replace('Affected rows: 1000', 'Affected rows: 100') | Set-Content -LiteralPath $report
    Assert-Equal (Get-VerifiedQaHtmlExport $temp $fixtureHash) $null 'reject a wrong missing-value count'
    $rendered | Set-Content -LiteralPath $report
    Assert-Equal (Get-VerifiedQaHtmlExport $temp ('b' * 64)) $null 'reject a different dataset digest'
    $verified = Get-VerifiedQaHtmlExport $temp $fixtureHash
    Assert-Equal $verified.verified_missing_premium 1000 'accept the filename generated by Export HTML'
    Assert-Equal $verified.sha256 (Get-FileHash -LiteralPath $report).Hash.ToLowerInvariant() 'record actual saved file hash'
    Rename-Item -LiteralPath $report -NewName 'PilotODIN-RAM-report.html'
    Assert-Equal (Get-VerifiedQaHtmlExport $temp $fixtureHash).verified_rows 4000 'accept a manually named export'

    $csv = Join-Path $temp 'wide.csv'
    New-WideFixture $csv
    $fixture = @(Import-Csv -LiteralPath $csv)
    Assert-Equal $fixture.Count 4000 'wide rows'
    Assert-Equal @($fixture[0].PSObject.Properties).Count 28 'wide columns'
    Assert-Equal @($fixture | Where-Object { $_.premium -eq '' }).Count 1000 'missing premiums'
    Assert-Equal @($fixture | Where-Object { $_.outcome -eq 'Yes' }).Count 2000 'Yes outcomes'

    $birth = [datetime]::UtcNow.AddSeconds(-10)
    $app = [pscustomobject]@{ Id = 100; StartTime = $birth; HasExited = $false; Responding = $true }
    $app | Add-Member ScriptMethod Refresh {}
    $root = 'C:/qa/pilotodin-desktop.exe'
    $desktop = New-FakeProcess 100 1 $birth 'pilotodin-desktop.exe' $root
    $engine = New-FakeProcess 101 100 ($birth.AddSeconds(1)) 'pilotodin-engine.exe'
    $web = New-FakeProcess 102 100 ($birth.AddSeconds(1)) 'msedgewebview2.exe'
    $renderer = New-FakeProcess 103 102 ($birth.AddSeconds(2)) 'msedgewebview2.exe'
    $unrelated = New-FakeProcess 104 1 ($birth.AddSeconds(1)) 'msedgewebview2.exe'
    $impossibleChild = New-FakeProcess 105 102 ($birth.AddSeconds(-2)) 'other.exe'
    $snapshot = @($renderer, $unrelated, $engine, $web, $impossibleChild, $desktop)
    $seen = @{}
    $found = @(Get-OwnedProcesses $snapshot $app $root $seen)
    Assert-Equal (($found.ProcessId | Sort-Object) -join ',') '100,101,102,103' 'full scoped tree'
    $reused = New-FakeProcess 102 1 ($birth.AddSeconds(3)) 'msedgewebview2.exe'
    $found = @(Get-OwnedProcesses @($reused, $renderer) $app $root $seen)
    Assert-Equal $found.Count 1 'retain only known former child'
    Assert-Equal $found[0].ProcessId 103 'exclude reused PID'
    $found = @(Get-OwnedProcesses @($desktop, $web) $app 'C:/other/pilotodin-desktop.exe' @{})
    Assert-Equal $found.Count 0 'reject wrong desktop path without prior identity'

    $script:systemFailuresRemaining = 0
    $script:processSnapshotFails = $false
    $script:systemTimeouts = [Collections.Generic.List[int]]::new()
    function Get-CimInstance {
        [CmdletBinding()]
        param([string]$ClassName, [string]$Filter, [int]$OperationTimeoutSec, [string[]]$Property)
        switch ($ClassName) {
            'Win32_Process' {
                if ($script:processSnapshotFails) { throw 'Timed out' }
                return $snapshot
            }
            'Win32_PerfFormattedData_PerfOS_Memory' {
                $script:systemTimeouts.Add($OperationTimeoutSec)
                if ($script:systemFailuresRemaining -gt 0) {
                    $script:systemFailuresRemaining--
                    [pscustomobject]@{ AvailableMBytes = 123; CommittedBytes = 456; PagesInputPersec = 789 }
                    throw 'Timed out'
                }
                return [pscustomobject]@{ AvailableMBytes = 1400; CommittedBytes = 7000; PagesInputPersec = 98 }
            }
            'Win32_PerfFormattedData_PerfProc_Process' {
                if ($Filter -match '104|105') { throw 'Unrelated processes must stay outside the counter query.' }
                foreach ($name in @('pilotodin-desktop', 'pilotodin-engine', 'msedgewebview2#1', 'wrong-image')) {
                    $offset = [array]::IndexOf(@('pilotodin-desktop', 'pilotodin-engine', 'msedgewebview2#1', 'wrong-image'), $name)
                    [pscustomobject]@{
                        IDProcess = 100 + $offset; Name = $name
                        WorkingSet = 100; WorkingSetPrivate = 75; PrivateBytes = 150
                    }
                }
            }
            default { throw "Unexpected CIM class: $ClassName" }
        }
    }
    $retryUsed = @{}
    $script:systemFailuresRemaining = 1
    Write-Sample 'system_idle' 1 $null $root @{} $temp $retryUsed
    Write-Sample 'ready_idle' 2 $app $root @{} $temp $retryUsed
    $samples = @(Import-Csv -LiteralPath (Join-Path $temp 'samples.csv'))
    Assert-Equal $samples.Count 2 'idle and active samples'
    Assert-Equal $samples[0].working_set_bytes_sum '' 'idle app usage unknown'
    Assert-Equal $samples[0].available_mib '1400' 'cold system query recovered'
    Assert-Equal ($script:systemTimeouts -join ',') '4,12,4' 'retry once with longer timeout and restore regular timeout'
    Assert-Equal $samples[1].working_set_bytes_sum '300' 'sum only current matching readings'
    Assert-Equal $samples[1].private_resident_bytes_sum '225' 'private resident total'
    Assert-Equal $samples[1].measured_processes '3' 'missing counter marked'
    Assert-Equal $samples[1].owned_processes '4' 'partial coverage retained'
    Assert-Equal $samples[1].core_roles_measured 'True' 'all core roles seen'
    $measurements = @(Import-Csv -LiteralPath (Join-Path $temp 'processes.csv'))
    Assert-Equal $measurements.Count 4 'all identities recorded'
    Assert-Equal ($measurements | Where-Object pid -eq '103').private_commit_bytes '' 'wrong instance commit is blank'

    $script:systemFailuresRemaining = 2
    Write-Sample 'ready_idle' 3 $app $root @{} $temp $retryUsed
    $script:processSnapshotFails = $true
    Write-Sample 'explore' 4 $app $root @{} $temp $retryUsed
    $script:processSnapshotFails = $false
    Write-Sample 'cooldown' 5 $app $root @{} $temp $retryUsed
    $samples = @(Import-Csv -LiteralPath (Join-Path $temp 'samples.csv'))
    Assert-Equal $samples.Count 5 'collector failures do not end the walkthrough'
    Assert-Equal $samples[2].system_memory_measured 'False' 'missing system counters flagged'
    Assert-Equal $samples[2].available_mib '' 'partial failed query results discarded'
    Assert-Equal $samples[2].working_set_bytes_sum '300' 'system gap retains app readings'
    Assert-Equal $samples[3].owned_processes '' 'unavailable process evidence remains blank'
    Assert-Equal $samples[3].core_roles_measured 'False' 'unavailable process evidence flagged'
    Assert-Equal $samples[4].system_memory_measured 'True' 'system readings resume'
    Assert-Equal $samples[4].core_roles_measured 'True' 'app readings resume'
    $failures = @(Import-Csv -LiteralPath (Join-Path $temp 'collector-errors.csv'))
    Assert-Equal ($failures.outcome -join ',') 'retry,gap,gap,retry,gap' 'retry and gap evidence recorded'
    Assert-Equal ($failures.operation_timeout_seconds -join ',') '4,4,4,4,12' 'warm-up retry bounded independently per provider'
} finally {
    Remove-Item -LiteralPath $temp -Recurse
}
Write-Host 'Everyday RAM baseline fixture, scoped process identity and sampling checks passed.'
