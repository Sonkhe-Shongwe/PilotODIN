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

. (Join-Path $PSScriptRoot 'Invoke_P4_Native_Project_Switch_Control.ps1')
Invoke-P4NativeProjectSwitchControl -AppProcessId $appPid -Action $Action
Write-Output "Native project-switch dialog action invoked: $Action"
