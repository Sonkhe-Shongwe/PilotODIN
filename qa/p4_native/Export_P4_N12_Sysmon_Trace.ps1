# Read-only export of a record-bounded disposable runner log.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][long]$FirstRecord,
    [Parameter(Mandatory=$true)][long]$LastRecord,
    [Parameter(Mandatory=$true)][string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'This exporter requires disposable hosted Windows.'
}
if ($FirstRecord -lt 1 -or $LastRecord -lt $FirstRecord) {
    throw 'Invalid inclusive Sysmon record boundaries.'
}
if ($OutputFile -notmatch '^[A-Za-z]:[\\/]') { throw 'Use a drive-absolute output path.' }
$path = [IO.Path]::GetFullPath($OutputFile)
$runner = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'
if (-not $path.StartsWith($runner,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Sysmon export must stay under RUNNER_TEMP.'
}
$directory = Get-Item -LiteralPath (Split-Path -Parent $path) -Force
while ($directory) {
    if ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Refusing an evidence path through a reparse point.'
    }
    $directory = $directory.Parent
}
$channel = 'Microsoft-Windows-Sysmon/Operational'
$xpath = "*[System[EventRecordID >= $FirstRecord and EventRecordID <= $LastRecord]]"
$file = [IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try {
    $writer = [IO.StreamWriter]::new($file,[Text.UTF8Encoding]::new($false))
    try {
        $writer.WriteLine('<Events>')
        Get-WinEvent -LogName $channel -FilterXPath $xpath -Oldest |
            ForEach-Object { $writer.WriteLine($_.ToXml()) }
        $writer.WriteLine('</Events>')
    } finally { $writer.Dispose() }
} finally { $file.Dispose() }
