# P1 import rollback regression + E2 READ-ONLY system inventory in one local run.
# This DOES NOT repeat the larger A2/A3/A4 suites or certify offline inference.
[CmdletBinding()]
param(
    [string]$ModelPath = '',
    [string]$RuntimePath = ''
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $root '.venv-live\Scripts\python.exe'
$probe=Join-Path $PSScriptRoot 'Probe_E2_8GB_Offline_Inventory.ps1'
$dir=Join-Path $env:TEMP ('pilotodin-p1-e2-' + [guid]::NewGuid().ToString('N').Substring(0,12))
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$zip=$dir+'.zip'
$testLog=Join-Path $dir 'p1-import-regressions.log'
$inventory=Join-Path $dir 'e2-readonly-inventory.json'
$summaryFile=Join-Path $dir 'result.json'
$summary=[ordered]@{
    phase = 'P1 import recoverability + early E2 inventory'
    generated_utc = [datetime]::UtcNow.ToString('o')
    p1_regressions = 'NOT_RUN'
    p1_test_exit_code = $null
    e2_inventory = 'NOT_RUN'
    offline_ai_and_8gb_certification = 'NOT_TESTED'
    installer_and_hosted_ci = 'NOT_RUN'
    diagnostic_note = 'All tests use synthetic temp-home data. Inventory is read-only and omits file paths and personal data.'
}
function Finish([int]$code){
    $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summaryFile -Encoding UTF8
    $files=@($summaryFile)
    if(Test-Path -LiteralPath $testLog){$files+= $testLog}
    if(Test-Path -LiteralPath $inventory){$files+= $inventory}
    Compress-Archive -LiteralPath $files -DestinationPath $zip -Force
    Write-Host ''
    Write-Host ('P1 regression status: '+$summary.p1_regressions)
    Write-Host ('E2 inventory status: '+$summary.e2_inventory)
    Write-Host 'True offline local-Qwen inference / real 8 GB combined load: NOT TESTED'
    Write-Host ('Single diagnostics ZIP: '+$zip)
    exit $code
}
if($env:OS -ne 'Windows_NT'){Write-Host 'Windows only';Finish 1}
if(-not (Test-Path -LiteralPath $python)){
    Write-Host 'Missing .venv-live Python; use the normal PilotODIN dev setup first.'
    Finish 1
}
if(-not (Test-Path -LiteralPath $probe)){Write-Host 'Missing E2 inventory script';Finish 1}
$oldHome=$env:PILOTODIN_HOME
$env:PILOTODIN_HOME=Join-Path $dir 'isolated-backend-home'
New-Item -ItemType Directory -Path $env:PILOTODIN_HOME -Force | Out-Null
$previous=$ErrorActionPreference
$exitCode=1
Push-Location $root
try{
    # Windows PowerShell 5.1 can treat native STDERR as a terminating error
    # when globally set to Stop. Rely on Pytest's actual exit code instead.
    $ErrorActionPreference='Continue'
    & $python -m pytest -q tests/test_p1_import_recovery.py 2>&1 | Tee-Object -FilePath $testLog
    $exitCode=if($null -eq $LASTEXITCODE){1}else{[int]$LASTEXITCODE}
}catch{
    Add-Content -LiteralPath $testLog -Value ('Test runner exception: '+$_.Exception.Message)
}finally{
    $ErrorActionPreference=$previous
    Pop-Location
    if($null -eq $oldHome){Remove-Item Env:\PILOTODIN_HOME -ErrorAction SilentlyContinue}
    else{$env:PILOTODIN_HOME=$oldHome}
}
$summary.p1_test_exit_code=$exitCode
$summary.p1_regressions=if($exitCode -eq 0){'PASS'}else{'FAIL'}
try{
    & $probe -ModelPath $ModelPath -RuntimePath $RuntimePath -OutputPath $inventory
    if(Test-Path -LiteralPath $inventory){
        $summary.e2_inventory='COLLECTED_NO_FEASIBILITY_CLAIM'
    }else{
        $summary.e2_inventory='FAILED'
    }
}catch{
    $summary.e2_inventory='FAILED'
    Write-Host ('E2 inventory failed: '+$_.Exception.Message)
}
if($summary.p1_regressions -ne 'PASS' -or $summary.e2_inventory -eq 'FAILED'){
    Finish 1
}
Finish 0
