# PilotODIN P4-72 | CDP native target discovery analysis and fail-closed QA repair

**12 November 2026.** Scope: source/QA-only investigation after P4-71 consumed its owner-approved *one* unpackaged Windows developer compilation. **NO new native compilation, workflow dispatch, installer, owner original app-data access, model fit or phase closure.**

## Verified actual historical source and Windows log

- P4-71 exact executable source: `8060d17b679d959d7b404a06a382d52ce20a8cf7`; successful GitHub Actions [run #43276839784](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43276839784), native job 131387520533.
- Win2022 process and profile evidence **PASS** (5 isolated WebView2 processes, distinct identity, CDP at 127.0.0.1:9331 responding). The job log at 18:13:10Z reports **“NATIVE INTERACTIONS BLOCKED: no actual Tauri dev WebView2 at 127.0.0.1:5173.”** No browser candidate URL or navigation status was captured, so **the actual cause cannot be established from this log**.
- Source inspection of `frontend/e2e/p4-71-native-webview-qa.mjs` finds an immediate, one-shot `browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().startsWith(SITE))` after `connectOverCDP`. This is insufficient to distinguish a late-arriving page from a different target or legitimate WebView internals. A successful CI job was correctly recorded as a native bootstrap PASS and an interaction **BLOCKED**, not a full P4 PASS.

## Bounded QA-only repair (not yet Windows-tested)

- In the research-only Playwright CDP probe, poll the connected target list **up to twenty times, 1.5 seconds apart**, without navigating/altering the UI until one exact expected loopback development root is seen. Preserve a fail-closed blocked result for missing or ambiguous matching pages.
- Classify only target *types* (`about:blank`, Tauri scheme, `tauri.localhost`, alternate localhost, unexpected app path or unrelated origin), never log full URLs, query strings, paths, tokens or local app-data directories. Treat localhost aliases and alternate schemes only as diagnostics; **do not accept them for automated interaction without proof of native provenance**.
- New pure standard-library Node tests check allowed exact origin/root and rejection of misleading or hostile near-matches plus redacted origin classification. No browser connection, backend, training or build in these tests.
- The P4-71 one-use trigger/workflow remains disabled and no new native job is scheduled by this change. The code has **not** been exercised on actual Windows WebView2, so the underlying target discovery is still **UNVERIFIED**, not a confirmed root-cause fix.

## Residuals

R02 native N2–N12, R04 current native UX and R05 native Prepare remain **NOT TESTED**. R03 physical offline 8 GB/Qwen still **NOT TESTED**. R01 real operational decision usefulness/Gate C **UNVERIFIED**. R06 historical whole original app-data tree **STRICT FAIL**, past writer **UNKNOWN**. **P4 ACTIVE, all R01–R06 OPEN, P5 NOT AUTHORISED, P8 NOT CERTIFIED.** The next real native execution requires new explicit owner approval and an independently verified safe isolated execution environment; do not reuse the consumed P4-71 permission.
