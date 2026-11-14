# P4 increment 4 — two independent evidence axes for target opportunities

**25 October 2026. Owner-observed focused Windows verification PASS (screenshot), with limits stated below.**

## Accepted predecessor and evidentiary boundary
Owner screenshot of `Run_PilotODIN_P4_Prediction_Timing.bat` shows three phase PASS lines: `p4-timing-backend: PASS`, `p4-timing-node: PASS`, `frontend-typescript-vite: PASS`, overall `P4 timing review gate: PASS`. File shown `pilotodin-p4-timing-75gawth0.zip`, but the ZIP/logs have not been uploaded or independently inspected. Accept the third P4 increment as owner-observed **focused developer verification**, not complete native/release acceptance. Earlier P4 screening/context gates remain accepted with previously recorded limits.

## New fourth increment
P4 uses two separate notions that should not be collapsed into an invented business-value score:

1. **Technical readiness** is derived solely from observed label support and existing structural screening. State is `structurally_reviewable` or `structurally_blocked`. No predictive-success percentage is calculated. A structurally reviewable target is NOT confirmed safe from leakage, incorrect splits or unavailable predictors.
2. **Decision relevance** is `undocumented` or `user_described_unverified`. User text supports a documented *description* of intended business action, not its verified value, permission to use sensitive data, or truth of the recorded label.

`backend/target_opportunities.py` adds additive `assessment_axes` with these two independently labelled evidence states and preserved observed aggregates. Existing candidate qualification, blockers, ordering, `risk_review`, capped suggestions, manual target selection and abstention remain unchanged. `frontend/src/TargetOpportunities.tsx` displays two small labelled status lines for each reviewable candidate, explicitly saying they are not performance or business-value scores. No new storage, endpoint, model, training, privacy transfer, cloud call or Qwen dependency.

## Verification
NEW `tests/test_p4_two_axis_evidence.py` exercises independent states, missing/added user context, blocked rare label, reported fraud caveats, abstention, data privacy, deterministic ordering. NEW `frontend/tests/p4-two-axis-contracts.test.cjs` covers additive source state, invariants, UI and absence of training. One new local Windows launcher `Run_PilotODIN_P4_Two_Axis.bat` calls `tools/Verify_P4_Two_Axis_Local.py` to execute new and directly affected P4 Python/Node suites, plus frontend TypeScript/Vite build, all in isolated `PILOTODIN_HOME`, one `pilotodin-p4-axes-*.zip`. No old P0/P1/P3/P5/A4 replay.

**Status: source committed once applied; owner Windows focused check NOT YET EXECUTED.** A green focused gate will not prove business relevance, predictive metrics, native real-project UI, any original E-01–E-24 scenario, an offline installer or E2 licensed disconnected Qwen with combined 8 GB RAM.

**Next one owner action:** Pull the feature branch and run `Run_PilotODIN_P4_Two_Axis.bat` once. If red share one diagnostic ZIP; if green report PASS. Keep original data immutable, Quality approvals strict, target choice explicit. No hosted GitHub Actions, high-RAM AI, Qwen download or installer.

## Owner Windows focused acceptance (25 October 2026)

Owner supplied a Windows screenshot of `Run_PilotODIN_P4_Two_Axis.bat` showing `p4-axes-backend: PASS`, `p4-axes-node: PASS`, `frontend-typescript-vite: PASS`, `P4 two-axis focused gate: PASS` and `P4 two-axis focused gate passed`. Local diagnostic `pilotodin-p4-axes-897c8o37.zip` appears in the screenshot but was not uploaded or independently inspected; do not invent precise individual test counts/elapsed times. **Focused developer acceptance PASS**, not a real native-project UX or certified business value/model predictability. Roadmap transitions to deterministic P1/P2 reliability, with next active source work `docs/P1_UPLOAD_STAGING_ACCEPTANCE.md`.
