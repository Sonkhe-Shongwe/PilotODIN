function Wait-P4N12CollectorExit {
    param(
        [Parameter(Mandatory)][System.Diagnostics.Process]$Process,
        [Parameter(Mandatory)][ValidateRange(1,60000)][int]$TimeoutMs
    )

    if (-not $Process.WaitForExit($TimeoutMs)) {
        return [pscustomobject]@{ Status = 'TIMEOUT'; ExitCode = $null }
    }
    $code = $Process.ExitCode
    $status = if ($code -eq 0) { 'EXITED' } else { 'NONZERO_EXIT' }
    return [pscustomobject]@{ Status = $status; ExitCode = $code }
}

function Confirm-P4N12ClosedCapture {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Description
    )

    try {
        $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
    } catch [IO.IOException] {
        throw "$Description is missing or still open."
    } catch [UnauthorizedAccessException] {
        throw "$Description cannot be opened for verification."
    }
    try {
        if ($stream.Length -eq 0) { throw "$Description is empty." }
        Write-Host "$Description closed and readable ($($stream.Length) bytes)."
    } finally {
        $stream.Dispose()
    }
}
