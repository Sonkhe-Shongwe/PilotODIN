$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$launcher = Join-Path $root 'tools/Start_P4_R03_Offline_QA.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($launcher, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors -join [Environment]::NewLine) }
foreach ($statement in $ast.EndBlock.Statements) {
    if ($statement -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
        . ([scriptblock]::Create($statement.Extent.Text))
    }
}

$temp = Join-Path ([IO.Path]::GetTempPath()) ('PilotODIN-R03-Launcher-Test-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $temp
try {
    $original = Join-Path $temp 'baseline'
    $candidate = Join-Path $temp 'candidate'
    $null = New-Item -ItemType Directory -Path $original,$candidate
    'previous benchmark' | Set-Content -LiteralPath (Join-Path $original 'r03-benchmark.jsonl')
    $archived = Move-R03BenchmarkProfileAside $original
    if ((Test-Path -LiteralPath $original) -or -not (Test-Path -LiteralPath $candidate) -or
        (Get-Content -LiteralPath (Join-Path $archived 'r03-benchmark.jsonl')) -ne 'previous benchmark') {
        throw 'Isolated profile preservation failed.'
    }
    if ($null -ne (Move-R03BenchmarkProfileAside $original)) { throw 'Absent profile created a false archive.' }
    $plainFile = Join-Path $temp 'plain-file'
    'keep me' | Set-Content -LiteralPath $plainFile
    $rejected = $false
    try { Move-R03BenchmarkProfileAside $plainFile } catch { $rejected = $_.Exception.Message -like 'Expected an ordinary file or directory:*' }
    if (-not $rejected -or (Get-Content -LiteralPath $plainFile) -ne 'keep me') { throw 'The launcher accepted an unexpected profile path.' }

    $profileRoot = $candidate
    '{"stage":"desktop_preflight","decision":"allow"}' | Set-Content -LiteralPath (Join-Path $candidate 'r03-benchmark.jsonl')
    $disposable = $temp
    $BenchmarkProfile = 'candidate'
    $source = 'synthetic-source'
    $identity = 'com.pilotodin.p4r03benchmark'
    $modelHash = 'synthetic-model'
    $workerHash = 'synthetic-worker'
    $provenance = [pscustomobject]@{ run_id = '123'; desktop_sha256 = 'synthetic-desktop'; engine_sha256 = 'synthetic-engine' }
    $app = [pscustomobject]@{ HasExited = $false; ExitCode = 0; Responding = $true }
    $app | Add-Member ScriptMethod Refresh {}
    $script:reads = 0
    function Get-CimInstance {
        [CmdletBinding()]
        param([string]$ClassName, [int]$OperationTimeoutSec)
        $script:reads++
        if ($script:reads -eq 1) { throw 'Timed out' }
        [pscustomobject]@{ AvailableMBytes = 2300; CommittedBytes = 5368709120; PagesInputPersec = 0 }
    }
    function Start-Sleep([int]$Seconds) {
        if ($script:reads -eq 2) { $app.HasExited = $true }
    }

    # Exercise the launcher's benchmark capture without starting a desktop.
    $capture = $ast.EndBlock.Statements[-1]
    if ($capture.Extent.Text -notlike '*PilotODIN-R03-Offline-Evidence.zip*') { throw 'Benchmark capture block missing.' }
    . ([scriptblock]::Create($capture.Extent.Text))
    $rows = @(Import-Csv -LiteralPath (Join-Path $temp 'r03-memory.csv'))
    if ($rows.Count -ne 2 -or $rows[0].available_mib -or -not $rows[0].collector_error -or $rows[1].available_mib -ne '2300') {
        throw 'Sampler did not recover after a missed read.'
    }
    $receipt = Get-Content -LiteralPath (Join-Path $temp 'r03-session.json') -Raw | ConvertFrom-Json
    if ($receipt.collector_errors -ne 1 -or -not $receipt.admission_log_present -or $receipt.desktop_exit_code -ne 0) {
        throw 'Wrong benchmark receipt.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $temp 'PilotODIN-R03-Offline-Evidence.zip'))
    try {
        if ((($archive.Entries.Name | Sort-Object) -join ',') -ne 'r03-benchmark.jsonl,r03-memory.csv,r03-session.json') {
            throw 'Unexpected files in the evidence ZIP.'
        }
    } finally { $archive.Dispose() }
} finally {
    Remove-Item -LiteralPath $temp -Recurse
}
Write-Host 'R03 profile preservation, sampler retry recovery and scoped evidence archive passed.'
