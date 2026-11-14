Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'P4_N12_Collector_Process.ps1')

function Assert-RejectedCapture($Path, $ExpectedError) {
    try {
        Confirm-P4N12ClosedCapture -Path $Path -Description 'Synthetic backing file'
    } catch {
        if ($_.Exception.Message -eq "Synthetic backing file $ExpectedError") { return }
        throw
    }
    throw 'An invalid synthetic backing file was accepted.'
}

foreach ($code in 0, 17) {
    $child = Start-Process -FilePath $env:ComSpec -ArgumentList "/d /c exit $code" -PassThru
    try {
        $result = Wait-P4N12CollectorExit -Process $child -TimeoutMs 10000
        $expectedStatus = if ($code -eq 0) { 'EXITED' } else { 'NONZERO_EXIT' }
        if ($result.Status -ne $expectedStatus -or $result.ExitCode -ne $code) {
            throw "Unexpected status for synthetic process exit $code."
        }
    } finally {
        $child.Dispose()
    }
}

$child = Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList '-NoProfile -NonInteractive -Command Start-Sleep -Seconds 15' -PassThru
try {
    $result = Wait-P4N12CollectorExit -Process $child -TimeoutMs 100
    if ($result.Status -ne 'TIMEOUT' -or $null -ne $result.ExitCode) {
        throw 'A running synthetic process must report a timeout without an exit code.'
    }
} finally {
    if (-not $child.HasExited) { $child.Kill() }
    $child.Dispose()
}

$fixture = Join-Path $env:RUNNER_TEMP "p4-n12-stop-test-$([guid]::NewGuid()).pml"
try {
    Assert-RejectedCapture $fixture 'is missing or still open.'
    [IO.File]::WriteAllBytes($fixture, [byte[]]@())
    Assert-RejectedCapture $fixture 'is empty.'
    [IO.File]::WriteAllBytes($fixture, [byte[]]@(42))
    $lock = [IO.File]::Open($fixture, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
    try {
        Assert-RejectedCapture $fixture 'is missing or still open.'
    } finally {
        $lock.Dispose()
    }
    Confirm-P4N12ClosedCapture -Path $fixture -Description 'Synthetic backing file'
} finally {
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture }
}
Write-Host 'N12 synthetic stop and backing-file checks passed.'
