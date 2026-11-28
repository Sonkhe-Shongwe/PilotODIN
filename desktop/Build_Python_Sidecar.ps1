# PilotODIN C5: this legacy mutating entrypoint is frozen before setup.
# Previous implementation retained at 898230f116266e064f6925c03d538c8e3b863f7e:desktop/Build_Python_Sidecar.ps1.
# A separately reviewed exact-input contract and explicit scope are required.
Write-Error 'STOP: C5_SIDECAR_BUILD_BLOCKED; exact production build inputs and separate approval required.' -ErrorAction Continue
exit 2
