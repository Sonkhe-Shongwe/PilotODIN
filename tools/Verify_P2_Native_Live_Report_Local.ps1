# Retired unmanaged temporary report-chain launcher.
# Previous implementation and historical evidence remain in Git history.
[CmdletBinding()]
param()
Write-Host 'Legacy unmanaged P2 native report launcher is retired.' -ForegroundColor Yellow
Write-Host 'Use Run_PilotODIN_P2_DevQA_Native_Chain.bat only with separate native approval.'
Write-Host 'No workspace, process, model, installer or export was started.'
exit 2
