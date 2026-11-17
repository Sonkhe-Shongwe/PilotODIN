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
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
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
    $fieldMatch = [Windows.Automation.AndCondition]::new(
        $property::new($element::AutomationIdProperty, '1001'),
        $property::new($element::ControlTypeProperty, [Windows.Automation.ControlType]::Edit)
    )
    $filename = $dialog.FindFirst($descendants, $fieldMatch)
    if ($null -eq $filename) { throw 'The filename control is unavailable.' }
    $value = $filename.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern)
    $value.SetValue($Destination)
    if ($value.Current.Value -ine $Destination) { throw 'The native dialog did not accept the exact disposable filename.' }
}
$buttonName = if ($Cancel) { 'Cancel' } else { 'Save' }
$buttonMatch = [Windows.Automation.AndCondition]::new(
    $property::new($element::ControlTypeProperty, [Windows.Automation.ControlType]::Button),
    $property::new($element::NameProperty, $buttonName)
)
$button = $dialog.FindFirst($descendants, $buttonMatch)
if ($null -eq $button) { throw 'The required Save As action is unavailable.' }
$actionAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
[pscustomobject]@{observed_at = $observedAt; action_at = $actionAt} | ConvertTo-Json -Compress
