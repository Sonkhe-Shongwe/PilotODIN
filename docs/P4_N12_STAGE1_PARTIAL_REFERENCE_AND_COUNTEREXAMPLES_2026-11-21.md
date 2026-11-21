# P4 N12 | Real-observation partial golden fixture and backward counterexamples

**21 November 2026. SOURCE-ONLY.** Implemented from the reference-first [success contract](./P4_N12_STAGE1_GOLDEN_REFERENCE_AND_BACKWARD_VERIFICATION_2026-11-21.md) and [S01-S11 worksheet](./P4_N12_STAGE1_SOURCE_EVIDENCE_WORKSHEET_2026-11-21.md). No owner device, native Windows app/WebView2, installer, firewall, data change or model was executed.

## Independent reference boundary

The new redacted [partial reference JSON](../qa/p4_research/fixtures/n12_stage1_partial_reference_44893498723.json) is a **derived record**, not raw events, original handle timestamps or a reproducible full process trace. It pins the approved [native diagnostic #44893498723](./P4_N12_STAGE1_NATIVE_SYSMON_ETW_EXIT_CLOCK_DIAGNOSIS_44893498723.md) to exact reviewed source **41eaa3b240d621491ed0aec3a7a8ae227d92a626** and one-use activation **d55a956fd4f691f91549fb574507325fad506505**.

App and launcher each had original-handle birth/exit exactly equal ETW (0 ticks), with Sysmon Event 5 exit preceding ETW by **77,625 ticks** for the app and **32,932 ticks** for the launcher. Their ETW births were respectively **8,582** and **6,393 ticks** later than Sysmon births. Six ordinary WebView2 and one WebView2 network child were observed, but **zero of seven original child query handles** were retained in the historic evidence. Every original-child-handle status is explicitly **MISSING**, not a placeholder success. ETW capture counters reported zero lost events/buffers and five written buffers, but polling completeness is unproved. The protected endpoint comparison matched; it cannot exclude transient writes. Strict native Stage 1 remains **BLOCKED** and full N12/FileIO/network remain **NOT EVALUATED** in this run.

## Executable backward checks (actual implementation, not intended behavior)

The existing routine P4 test file [test_p4_n12_source_evidence_map.py](../tests/test_p4_n12_source_evidence_map.py) now validates the redacted reference and rejects fabricated full-green, invented child original handles, forged source/clock parity, altered observed offsets, newly claimed ETW loss or extra success fields. The numeric values are **historical measurements, not tolerances or new universal admission criteria**.

The existing synthetic original-handle observer fixture is used to demonstrate a specific Q2 inconsistency:

- Synthetic child born at observer-relative tick 210,000, **still running and sampled** at 250,000, with its original handle later reporting exit at 640,000, retains verified parent/image and ETW matching in the fixture.
- The real *private diagnostic* rejects the 250,000 sampling start with \`private-evidence-child-outside-sampling-or-profile\` **solely because child birth is before the sampling start**.
- With an otherwise identical 200,000 sampling-start field, the same original handles, parents, images and ETW events produce **REVIEWABLE_ONLY**, never native PASS.

This proves a **source-contract overrestriction counterexample** in the diagnostic, not what happened for any of the seven real WebView2 children. It does not authorize relaxing the strict native verifier or inventing missing original handles. A separate synthetic variation confirms that the current join rejects an all-WebView-role tree as \`browser-role-coverage-missing\`; whether a network child is universally mandatory remains unestablished. No permission or strict acceptance changes were made.

## Focused verification and outstanding decision

**Planned focused check:** \`python -m pytest -q tests/test_p4_n12_source_evidence_map.py\`. The routine P4 workflow includes this existing test file and should test exact changed code on push. Its CI result and last stage must be reported separately after inspection. A source-only passing fixture never earns N12 or R02 points.

**Next decision-relevant work:** Review the timing provenance of a retained original handle opened after a child's birth, determine whether to correct the QA-only diagnostic birth inequality, and independently justify cross-provider Sysmon Event 5 versus ETW ExitTime semantics with additional adversarial variants. Preserve full PID+birth, GUID, parent, exact images, ETW loss/sequence and capture window checks. No blanket 8 ms tolerance, no weakening of the strict native reducer, and no assumptions of a fixed seven-child role mix.

**Official checkpoint unchanged:** P4 **14/20 (70%)**; file mutation **3/4 (75%)**; N12 **0/2**; R02.5 **0/5**; desktop network **2/3**. A real source-pinned native run needs separately granted fresh one-use owner approval; the workflow remains disabled and its old marker absent.
