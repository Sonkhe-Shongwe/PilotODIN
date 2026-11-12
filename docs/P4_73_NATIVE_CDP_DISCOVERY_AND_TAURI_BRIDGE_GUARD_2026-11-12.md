# PilotODIN P4-73 | Testable native CDP discovery and mandatory Tauri bridge identity

**12 November 2026.** Current source-only bounded P4 continuation. The owner typed "next", **not new explicit native compilation approval**. The one P4-71 consent was consumed; the one-shot native jobs remain blocked.

## Why this source-only increment is justified

The previously verified P4-71 Windows run [#43276839784](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43276839784) compiled and launched an isolated Tauri process with five isolated WebView2 processes and a responding CDP debugging endpoint, but no real developer UI target was found. P4-72 added 20×1.5-second polling and redacted URL classifications. Its **three tests only validated URL classification**, not polling behavior. The old probe also accepted a same-origin browser page without verifying the Tauri native bridge before writing synthetic projects.

## Corrective QA-only changes

- Refactor the bounded page discovery into a **pure injected-snapshot/wait helper**; an observed developer page is selected only when exactly one current target has the exact permitted loopback origin/root. Missing, invalid or multiple matches are **BLOCKED**, never treated as a pass. Report only safe classification strings, not page URLs, query tokens or source files.
- Before creating even disposable synthetic projects or navigating a page, require a **read-only in-page Tauri v2 bridge check**, `window.__TAURI_INTERNALS__.invoke` callable. This is a necessary signal that the selected page is a Tauri context, **not independent proof of app identifier, WebView profile isolation or absence of original file writes**.
- New **6/6 Node built-in unit tests PASS locally**, covering delayed arrival, bounded missing targets, ambiguity, hostname spoof rejection, invalid snapshot, and present/missing/malformed native bridge; existing P4-72 classifier unchanged. The standalone new source files were tested without a browser, network, native executable or synthetic project uploads.
- Only frontend QA test files change plus this documentation. Existing P4-71 workflow's two `if: ${{ false }}` compilation jobs are unchanged and not dispatched. No app code, Rust, npm scripts, Tauri configuration, backend, data model, native build, installer, Qwen inference or model training.

## Evidence limits and next real gate

This is a **test-harness reliability** improvement, **not evidence that the formerly blocked P4-71 native page is now discoverable**. The actual previous CDP targets were not logged; root cause unknown. N2–N12 actual native UI still **NOT TESTED**, R03 physical offline 8 GB/Qwen **NOT TESTED**, business Gate C **UNVERIFIED**, historical full original app-data integrity **STRICT FAIL** (320 baseline vs 346 observed, historical writer UNKNOWN). **P4 ACTIVE, P4-R01–R06 OPEN, P5 NOT AUTHORISED, P8 NOT CERTIFIED**. Future native runtime work requires separate owner decision and isolated preflight. Avoid repetitive source-only changes absent new evidence.
