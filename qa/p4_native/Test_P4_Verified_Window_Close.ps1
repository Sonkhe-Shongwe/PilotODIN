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
$hostExe = Join-Path $PSHOME 'pwsh.exe'
foreach ($expectedCode in @(0, 17)) {
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
