param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Stay', 'Switch project')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
    $env:RUNNER_OS -cne 'Windows' -or $env:VITE_PILOTODIN_NATIVE_SMOKE -cne '1') {
    throw 'Native project-switch QA requires the disposable hosted Windows runner'
}

[int]$appPid = 0
if (-not [int]::TryParse($env:P4_NATIVE_QA_APP_PID, [ref]$appPid) -or $appPid -le 0) {
    throw 'The isolated app PID was not provided by the Windows runner'
}
$expected = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../frontend/src-tauri/target/debug/pilotodin-desktop.exe')).Path
$app = Get-Process -Id $appPid
if (-not [string]::Equals($app.Path, $expected, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The dialog owner does not match the isolated QA executable'
}

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$process = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $appPid)
$title = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::NameProperty, 'PilotODIN - Unsaved changes')
$windowCondition = [System.Windows.Automation.AndCondition]::new(
    [System.Windows.Automation.Condition[]]@($process, $title))
$buttonType = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
$stayName = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::NameProperty, 'Stay')
$switchName = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::NameProperty, 'Switch project')
$stay = [System.Windows.Automation.AndCondition]::new(
    [System.Windows.Automation.Condition[]]@($buttonType, $stayName))
$switch = [System.Windows.Automation.AndCondition]::new(
    [System.Windows.Automation.Condition[]]@($buttonType, $switchName))
$deadline = [System.Diagnostics.Stopwatch]::StartNew()

while ($deadline.Elapsed.TotalSeconds -lt 12) {
    $dialogs = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $windowCondition)
    if ($dialogs.Count -gt 1) { throw 'More than one matching native project-switch dialog was found' }
    if ($dialogs.Count -eq 1) {
        $stayButtons = $dialogs[0].FindAll([System.Windows.Automation.TreeScope]::Descendants, $stay)
        $switchButtons = $dialogs[0].FindAll([System.Windows.Automation.TreeScope]::Descendants, $switch)
        if ($stayButtons.Count -gt 1 -or $switchButtons.Count -gt 1) {
            throw 'The native project-switch buttons are ambiguous'
        }
        if ($stayButtons.Count -eq 1 -and $switchButtons.Count -eq 1) {
            $button = $stayButtons[0]
            if ($Action -ceq 'Switch project') { $button = $switchButtons[0] }
            $invoke = $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $invoke.Invoke()
            Write-Output "Native project-switch dialog action invoked: $Action"
            exit 0
        }
    }
    Start-Sleep -Milliseconds 200
}
throw 'The isolated native project-switch dialog and both expected buttons were not available to Windows UI Automation'
