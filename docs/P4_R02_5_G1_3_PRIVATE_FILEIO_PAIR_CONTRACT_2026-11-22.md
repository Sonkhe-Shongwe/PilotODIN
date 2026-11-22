# PilotODIN R02.5 | G1.3 private FileIO pair contract, source-only

**22 November 2026. Not a native capture, not a live reducer integration, and not an acceptance result.**

## Reviewed source of truth

- Repository: `Sonkhe-Shongwe/PilotODIN`, development branch `feature/live-dev-workspace-20261023`.
- Published HEAD on inspection: [`66d589f33a6e775c59dd0031d971109096d8e03d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/66d589f33a6e775c59dd0031d971109096d8e03d) (branch compare `identical`).
- Published physical destination module `qa/p4_research/n12_physical_destination.py`, blob `babeaac8f207510162f848d15b696b6c1df4653d`. Its focused test blob is `4bf13d7a2badb8f0aafef816d236c7eb68446047`.
- Strict native ETW correlator `qa/p4_native/n12_etw_correlate.py`, blob `e6a16a540a0e57179775881b0bd447dbe5c69563` (read only).
- No-CDP strict reducer `qa/p4_research/n12_no_cdp_fileio_review.py`, blob `11e13a58f84f0ee7b270a1842d3cdae8ad9433eb` (read only).
- Governing handoff: `docs/SESSION_HANDOFF_CURRENT.md`. `AGENTS.md` and a named 22 November local audit are not published on the reviewed branch and were not silently assumed to have been read.

## Exactly what this addition does

Two additive Python files form a pure diagnostic contract, complemented by one dedicated source-only GitHub workflow:

1. `qa/p4_research/n12_fileio_pair_contract.py` constructs an index of numeric event identity fields from caller-supplied Kernel-File records. It checks a unique Event 16 write request and Event 24 completion; issuing writer process/thread and their externally supplied lifetimes; independently claimed original handle FileObject/FileKey; and absence of relevant name/object transitions between handle observation and completed write. It then calls the existing `assess_private_destination` for a **candidate-only** root decision. It never logs or retains raw paths from ETW records, opens files, requests OS handles, starts a process, or updates the strict native reducer.
2. `tests/test_p4_n12_fileio_pair_contract.py` exercises synthetic cross-process browser/network write identity and fail-closed negatives for missing or reused IRPs, completion conflicts, rename/close/NameCreate/unknown operations, PID/thread/lifetime mismatches, missing proof flags, outside paths, malformed inputs and private-public output separation.

3. `.github/workflows/p4-r02-5-fileio-source-contract.yml` is a **new, separately reviewable** push-triggered `ubuntu-24.04` job for only these two focused Python suites and syntax checks. It has read-only repository permissions, pinned checkout/setup actions, no dependencies, no Windows/native collector steps, no application build and no user-data fixture. The workflow itself is a GitHub configuration change, and must not be published without the owner's separate source-only commit approval. The workflow is not a native acceptance run.

Index ingestion is linear in the number of ETW events, with grouped timestamp sorting at worst O(N log N). Repeated writes to a dominant FileObject are grouped into sorted numeric timestamp lists. Per-pair epoch checks search those lists rather than scanning all the ordinary writes afresh. This is a *source design property*, not a production benchmark or proof of whole-trace scalability.

## Trust boundary: what cannot be manufactured from source alone

The current strict `qa/p4_native/n12_etw_correlate.py` `canonical_file_path()` uses `casefold()` before returning a path. Its output therefore **cannot** serve as an independently verified exact-case request-time path for this candidate. The bridge blocks such mismatches; a real native source would need to retain and corroborate the actual physical path privately before any path assessment.

The `PrivateWriterSpan`, `PrivateOriginalFilePair`, `Corroboration` and `PrivateHandlePath` objects are **claims supplied by the caller**. They are **not authenticated** here. The existing `observe_supplied_windows_handle` Win32 adapter reads a handle-derived final path and volume serial, but **does not return an NT kernel `FileObject` pointer**. A user-supplied `(FileObject, FileKey)` tuple or an existing browser **process** handle cannot replace independently corroborated original **file** handle provenance. A `CONTAINED_CANDIDATE_ONLY` result on synthetic values grants no permission and does not close a strict path gap.

The following facts remain unproven until a separate, owner-authorised original-file-handle collector and full native evidence exist:

- Authentic ownership/acquisition of the exact original file handle for the actual write, and a trustworthy kernel object relation to ETW's FileObject/FileKey/IRP.
- Original writer process/thread birth and exit, process identity, browser child provenance, independent loss counters and complete capture.
- The actual request-time filesystem path epoch, reparse/alias evaluation, and observed physical destination on the real Windows host.
- Coverage of **all** operations including create/overwrite/rename/setinfo/FSCTL and the protected-root prevention controls. The pair contract examines only Event 16 writes; other file mutations remain subject to the unchanged strict reducer.
- Consistency of synthetic identities with the real ETW provider schema under Windows. The source-only event rows are not native test results.

## Required integration admission steps

1. Preserve the existing `inspect_etw_files` strict outcome and keep all unapproved/missing writes reportable. Do not import this module into the running no-CDP reducer until the exact native original-file-handle source and its permissions are separately reviewed and approved.
2. Determine whether the private collector can actually observe the original handle and bind it independently to the corresponding ETW FileObject and IRP. If not, return **BLOCKED**; do not substitute `GetFinalPathNameByHandleW` on a reopened file or claim that a process handle is a file handle.
3. Validate capture loss, request-time naming, name/identity reuse, root handles, actual volume and protected-root nonmutation on the same bounded capture. Failure or ambiguity must not be converted to a candidate PASS.
4. Evaluate whole-repo source/synthetic tests and exact source/hash manifests through separately authorised GitHub operations. The uncommitted candidate is not a new baseline and does not spend any native-run approval.
5. Only after fresh explicit owner consent may a new one-use source-pinned hosted Windows baseline be considered. Previously consumed approvals cannot be reused.

## Verification and scores

Local isolated Linux Python 3.13 source-only tests (no native operations):

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -p 'test_p4_n12_physical_destination.py' -v
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -p 'test_p4_n12_fileio_pair_contract.py' -v
```

**Source-only verification performed locally:** 74/74 focused tests passed (35 existing physical-destination + 39 new pair-contract tests). Both new Python files passed syntax parsing with the Python 3.11 grammar under the local Python 3.13 interpreter. The proposed workflow parsed structurally and its in-memory syntax-check command passed. These are **not** actual GitHub-run CI results or native Windows tests.

G1.3 code and the optional source-only CI workflow have not been committed or executed in GitHub Actions; no manual workflow dispatch, application launch, real original file handle access or policy change. Current remaining-work tracker: **G1 still in progress, 0/4 gates earned**. Historical engineering file mutation: **3/4 (75%)**; official R02.5 **0/5**, N12 **0/2**, overall P4 **14/20 (70%)**. Those figures must not change from a source-only synthetic candidate.

## Four-gate tracker boundary refinement (recommendation only)

The first **25% source-phase** should be awardable from published and source-tested
integration *contracts*, rather than requiring a real original-file-handle
capture that belongs to the **next 25% native evidence phase**. Proposed G1 exit:
verified baseline, published fail-closed path and pair contracts, passing
exact-source Linux-only GitHub CI, and explicit no-native-wiring caveats. The
real original file handle, authenticated process/IRP/physical path join and
actual protected-root native proof remain Phase 2 dependencies. This is only a
working tracker clarification, not authority to change native approval,
protected-root policy or official R02.5/N12 scores.
