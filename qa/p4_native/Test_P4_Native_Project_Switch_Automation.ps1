param(
    [ValidateSet('none', 'both', 'missing')][string]$Fixture = 'none',
    [ValidateSet('startup', 'compile', 'dialog')][string]$HelperStage,
    [ValidateSet('Stay', 'Switch project')][string]$Action,
    [int]$FixtureProcessId,
    [string]$ReadyPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:RUNNER_OS -cne 'Windows') {
    throw 'The synthetic desktop visibility test requires a GitHub-hosted Windows runner'
}

if ($HelperStage) {
    if ($Fixture -cne 'none' -or $PSVersionTable.PSVersion.Major -ne 5 -or $ReadyPath) {
        throw 'The helper stages require standalone Windows PowerShell 5.1.'
    }
    if ($HelperStage -cin 'compile', 'dialog') {
        . (Join-Path $PSScriptRoot 'Invoke_P4_Native_Project_Switch_Control.ps1')
    }
    if ($HelperStage -ceq 'dialog') {
        if ($FixtureProcessId -le 0 -or -not $Action) { throw 'The synthetic dialog PID and action are required.' }
        Invoke-P4NativeProjectSwitchControl -AppProcessId $FixtureProcessId -Action $Action
    }
    Write-Output "N12 dialog helper stage completed: $HelperStage"
    exit 0
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
    if ($ReadyPath) { $form.Add_Shown({ [IO.File]::WriteAllText($ReadyPath, 'ready') }) }
    try {
        $result = $form.ShowDialog()
    } finally {
        $form.Dispose()
    }
    # Keep this PowerShell process alive until the caller has sampled the helper's exit.
    if ($ReadyPath) { [void][Console]::ReadLine() }
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
        if ($_.Exception.Message -notmatch 'Stage=DIALOG_FOUND_BUTTONS_MISSING; visible app window count=\d+; native button count=1') { throw }
    }
    if ($fixtureProcess.HasExited) { throw 'The driver closed a synthetic dialog with a missing button' }
    Write-Output 'Synthetic Windows dialog: missing button reported without invoking Stay'
} finally {
    if (-not $fixtureProcess.HasExited) { Stop-Process -Id $fixtureProcess.Id -Force }
    $fixtureProcess.Dispose()
}
