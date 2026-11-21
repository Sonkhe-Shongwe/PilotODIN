# P4 R02.5 | Stage 1 debugger-free hosted Windows entrypoint

**21 November 2026 | Source-only entrypoint, not a native pass.** Current goal: a single approved, source-pinned, unpackaged, disposable hosted-Windows no-CDP startup, unique process/profile attribution and ordinary shutdown, with complete Sysmon/ETW process-lifetime evidence.

## Previously missing integration

The existing dormant `qa.p4_research.n12_app_lifetime --no-cdp` path was ready for a source-pinned run, but the real PowerShell collector entrypoint always called the default CDP variant. Its old native workflow remained disarmed, and it supplied only the original lifetime consent. Activating that workflow without extending the entrypoint would run the **wrong test**.

`qa/p4_native/Invoke_P4_N12_Live_Calibration.ps1` now exposes `-NoCdp` **only** alongside `-AppLifetime -WithEtw`, and refuses it with other collector, app journey, diagnostic or runtime-override modes. It additionally requires the distinct `PILOTODIN_N12_NO_CDP_STORAGE_CONSENT=I_APPROVE_ONE_N12_NO_CDP_STORAGE` before any Sysmon provisioning or dependency work. The previous N12 lifetime, WebView storage and journey paths remain unchanged, and the new flag is forwarded to the existing separately consent-gated Python CLI. Static source tests enforce the flag, routing and still-disabled workflow.

## Exact one-use native procedure and stop boundaries

A **later separately activated** workflow must remain a direct child of its reviewed source SHA, changing **only** the workflow and a new approval marker, with clean checkout detached back to the reviewed source and two distinct lifetime/no-CDP consents. A genuine approved run must be first-attempt GitHub-hosted Windows; check the original native QA identity `com.pilotodin.p4isolatednativedev`, Cargo.lock and binary digests, isolated home and WebView profile, original Rust main close veto, hidden peer normal close, live window/birth/handle, Sysmon GUID ancestry and ETW start/stop, and zero ETW loss or missing stages. No installer, owner-device changes, protected project access, product data-folder migration or firewall change.

The previously approved complete N12 is still **filesystem FAIL / network FAIL / FileIO coverage BLOCKED**. Even a real Stage 1 PASS would prove **only** no-CDP lifetime/profile identity. R02.5 0/5, file-mutation 3/4 (75%), P4 14/20 (70%), N12 0/2 and the separate strict FileIO/network acceptance requirements remain unchanged.

**No native execution or one-use workflow activation occurs in this source increment.**
