# PilotODIN 1.0 | P4 native Windows acceptance kit

## P4-16 current-source installer integrity check (new, read-only)

The original `p4-native-v1` CSV fixtures below remain applicable **only as synthetic examples**; their historical source-lineage note does not certify the new QA installation. P4-16 produced a distinct `pilotODIN-P4-Native-QA` candidate from source `bca3c57b94a425cd9ef489726e721328d12c2ead`, whose **disposable CI** provenance passed in [run #42621192759](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42621192759). Owner PC still NOT TESTED.

Before *any separately approved* owner milestone installation, obtain `source-and-windows-artifact.json` from that exact trusted GitHub workflow and the matching extracted QA NSIS file (if still available). An optional standalone, **non-executing and non-installing** integrity check is:

```powershell
py qa/p4_native/verify_qa_installer_provenance.py --manifest "C:\\QA\\source-and-windows-artifact.json" --installer "C:\\QA\\pilotODIN-P4-Native-QA_1.0.0-alpha.1_x64-setup.exe" --expected-source bca3c57b94a425cd9ef489726e721328d12c2ead
```

Requires Python only for this **developer QA helper**, not the shipped desktop app. It checks source and QA/production IDs, CI/safety flags, installer filename, byte size and SHA-256, and rejects mismatch. The manifest must be sourced independently from GitHub; the helper does **not** establish authenticity of the supplied JSON, certify origin by signature, safely install software, verify old-app coexistence or approve a release. Synthetic helper tests: `python -m pytest -q tests/test_p4_installer_provenance.py` (21 local cases passed on 9 Nov 2026; not a Windows test). Never install the candidate without explicit separate owner consent. After verified owner-side installation, fill only actually observed N1–N10 and business evidence in [Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9).


**Kit:** p4-native-v1, 9 November 2026. All values are invented. This is a **manual test aid**, not proof of running the app or permission to close P4.

## Before importing anything

1. Use a **disposable test environment** and fresh, clearly labelled *synthetic* PilotODIN projects only. Do not open/edit/overwrite existing owner projects, Quality history, models or reports. Do not trigger a training experiment.
2. Record Windows version, application version, Tauri/WebView2 identity if available, and **verifiable native build/source commit** in RESULTS_TEMPLATE.md. The current P4-tested application source before this kit was **e855d945139267e9a16104fb43cb24b9150fb3dc**. This is a **minimum source lineage reference**, not a claim your installed executable contains it. A Git checkout SHA or CI result **does not prove installed app provenance**. If the installed version cannot be tied to an exact P4 source commit, leave native acceptance **NOT TESTED**.
3. Do **not** build an installer, download runtime/model weights, alter registry/services or move the source database. If the native application cannot run safely in its current state, record **BLOCKED / NOT TESTED** and stop.
4. The five CSV files and MANIFEST.json must remain together. The manifest hashes validate **CSV fixture bytes only**. They do not verify the app, labels, business meaning or model predictions.

## Test protocol (only if native build provenance is established)

Create a **new imported project per CSV**. Open **Prepare**. Use only the existing target controls, review disclosures and project selector. Do not open Model Lab to train anything.

| CSV | Expected visible behaviour in a source-matched build |
| --- | --- |
| \`p4_classification.csv\` | 80 rows, balanced \`churn\` labels. Five possible outcome columns (\`churn\`, \`fraud_reported\`, \`failure_flag\`, \`outcome\`, \`future_cost\`) support top-three and alternative review paths. \`account_id\` has 80 nonmissing values / 40 distinct / 40 additional occurrences, a **question** for grouped validation, not proven leakage. Review → Defer → Review → Decline → No prediction objective should be explicit and not create an experiment. |
| \`p4_regression.csv\` | \`future_cost\` is a structurally reviewable numeric regression hypothesis, not verified forecast value. Any target choice is manual. Switching here from classification must not carry a selected target or deferred/declined status. |
| \`p4_rare_class.csv\` | \`churn\` has 76 vs 4 observed classes; the 4-row minority is structurally **blocked**. No recommended training-ready target. |
| \`p4_insufficient_labels.csv\` | \`churn\` has 24 labelled rows / 56 missing; structurally **blocked** by the minimum 30 labelled rows. |
| \`p4_no_named_target.csv\` | All candidate columns lack supported outcome-name cues; the recommender should **abstain**. Manual selection remains available but carries no P4 suitability approval. |

On classification, also review the lower-ranked candidates, inspect the bounded evidence disclosures, and select then clear a target. On a regression project, check that the selected-target checkpoint shows the numeric task hypothesis and caveats. Return to classification: prior temporary defer/decline/abstain decisions should not survive the project switch as cross-project judgments.

For a Quality-version boundary, only use an **already approved, harmless, disposable synthetic** Quality workflow. If a safe procedure is unavailable, mark **UNTESTED**, not PASS. No direct database writes or destructive undo/restore steps.

## Recording and disposition

Copy RESULTS_TEMPLATE.md and fill in each case with actual **PASS / FAIL / UNTESTED / BLOCKED**, a brief observed outcome, exact installed native identity and sanitized screenshot/log references where appropriate. If the installed app predates P4-08/P4-09, that is **NOT TESTED for the current source**, not a test failure of this commit.

Never send sensitive data or credentials in the notes. Escalate reproducible defects to GitHub QA Issue #2 with expected/actual behaviour; preserve historical defects.

**P4 remains ACTIVE** until missing operational label/provenance/decision-timing evidence and verified native results are reviewed and the owner explicitly approves scoped P4 closure. A green synthetic CI and this kit do not authorise P5 or certify P8.
