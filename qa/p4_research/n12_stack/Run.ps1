# One generated-file capture using the existing strict N12 fixture and reducers.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or
    $env:RUNNER_OS -ne 'Windows') {
    throw 'The stack comparison requires disposable GitHub-hosted Windows.'
}
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PSNativeCommandUseErrorActionPreference = 'false'
$PSNativeCommandUseErrorActionPreference = $false
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$work = Join-Path $env:RUNNER_TEMP "pilotodin-n12-stack-$([guid]::NewGuid().ToString('N'))"
$null = New-Item -ItemType Directory $work
$native = Join-Path $work 'native'
Copy-Item -Recurse -LiteralPath (Join-Path $repo 'qa/p4_native') -Destination $native
$env:PILOTODIN_N12_STACK_META = Join-Path $work 'stack-fixture.json'
$env:PILOTODIN_N12_STACK_CAPTURE = Join-Path $PSScriptRoot 'capture.py'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vsInstall = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $vsInstall) { throw 'The x64 trace decoder compiler is unavailable.' }
$vcvars = Join-Path $vsInstall 'VC/Auxiliary/Build/vcvars64.bat'
$decoder = Join-Path $work 'decode.exe'
$compile = 'call "{0}" >nul && cl.exe /nologo /std:c++17 /EHsc /W4 "{1}" /Fe:"{2}" /link advapi32.lib' -f $vcvars, (Join-Path $PSScriptRoot 'decode.cpp'), $decoder
Push-Location $work
try {
    & $env:ComSpec /d /s /c $compile
    if ($LASTEXITCODE -ne 0) { throw 'The stack decoder did not compile.' }
} finally {
    Pop-Location
}

# Use the original strict workload and reducer. Include comparison read
# and flush records in the temporary exporter alongside the original events.
$fixture = Join-Path $native 'Test_P4_N12_ETW_Fixture.ps1'
$original = Get-Content -LiteralPath $fixture -Raw
$probeEntry = 'python (Join-Path $PSScriptRoot ''n12_etw_probe.py'') @probeArgs'
$timingFilter = '($SystemTiming -and $eventId -in 15,21)'
if ([regex]::Matches($original, [regex]::Escape($probeEntry)).Count -ne 1 -or
    [regex]::Matches($original, [regex]::Escape($timingFilter)).Count -ne 1) {
    throw 'The strict fixture probe entry point or comparison event filter changed.'
}
$exportScript = $original.Replace($probeEntry, 'python $env:PILOTODIN_N12_STACK_CAPTURE @probeArgs')
$exportScript.Replace($timingFilter, '($eventId -in 15,21)') |
    Set-Content -LiteralPath $fixture -Encoding utf8
$fixtureFailure = $false
try {
    & $fixture -PreopenedControl -Rundown
} catch {
    $fixtureFailure = $true
    Write-Host 'The strict fixture failed. Checking whether the stack evidence can still be decoded.'
}
if (-not (Test-Path -LiteralPath $env:PILOTODIN_N12_STACK_META -PathType Leaf)) {
    throw 'The capture did not produce stack fixture metadata.'
}

$metadata = Get-Content -LiteralPath $env:PILOTODIN_N12_STACK_META -Raw | ConvertFrom-Json
$root = $metadata.root
$rawTrace = Join-Path $root 'rundown.etl'
$stackRows = Join-Path $root 'stack-rows.tsv'
$decoderResult = & $decoder $rawTrace $stackRows
if ($LASTEXITCODE -ne 0) { throw 'The stack decoder could not consume the WPR trace.' }
Write-Host "N12 stack decoder: $decoderResult"
python (Join-Path $PSScriptRoot 'analyze.py') $env:PILOTODIN_N12_STACK_META $decoderResult
if ($LASTEXITCODE -ne 0) { throw 'The stack correlation report failed.' }

if ($fixtureFailure) { throw 'The strict fixture did not pass its original control assertions.' }
