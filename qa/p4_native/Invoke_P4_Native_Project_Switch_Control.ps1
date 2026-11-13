function Invoke-P4NativeProjectSwitchControl {
    param(
        [Parameter(Mandatory = $true)][int]$AppProcessId,
        [Parameter(Mandatory = $true)][ValidateSet('Stay', 'Switch project')][string]$Action,
        [ValidateRange(1, 12)][int]$TimeoutSeconds = 12
    )

    Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $process = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $AppProcessId)
    $buttonType = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
    $desktopScope = [System.Windows.Automation.TreeScope]::Children
    $dialogScope = [System.Windows.Automation.TreeScope]::Descendants
    $stage = 'APP_WINDOW_NOT_VISIBLE'
    $buttonCount = 0
    $deadline = [System.Diagnostics.Stopwatch]::StartNew()

    while ($deadline.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $appWindows = $root.FindAll($desktopScope, $process)
        $dialogs = @()
        foreach ($window in $appWindows) {
            if ($window.Current.Name -ceq 'PilotODIN - Unsaved changes') { $dialogs += $window }
        }
        if ($dialogs.Count -gt 1) { throw 'DIALOG_AMBIGUOUS: multiple matching project-switch dialogs' }
        if ($dialogs.Count -eq 1) {
            $stage = 'DIALOG_FOUND_BUTTONS_MISSING'
            $buttons = $dialogs[0].FindAll($dialogScope, $buttonType)
            $buttonCount = $buttons.Count
            $stayButtons = @()
            $switchButtons = @()
            foreach ($button in $buttons) {
                if ($button.Current.Name -ceq 'Stay') { $stayButtons += $button }
                if ($button.Current.Name -ceq 'Switch project') { $switchButtons += $button }
            }
            if ($stayButtons.Count -gt 1 -or $switchButtons.Count -gt 1) {
                throw 'BUTTONS_AMBIGUOUS: multiple matching project-switch buttons'
            }
            if ($stayButtons.Count -eq 1 -and $switchButtons.Count -eq 1) {
                $button = $stayButtons[0]
                if ($Action -ceq 'Switch project') { $button = $switchButtons[0] }
                $invoke = $null
                if (-not $button.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$invoke)) {
                    throw 'BUTTON_INVOKE_UNAVAILABLE: the requested project-switch button does not expose InvokePattern'
                }
                $invoke.Invoke()
                return
            }
        } elseif ($appWindows.Count -gt 0 -and $stage -eq 'APP_WINDOW_NOT_VISIBLE') {
            $stage = 'APP_VISIBLE_DIALOG_MISSING'
        }
        Start-Sleep -Milliseconds 200
    }
    throw "Native project-switch discovery timed out. Stage=$stage; last matching dialog button count=$buttonCount"
}
