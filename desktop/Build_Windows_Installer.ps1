# P4-P7 installer freeze. The historical builder is retained in Git history.
# P8 requires fresh explicit owner authority and verified reproducible inputs.
# No environment marker, command-line argument or previous approval bypasses this.
Write-Error 'STOP: PilotODIN intermediate installer packaging remains frozen. No environment, dependency, sidecar or installer operation started.' -ErrorAction Continue
exit 2
