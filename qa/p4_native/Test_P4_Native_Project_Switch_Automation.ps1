param([ValidateSet('none', 'both', 'missing')][string]$Fixture = 'none')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:RUNNER_OS -cne 'Windows') {
    throw 'The synthetic desktop visibility test requires a GitHub-hosted Windows runner'
}

if ($Fixture -ne 'none') {
    Add-Type -AssemblyName System.Windows.Forms
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'PilotODIN - Unsaved changes'
    $form.Width = 390
    $form.Height = 135
    $stay = New-Object System.Windows.Forms.Button
    $stay.Text = 'Stay'
    $stay.Left = 12
    $stay.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $form.Controls.Add($stay)
    if ($Fixture -eq 'both') {
        $switch = New-Object System.Windows.Forms.Button
        $switch.Text = 'Switch project'
        $switch.Left = 105
        $switch.Width = 120
        $switch.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Controls.Add($switch)
    }
    try {
        $result = $form.ShowDialog()
    } finally {
        $form.Dispose()
    }
    if ($result -eq [System.Windows.Forms.DialogResult]::Cancel) { exit 20 }
    if ($result -eq [System.Windows.Forms.DialogResult]::OK) { exit 21 }
    exit 1
}

. (Join-Path $PSScriptRoot 'Invoke_P4_Native_Project_Switch_Control.ps1')
$hostExe = Join-Path $PSHOME 'powershell.exe'
foreach ($action in @('Stay', 'Switch project')) {
    $fixtureProcess = Start-Process -FilePath $hostExe -ArgumentList "-NoProfile -NonInteractive -STA -File `"$PSCommandPath`" -Fixture both" -PassThru
    try {
        Invoke-P4NativeProjectSwitchControl -AppProcessId $fixtureProcess.Id -Action $action
        if (-not $fixtureProcess.WaitForExit(5000)) { throw 'Synthetic dialog did not close after invocation' }
        $expectedExit = if ($action -ceq 'Stay') { 20 } else { 21 }
        if ($fixtureProcess.ExitCode -ne $expectedExit) { throw "Synthetic dialog returned the wrong result for $action" }
        Write-Output "Synthetic Windows dialog: $action verified across processes"
    } finally {
        if (-not $fixtureProcess.HasExited) { Stop-Process -Id $fixtureProcess.Id -Force }
        $fixtureProcess.Dispose()
    }
}

$fixtureProcess = Start-Process -FilePath $hostExe -ArgumentList "-NoProfile -NonInteractive -STA -File `"$PSCommandPath`" -Fixture missing" -PassThru
try {
    try {
        Invoke-P4NativeProjectSwitchControl -AppProcessId $fixtureProcess.Id -Action 'Stay' -TimeoutSeconds 5
        throw 'Synthetic dialog with a missing button was unexpectedly accepted'
    } catch {
        if ($_.Exception.Message -notmatch 'Stage=DIALOG_FOUND_BUTTONS_MISSING; last matching dialog button count=1') { throw }
    }
    if ($fixtureProcess.HasExited) { throw 'The driver closed a synthetic dialog with a missing button' }
    Write-Output 'Synthetic Windows dialog: missing button reported without invoking Stay'
} finally {
    if (-not $fixtureProcess.HasExited) { Stop-Process -Id $fixtureProcess.Id -Force }
    $fixtureProcess.Dispose()
}
