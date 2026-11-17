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
    # The pinned launcher refuses an altered payload even in verify-only mode.
    'fake' | Set-Content -LiteralPath (Join-Path $temp 'pilotodin-desktop.exe')
    $rejected = $false
    try {
        $null = Get-VerifiedPayload $temp
    } catch {
        $rejected = $_.Exception.Message -like '*Unexpected SHA-256*'
    }
    Assert-Equal $rejected $true 'reject changed executable'

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

    function Get-CimInstance([string]$ClassName, [string]$Filter, [int]$OperationTimeoutSec, [string[]]$Property) {
        switch ($ClassName) {
            'Win32_Process' { return $snapshot }
            'Win32_PerfFormattedData_PerfOS_Memory' {
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
    Write-Sample 'system_idle' 1 $null $root @{} $temp
    Write-Sample 'ready_idle' 2 $app $root @{} $temp
    $samples = @(Import-Csv -LiteralPath (Join-Path $temp 'samples.csv'))
    Assert-Equal $samples.Count 2 'idle and active samples'
    Assert-Equal $samples[0].working_set_bytes_sum '' 'idle app usage unknown'
    Assert-Equal $samples[1].working_set_bytes_sum '300' 'sum only current matching readings'
    Assert-Equal $samples[1].private_resident_bytes_sum '225' 'private resident total'
    Assert-Equal $samples[1].measured_processes '3' 'missing counter marked'
    Assert-Equal $samples[1].owned_processes '4' 'partial coverage retained'
    Assert-Equal $samples[1].core_roles_measured 'True' 'all core roles seen'
    $measurements = @(Import-Csv -LiteralPath (Join-Path $temp 'processes.csv'))
    Assert-Equal $measurements.Count 4 'all identities recorded'
    Assert-Equal ($measurements | Where-Object pid -eq '103').private_commit_bytes '' 'wrong instance commit is blank'
} finally {
    Remove-Item -LiteralPath $temp -Recurse
}
Write-Host 'Everyday RAM baseline fixture, scoped process identity and sampling checks passed.'
