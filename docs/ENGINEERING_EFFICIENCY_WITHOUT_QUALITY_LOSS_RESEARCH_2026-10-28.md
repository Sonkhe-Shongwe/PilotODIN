# PilotODIN 1.0 | Research: Engineering Efficiency Without Quality Loss

**Research date:** 28 October 2026 (SAST)  
**Active development branch reviewed:** `feature/live-dev-workspace-20261023`  
**Source checkpoint at review:** `4e274c5cc0a5c1dc953ba8126274d3a0f35ae727` (documentation-only commits may move HEAD)  
**Status:** RESEARCH / RECOMMENDATIONS, **not** approval to restructure CI, install new dependencies, remove tests or weaken the original blueprint.

## Owner requirement

Preserve accuracy, professionalism, data safety, offline/local-first design, deterministic analytical integrity, manual approval for destructive/meaning-changing actions and meaningful Windows acceptance. Reduce unnecessary repetition and late discovery of defects. Keep complexity-last sequencing for large implementations, with early narrow feasibility evidence for dependency risks.

## What was verified directly in the repository

1. The source has **nine existing GitHub Actions YAML workflows** under `.github/workflows`. `frontend-compile.yml`, `live-dev-smoke.yml` and `live-dev-backend-tests.yml` are **manual workflow_dispatch**. `build-e-verification.yml` and several installer/native workflows automatically trigger on **build-e** or designated release tags, **not** on every push to `feature/live-dev-workspace-20261023`. Do not propose replacing existing pipelines; extend only after review of triggers, secrets, costs and actual tests.
2. `frontend/package.json` already provides `npm run test:workspace` (Node test runner) and `npm run build` (`tsc --noEmit && vite build`). `frontend/package-lock.json` exists on the reviewed branch, permitting reproducible `npm ci`; workflows should not silently switch to unlocked `npm install` when the lockfile exists.
3. The `frontend/tests` directory contains **66 files**, including substantial P1/P2 regression contracts. Several P1 tests (for example `p1-external-route-activation-guard.test.cjs` and `p1-preupload-consent.test.cjs`) extract strings/functions from `App.tsx`/`UnifiedShell.tsx`, transpile or replay them against mocks, and perform regular-expression source assertions. This is useful for pure contracts, but **does not prove mounted React/DOM behavior**.
4. The last accepted P1 checkpoint has **41/41 owner Windows tests and TypeScript/Vite build PASS**, plus **real Chrome pre-upload warning → Cancel → original project, edited dock and selected upload file retained**. Screenshot alone is not an independent backend network trace. Older 49-case external project/route/restore, 24-case direct-load, hash-cancellation and two-tab browser smokes remain separately accepted. Do not repeat them reflexively or add unrelated historical totals into one purported system-wide run.
5. Risk-bearing outstanding phases include primary Studio form draft lifetime, reload/history semantics, real below-width dock pause, P2 production Unicode/report fonts, measured concurrent 8 GB offline AI+ML, P6/P7 Master modes and local model inference, and P8 clean offline Windows E-01–E-24 release. The dated P0–P8 reflection notes that tests at different commits cannot be added up as a single full-system pass.

## External research and how it applies

### A. Small reviewable changes, fast feedback, not rushed work

DORA's small-batches and continuous-integration guidance supports meaningful, independently testable changes and rapid feedback while preserving a stable working baseline. Keep bounded implementation increments and explicit acceptance. **Do not** generalize this into a requirement to merge unreviewed AI-generated code, rush release, or abandon the feature branch.

Sources:
- https://dora.dev/capabilities/working-in-small-batches/
- https://dora.dev/capabilities/continuous-integration/
- https://dora.dev/capabilities/test-automation/

### B. Test observable user behavior above brittle implementation details

Testing Library and Playwright prefer tests that act on user-visible elements and observe outcomes. PilotODIN's source-extraction tests should remain as guardrail tests where valuable, but **new critical UI regressions should first be covered by a real mounted browser harness**, not another regex alone. Concrete pilot scenarios:
- Existing project A, Quality primary + Prepare secondary, edit target, attempt external hash promotion, choose Cancel: assert URL, active tab, primary heading, secondary target, and no duplicate.
- Two isolated browser pages/tabs with shared test-origin storage and independent in-memory drafts: switch B in tab 2, Cancel in tab 1, assert both final projects and warning. Never seed actual user projects.
- Existing edited dock + harmless local file: click Analyze dataset, Cancel native confirmation: assert **zero upload HTTP requests** and original dock/selected file preserved.
- Responsive narrow viewport: assert the edited dock pauses without losing selected input and resumes on widening.

Use stable role/label/accessible-name locators, avoid CSS class and brittle snapshot-only assertions. Capture local Playwright trace on failure; sanitize fixtures and artifacts so actual user data, file paths, private project names or model prompts are not uploaded to CI. Use an explicit temporary developer database/origin; CI must not run against production/owner data.

Sources:
- https://testing-library.com/docs/guiding-principles/
- https://playwright.dev/docs/best-practices
- https://playwright.dev/docs/trace-viewer
- https://playwright.dev/docs/ci

### C. Adapt existing CI rather than add a second infrastructure

A cautious CI pilot: add an isolated **frontend fast verification** path for changes to `frontend/src/**`, `frontend/tests/**`, lockfile or relevant workflow itself on the active feature branch or pull request. Start with `npm ci`, `npm run test:workspace` and `npm run build` on Windows; compare with the existing `frontend-compile.yml` and `live-dev-smoke.yml` to avoid duplicates. Use GitHub Actions job/artifact receipts bound to **commit SHA, OS, runtime, commands and exit status**. Leave expensive sidecar/native bundling **manual or separately gated** until the installer risks, dependencies and cost are reviewed. Test workflow changes in a scoped dry run before relying on them as authority. Dependency caches must not contain secrets or sensitive data.

