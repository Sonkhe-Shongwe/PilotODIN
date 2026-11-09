# PilotODIN 1.0 | P4 native Windows acceptance kit

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
