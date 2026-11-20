param([int]$FixtureExitCode = -1)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:RUNNER_OS -cne 'Windows') {
    throw 'The synthetic close check requires a GitHub-hosted Windows runner'
}
$title = 'PilotODIN synthetic close fixture'
if ($FixtureExitCode -ge 0) {
    Add-Type -AssemblyName System.Windows.Forms
    $form = New-Object System.Windows.Forms.Form
    $form.Text = $title
    try {
        [void]$form.ShowDialog()
    } finally {
        $form.Dispose()
    }
    exit $FixtureExitCode
}

. (Join-Path $PSScriptRoot 'Close_P4_Verified_Window.ps1')
. (Join-Path $PSScriptRoot 'P4_N12_Collector_Process.ps1')
$hostExe = Join-Path $PSHOME 'pwsh.exe'
foreach ($case in @(
    @{ CloseMode = 'app'; ExitCode = 0 }
    @{ CloseMode = 'app'; ExitCode = 17 }
    @{ CloseMode = 'collector'; ExitCode = 0 }
    @{ CloseMode = 'collector'; ExitCode = 1 }
)) {
    $expectedCode = $case.ExitCode
    $child = Start-Process -FilePath $hostExe -ArgumentList "-NoProfile -NonInteractive -STA -File `"$PSCommandPath`" -FixtureExitCode $expectedCode" -PassThru
    try {
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            $child.Refresh()
            if ($child.HasExited) { throw 'Synthetic close fixture exited before the test' }
            if ($child.MainWindowTitle -ceq $title) { $ready = $true; break }
            Start-Sleep -Milliseconds 200
        }
        if (-not $ready) { throw 'Synthetic close fixture window did not open' }
        if ($case.CloseMode -eq 'collector') {
            Request-P4N12CollectorWindowClose -Process $child
            $result = Wait-P4N12CollectorExit -Process $child -TimeoutMs 15000
            $expectedStatus = if ($expectedCode -eq 0) { 'EXITED' } else { 'NONZERO_EXIT' }
            if ($result.Status -ne $expectedStatus -or $result.ExitCode -ne $expectedCode) {
                throw "Unexpected collector window-close result for synthetic exit $expectedCode."
            }
            Write-Output "Synthetic collector window close: observed exit code $expectedCode"
            continue
        }
        try {
            Close-P4VerifiedWindow -AppProcessId $child.Id -ExpectedPath $hostExe -ExpectedTitle $title
            if ($expectedCode -ne 0) { throw 'A nonzero Windows process exit was incorrectly accepted' }
        } catch {
            if ($expectedCode -eq 0 -or $_.Exception.Message -cne "The verified QA process exited with code $expectedCode after the close request") { throw }
        }
        Write-Output "Synthetic Windows close: observed exit code $expectedCode"
    } finally {
        if (-not $child.HasExited) { Stop-Process -Id $child.Id -Force }
        $child.Dispose()
    }
}
