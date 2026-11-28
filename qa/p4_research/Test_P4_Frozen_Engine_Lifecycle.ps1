# Runs on the disposable, scope-checked Windows build job.
param(
    [Parameter(Mandatory = $true)][string]$Desktop,
    [Parameter(Mandatory = $true)][string]$ExpectedDesktopHash,
    [Parameter(Mandatory = $true)][string]$ExpectedEngineHash
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:RUNNER_OS -cne 'Windows' -or
    $env:GITHUB_RUN_ATTEMPT -cne '1' -or $env:WEBVIEW2_USER_DATA_FOLDER -or $env:PILOTODIN_HOME) {
    throw 'Expected a fresh, first-attempt hosted Windows fixture.'
}
$desktopExe = Get-Item -LiteralPath $Desktop
$layout = $desktopExe.DirectoryName
$engine = Get-Item -LiteralPath (Join-Path $layout 'pilotodin-engine.exe')
if ($desktopExe.Name -cne 'pilotodin-desktop.exe' -or
    -not $desktopExe.FullName.StartsWith(([IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'),
        [StringComparison]::OrdinalIgnoreCase) -or
    ($desktopExe.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    ($engine.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    (Get-FileHash -LiteralPath $desktopExe.FullName).Hash -ine $ExpectedDesktopHash -or
    (Get-FileHash -LiteralPath $engine.FullName).Hash -ine $ExpectedEngineHash) {
    throw 'The isolated executable paths or hashes differ from the build receipt.'
}
foreach ($name in @('pilotodin-inference.exe','models','llama-runtime')) {
    if (Test-Path -LiteralPath (Join-Path $layout $name)) { throw 'Unexpected inference payload in analytics-only QA.' }
}

function Get-FixtureEngineRows {
    Get-CimInstance -ClassName Win32_Process -Filter "Name = 'pilotodin-engine.exe'" -OperationTimeoutSec 5 |
        Where-Object { $_.ExecutablePath -ieq $engine.FullName }
}

function Get-OwnedEnginePair($App) {
    $rows = @(Get-FixtureEngineRows | Where-Object { $_.CreationDate -ge $App.StartTime })
    $parents = @($rows | Where-Object ParentProcessId -EQ $App.Id)
    if ($parents.Count -ne 1) { return }
    $children = @($rows | Where-Object {
        $_.ParentProcessId -eq $parents[0].ProcessId -and $_.CreationDate -ge $parents[0].CreationDate
    })
    if ($children.Count -ne 1 -or $rows.Count -ne 2) { return }
    return $parents[0],$children[0]
}

function Open-FixtureProcess($Row) {
    $process = [Diagnostics.Process]::GetProcessById([int]$Row.ProcessId)
    try {
        # Retain the original process handle across shutdown to avoid PID reuse.
        $null = $process.SafeHandle
        if ($process.MainModule.FileName -ine $engine.FullName -or
            [Math]::Abs(($process.StartTime.ToUniversalTime() - $Row.CreationDate.ToUniversalTime()).TotalMilliseconds) -gt 2) {
            throw 'Engine process identity changed before its handle was retained.'
        }
        return $process
    } catch {
        $process.Dispose()
        throw
    }
}

function Wait-Ready($App) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    while ($clock.Elapsed.TotalSeconds -lt 45) {
        if ($App.HasExited) { throw 'Desktop stopped before the engine became ready.' }
        $pair = @(Get-OwnedEnginePair $App)
        if ($pair.Count -eq 2) {
            $listeners = @(Get-NetTCPConnection -State Listen -OwningProcess $pair[1].ProcessId -ErrorAction SilentlyContinue)
            if ($listeners | Where-Object LocalAddress -NE '127.0.0.1') { throw 'Unexpected non-loopback engine listener.' }
            foreach ($listener in $listeners) {
                try {
                    $response = Invoke-WebRequest "http://127.0.0.1:$($listener.LocalPort)/api/health" -NoProxy -SkipHttpErrorCheck -TimeoutSec 2
                } catch [Net.Http.HttpRequestException], [System.OperationCanceledException] {
                    continue
                }
                if ($response.StatusCode -eq 401) { return $pair }
                throw 'The live engine did not enforce its local session token.'
            }
        }
        Start-Sleep -Milliseconds 250
    }
    throw 'The two-process frozen engine did not become ready.'
}

function Invoke-ShutdownCase([bool]$Abrupt) {
    if (@(Get-FixtureEngineRows).Count -ne 0) { throw 'The preceding fixture retained an engine process.' }
    $kind = if ($Abrupt) { 'desktop-only-termination' } else { 'normal-window-close' }
    $env:WEBVIEW2_USER_DATA_FOLDER = Join-Path $layout "webview-$kind"
    $app = $null
    $owned = @()
    try {
        $app = Start-Process -FilePath $desktopExe.FullName -WorkingDirectory $layout -PassThru
        $null = $app.SafeHandle
        foreach ($row in @(Wait-Ready $app)) {
            $owned += Open-FixtureProcess $row
        }
        if ($owned.Count -ne 2) { throw 'Expected a verified one-file launcher and engine worker.' }
        # Let the production frontend register its native close handler after the health check.
        Start-Sleep -Seconds 2
        $timer = [Diagnostics.Stopwatch]::StartNew()
        if ($Abrupt) {
            $app.Kill()
        } else {
            $app.Refresh()
            if (-not $app.CloseMainWindow()) { throw 'Windows could not request a normal desktop close.' }
        }
        if (-not $app.WaitForExit(15000)) { throw "Desktop did not exit for $kind." }
        if (-not $Abrupt -and $app.ExitCode -ne 0) { throw 'Normal desktop close returned an unexpected exit code.' }
        foreach ($process in $owned) {
            if (-not $process.WaitForExit(15000)) { throw "Engine remained after $kind." }
            if ($Abrupt -and $process.ExitCode -ne 0) { throw 'The orphaned engine did not shut down cleanly.' }
        }
        if (@(Get-FixtureEngineRows).Count -ne 0) { throw "An extra engine process remained after $kind." }
        [pscustomobject]@{
            case = $kind; frozen_engine_processes = $owned.Count; engine_exit_codes = @($owned | ForEach-Object ExitCode)
            desktop_exit_code = $app.ExitCode; shutdown_ms = $timer.ElapsedMilliseconds
        } | ConvertTo-Json -Compress
    } finally {
        Remove-Item Env:WEBVIEW2_USER_DATA_FOLDER -ErrorAction SilentlyContinue
        if ($null -ne $app) {
            if (-not $app.HasExited) { $app.Kill(); $null = $app.WaitForExit(5000) }
            $app.Dispose()
        }
        foreach ($process in ($owned | Sort-Object Id -Descending)) {
            if (-not $process.HasExited) { $process.Kill(); $null = $process.WaitForExit(5000) }
            $process.Dispose()
        }
        # A failed readiness check may run before handles are retained. Only
        # clean up executables from the unique, hash-checked build directory.
        foreach ($row in @(Get-FixtureEngineRows)) {
            try { $leftover = Open-FixtureProcess $row } catch [ArgumentException] { continue }
            try { if (-not $leftover.HasExited) { $leftover.Kill(); $null = $leftover.WaitForExit(5000) } }
            finally { $leftover.Dispose() }
        }
    }
}

Invoke-ShutdownCase $false
Invoke-ShutdownCase $true
Write-Host 'PASS: frozen analytics engine stopped after normal desktop exit and desktop-only termination.'
