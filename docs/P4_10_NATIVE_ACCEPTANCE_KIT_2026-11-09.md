# PilotODIN 1.0 | P4-10 Disposable Windows Native Acceptance Kit

**Prepared:** 9 November 2026  
**Active development branch:** `feature/live-dev-workspace-20261023`  
**Kit/CI source SHA:** [`e273bc0d554a131485f1457ab5c07b6a1f7b7fb2`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e273bc0d554a131485f1457ab5c07b6a1f7b7fb2)  
**Phase:** P4 ACTIVE; P1/P2/P3 development-CLOSED; P5 NOT AUTHORISED; P8 NOT CERTIFIED.

## Why this kit and not another unrequested development phase?

At the P4-09 checkpoint, focused synthetic P4 source, backend and real-HTTP browser tests passed. The remaining phase-exit gate demands **owner-observed native Windows/Tauri/WebView2 behaviour**, independently grounded business target provenance/usefulness and an explicit owner phase closure decision. CI cannot manufacture installed-app evidence. The owner's `okay next` after that checkpoint permits preparing a repeatable, non-destructive test aid without pretending to run the user's Windows desktop, changing the installed app or starting P5.

## Committed source artifacts

- [`qa/p4_native/generate_fixtures.py`](../qa/p4_native/generate_fixtures.py): stdlib-only local generator, must be given a **nonexistent destination directory**, which it creates; refuses overwrite if present. Creates five 80-row CSVs and `MANIFEST.json` with CSV sha256, plus the static README and results form. No network, binaries, original user data or model training involved.
- [`qa/p4_native/README.md`](../qa/p4_native/README.md): native provenance gate and safe manual outcomes. Read this before importing anything.
- [`qa/p4_native/RESULTS_TEMPLATE.md`](../qa/p4_native/RESULTS_TEMPLATE.md): deliberately unfilled native test matrix with **UNTESTED** cases, separate unverified real-world suitability evidence, owner closure **NOT APPROVED**, P5 **NOT GIVEN**, P8 **NOT CERTIFIED**.
- `tests/test_p4_native_acceptance_kit.py`: three synthetic generator and screening tests, including output checksums and never-overwrite validation.
- `.github/workflows/p4-target-ranking.yml`: triggers on kit files and includes kit self-tests with the existing scoped P4 synthetic CI suite. Existing P4-01–09 source, accepted training/Quality gates and native packaging unchanged.
- A standalone ZIP with five CSVs, manifest, short guide and results form is attached to this conversation, independently verified for ZIP integrity and per-fixture checksums. The repository source generator, not an EXE download, is the reproducible authority.

## Fixture expectations

| Fixture | Synthetic observations | Expected native *review* result on exact source-matched app |
| --- | --- | --- |
| `p4_classification.csv` | 80 rows, balanced churn 40/40, five outcome-like columns and repeated synthetic account IDs 80 nonmissing / 40 distinct | Human review cards and lower-ranked alternatives; **defer, decline, abstain** clear selected target safely; no automatic experiment |
| `p4_regression.csv` | 80 finite distinct `future_cost` labels and variable predictors | Structurally reviewable regression, not forecast accuracy or business value; project switch isolates session decisions |
| `p4_rare_class.csv` | Churn majority 76, minority 4 | Structural **blocker**, no automatically reviewable target |
| `p4_insufficient_labels.csv` | 24 labelled churn values, 56 missing | Structural **blocker** due to fewer than 30 labels |
| `p4_no_named_target.csv` | No named outcome columns | **Abstain**, no arbitrary numeric target suggestion |

**Never infer:** the observed repeated account ID pattern proves the true entity key, grouping is resolved, leakage absent, the selected target valuable, the label independently verified, or training authorised.

## Exact verified evidence

[P4 workflow #42594992258](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42594992258) was **COMPLETED SUCCESS** at the exact kit source commit `e273bc0d554a...`. Actual job logs: **52 Python tests PASS**, **21 Node source contracts PASS**, TypeScript/Vite production build **PASS**, and **3 disposable real-HTTP Chromium scenarios PASS**.

These checks establish source generator correctness and pre-existing P4 synthetic browser regression. They do **NOT** establish that a Windows app was built, launched, upgraded or tested. No native Windows test performed. No P1/P2/P3 workflow is claimed as rerun on this kit-only source commit.

## Owner run conditions and results

1. Check the *actual installed Windows app* and verifiable source/build provenance. A Git checkout HEAD or CI SHA is **not** proof the installed app includes P4-09. If identity cannot be proven, mark **N1 NOT TESTED/BLOCKED** and do not issue P4 native PASS.
2. Use isolated disposable projects and CSV fixtures only. Never restore/undo existing Quality history, edit originals, use real user datasets, train models, install new app packages or download AI weights as part of this P4-only acceptance.
3. Apply the specific expected outcomes in [kit README](../qa/p4_native/README.md) and record each actual **PASS, FAIL, NOT TESTED or BLOCKED** in the [results template](../qa/p4_native/RESULTS_TEMPLATE.md).
4. If a safe synthetic Quality-version procedure is unavailable, explicitly record that case **UNTESTED**; no destructive workaround.
5. Only after owner-observed native results and independent operational provenance, timing and decision evidence are recorded may the owner separately decide whether to close P4 with documented residuals. Neither a new kit nor another `next` authorises P5.

## Disposition

**P4-10 engineering / kit-scope ACCEPTED. Overall P4 phase remains ACTIVE / NATIVE ACCEPTANCE UNTESTED / OWNER CLOSURE PENDING. P8 NOT CERTIFIED.** Historical Critical/High release issues, including native Qwen3 and other workspaces, remain open in QA Issue #2. This artifact neither closes nor changes them.
