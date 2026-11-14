# PILOTODIN P2 READ-ONLY recovery: verify previously saved native report outputs.
# Never starts Tauri, FastAPI, a browser or AI. Does not rename, move or copy files.
[CmdletBinding()]
param([string]$SessionId='292199a81c44')
$ErrorActionPreference='Stop'
$report=[ordered]@{
  scope='P2 previously-run synthetic live-report-to-native Saved As: recovery-only'
  previous_session=$SessionId
  overall='FAIL'
  previous_gate='FAIL: original entered Downloads without absolute path'
  previous_native_actions='OWNER_REPORTED_PASS_FROM_PREVIOUS_RESULT_JSON'
  output_sha_verification='NOT_RUN'
  exact_filenames='NOT_VERIFIED'
  source_unchanged='NOT_VERIFIED'
  no_rebuild=$true
  no_file_modifications=$true
  failure_reason=''
  files=[ordered]@{}
}
$diagnosticRoot=Join-Path ([IO.Path]::GetTempPath()) ('pilotodin-p2-native-chain-recovery-'+[guid]::NewGuid().ToString('N').Substring(0,12))
New-Item -ItemType Directory -Path $diagnosticRoot -Force | Out-Null
$reportFile=Join-Path $diagnosticRoot 'result.json'
$zipPath=$diagnosticRoot+'.zip'
function Finish-Verification {
  $report | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath $reportFile -Encoding UTF8
  Compress-Archive -LiteralPath $reportFile -DestinationPath $zipPath -Force
  Write-Host ('P2 native live-report saved-file recovery: '+$report.overall) -ForegroundColor $(if($report.overall -eq 'PASS'){'Green'}else{'Red'})
  Write-Host ('One diagnostic ZIP (only status JSON; no chosen folder or data files): '+$zipPath)
  if($report.overall -eq 'PASS'){exit 0}
  exit 1
}
function Verify-ExpectedFile([string]$format,[string]$folder,[string]$expectedFilename,[string]$expectedSha) {
  $actual=Join-Path $folder $expectedFilename
  $rec=[ordered]@{filename=$expectedFilename;exists=$false;sha256_match=$false;bytes=$null;status='FAIL'}
  if(Test-Path -LiteralPath $actual -PathType Leaf) {
    $rec.exists=$true
    $rec.bytes=(Get-Item -LiteralPath $actual).Length
    $rec.sha256_match=((Get-FileHash -LiteralPath $actual -Algorithm SHA256).Hash -eq $expectedSha)
    if($rec.sha256_match){$rec.status='PASS'}
  }
  $report.files[$format]=$rec
  if(-not $rec.exists) {
    Write-Host ($format.ToUpperInvariant()+': MISSING expected file '+$expectedFilename) -ForegroundColor Red
  }elseif(-not $rec.sha256_match) {
    Write-Host ($format.ToUpperInvariant()+': FOUND but SHA-256 MISMATCH '+$expectedFilename) -ForegroundColor Red
  }else{
    Write-Host ($format.ToUpperInvariant()+': PASS exact filename and original backend-export SHA-256') -ForegroundColor Green
  }
  return $rec.status -eq 'PASS'
}
Write-Host 'PilotODIN P2: verify ALREADY-SAVED real report native exports ONLY'
Write-Host 'No Tauri/Rust rebuild; no FastAPI; no new Save As; no broad file search.'
try{
  if($env:OS -ne 'Windows_NT'){throw 'This check requires Windows.'}
  if($SessionId -cnotmatch '^[a-f0-9]{12}$'){throw 'Invalid previous test-session ID.'}
  $sessionRoot=Join-Path ([IO.Path]::GetTempPath()) ('pilotodin-p2-native-chain-'+$SessionId)
  $workspace=Join-Path $sessionRoot 'workspace'
  $manifestPath=Join-Path $workspace 'synthetic-manifest.json'
  $oldResult=Join-Path $sessionRoot 'logs\result.json'
  if(-not(Test-Path -LiteralPath $manifestPath -PathType Leaf)){
    throw 'Previous isolated synthetic manifest no longer exists. Do not guess the expected PDF hash.'
  }
  if(-not(Test-Path -LiteralPath $oldResult -PathType Leaf)){
    throw 'Previous result.json is missing. Cannot connect current outputs to original owner run.'
  }
  $manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
  $earlier=Get-Content -LiteralPath $oldResult -Raw -Encoding UTF8 | ConvertFrom-Json
  if($earlier.phases.'p2-owner-real-report-export-observations' -ne 'PASS' -or
     $earlier.phases.'p2-real-report-native-tauri-window' -ne 'PASS' -or
     $earlier.phases.'p2-live-export-reference-digests' -ne 'PASS'){
    throw 'Previous native actions or live HTTP baseline were not marked PASS; do not promote this result.'
  }
  if($earlier.message -ne 'Selected Save As folder does not exist.' -or $manifest.revision -ne 2 -or
     $manifest.report_id -notmatch '^[a-f0-9]{32}$' -or
     $manifest.project_id -notmatch '^[a-f0-9]{32}$'){
    throw 'Unexpected previous result or invalid saved report identity.'
  }
  $prefix='pilotodin_report_'+$manifest.report_id.Substring(0,12)+'_rev2'
  foreach($ext in @('html','pdf')){
    $expectedName=$prefix+'.'+$ext
    $entry=$manifest.exports.$ext
    if($entry.filename -cne $expectedName -or $entry.sha256 -notmatch '^[a-fA-F0-9]{64}$'){
      throw ('Synthetic '+$ext+' manifest does not match strict revision-2 filename/hash contract.')
    }
  }
  $rel=[string]$manifest.source_relative
  if([IO.Path]::IsPathRooted($rel) -or $rel.Contains('..') -or $rel -notmatch '^datasets[\\/]'){
    throw 'Unsafe synthetic source path in manifest.'
  }
  $workspaceAbsolute=[IO.Path]::GetFullPath($workspace)
  $sourceAbsolute=[IO.Path]::GetFullPath((Join-Path $workspace $rel))
  if(-not $sourceAbsolute.StartsWith($workspaceAbsolute+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){
    throw 'Synthetic source is outside the isolated test workspace.'
  }
  if(-not(Test-Path -LiteralPath $sourceAbsolute -PathType Leaf) -or
     (Get-FileHash -LiteralPath $sourceAbsolute -Algorithm SHA256).Hash -ne $manifest.source_sha256){
    throw 'Original synthetic source does not match the previous run.'
  }
  $report.source_unchanged='PASS'
  Write-Host ('Prior report '+$manifest.report_id+' revision 2 baseline: PASS') -ForegroundColor Green
  Write-Host 'Original synthetic CSV integrity: PASS' -ForegroundColor Green
  Write-Host ('Expected HTML filename: '+$manifest.exports.html.filename)
  Write-Host ('Expected PDF filename:  '+$manifest.exports.pdf.filename)
  Write-Host 'The prior console entry "Downloads" failed because it was not a full directory path.'
  Write-Host 'You may type Downloads (resolved to the Windows user Downloads folder), or paste an ABSOLUTE directory.'
  $ownerAnswer=(Read-Host 'Are these the two ORIGINAL, unmodified files from the previous real Tauri Save As dialogs? [yes/no]').Trim().ToLowerInvariant()
  if($ownerAnswer -notin @('y','yes')){throw 'Original native Save As provenance not confirmed by owner.'}
  $raw=(Read-Host 'Enter the folder CONTAINING the two files (Downloads or full C:\ path)').Trim().Trim('"')
  if([string]::IsNullOrWhiteSpace($raw)){throw 'No folder entered.'}
  if($raw -ieq 'Downloads'){
    $raw=Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
  }
  if(-not([IO.Path]::IsPathRooted($raw))){throw 'Folder must be an absolute path or the special Downloads keyword.'}
  if(-not(Test-Path -LiteralPath $raw -PathType Container)){throw 'Selected folder does not exist.'}
  $folder=(Resolve-Path -LiteralPath $raw).Path
  $htmlOk=Verify-ExpectedFile 'html' $folder ([string]$manifest.exports.html.filename) ([string]$manifest.exports.html.sha256)
  $pdfOk=Verify-ExpectedFile 'pdf' $folder ([string]$manifest.exports.pdf.filename) ([string]$manifest.exports.pdf.sha256)
  $report.exact_filenames=$(if($htmlOk -and $pdfOk){'PASS'}else{'FAIL'})
  $report.output_sha_verification=$(if($htmlOk -and $pdfOk){'PASS'}else{'FAIL'})
  if(-not($htmlOk -and $pdfOk)){
    throw 'Saved file(s) absent or hash mismatch. Differently named copies/downloads cannot establish exact native Save As filename acceptance.'
  }
  $report.overall='PASS'
  $report.failure_reason=''
  Write-Host 'Both existing native export outputs match the exact frozen real FastAPI PDF/HTML bytes.' -ForegroundColor Green
}catch{
  $report.failure_reason=$_.Exception.Message
  Write-Host ('P2 recovery cannot certify native exports: '+$report.failure_reason) -ForegroundColor Red
}
Finish-Verification
