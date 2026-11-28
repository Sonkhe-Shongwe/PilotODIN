# PilotODIN R02.5 | G2.0 native readiness preflight

**22 November 2026. GitHub-first, source-only. No actual Windows run, live Sysmon validation, approval or R02.5 acceptance.**

## Baseline and findings

- Current reviewed parent: `72a1010d3c2f160261cecc82a9a881d560dc40a9` on `feature/live-dev-workspace-20261023`. G1 is **PASSED at 25%** after 126/126 synthetic tests in [CI #45038916372](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45038916372).
- Actual [one-use baseline #44932378332](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44932378332) **failed before PilotODIN/WebView2 launch** because child-scoped Sysmon TCP and UDP Event 3 calibration was missing. Its owner approval was consumed.
- Published PowerShell source now generates `NetworkConnect onmatch="exclude"` and writes that definition directly. The formerly defective empty `include` form is not active in source. **This does not prove actual Event 3 capture after the correction.**
- The original native FileIO workflow is disarmed; the old approval marker still refers to the consumed source. It is neither fresh permission nor a usable new activation.
- The original strict FileIO reducer remains unchanged, retains unresolved and prohibited writes, and never upgrades source-only witnesses to native acceptance.

## G2.0 change and narrow automation

`tests/test_p4_n12_g2_static_preflight.py` adds source-only regressions for embedded Sysmon XML, configuration mutation, consent/source/binary guards, disarmed first-attempt workflow, consumed marker, redacted reporting and unchanged native nonacceptance. Negative fixtures detect the old Event 3 `include` mistake and accidental native activation.

The existing **Ubuntu-only** `.github/workflows/p4-r02-5-fileio-source-contract.yml` runs these tests after the current G1 suites. It keeps `contents: read`, pinned checkout, no production dependencies, no Windows host, no Sysmon/ETW operations and no installer. A green Linux job is static evidence only.

## Next necessary measurement, separately authorised

One source-pinned **GitHub-hosted Windows no-CDP FileIO baseline** could be approved specifically to:

1. Build and hash one isolated **unpackaged** staged binary, using disposable generated QA roots only.
2. Temporarily provision Sysmon and Kernel-File ETW on the hosted runner, enforce the first generated child-scoped TCP **and** UDP calibration before app launch, then stop without retry if either fails.
3. If both controls pass, run one no-CDP Tauri/WebView2 startup-to-exit journey, retain original child **process** handles via the private authenticated channel, observe completed writes and the same-capture write/restore control, and review losses and protected snapshots.
4. Clean up, publish only fixed-label counts or `BLOCKED`, and **not upload raw traces, handles, PIDs, paths or process command lines**. The original native approval marker stays consumed; a new marker and separate direct-child activation contract are necessary.

**Risks:** WebView2 may initiate outbound network traffic; the baseline does **not** install a firewall egress block or guarantee offline isolation. ETW/Sysmon may temporarily observe file, process and network metadata on the hosted runner. No original owner files or local Windows workstation are in scope. Approval would be spent even on a pre-app calibration failure. Never re-run automatically.

**G2 is not satisfied by calibration alone.** The existing process-child handle witness is **not** the original WebView2 **file** handle. It cannot independently link that handle to the ETW FileObject/IRP, successful operation and actual physical request-time path. A second separately approved private path mechanism may be required. A clean or blocked first baseline must not silently credit historical outside-scope WebView writes or unresolved gaps.

## Approval boundary and ledger

Routine GitHub source changes and source-only CI are covered by standing owner authorisation. A genuine Windows capture, external WebView2 traffic, original file-handle inspection, protected owner data, installer, policy adjustment or native workflow activation still requires a fresh explicit, source-pinned one-use approval. **Do not activate the disarmed job on this source-only commit.**

Delivery tracker remains **G1 1/4 PASSED (25%) → G2 IN PROGRESS (still 25%)**, pending actual native evidence. Official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**, historical internal file-mutation engineering **3/4 (75%)** remain unchanged.