Sources:
- https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching
- https://dora.dev/capabilities/continuous-integration/

### D. Risk-tiered evidence instead of repetitive manual verification

Recommended minimum gates (all **additive**, never substitutes for correctness):

| Change and risk | Fast local / CI | Integration | Human/real-system acceptance |
| --- | --- | --- | --- |
| Pure UI / layout logic | Focused unit + typecheck | Mounted React/browser behavior where relevant | One new meaningful interaction if automation doesn't fully cover it |
| Routes, navigation, input retention | Focused pure guard | Real browser flow with DOM + URL + HTTP/no-write checks | Windows smoke of novel behavior only |
| Data Quality, import, ML safety | Fast deterministic contracts | Isolated real backend and disposable datasets, consent/no-side-effect checks | Owner acceptance for irreversible or meaning-changing actions |
| PDFs / Unicode exports | Renderer, extraction, fonts, exact evidence | Real PDF visual/copy/search test and package-specific font loading | Human visual and production bundled binary when affected |
| Offline AI and Master modes | Typed tools, citation/version checks, adversarial tests | Fixed evaluation dataset with error/abstain and 8GB measurements | Real hardware/offline/resource acceptance before claiming readiness |
| Native release | Locked builds + checksum + smoke | Clean offline installer and E-01–E-24 full evidence | Owner final release sign-off |

Retain all accepted regression cases. Run the *affected set* on small changes; run broader relevant suites periodically, before merges, and when cross-cutting/shared code changes; run the full release matrix at P8. A source-only pass is never a browser pass; a browser pass is never an offline installer pass.

### E. Reusable deterministic datasets, AI evaluation and honest stopping

Maintain small, synthetic, versioned fixtures for CSV/XLSX mixed dates, Unicode/non-Latin text, missing/null records, duplicates, identifier leading zeroes, tiny/sparse datasets, leakage traps, unbalanced labels, time/group splits and invalid targets. Preserve expected output contracts (rows, hashes, schema, missing-value semantics, versions and permitted actions). Test positives and deliberate **abstentions**. Provide privacy-safe `pytest tmp_path` isolation for backend and a dedicated temporary browser test origin. NIST AI RMF recommends documented datasets, test methods, benchmarks and measurable validity/reliability, and OWASP recommends limiting AI privileges, validating tool inputs/outputs and retaining human approval for high-risk actions.

Sources:
- https://docs.pytest.org/en/stable/how-to/tmp_path.html
- https://airc.nist.gov/airmf-resources/playbook/measure/
- https://genai.owasp.org/llmrisk/llm01-prompt-injection/

### F. Test hard feasibility early, not full autonomy early

Preserve the approved complexity-last feature sequencing. Create *isolated, opt-in proof gates* for (i) actual local model response + reliable version-grounded evidence, (ii) simultaneous local AI/ML RAM and UI responsiveness on an 8 GB Windows machine, and (iii) actual sidecar/Unicode fonts in a clean offline binary. Do not replace actual 8 GB measurements with synthetic resource-policy tests, or a real production PDF visual inspection with an isolated font-path contract. These early probes avoid large dependency mistakes while leaving full P6–P8 implementation for the planned stages.

## Proposed trial order (NOT YET IMPLEMENTED)

1. **Record baseline:** time from code commit to trustworthy feedback, number of user manual actions, browser-only escaped defects, failed QA gates, and which test environments were actually used. No fabricated ROI numbers.
2. **Pilot one browser test on the next primary-form-draft work:** initially one read-only/synthetic route/dock scenario. Run it locally against disposable state and confirm no user dataset access. Compare results with existing Node source contracts.
3. **Review existing CI triggers and add only a scoped fast-check workflow when safe:** no native installer, model downloads, training or font release changes; preserve owner choice about running it automatically.
4. **Gradually cover only high-risk browser journeys** (URL Cancel, cross-tab Cancel, pre-upload no-write, narrow dock). Retain focused source tests and stop writing duplicate tests with no additional detection value.
5. **Add a release evidence matrix**, updated once per meaningful gate: code SHA, Windows/Python/Node/browser, test path, user acceptance, outcome PASS/FAIL/OPEN/BLOCKED, and whether dataset mutation or network calls were possible.
6. **Measure trial outcome after several increments:** compare escaped browser defects, manual minutes, test flakiness and rework. Keep a change only if it maintains or improves coverage and reduces repeat cost.

## Non-negotiable safeguards

- No weakened user consent, data lineage, rollback, privacy or model versioning.
- No AI-generated conclusion without evidence/reference state or explicit uncertainty/abstention.
- No auto-import, auto-training, Quality approval or installer merely to exercise a test.
- No storing arbitrary inputs, real project records, passwords or local paths in CI artifacts/traces.
- No promoting synthetic test results into claims of real Windows/browser/PDF/offline release acceptance.
- No broad automated release workflow without explicit review of its destructive effects, privileges and data location.

## Recommendation

**Optimize our QA feedback loop before optimizing implementation speed.** Start with one narrowly scoped browser integration test complementing existing deterministic Node checks, then assess a safe re-use of GitHub's existing frontend verification workflow. This preserves the architecture and documented roadmap rather than replacing them. This document records research, **not a newly accepted workflow or scope change**.
