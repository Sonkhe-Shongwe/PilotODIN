# PilotODIN P4 READ-ONLY Windows observation; no application launches.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OriginalDataRoot,
    [Parameter(Mandatory=$true)][string]$QaDataRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This diagnostic is Windows-only.' }
Import-Module (Join-Path $PSScriptRoot 'P4_WebView_Process_Evidence.psm1') -Force
# Only current WebView2 metadata. Command lines are kept in memory,
# never printed or saved. Access-denied failure is not a negative finding.
$processes = @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'msedgewebview2.exe'" -ErrorAction Stop)
$result = Resolve-P4WebViewProcessOwnership -Processes $processes -OriginalDataRoot $OriginalDataRoot -QaDataRoot $QaDataRoot
# No owner path, process command line, PID or file name appears in output.
$result
