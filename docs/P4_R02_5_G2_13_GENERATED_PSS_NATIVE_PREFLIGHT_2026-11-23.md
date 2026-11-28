# PilotODIN R02.5 G2.13 | Generated-only Windows PSS feasibility prepared

**23 November 2026. SOURCE-ONLY CHECKPOINT. LIVE WINDOWS NOT AUTHORISED.**

## Deliverable
- `qa/p4_native/g213_generated_pss_probe.cpp`: standalone x64 MSVC and Windows SDK source. Compile-time `PSS_HANDLE_ENTRY` size/offset contract against the SDK; generated-only self-process with a single delete-on-close fixture inside GitHub `RUNNER_TEMP`; flags 0x14; full max-256 PSS handle walk; fixed-label `File` TypeName presence or absence; unconditional snapshot, marker, fixture cleanup. No PilotODIN, WebView2, ETW, Sysmon, owner files, network or installer.
- `.github/workflows/p4-r025-g213-generated-pss.yml`: trigger listens only for an **absent fresh marker**, has `if: false`, one-use exact SHA/direct-parent/2-file activation requirement, first-attempt hosted Windows guard. No marker or owner approval has been created and the workflow cannot run a native job today.
- `tests/test_p4_n12_g2_13_source_contract.py`: nine source/static tests enforcing the disabled workflow, synthetic-only path, PSS flags and ABI, exact root and cleanup rules, public fixed-label summary.
- Existing Ubuntu-only R02.5 source CI watches these files and runs the new tests. Source CI does not execute Windows PSS or compile MSVC.

## What remains unproven
The x64 layout (136 bytes; `TypeName` offset 64) is a **source-computed candidate** until the approved Windows SDK compile passes. Whether flags 0x14 expose TypeName `File` on an actual generated Windows handle remains **NOT_MEASURED**. Even a complete generated-only success cannot establish original WebView2 file-handle ownership, ETW FileObject/IRP correlation, request-time destination or strict R02.5 acceptance.

## Required separate approval
Before enabling this job: present exact merged source SHA, explicitly disclose that a hosted Windows executable will be compiled and invoked to snapshot **its own generated temporary file only**, and secure fresh one-use owner approval. Activation must change the job gate plus add a new 2-line approval marker, with no other changes. After the run, disarm, reconcile redacted fixed-label output and preserve blocked verdict if incomplete. **Do not reuse prior consumed N12 approvals.**

Four-gate delivery **G1 1/4 (25%)**, **G2 OPEN**. Official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**.
