# Synthetic Windows-only test. No actual WebView or owner process is inspected.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:RUNNER_OS -ne 'Windows') { throw 'Requires disposable Windows GitHub runner.' }
Import-Module (Join-Path $PSScriptRoot 'P4_WebView_Process_Evidence.psm1') -Force
$root = 'C:\P4synthetic\Local'
$old = Join-Path $root 'com.pilotodin.studio'
$qa = Join-Path $root 'com.pilotodin.p4nativeqa'
$oldProfile = Join-Path $old 'EBWebView'
$qaProfile = Join-Path $qa 'EBWebView'
$otherProfile = Join-Path $root 'com.pilotodin.studio-other\EBWebView'
function Process([string]$name,[string]$command) {
    return [pscustomobject]@{ Name=$name; CommandLine=$command }
}
function Check([bool]$okay,[string]$message) {
    if (-not $okay) { throw $message }
}
$records = @(
    (Process 'msedgewebview2.exe' ('"C:\Program Files\WebView2\msedgewebview2.exe" --user-data-dir="' + $oldProfile + '" --type=renderer')),
    (Process 'msedgewebview2.exe' ('"C:\Program Files\WebView2\msedgewebview2.exe" --user-data-dir="' + $qaProfile + '"')),
    (Process 'msedgewebview2.exe' ('msedgewebview2.exe --user-data-dir=' + $otherProfile)),
    (Process 'msedgewebview2.exe' 'msedgewebview2.exe --type=renderer'),
    (Process 'msedgewebview2.exe' 'msedgewebview2.exe --user-data-dir=relative-profile'),
    (Process 'msedgewebview2.exe' ('msedgewebview2.exe --user-data-dir="' + $oldProfile + '" --user-data-dir="' + $qaProfile + '"')),
    # The text below is inside --log-file, never a separate --user-data-dir flag.
    (Process 'msedgewebview2.exe' ('msedgewebview2.exe --log-file="note --user-data-dir=' + $oldProfile + ' trailing"')),
    (Process 'msedgewebview2.exe' ('msedgewebview2.exe --user-data-dir="' + $qaProfile + '"garbage')),
    (Process 'msedgewebview2.exe' ('msedgewebview2.exe --user-data-dir=' + $oldProfile + '"garbage')),
    # A valid flag remains discoverable after an unrelated quoted argument.
    (Process 'msedgewebview2.exe' ('msedgewebview2.exe --log-file="safe message" --user-data-dir="' + $oldProfile + '"')),
    (Process 'chrome.exe' ('chrome.exe --user-data-dir="' + $oldProfile + '"'))
)
$observed = Resolve-P4WebViewProcessOwnership -Processes $records -OriginalDataRoot $old -QaDataRoot $qa
Check ($observed.webview2_processes_observed -eq 10) 'WebView2 process count wrong'
Check ($observed.original_profile_processes -eq 2) 'Original flag recognition wrong'
Check ($observed.qa_profile_processes -eq 1) 'QA flag recognition wrong'
Check ($observed.other_profile_processes -eq 1) 'Sibling prefix misclassified'
Check ($observed.unresolved_profile_processes -eq 6) 'Ambiguous/missing/relative flag guessed'
Check ($observed.status -eq 'CURRENT_LAUNCH_FLAGS_ONLY_NOT_HISTORICAL_WRITE_PROOF') 'Misleading result status'
Check (-not $observed.historical_writer_process_identified -and
       -not $observed.qa_cross_app_write_excluded -and
       -not $observed.original_full_data_preservation_passed -and
       -not $observed.original_project_data_certified -and
       -not $observed.offline_8gb_certified) 'Synthetic observer falsely certified safety'
$empty = Resolve-P4WebViewProcessOwnership -Processes @() -OriginalDataRoot $old -QaDataRoot $qa
Check ($empty.webview2_processes_observed -eq 0 -and
       $empty.status -eq $observed.status -and
       -not $empty.qa_cross_app_write_excluded) 'Empty process result falsely accepted history'
$badRoots = $false
try {
    $null=Resolve-P4WebViewProcessOwnership -Processes @() -OriginalDataRoot $old -QaDataRoot (Join-Path $old 'nested')
} catch { $badRoots = $true }
Check $badRoots 'Overlapping roots were accepted'
$src = Join-Path $PSScriptRoot '..\..\frontend\src-tauri'
$cfgOld = Get-Content -LiteralPath (Join-Path $src 'tauri.conf.json') -Raw | ConvertFrom-Json
$cfgQa = Get-Content -LiteralPath (Join-Path $src 'tauri.p4-native-qa.conf.json') -Raw | ConvertFrom-Json
Check ($cfgOld.identifier -eq 'com.pilotodin.studio') 'Production identity changed'
Check ($cfgQa.identifier -eq 'com.pilotodin.p4nativeqa') 'QA identity changed'
$observerSource=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'Observe_P4_WebView_Profile_Processes.ps1') -Raw
Check ($observerSource.Contains('Get-CimInstance')) 'Observer missing live metadata read'
foreach ($forbidden in @('Start-Process','Stop-Process','Remove-Item','Set-Content','Copy-Item','New-Item','New-Object')) {
    Check (-not $observerSource.Contains($forbidden)) 'Observer source contains mutable operation'
}
Write-Host 'PASS: synthetic WebView2 flag classification, conflicting/empty/relative guard, prefix safety, both Tauri IDs and no observer writes.'
Write-Host 'NOT TESTED: owner Windows live processes, historical file writer, actual profile isolation or offline 8GB.'
