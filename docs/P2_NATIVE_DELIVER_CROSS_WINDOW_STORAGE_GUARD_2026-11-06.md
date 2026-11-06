# PilotODIN P2 | Native cross-window storage selection and unsaved Deliver safety
**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Phase:** P2 ACTIVE / REVIEW_REQUIRED; P1 development CLOSED; P8 Windows release NOT CERTIFIED.  
**Outcome:** SOURCE PATCH COMMITTED; LOCAL FOCUSED HARNESS PASS; repository-wide CI and owner-native multi-window acceptance NOT EXECUTED for this change.

## Source-confirmed inconsistency
In `frontend/src/UnifiedShell.tsx`, the `reviewProject` event listener used synchronous browser `window.confirm` for a `storage` event changing `pilotodin-current`, even when the mounted primary view contained an unsaved Deliver draft. Native Tauri/WebView2 prompt reliability was precisely why other P2 Deliver exits were moved to one-use native confirmation. A project-selection change by a different window is not explicit permission to discard the current window's report. This is a source-level risk, **not** evidence of an owner-observed Windows data-loss incident.

## Bounded fix
- `frontend/src/externalProjectTransitionGuard.ts` adds `shouldHoldNativeDeliverExternalProjectChange`, a pure identity-only predicate requiring (1) external `storage` event, (2) existing transition `confirm`, (3) native desktop, and (4) the current project's primary `deliver` dirty marker.
- `frontend/src/UnifiedShell.tsx` invokes that predicate after the unchanged-project check and **before** any browser confirm. A match displays a specific warning, stops event propagation to the legacy Studio listener and retains the same mounted project/draft. It does not rewrite another window's localStorage selection or create a provisional project load.
- Intentional in-window project changes continue through their existing selector/native confirmation. Clean/native and non-Tauri/browser external transitions retain prior handling. Prepare/Model/Predict, edited docks, project archival, report revision persistence, backend, Rust and fonts are not modified.
- Existing data remains untouched. The warning explicitly notes a reload may follow the other window's shared project selection.

## Focused verification and exact limitations
- Locally executed **8/8 Node tests PASS** in an isolated mirrored harness with the same new pure guard and corresponding `reviewProject` callback logic; includes native veto/no writes, repeat notifications, browser refusal, clean native reconciliation, same-window event retention, other form identities and unchanged selection.
- Local `tsc --noEmit --strict` on the helper plus minimal type stubs passed. This is **not** a full application TypeScript/Vite compile. The committed regression file `frontend/tests/p2-native-deliver-external-project.test.cjs` contains eight tests that transpile the **actual repository callback and guard** when run in the full frontend checkout. Its GitHub-fetched JavaScript syntax was parsed successfully, but **the committed regression file was not executed against a full checkout or in GitHub Actions in this session**.
- Production helper [`45f16dcbdf4b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/45f16dcbdf4bba028aa02664766052af3bc0bdaa); shell [`6a8a2274c103`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6a8a2274c1033a0ecb67994d1d35c06826aa5938); committed eight-test harness [`9a03a23a9e90`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9a03a23a9e903e4459f8eca9532768191370a198).
- Prior finished shared frontend [`#42186216164`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42186216164) and real HTTP/browser [`#42186216068`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42186216068) passed at **earlier source `8517ef9a462f`**, so they **do not validate the new source change**. No new workflow was dispatched under the repository's manual-only CI policy.

## Still required
1. Run the new repository test, existing affected frontend contracts and production `tsc`/Vite build in a full checkout using the existing locked dependencies. Do not install/download merely for this minor source edit.
2. Run one **disposable** native Windows multi-window storage-selection scenario: A has an unsaved Deliver note; B selects another project; A retains its note, current visible project and route with an explicit warning, without a browser prompt or implicit Studio load. Then explicitly switch using A's guarded project selector. Verify clean-case and browser fallback separately. Record OS/WebView2, exact executable source SHA and actual observed result.
3. Continue the existing owner full-shell native Leave/Keep launcher gate and independent Noto/OFL release-font decision. This patch does **not** close them, approve Unicode PDF redistribution or certify P8.

**Acceptance:** P2 development remains ACTIVE / REVIEW_REQUIRED. New cross-window protection is **source-patched, local-harness verified, full-checkout and native pending**. Do not call this an owner Windows PASS.
