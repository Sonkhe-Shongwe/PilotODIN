# PilotODIN 1.0 | P3 scope and closure decision pack

## 9 November 2026 | P3 owner-authorised BOUNDED DEVELOPMENT CLOSURE

- **Owner explicitly approved** after being told `P3 overall closure: Awaiting final review and approval` and replied `i approve`. This covers **bounded P3 development**, not automatic P4 authorisation, not a whole-app no-high-defect assertion and not P8 release certification.
- **Formal scope/risk review:** [`P3_DEVELOPMENT_CLOSURE_2026-11-09.md`](./P3_DEVELOPMENT_CLOSURE_2026-11-09.md) freezes P3-01/02/03a/b, P3-03 **Option A** manual owner-attestation and P3-04 version boundary; names every accepted evidence family and source SHA. Original W1–W4 and independently reviewed successful W5 (owner native attestation plus integrity-checked status archive) are scoped accepted. New Option A real-HTTP/Chromium, owner Chrome and backend consent/version/audit evidence accepted without claiming independent native Tauri observation.
- **Gate 2 screened:** Master QA Issue #2 BE-001–BE-035 screened for P3 bounded semantic metadata/consent risks; **no known still-open confirmed critical/high within the frozen P3 requirements**. Critical/high *elsewhere* (ODIN AI, Investigate tie-breaking, Predict invalid values, Deliver reports, Explore) remain open with unchanged severity and future release implications.
- **Residual R-01:** Separate WebView2 manual-review form parity was **not physically demonstrated**; classified as native integration **UNTESTED**, not PASS, to be checked once in a consolidated future native/release gate (at latest P8). Standard React/HTTP form does not add new native OS/IPC behavior. No need to repeat W5/W1–W4 or all accepted browser tests. Independent truth/ontology/cross-view propagation excluded from Option A.
- **Six scoped exit criteria:** Bounded scope frozen, P3-specific critical/high screen complete, essential prior native and current real-browser journeys assessed with explicit R-01, narrow tests/build green at last *application* SHA `42176b3ea90eae7dcd891fe11170ec16839118d8` (native W5 at `9042c660ff541d4a012c7e3d637aa2a47f9bd841`), durability/consent demonstrated, this issue + both handoffs + owner approval recorded. Documentation commit is not a new product build.
- **Status:** P1/P2/P3 **CLOSED for bounded development**. **NO primary new phase authorised**, P4 **NOT AUTHORISED**, P8 **NOT CERTIFIED**. Reopen a new P3 critical/high safety defect if one is credibly found despite closure.


## 8 November 2026 | Owner approved P3-03 Option A, bounded human semantic review source and browser PASS

