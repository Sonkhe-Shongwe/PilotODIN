# Predictive P2 DevQA entrypoint: allocate fresh local QA run before native activity.
# No downloads, model loads, installed release or actual user workspace access.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExe=Join-Path $root '.venv-live\Scripts\python.exe'
$qaTool=Join-Path $PSScriptRoot 'qa_foundation.py'
$runner=Join-Path $PSScriptRoot 'Verify_P2_DevQA_Native_Chain_Local.ps1'
$runDir=$null
$archive=$null
function Failure-Diagnostic([string]$message){
    Write-Host ('P2 DevQA preflight BLOCK: '+$message) -ForegroundColor Red
    if($runDir -and (Test-Path -LiteralPath $runDir -PathType Container)){
        $diag=Join-Path $runDir 'diagnostics\bootstrap-failure.json'
        $archiveDir=Join-Path (Split-Path (Split-Path $runDir -Parent) -Parent) 'archive'
        $archive=Join-Path $archiveDir ((Split-Path $runDir -Leaf)+'-bootstrap-fail.zip')
        @{state='BLOCKED';product_acceptance='NOT_TESTED';source='DevQA preflight';message=$message} |
            ConvertTo-Json | Set-Content -LiteralPath $diag -Encoding UTF8
        try{Compress-Archive -LiteralPath $diag -DestinationPath $archive -Force
            Write-Host ('Diagnostic ZIP (only status JSON): '+$archive)
        }catch{Write-Warning ('Could not archive bootstrap status: '+$_.Exception.Message)}
    }
}
Write-Host 'PilotODIN P2: Predictive DevQA full native report-to-Windows Save As test'
Write-Host 'This creates ONE new isolated run. Nothing is copied from old user projects.'
try{
    if($env:OS -ne 'Windows_NT'){throw 'Windows is required for actual native Save As.'}
    if(-not(Test-Path -LiteralPath $pythonExe -PathType Leaf) -or
       -not(Test-Path -LiteralPath $qaTool -PathType Leaf) -or
       -not(Test-Path -LiteralPath $runner -PathType Leaf)){
        throw 'Existing .venv-live Python or required DevQA source missing. No installation attempted.'
    }
    Push-Location $root
    try{
        $initLines=@(& $pythonExe -B $qaTool init --phase P2-NATIVE-CHAIN --json)
        $initExit=$LASTEXITCODE
    }finally{Pop-Location}
    if($initExit -ne 0){throw 'DevQA workspace allocator refused the path; no native test started.'}
    $payload=($initLines | Out-String | ConvertFrom-Json)
    if($payload.status -ne 'READY_NOT_TESTED' -or
       $payload.product_acceptance -ne 'NOT_TESTED' -or
       -not [IO.Path]::IsPathRooted([string]$payload.run_dir)){
        throw 'DevQA allocator returned an invalid or non-fresh run.'
    }
    $runDir=[string]$payload.run_dir
    $logs=Join-Path $runDir 'logs'
    Write-Host ('NEW DEVQA RUN: '+$runDir) -ForegroundColor Cyan
    Write-Host ('REQUIRED WINDOWS SAVE AS FOLDER: '+$payload.exports_dir) -ForegroundColor Cyan
    $testLog=Join-Path $logs 'devqa-selftests.log'
    Push-Location $root
    try{
        $prior=$ErrorActionPreference
        $ErrorActionPreference='Continue'
        & $pythonExe -B -m unittest discover -s tests -p test_qa_foundation.py -v 2>&1 |
            Tee-Object -FilePath $testLog
        $testExit=$LASTEXITCODE
    }finally{$ErrorActionPreference=$prior;Pop-Location}
    if($testExit -ne 0){throw 'DevQA foundation regression tests failed; no native test started.'}
    Write-Host 'P2 DevQA foundation regressions: PASS' -ForegroundColor Green
    $preflightLog=Join-Path $logs 'devqa-preflight.json'
    Push-Location $root
    try{
        $preflightLines=@(& $pythonExe -B $qaTool preflight tools/Verify_P2_DevQA_Native_Chain_Local.ps1)
        $preflightExit=$LASTEXITCODE
    }finally{Pop-Location}
    $preflightText=$preflightLines | Out-String
    $preflightText | Set-Content -LiteralPath $preflightLog -Encoding UTF8
    if($preflightExit -ne 0){throw 'P2 native runner source preflight BLOCKED.'}
    $preflight=$preflightText | ConvertFrom-Json
    if($preflight.status -ne 'REVIEW_READY'){throw 'Preflight status was not REVIEW_READY.'}
    if(@($preflight.findings).Count -gt 0){
        foreach($item in $preflight.findings){
            Write-Warning ('P2 source preflight '+$item.id+': '+$item.detail)
        }
    }
    Write-Host 'P2 DevQA source preflight: REVIEWED (no blocking findings)' -ForegroundColor Green
    Write-Host 'NEXT: Windows Save As dialogs MUST use the exact displayed DevQA exports directory.'
    & $runner -QaRunDir $runDir
    $nativeCode=$LASTEXITCODE
    if($nativeCode -ne 0){
        Write-Host 'P2 native DevQA scoped gate: FAIL. Share the single ZIP printed by the runner.' -ForegroundColor Red
        exit 1
    }
    Write-Host 'P2 native DevQA scoped gate: PASS (synthetic development integration only)' -ForegroundColor Green
    exit 0
}catch{
    Failure-Diagnostic $_.Exception.Message
    exit 1
}
