function Close-P4VerifiedWindow {
    param(
        [Parameter(Mandatory = $true)][int]$AppProcessId,
        [Parameter(Mandatory = $true)][string]$ExpectedPath,
        [Parameter(Mandatory = $true)][string]$ExpectedTitle
    )

    $app = [System.Diagnostics.Process]::GetProcessById($AppProcessId)
    try {
        # Hold the native handle before posting WM_CLOSE. A PID by itself
        # cannot retrieve the exit status after a short-lived process exits.
        if ($app.Handle -eq [IntPtr]::Zero) { throw 'Could not retain the QA process handle' }
        if (-not [string]::Equals($app.MainModule.FileName, $ExpectedPath, [StringComparison]::OrdinalIgnoreCase) -or
            $app.MainWindowTitle -cne $ExpectedTitle) {
            throw 'The close request did not match the expected QA executable and window'
        }
        if (-not $app.CloseMainWindow()) { throw 'Windows did not accept the QA close request' }
        if (-not $app.WaitForExit(15000)) { throw 'The QA process did not exit after the Windows close request' }
        $code = $app.ExitCode
        if ($code -ne 0) { throw "The verified QA process exited with code $code after the close request" }
    } finally {
        $app.Dispose()
    }
}
