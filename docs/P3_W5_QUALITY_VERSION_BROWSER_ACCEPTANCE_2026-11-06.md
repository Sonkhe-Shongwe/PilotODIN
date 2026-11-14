# PilotODIN P3-04 W5 | Approved Quality version transition in real browser

**Evidence date:** 6 November 2026  
**Exact source:** [`805fb6582b47f1d16b3b10c041bd0db761646faf`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/805fb6582b47f1d16b3b10c041bd0db761646faf) on `feature/live-dev-workspace-20261023`  
**Disposition:** **Synthetic Quality v0→v1 version boundary, real local-HTTP Chromium UI PASS.** Native owner Windows Tauri/WebView2 W5 **NOT TESTED**. Not a full product, release, P3 phase or P4 acceptance.

## Gap and bounded implementation

Previously `tests/test_p3_semantic_business_context.py` verified the real approved Quality proposal→commit API moves the working version from v0 to v1, rejects stale v0 semantic reads/writes and leaves v0 context version-scoped. That does not prove the actual frontend Quality approval and subsequent `Your data` semantic reload.

Source [`805fb6582b47f1d16b3b10c041bd0db761646faf`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/805fb6582b47f1d16b3b10c041bd0db761646faf) changes **test infrastructure only**:
- Adds `frontend/e2e/p3-real-http-semantic-quality-version.spec.ts`, a single disposable synthetic W5 scenario using existing CI-only Uvicorn process-owner guard and private `PILOTODIN_HOME`.
- Adds it to the existing `frontend/playwright.p3-real-http.config.ts` focused test match and to the existing branch-scoped P3 real HTTP workflow path filter.
- Does **not** modify `QualityWorkspace`, `SemanticOverview`, `SemanticContextEditor`, backend, storage, model, project data, desktop identity, installer or release.

### Actual exercised journey and safety boundary

1. Seed a new 36-row synthetic `claim_id,claim_amount,policy_number,Region` CSV through the isolated fixture process. Two `Region` cells have surrounding spaces; no actual owner dataset is loaded.
2. Store explicitly owner-described version-0 insurance context in this synthetic project via the test fixture API. The actual browser opens `Your data` and visibly shows these saved **unverified** notes at working version 0.
3. In the actual `Quality` UI, select the **Region / Surrounding whitespace** finding, request the **approve** proposal restricted to that exact issue and expected version 0, inspect the native-in-browser **Review exact dataset change** dialog showing working v0, Region and the two changed cells, then explicitly click **Approve these changes**. The browser request interceptor permits just **one** exact v0 approval proposal and **one** cryptographically receipt-matched Quality commit; it blocks unreviewed mutations and non-allowlisted origins. This consent is test-only and does not automatically approve anything in installed PilotODIN.
4. Await HTTP 200 commit returning **version 1**; verify Quality UI shows **WORKING VERSION 1**. Navigate back through the **Your data** UI; verify dictionary version 1 and **Optional: describe what this dataset means** with no v0 human notes in v1.
5. Verify the real synthetic backend `/semantics?expected_version=1` returns `user_context=null`, stale v0 semantic GET returns **409** and stale v0 POST returns **409**. Verify version-1 Quality preview preserves original spaced `Region` while the approved *working* value is trimmed; history records versions **[0,1]**. No extra browser API mutation or remote request is permitted.

The browser test proves that v0 notes are not **silently migrated into current v1 UI** and stale versions cannot be used. It does not require owners to edit or clear their existing projects or perform an installer run. The source backend unit test independently covers stored v0 notes and source CSV invariants. This CI does not independently compare the entire original imported CSV byte hash.

## Observed actual CI

| Workflow | Source SHA | Observed outcome |
| --- | --- | --- |
| [P3 actual Uvicorn + Chromium #42282095666](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42282095666), job `128113428524` | `805fb6582b47f1d16b3b10c041bd0db761646faf` | **COMPLETED SUCCESS: 2/2 scoped real HTTP P3 browser tests PASS (13.4s)**, including the new W5 actual Quality approval journey **PASS (5.0s)** and earlier description Save/reload/project-isolation/unknown-hint journey |
| [P1 isolated frontend #42282095621](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42282095621), job `128113426307` | `805fb6582b47f1d16b3b10c041bd0db761646faf` | **COMPLETED SUCCESS: 160/160 Node contracts**, `tsc --noEmit && vite build` **PASS** (1,653 modules, 1.71s), **5/5 synthetic Chromium scenarios PASS (10.7s)** |

No unrun CI is claimed. This test-only code change did not trigger the P3 Python-contract job because it does not alter the backend or frontend application.

## Remaining acceptance and disposition

- **P3-04 W5 browser subgate: SCOPED ACCEPTED** at `805fb6582b47f1d16b3b10c041bd0db761646faf`; includes a reviewed exact UI proposal/commit and version-bound human context reload.
- **P3-04 W5 native Windows/WebView2: PENDING**, not inferred from the browser test or previously accepted physical W1–W4. Any native W5 test must run on a **fresh, purpose-built synthetic isolated checkout/run**, with a separately reviewed one-time Quality proposal/commit, no reused v0-A two-save guard and no owner source.
- **Native W1a/W1b/W2/W3/W4: previously scoped ACCEPTED** at exact owner-tested `57817544768af1681f60cb4600dbc4dde984a7cb`; do not repeat or reassign them to current CI.
- **P3-03 broader semantic truth/adjudication and owner phase scope freeze: OPEN**. This test does not grant independence or business truth to user descriptions and does not allow P4 model/target propagation.
- **P3 remains ACTIVE**. P1/P2 bounded-development CLOSED. P4 NOT AUTHORISED. P8 installer/offline release NOT CERTIFIED.

**Next safe decision:** Do not close P3 from this browser result. Decide whether an independently isolated **native W5** is an essential P3 exit criterion and whether broader P3-03 human adjudication is required or explicitly deferred, then freeze the phase matrix only with the owner's review.