- **Owner scope decision:** Owner explicitly selected **Option A** in the current conversation. This authorises a bounded P3-03 owner *attestation* of current field hypotheses, NOT automatic business truth, ML/target selection, installed product mutation, P4 or release certification. Option B was not selected. No independent authority for domain/record-grain truth was provided.
- **Implemented in authorised branch:** [Initial P3 human-review implementation `8f4a2e5cc77e`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8f4a2e5cc77e299dce9ea80cf04c298cd0d95d90), real-HTTP browser and existing-guard correction [`9bab3f4e4982`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9bab3f4e4982e4dce9acf1dd3fa7d1a7c95ffe7d), combined unsaved guard test correction [`e0358d92053d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e0358d92053d6fe83a5351610cf9b34482f76a7a), paired owner-description display + exact hypothesis fingerprint in audit [`d42b5c2a9f5c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d42b5c2a9f5c383c93dd8e8e8711fa0894e957d3), project-deletion dependency register and archive-transaction guard [`42176b3ea90e`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/42176b3ea90eae7dcd891fe11170ec16839118d8).
- **Bounded feature:** `frontend/src/SemanticReviewPanel.tsx` under Your data lets the owner explicitly mark each current, field- and role-bound unverified hint `acceptable`, `needs_correction` (requires explanation), or `cannot_assess`, with optional note. The associated owner-authored field definition is visible beside the role, and existing owner-description form drafts and new review drafts jointly activate unsaved-change protection. POST requires the exact server-issued hypothesis SHA256, current Quality version, explicit decision and expected revision. SQLite `semantic_human_reviews` tracks current owner attestation; immutable `semantic_human_review_events` retains each saved revision, old/new decisions and exact reviewed hypothesis hash, without redundant explanations. All writes use immediate SQLite transaction, archive fence and compare-and-swap revision; no cross-project or cross-version migration. A changed hypothesis remains unassessed until explicit re-review.
- **Verified (source/real browser, no owner physical test):** [P3 focused #42520258684](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42520258684) **SUCCESS: 86/86 Python, 16/16 Node, TypeScript/Vite and Windows PowerShell split-status selftest**. [P3 real Uvicorn/Chromium #42520258801](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42520258801) **SUCCESS 3/3**, including a fresh owner-review save, discard, reload, edit, stale-revision rejection and independent project isolation. [P1 project lifecycle #42520258680](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42520258680) **SUCCESS 18/18** after impact inventory learned the two new review tables. [P1 real HTTP #42520258844](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42520258844) **SUCCESS**; previous related P1 frontend #42520105802 SUCCESS at `d42b5c2`. Earlier CI failures at initial implementation were test assumptions and missing deletion impact classification; retain their history, do not call them a product crash.
- **Phase truth:** P3-03 Option A **scoped source and real-browser implementation PASS; owner/native observation of the NEW manual review UI not yet demonstrated**. P3 remains ACTIVE; no P3 scope freeze or phase closure. Owner's later W5 "all is well" remains reported-success pending matching successful status ZIP independent review (earlier `181423Z-462deb4cae` ZIP is BLOCKED and not valid success evidence). W1–W4 remain accepted. No W5 retest requested. P4 NOT AUTHORISED, P8 release NOT CERTIFIED.
- **Next:** One bounded native Windows observation of the *new P3-03 human review UI* if required by owner/phase exit; do not repeat W5 or previously accepted W1–W4. Independently review a later successful W5 status ZIP if provided, then reconcile six P3 closure criteria and request separate owner approval before moving phases.

**Prepared:** 8 November 2026 | **Active primary phase:** P3 | **Authorised branch:** `feature/live-dev-workspace-20261023` | **Evidence baseline:** `9042c660ff541d4a012c7e3d637aa2a47f9bd841`

**Purpose:** Move from repeated W5 testing to the next genuine product decision. This is a proposed, unfrozen decision packet. No change in this document constitutes owner approval, user data verification, P3 closure, P4 authorisation or release certification.

## What is already proven and what is not

| P3 scope item | Verifiable evidence | Honest status | What is left |
| --- | --- | --- | --- |
| P3-01 deterministic hypotheses and abstention | Existing bounded backend/source contracts in the P3 acceptance register | SCOPED PASS | Do not rerun unchanged tests |
| P3-02 project/version-scoped owner descriptions and dirty navigation | Actual synthetic owner Windows W1–W4 status ZIP accepted 6 November; real-HTTP Save/reopen/editor tests | SCOPED ACCEPTED | None for the existing W1–W4 scope; release-specific checks are separate |
| P3-03a domain/grain/exact-column system-hypothesis vs human-description display | P3 hosted real-HTTP/browser and focused tests | SCOPED PASS, explicitly UNVERIFIED | No semantic truth/adjudication inferred |
| P3-03b unassessed/no-hypothesis/no-description states | Scoped source and real-HTTP owner-only-field browser tests | SCOPED PASS | No owner-review record or independent verification engine |
| P3-03 broader human adjudication, reconciliation and cross-workspace reuse | No authorised definition of independent truth or owner verdict lifecycle | **SCOPE DECISION OPEN** | Owner must include bounded manual-review record or explicitly defer it; no automatic agreement labels |
| P3-04 approved Quality v0→v1, semantic note version boundary | Real-HTTP W5 passed earlier, plus isolated real backend+SQLite and Windows runner self-tests through `9042c660`; owner now reports latest native W5 test **“all is well”** | **OWNER-REPORTED NATIVE SUCCESS, ARCHIVE NOT YET INDEPENDENTLY VERIFIED** | Collect most recent **completed** status-only ZIP if available; verify source/run/result. Do not repeat W5 |
| P3 closure | Frozen scope and six phase-exit criteria not yet signed off | **OPEN** | Resolve P3-03 choice, independent W5 evidence, risk reconciliation and written closure consent |
| P4 and P8 | Explicit phase policy | **NOT AUTHORISED / NOT CERTIFIED** | Separate permission and evidence |

**Important:** Earlier uploaded ZIP from run `P3-NATIVE-QUALITY-W5-20261108T181423Z-462deb4cae` was `BLOCKED` at older harness conditions. It cannot stand in for the new reported successful run. The user's “all is well” is valuable owner testimony; it does not give the last run ID, diagnostic ZIP content, exact local HEAD or independent verifier result.

## One owner scope decision: P3-03

### Option A | Implement bounded owner adjudication in P3 1.0 (recommended for a useful minimum)

Build a *manual*, version-pinned review record on each exact project/Quality-version/column hypothesis pair. Let an owner explicitly select `Reviewed, interpretation acceptable`, `Needs correction`, or `Cannot assess`, with optional user explanation. These are **owner attestations**, never independent semantic truth or AI-verified agreement. Data records would be stored separately from the imported dataset, scoped to version and project, auditable and editable, with explicit consent and no automatic carry-over when Quality changes. No training, target/model selection, automatic data correction, cross-view business truth propagation, private data transfer or external lookup.

Minimum proof before accepting this option: backend version/project isolation and staleness denial; cancel/no-write; consent audit; reload persistence; mismatch and unknown states; one scoped real-HTTP UI journey; a real Windows native check only where a new native behavior is introduced. No automatic “validated” badge. Owner must approve the exact option before implementing any persistent user-review mechanism.

**Benefit:** P3 produces an actionable human review state beyond side-by-side unverified text. **Cost/risk:** New persistence and consent workflow add scope and safety tests.

### Option B | Defer broad adjudication to a separately approved future phase

Freeze P3 1.0 as *deterministic unverified hypotheses + project/version-specific owner descriptions + explicit unassessed comparison states*, with a named residual: no adjudication record, independently validated meaning, conflict resolution, truth scoring or cross-view propagation. Those controls remain disabled/absent. Document why deferral is safe for those bounded capabilities, responsible future phase, owner acceptance and non-release limitations.

**Benefit:** Smaller immediate scope and earlier closure review. **Cost/risk:** P3 cannot truthfully claim a verified business ontology or resolved semantic contradictions.

**Decision update:** The owner subsequently selected **Option A**. Bounded manual field-hypothesis review is now implemented and scoped source/real-browser tested as documented above. This does **not** imply independent semantic truth or P3 closure.

## Six binding phase-exit criteria: current readiness

1. **Frozen scope and evidence mapping:** NOT MET. This is a candidate matrix pending P3-03 and native W5 review.
2. **No unresolved critical/high in-scope issues:** NOT ATTESTED. Current QA Issue #2 residuals need a focused in-scope classification, not a blanket “none”.
3. **Real UI/browser and native journeys:** PARTIAL. W1–W4 independently accepted; W5 latest owner-reported successful, no reviewed status ZIP yet. P3-03 broader scope undecided.
4. **Affected tests and build:** PASS for redesigned W5 harness at `9042c660`: [P3 #42512462060](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42512462060). This is not a native GUI certification.
5. **Durability, isolation, consent and rollback:** SCOPED PASS for prior W1–W4 and synthetic backend suites; broader P3-03 and current physical W5 archive cannot be assumed.
6. **Issue #2, exact SHA, two authoritative handoffs, owner signoff:** PARTIAL. Current handoffs and issue record historical evidence; final P3 scope and closure require separate owner signoff.

## Next engineering sequence, no repeat testing

1. Await one owner decision: **Option A** or **Option B** for P3-03.
2. If a successful W5 status ZIP exists, independently review it once; never repeat accepted UI actions merely to regenerate screenshots.
3. If A, implement one bounded manual-review capability and validate affected functionality; if B, write and request approval of a specific deferral/residual, with no invented new work.
4. Reconcile the six exit criteria and obtain separate, explicit P3 phase closure authorisation. Do not start P4 or claim P8.

**No action on real owner datasets, local build artifacts, installed apps, offline models or release assets is authorised by this proposal.**
