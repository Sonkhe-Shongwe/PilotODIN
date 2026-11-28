# P2 repair-only verification of existing synthetic native Save As outputs.
# Reads only two specifically named files from a directory selected by the owner.
# DOES NOT rerun Rust, open Tauri, search whole disks, copy, modify or delete files.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$expectedPdf='42DB62AFED2EDC10AA27FB1DB239DA7DCBB5CF0E0B6C343306C8B5174A4D7FA8'
$expectedHtml='13FF57225C51CAD2D9887494D823483EF3D99D6598163A9EF9576A9E57C9D7CA'
$folder=Join-Path ([IO.Path]::GetTempPath()) ('pilotodin-p2-native-recovery-' + [guid]::NewGuid().ToString('N').Substring(0,12))
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$archive=$folder+'.zip'
$reportFile=Join-Path $folder 'result.json'
$report=[ordered]@{
    scope='P2 Native Export: repair-only verification of existing Save As files'
    timestamp_utc=[datetime]::UtcNow.ToString('o')
    previous_native_five_actions='OWNER_SCREENSHOT_PASS'
    previous_rust_dev_window='PREVIOUS_OWNER_ZIP_PASS'
    previous_full_gate='FAIL: expected-folder hashes not established'
    current_status='FAIL'
    source_originals='PENDING'
    owner_provenance='NOT_CONFIRMED'
    files=[ordered]@{}
    cancel_file_absent='NOT_TESTED'
    actual_save_location='OWNER_SELECTED_NOT_RECORDED'
    no_native_rebuild=$true
    no_data_writes=$true
    message=''
}
function Finish([string]$reason,[bool]$passed){
    $report.current_status=$(if($passed){'PASS'}else{'FAIL'})
    $report.message=$reason
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportFile -Encoding UTF8
    Compress-Archive -LiteralPath $reportFile -DestinationPath $archive -Force
    Write-Host ('Native saved-file recovery verification: '+$report.current_status) -ForegroundColor $(if($passed){'Green'}else{'Red'})
    Write-Host ('Diagnostic ZIP (contains only result.json; no report files or save path): '+$archive)
    exit $(if($passed){0}else{1})
}
function Verify-File([string]$label,[string]$path,[string]$expected){
    $item=[ordered]@{name=[IO.Path]::GetFileName($path);exists=$false;status='FAIL';bytes=$null;sha_match=$false}
    if(Test-Path -LiteralPath $path -PathType Leaf){
        $item.exists=$true
        $item.bytes=(Get-Item -LiteralPath $path).Length
        $item.sha_match=((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $expected)
        if($item.sha_match){$item.status='PASS'}
    }
    $report.files[$label]=$item
    if(-not $item.exists){
        Write-Host ($label+': FAIL: file is absent from the selected folder.') -ForegroundColor Red
    }elseif(-not $item.sha_match){
        Write-Host ($label+': FAIL: file exists, but bytes differ from committed synthetic fixture.') -ForegroundColor Red
    }else{
        Write-Host ($label+': PASS: found and SHA-256 matches the earlier owner run.') -ForegroundColor Green
    }
    return $item.status -eq 'PASS'
}
Write-Host 'PilotODIN P2: Verify previous native Save As files ONLY'
Write-Host 'No native rebuild, no browser, no file writes, no user-data search.'
Write-Host 'This does NOT convert the earlier failed gate to PASS without exact file proof.'
$pdfFixture=Join-Path $root 'frontend\public\p2-native-fixtures\report.pdf'
$htmlFixture=Join-Path $root 'frontend\public\p2-native-fixtures\report.html'
if(-not (Test-Path -LiteralPath $pdfFixture -PathType Leaf) -or -not (Test-Path -LiteralPath $htmlFixture -PathType Leaf)){
    Finish 'Required committed synthetic source fixtures were not found.' $false
}
$originalsOK=((Get-FileHash -LiteralPath $pdfFixture -Algorithm SHA256).Hash -eq $expectedPdf) -and
    ((Get-FileHash -LiteralPath $htmlFixture -Algorithm SHA256).Hash -eq $expectedHtml)
$report.source_originals=$(if($originalsOK){'PASS'}else{'FAIL'})
if(-not $originalsOK){Finish 'Committed fixture checksum differs from the independently inspected previous run.' $false}
Write-Host 'Committed synthetic fixture integrity: PASS' -ForegroundColor Green
Write-Host ''
Write-Host 'Find the two files you saved using the Windows Save As dialogs in the LAST native P2 test.'
Write-Host 'They should be named: PilotODIN_P2_Synthetic.pdf and PilotODIN_P2_Synthetic.html'
Write-Host 'Use File Explorer to find them. Do NOT manually copy, rename or edit either file.'
$answer=(Read-Host 'Confirm these are the unmodified files saved by the previous native test? [yes/no]').Trim().ToLowerInvariant()
if($answer -notin @('yes','y')){Finish 'Owner has not confirmed source of the files; no acceptance.' $false}
$report.owner_provenance='OWNER_CONFIRMED_PREVIOUS_NATIVE_SAVE'
$pathEntry=(Read-Host 'Paste the FOLDER containing those two saved files (not a file path)').Trim().Trim('"')
if([string]::IsNullOrWhiteSpace($pathEntry)){Finish 'No folder supplied.' $false}
if(-not (Test-Path -LiteralPath $pathEntry -PathType Container)){Finish 'The supplied directory does not exist.' $false}
$actualFolder=(Resolve-Path -LiteralPath $pathEntry).Path
$pdf=Join-Path $actualFolder 'PilotODIN_P2_Synthetic.pdf'
$html=Join-Path $actualFolder 'PilotODIN_P2_Synthetic.html'
$cancel=Join-Path $actualFolder 'PilotODIN_P2_Cancel.pdf'
$pdfOK=Verify-File 'pdf' $pdf $expectedPdf
$htmlOK=Verify-File 'html' $html $expectedHtml
$cancelAbsent=(-not (Test-Path -LiteralPath $cancel))
$report.cancel_file_absent=$(if($cancelAbsent){'PASS'}else{'FAIL'})
Write-Host ('Cancelled file absent: '+$report.cancel_file_absent) -ForegroundColor $(if($cancelAbsent){'Green'}else{'Red'})
if($pdfOK -and $htmlOK -and $cancelAbsent){
    Finish 'Verified both prior native outputs byte-for-byte at owner-selected destination; does NOT establish use of original temporary target folder.' $true
}
Finish 'At least one output is missing, mismatched or cancelled file is present. Native file location/integrity remains unresolved.' $false
