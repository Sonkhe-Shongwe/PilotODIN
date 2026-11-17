param(
    [Parameter(Mandatory = $true)][int]$AppId,
    [string]$Destination,
    [switch]$Cancel
)

$ErrorActionPreference = 'Stop'
if ($env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:GITHUB_RUN_ATTEMPT -cne '1' -or
    $env:OS -cne 'Windows_NT' -or ($Cancel.IsPresent -eq [bool]$Destination)) {
    throw 'Expected a first-attempt hosted Windows Save As fixture.'
}
if ($Destination) {
    $parent = Split-Path -Parent ([IO.Path]::GetFullPath($Destination))
    if ($parent -ine $env:PILOTODIN_SAVE_QA_OUTPUT -or (Test-Path -LiteralPath $Destination)) {
        throw 'Save As destination differs from the empty disposable output location.'
    }
}
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Windows.Forms
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
$descendants = [Windows.Automation.TreeScope]::Descendants
if ($Destination) {
    $editMatch = $property::new($element::ControlTypeProperty, [Windows.Automation.ControlType]::Edit)
    $suggestedName = Split-Path -Leaf $Destination
    $suggestedStem = [IO.Path]::GetFileNameWithoutExtension($suggestedName)
    $fieldClock = [Diagnostics.Stopwatch]::StartNew()
    $value = $null
    do {
        foreach ($field in $dialog.FindAll($descendants, $editMatch)) {
            $candidate = $null
            if (-not $field.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern, [ref]$candidate)) { continue }
            if ($field.Current.AutomationId -eq '1001' -or
                $field.Current.Name -match '^File name:?$' -or
                $candidate.Current.Value -in @($suggestedName,$suggestedStem)) {
                $value = $candidate
                break
            }
        }
        if ($null -ne $value) { break }
        Start-Sleep -Milliseconds 100
    } while ($fieldClock.Elapsed.TotalSeconds -lt 3)
    if ($null -eq $value) {
        # Some common-dialog versions expose the filename edit only after its
        # mnemonic receives focus. Verify focus belongs to our exact dialog.
        Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PilotOdinSaveQaFocus {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
'@
        $window = [IntPtr]$dialog.Current.NativeWindowHandle
        $null = [PilotOdinSaveQaFocus]::SetForegroundWindow($window)
        if ($window -eq [IntPtr]::Zero -or [PilotOdinSaveQaFocus]::GetForegroundWindow() -ne $window) {
            throw 'The fixture dialog did not become the foreground window.'
        }
        [Windows.Forms.SendKeys]::SendWait('%n')
        $focused = $element::FocusedElement
        $ancestor = $focused
        $walker = [Windows.Automation.TreeWalker]::RawViewWalker
        while ($null -ne $ancestor -and [IntPtr]$ancestor.Current.NativeWindowHandle -ne $window) {
            $ancestor = $walker.GetParent($ancestor)
        }
        if ($null -eq $ancestor -or $focused.Current.ProcessId -ne $AppId -or
            $focused.Current.ControlType -ne [Windows.Automation.ControlType]::Edit -or
            -not $focused.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern, [ref]$value)) {
            throw 'The verified dialog did not focus the filename edit.'
        }
    }
    $value.SetValue($Destination)
    if ($value.Current.Value -ine $Destination) { throw 'The native dialog did not accept the exact disposable filename.' }
}
$buttonName = if ($Cancel) { 'Cancel' } else { 'Save' }
$buttonId = if ($Cancel) { '2' } else { '1' }
$labelMatch = [Windows.Automation.OrCondition]::new(
    $property::new($element::AutomationIdProperty, $buttonId),
    $property::new($element::NameProperty, $buttonName)
)
$buttonMatch = [Windows.Automation.AndCondition]::new(
    $property::new($element::ControlTypeProperty, [Windows.Automation.ControlType]::Button),
    $labelMatch
)
$button = $dialog.FindFirst($descendants, $buttonMatch)
if ($null -eq $button) { throw 'The required Save As action is unavailable.' }
$actionAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
[pscustomobject]@{observed_at = $observedAt; action_at = $actionAt} | ConvertTo-Json -Compress
