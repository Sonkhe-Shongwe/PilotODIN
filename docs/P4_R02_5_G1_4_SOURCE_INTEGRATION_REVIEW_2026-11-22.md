# PilotODIN P4 R02.5 | G1.4 source compatibility and strict isolation

**22 November 2026. Source-only. No native capture, owner-data inspection, product launch, installer, acceptance or allowlist change.**

## GitHub baseline and reviewed seams

- Development branch: `feature/live-dev-workspace-20261023`, reviewed parent `39bd933e82673f675b41483fa229b4decdac57c4` (G1.3, Linux-only source CI [#45037803846](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45037803846) successful, 74 focused tests).
- New candidate `qa/p4_research/n12_fileio_pair_contract.py` blob `ffaf70be55e572e44a59fbf3994b37b3492d99c1`; physical-path candidate `qa/p4_research/n12_physical_destination.py` blob `babeaac8f207510162f848d15b696b6c1df4653d`.
- Existing strict FileIO correlator `qa/p4_native/n12_etw_correlate.py` blob `e6a16a540a0e57179775881b0bd447dbe5c69563`; strict no-CDP reviewer `qa/p4_research/n12_no_cdp_fileio_review.py` blob `11e13a58f84f0ee7b270a1842d3cdae8ad9433eb`; existing writer/handle join `qa/p4_research/n12_fileio_identity_join.py` blob `f9803a762a6b60f0b459c099d31ea8ce9dc61414`. The established strict reducer and native workflow are **left unchanged**.
- The governing 22 November audit kept only in an owner Windows tree is not available on this GitHub branch. No claim is made about uncommitted owner-local changes; by owner instruction GitHub is the source of truth for this source-only phase. Local/native state is a later permission-gated evidence matter.

## Source compatibility correction

The G1.3 candidate incorrectly required both FileObject and FileKey on every Event 24 OperationEnd. Existing generated N12 tests and the strict correlator show that completion may carry only IRP and Status. G1.4 accepts *absent or zero* Event 24 object/key fields as **not contradictory**, not as positive object evidence, while continuing to require:

1. One unique successful Event 16 request plus its uniquely ordered Event 24 IRP completion, with original writer PID/thread and strict boundaries.
2. Complete supplied original-file-handle/FileObject/FileKey corroboration, unbroken epoch, original writer lifetime, exact request-time physical path, permitted root handles, alias and loss proof. Supplied flags are untrusted claims, not native verification.
3. Rejection of **nonzero contradictory** completion object/key values, intervening FileObject/key associations, unknown operations, close, rename, same-timestamp name transitions, reuse, ambiguous or missing writer lifetimes and malformed evidence. Non-completion operations missing counterpart identities remain blockers.
4. An explicit boolean lifecycle flag when present, so malformed events cannot impersonate Kernel-File events.

## Independent original audit comparison

A new source-only test compares the *same generated cross-process parent-open / network-child-write* in the two existing viewpoints. The G1 private candidate may return `CONTAINED_CANDIDATE_ONLY` when every **synthetic caller claim** is set, while the unchanged strict correlator must still retain `webview-network:write:path-missing` rather than use the candidate as path credit. Additional tests retain redacted non-acceptance on prohibited, ambiguous and reused-IRP scenarios.

The updated Linux-only GitHub workflow now runs the two candidate suites, the new source-seam cross-test, and existing `n12_fileio_identity_join`, `n12_no_cdp_fileio_review` and `n12_mutation_triage` regressions. The workflow must remain Ubuntu-only, with read-only permissions and without any product launch or collector. The existing strict ETW tests are not changed.

## Verification and milestone boundary

**Prior to GitHub publication:** isolated Python 3.13 synthetic suites `35/35 + 43/43`, Python 3.11 grammar parse, no native actions. The cross-seam test and older strict suites require the full repository, and therefore must pass in exact-source GitHub Actions before G1 can earn 25%.

**G1 source-only exit**: published source baseline; original strict reducer/approval policy unchanged; source-level pair and destination contracts tested; original strict gap and historical violations retained; exact-source GitHub CI across old and new suites green; explicit separation of authenticated file-handle evidence into G2. Because there is still **no proven native original WebView2 file handle**, G1 creates **no** real path credit and **no** official acceptance.

**Never change these from source-only work:** original N12 filesystem FAIL, network FAIL, mutation coverage BLOCKED; historical file-mutation 3/4 (75%), R02.5 0/5, N12 0/2, official P4 14/20 (70%). The previously consumed N12 one-use capture approval is not restored. A new actual Windows capture still requires explicit source-pinned owner authorisation addressing network and privacy.

## Published G1.4 result and independent CI

- Source-only GitHub commit: [`8138117bcb4479af9e136db303461a61672dee8a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8138117bcb4479af9e136db303461a61672dee8a), precisely six approved source, test, workflow and documentation files; original strict reducer and native one-use workflows unchanged.
- [GitHub Actions run #45038916372](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45038916372): first attempt **SUCCESS** at that exact source, Python 3.11, Ubuntu-only, no app/native launch. Job logs prove **126/126 tests passed**, in six independent suites: 35 physical destination, 43 pair contract, 3 new strict-isolation integration, 12 existing writer-identity join, 25 no-CDP strict reducer, 8 historical mutation-triage tests.
- The generated cross-process case retains the original strict `webview-network:write:path-missing` gap despite a private `CONTAINED_CANDIDATE_ONLY` result. Optional absent/zero Event 24 object identities never count as positive corroboration and nonzero conflicts still block.
- **G1 source-only milestone: 1/4 gates = 25%**, while R02.5 0/5, N12 0/2, P4 14/20 (70%) and file-mutation engineering 3/4 (75%) remain unchanged. No native FileIO evidence, original file-handle proof or acceptance was obtained.
