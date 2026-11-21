param([Parameter(Mandatory = $true)][int]$AppId)

$ErrorActionPreference = 'Stop'
if ($env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:GITHUB_RUN_ATTEMPT -cne '1' -or
    $env:OS -cne 'Windows_NT') {
    throw 'Expected a first-attempt hosted Windows Save As fixture.'
}
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class PilotOdinSaveQaWindow {
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool PostMessageW(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
}
'@
$element = [Windows.Automation.AutomationElement]
$property = [Windows.Automation.PropertyCondition]
$dialogMatch = [Windows.Automation.AndCondition]::new(
    $property::new($element::ProcessIdProperty, $AppId),
    $property::new($element::NameProperty, 'Save PilotODIN report')
)
$clock = [Diagnostics.Stopwatch]::StartNew()
do {
    $dialog = $element::RootElement.FindFirst([Windows.Automation.TreeScope]::Children, $dialogMatch)
    if ($null -ne $dialog) { break }
    Start-Sleep -Milliseconds 75
} while ($clock.Elapsed.TotalSeconds -lt 15)
if ($null -eq $dialog) { throw 'The verified application did not open its Save As dialog.' }
$observedAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$window = [IntPtr]$dialog.Current.NativeWindowHandle
[uint32]$owner = 0
if ($window -eq [IntPtr]::Zero -or
    [PilotOdinSaveQaWindow]::GetWindowThreadProcessId($window, [ref]$owner) -eq 0 -or $owner -ne $AppId) {
    throw 'The Save As window no longer belongs to the verified app.'
}
# Close only this modal with WM_CLOSE. The fixture checks the command's cancellation result.
$actionAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
if (-not [PilotOdinSaveQaWindow]::PostMessageW($window, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)) {
    throw 'The operating system declined to close the verified Save As window.'
}
[pscustomobject]@{observed_at = $observedAt; action_at = $actionAt} | ConvertTo-Json -Compress
