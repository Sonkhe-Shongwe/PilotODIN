# Shared by the disposable fixture and the approved app journey.
function Export-N12FileIoRundown($root) {
    # Use the native ProcessTrace consumer and TDH decoder. Decoded paths
    # are written only to the disposable runner-temp JSONL file.
    $rundownPath = Join-Path $root 'rundown.jsonl'
    $decoderSource = Join-Path $PSScriptRoot 'n12_fileio_rundown.cpp'
    $decoderExe = Join-Path $root 'n12_fileio_rundown.exe'
    $programFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if (-not $programFilesX86) { throw 'The Visual C++ build tools location is unavailable.' }
    $vswhere = Join-Path $programFilesX86 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) {
        throw 'The Visual Studio installation locator is unavailable.'
    }
    $vsInstall = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $vsInstall) {
        throw 'The native ETW decoder requires the Visual C++ x64 build tools.'
    }
    $vcvars = Join-Path $vsInstall 'VC\Auxiliary\Build\vcvars64.bat'
    if (-not (Test-Path -LiteralPath $vcvars -PathType Leaf)) {
        throw 'The Visual C++ x64 environment script is unavailable.'
    }
    $compileCommand = 'call "{0}" >nul && cl.exe /nologo /std:c++17 /EHsc /W4 /DUNICODE /D_UNICODE "{1}" /Fe:"{2}" /link tdh.lib advapi32.lib' -f $vcvars, $decoderSource, $decoderExe
    Push-Location $root
    try {
        & $env:ComSpec /d /s /c $compileCommand | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'The native ProcessTrace decoder did not compile.' }
    } finally {
        Pop-Location
    }
    if (-not (Test-Path -LiteralPath $decoderExe -PathType Leaf)) {
        throw 'The native ProcessTrace decoder executable was not produced.'
    }
    $decoderOutput = @(& $decoderExe (Join-Path $root 'rundown.etl') $rundownPath)
    $decoderExit = $LASTEXITCODE
    if ($decoderExit -ne 0) {
        foreach ($line in $decoderOutput) { Write-Host $line }
        throw 'The native ProcessTrace decoder could not read the rundown trace.'
    }
    $decoderText = ($decoderOutput -join "`n").Trim()
    try {
        $decoderSummary = $decoderText | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw 'The native ProcessTrace decoder did not return a valid diagnostic summary.'
    }
    Write-Host ('Native ProcessTrace decoder summary: ' + ($decoderSummary | ConvertTo-Json -Compress))
    if ([long]$decoderSummary.rundown_opcode_36 -le 0) {
        throw 'The native decoder observed no classic FileIO rundown records.'
    }
    $decodedRecords = [long]$decoderSummary.tdh_records_written + [long]$decoderSummary.raw_schema_records_written
    if ($decodedRecords -le 0) {
        throw 'The native decoder observed rundown records but recovered no file names.'
    }
    if ([long]$decoderSummary.callback_errors -gt 0) {
        throw 'The native decoder reported callback output errors.'
    }
    return $rundownPath
}
