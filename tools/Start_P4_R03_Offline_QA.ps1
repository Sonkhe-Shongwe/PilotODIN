param(
    [Parameter(Mandatory = $true)][string]$KitDirectory,
    [string]$RuntimeDirectory = (Join-Path $env:LOCALAPPDATA 'pilotODIN-P4-Native-QA'),
    [ValidateSet('baseline','candidate')][string]$BenchmarkProfile,
    [ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedSource,
    [switch]$ArchiveExistingQaProfile,
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$source = '4f3824c2f565f33a87f0195844d2d73242cf7571'
$identity = 'com.pilotodin.p4r03owner'
if ($BenchmarkProfile) {
    if (-not $ExpectedSource) { throw 'Supply the approved benchmark source SHA.' }
    $source = $ExpectedSource
    $identity = 'com.pilotodin.p4r03benchmark'
}
$modelName = 'qwen3-1.7b-q4_k_m.gguf'
$modelHash = 'd2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5'
$workerHash = 'b2ace4b8aed7c60e217fcaed8541850f4998539b8478880f1c3264387a0a8d97'
if ($ArchiveExistingQaProfile -and -not $BenchmarkProfile) {
    throw '-ArchiveExistingQaProfile applies to an isolated benchmark profile.'
}

function Get-PlainItem([string]$Path, [bool]$Directory) {
    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer -ne $Directory -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Expected an ordinary file or directory: $Path"
    }
    return $item.FullName
}

function Assert-Hash([string]$Path, [string]$Expected) {
    if ($Expected -cnotmatch '^[0-9a-f]{64}$' -or (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Expected) {
        throw "SHA-256 verification failed: $(Split-Path -Leaf $Path)"
    }
}

function Move-R03BenchmarkProfileAside([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $original = Get-PlainItem $Path $true
    $name = (Split-Path -Leaf $original) + '-before-r03-qa-' + [Guid]::NewGuid().ToString('N')
    Rename-Item -LiteralPath $original -NewName $name
    return (Join-Path (Split-Path -Parent $original) $name)
}

$kit = Get-PlainItem $KitDirectory $true
$runtime = Get-PlainItem $RuntimeDirectory $true
$runtimeModels = Get-PlainItem (Join-Path $runtime 'models') $true
$runtimeDlls = Get-PlainItem (Join-Path $runtime 'llama-runtime') $true
$provenance = Get-Content -LiteralPath (Get-PlainItem (Join-Path $kit 'provenance.json') $false) -Raw | ConvertFrom-Json
$manifestFile = Get-PlainItem (Join-Path $kit 'model-manifest.json') $false
if ($provenance.source_sha -cne $source -or $provenance.app_identifier -cne $identity -or
    [string]$provenance.run_id -cnotmatch '^[0-9]+$') {
    throw 'This kit does not identify the approved source and disposable app.'
}
Assert-Hash $manifestFile $provenance.model_manifest_sha256
$manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
if ($manifest.schema_version -ne 1 -or $manifest.model_file -cne $modelName -or
    $manifest.model_alias -cne 'pilotodin-qwen3-1.7b' -or
    $manifest.model_sha256 -cne $modelHash -or $manifest.server_sha256 -cne $workerHash) {
    throw 'Unexpected Qwen or inference worker identity.'
}
$files = @(
    @{From = (Join-Path $kit 'pilotodin-desktop.exe'); To = 'pilotodin-desktop.exe'; Hash = $provenance.desktop_sha256}
    @{From = (Join-Path $kit 'pilotodin-engine.exe'); To = 'pilotodin-engine.exe'; Hash = $provenance.engine_sha256}
    @{From = $manifestFile; To = 'models/model-manifest.json'; Hash = $provenance.model_manifest_sha256}
    @{From = (Join-Path $runtimeModels $modelName); To = "models/$modelName"; Hash = $modelHash}
    @{From = (Join-Path $runtime 'pilotodin-inference.exe'); To = 'pilotodin-inference.exe'; Hash = $workerHash}
)
$dlls = @($manifest.runtime_dll_sha256.PSObject.Properties)
if ($dlls.Count -lt 1) { throw 'The runtime checksum list is empty.' }
foreach ($dll in $dlls) {
    if ($dll.Name -cnotmatch '(?i)^[a-z0-9][a-z0-9_.-]*\.dll$') { throw 'Unexpected runtime DLL name.' }
    $files += @{From = (Join-Path $runtimeDlls $dll.Name); To = "llama-runtime/$($dll.Name)"; Hash = $dll.Value}
}

if ($VerifyOnly) {
    foreach ($file in $files) { Assert-Hash (Get-PlainItem $file.From $false) $file.Hash }
    Write-Host "Verified host kit identity and $($files.Count) file hashes. Desktop launch NOT RUN."
    return
}

if ($BenchmarkProfile) {
    $appRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) $identity
    if (Test-Path -LiteralPath $appRoot) { $null = Get-PlainItem $appRoot $true }
    $dataRoot = Join-Path $appRoot 'data'
    if (Test-Path -LiteralPath $dataRoot) { $null = Get-PlainItem $dataRoot $true }
    $profileRoot = Join-Path $dataRoot $BenchmarkProfile
    if ((Test-Path -LiteralPath $profileRoot) -and -not $ArchiveExistingQaProfile) {
        throw 'This benchmark profile already ran. Use -ArchiveExistingQaProfile to preserve it before retrying.'
    }
} else {
    foreach ($root in @([Environment]::GetFolderPath('LocalApplicationData'),[Environment]::GetFolderPath('ApplicationData'))) {
        if (Test-Path -LiteralPath (Join-Path $root $identity)) { throw 'The R03 QA profile already exists. Preserve it for review.' }
    }
}
if ($env:PILOTODIN_HOME -or $env:WEBVIEW2_USER_DATA_FOLDER -or $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS -or $env:PILOTODIN_R03_BENCHMARK) {
    throw 'Use a fresh PowerShell window with no PilotODIN or WebView2 environment overrides.'
}
if ($BenchmarkProfile -and (Get-Process -Name 'pilotodin-desktop','pilotodin-engine','pilotodin-inference' -ErrorAction SilentlyContinue)) {
    throw 'Close any running PilotODIN desktop or Live Dev session before starting this benchmark.'
}
$temp = Get-PlainItem ([IO.Path]::GetTempPath()) $true
$disposable = Join-Path $temp ('PilotODIN-P4-R03-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $disposable
$null = New-Item -ItemType Directory -Path (Join-Path $disposable 'models'),(Join-Path $disposable 'llama-runtime')
foreach ($file in $files) {
    $target = Join-Path $disposable $file.To
    Copy-Item -LiteralPath (Get-PlainItem $file.From $false) -Destination $target
    Assert-Hash $target $file.Hash
}
if ($BenchmarkProfile -and $ArchiveExistingQaProfile) {
    $archived = Move-R03BenchmarkProfileAside $profileRoot
    if ($archived) { Write-Host "Previous R03 QA profile preserved at $archived" }
}
$fixture = Join-Path $disposable 'r03_synthetic.csv'
@('premium,outcome','10,Yes',',No','30,Yes','40,No') | Set-Content -LiteralPath $fixture -Encoding Ascii
Write-Host "Verified source $source, GitHub run $($provenance.run_id)."
Write-Host "Desktop SHA-256: $($provenance.desktop_sha256)"
Write-Host "Import this synthetic CSV: $fixture"
$env:WEBVIEW2_USER_DATA_FOLDER = Join-Path $disposable 'webview'
if ($BenchmarkProfile) { $env:PILOTODIN_R03_BENCHMARK = $BenchmarkProfile }
try {
    $app = Start-Process -FilePath (Join-Path $disposable 'pilotodin-desktop.exe') -WorkingDirectory $disposable -PassThru
    Write-Host "Started isolated R03 desktop (PID $($app.Id))."
} finally {
    Remove-Item Env:WEBVIEW2_USER_DATA_FOLDER
    if ($BenchmarkProfile) { Remove-Item Env:PILOTODIN_R03_BENCHMARK -ErrorAction SilentlyContinue }
}

if ($BenchmarkProfile) {
    $admissionLog = Join-Path $profileRoot 'r03-benchmark.jsonl'
    $samples = Join-Path $disposable 'r03-memory.csv'
    $receipt = Join-Path $disposable 'r03-session.json'
    $evidence = Join-Path $disposable 'PilotODIN-R03-Offline-Evidence.zip'
    Write-Host "Benchmark profile: $BenchmarkProfile"
    Write-Host "Admission evidence: $admissionLog"
    Write-Host "Memory samples: $samples"
    Write-Host 'After recording the answer or deferral, close the QA desktop to finish sampling.'
    $started = [DateTime]::UtcNow
    $deadline = $started.AddMinutes(15)
    $collectorErrors = 0
    try {
        while (-not $app.HasExited -and [DateTime]::UtcNow -lt $deadline) {
            $memory = $null
            $collectorError = $null
            try {
                $memory = Get-CimInstance -ClassName Win32_PerfFormattedData_PerfOS_Memory -OperationTimeoutSec 4 -ErrorAction Stop
            } catch {
                $collectorError = $_.FullyQualifiedErrorId
                $collectorErrors++
                if ($collectorErrors -eq 1) { Write-Warning 'A Windows memory sample was missed. Sampling will continue.' }
            }
            $app.Refresh()
            [pscustomobject][ordered]@{
                at_utc = [DateTime]::UtcNow.ToString('o')
                available_mib = $(if ($null -ne $memory) { $memory.AvailableMBytes })
                system_commit_mib = $(if ($null -ne $memory) { [Math]::Round([double]$memory.CommittedBytes / 1MB, 2) })
                system_pages_input_per_sec = $(if ($null -ne $memory) { $memory.PagesInputPersec })
                desktop_responding = $(if (-not $app.HasExited) { $app.Responding })
                collector_error = $collectorError
            } | Export-Csv -LiteralPath $samples -Append -NoTypeInformation -Encoding UTF8
            Start-Sleep -Seconds 1
        }
    } finally {
        $logCaptured = Test-Path -LiteralPath $admissionLog -PathType Leaf
        [ordered]@{
            source_sha = $source; run_id = $provenance.run_id; app_identifier = $identity
            desktop_sha256 = $provenance.desktop_sha256; engine_sha256 = $provenance.engine_sha256
            benchmark_profile = $BenchmarkProfile; model_sha256 = $modelHash; worker_sha256 = $workerHash
            started_utc = $started.ToString('o'); ended_utc = [DateTime]::UtcNow.ToString('o')
            collector_errors = $collectorErrors; admission_log_present = $logCaptured
            desktop_exit_code = $(if ($app.HasExited) { $app.ExitCode })
        } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $receipt -Encoding UTF8
        $captured = @($receipt)
        if (Test-Path -LiteralPath $samples -PathType Leaf) { $captured += $samples }
        if ($logCaptured) {
            $captured += $admissionLog
            Get-Content -LiteralPath $admissionLog
        }
        Compress-Archive -LiteralPath $captured -DestinationPath $evidence
        if ($app.HasExited) { Write-Host "QA desktop exit code: $($app.ExitCode)" }
        Write-Host "Evidence ZIP: $evidence"
    }
}
