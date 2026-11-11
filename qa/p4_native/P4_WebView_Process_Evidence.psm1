# Pure, synthetic-testable classification of CURRENT WebView2 launch flags.
# No filesystem or process enumeration takes place in this module.
Set-StrictMode -Version Latest

# A flag embedded in another quoted argument is not an argument boundary.
# Windows command-line double quotes preceded by an odd number of backslashes
# are escaped; reject ambiguous cases instead of attributing profile ownership.
function Test-P4FlagOutsideQuotes {
    param([string]$CommandLine, [int]$Position)
    $quoted = $false
    for ($i = 0; $i -lt $Position; $i++) {
        if ($CommandLine[$i] -ne '"') { continue }
        $slashes = 0
        for ($j = $i - 1; $j -ge 0 -and $CommandLine[$j] -eq [char]'\'; $j--) {
            $slashes++
        }
        if (($slashes % 2) -eq 0) { $quoted = -not $quoted }
    }
    return (-not $quoted)
}

function Resolve-P4WebViewProcessOwnership {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][AllowEmptyCollection()][object[]]$Processes,
        [Parameter(Mandatory=$true)][string]$OriginalDataRoot,
        [Parameter(Mandatory=$true)][string]$QaDataRoot
    )
    if ([string]::IsNullOrWhiteSpace($OriginalDataRoot) -or
        [string]::IsNullOrWhiteSpace($QaDataRoot)) {
        throw 'Missing expected application roots; observation refused.'
    }
    $original = [IO.Path]::GetFullPath($OriginalDataRoot).TrimEnd([char]'\',[char]'/')
    $qa = [IO.Path]::GetFullPath($QaDataRoot).TrimEnd([char]'\',[char]'/')
    $comparison = [StringComparison]::OrdinalIgnoreCase
    if ($original.Equals($qa, $comparison) -or
        $original.StartsWith(($qa + '\'), $comparison) -or
        $qa.StartsWith(($original + '\'), $comparison)) {
        throw 'Expected original and QA profile roots overlap; observation refused.'
    }
    $originalCount = 0
    $qaCount = 0
    $outsideCount = 0
    $unresolvedCount = 0
    $observed = 0
    foreach ($process in $Processes) {
        if ([string]$process.Name -ine 'msedgewebview2.exe') { continue }
        $observed++
        # Exactly one explicit quoted or unspaced --user-data-dir.
        # Never guess from PID, parent PID, window title or Tauri ID.
        $cmd = [string]$process.CommandLine
        # Require a complete flag token, not a prefix of a malformed token.
        # Its leading space also must be outside other quoted arguments.
        $flags = [regex]::Matches($cmd, '(?i)(?:^|\s)--user-data-dir=(?:"([^"]+)"|([^\s"]+))(?=\s|$)')
        if ($flags.Count -ne 1 -or
            -not (Test-P4FlagOutsideQuotes -CommandLine $cmd -Position $flags[0].Index)) {
            $unresolvedCount++
            continue
        }
        $value = if ($flags[0].Groups[1].Success) {
            $flags[0].Groups[1].Value
        } else {
            $flags[0].Groups[2].Value
        }
        if ([string]::IsNullOrWhiteSpace($value) -or
            -not [IO.Path]::IsPathFullyQualified($value)) {
            $unresolvedCount++
            continue
        }
        try {
            $dir = [IO.Path]::GetFullPath($value).TrimEnd([char]'\',[char]'/')
        } catch {
            $unresolvedCount++
            continue
        }
        if ($dir.Equals($original,$comparison) -or
            $dir.StartsWith(($original + '\'),$comparison)) {
            $originalCount++
        } elseif ($dir.Equals($qa,$comparison) -or
                  $dir.StartsWith(($qa + '\'),$comparison)) {
            $qaCount++
        } else {
            $outsideCount++
        }
    }
    [pscustomobject][ordered]@{
        status = 'CURRENT_LAUNCH_FLAGS_ONLY_NOT_HISTORICAL_WRITE_PROOF'
        webview2_processes_observed = $observed
        original_profile_processes = $originalCount
        qa_profile_processes = $qaCount
        other_profile_processes = $outsideCount
        unresolved_profile_processes = $unresolvedCount
        observed_user_data_directories = $originalCount + $qaCount + $outsideCount
        snapshot_is_atomic = $false
        historical_writer_process_identified = $false
        qa_cross_app_write_excluded = $false
        original_full_data_preservation_passed = $false
        original_project_data_certified = $false
        offline_8gb_certified = $false
        note = 'Live WebView2 user-data-dir flags are not file-write attribution. Zero processes does not prove historical isolation. No data or process state modified.'
    }
}
Export-ModuleMember -Function Resolve-P4WebViewProcessOwnership
