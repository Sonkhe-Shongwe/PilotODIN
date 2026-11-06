# P2-U2a | Actual PyInstaller Onefile Font Resource Probe

**Date:** 26 October 2026 (South Africa)  
**Branch:** `feature/live-dev-workspace-20261023`  
**Status:** SOURCE IMPLEMENTED AND STRUCTURALLY REVIEWED. **NOT YET EXECUTED ON OWNER WINDOWS.**  
**Scope:** Disposable **standalone frozen DevQA probe**, NOT the existing PilotODIN Python sidecar, native installer, renderer or final release.

## Why this gate exists

The owner has already confirmed on Windows:
- mixed reporting 3 runner + 9 report cases PASS; display/omission 5/5 PASS; corrected chart pagination visual PASS; distinct native development Save As hash evidence;
- all six pinned Noto font and three SIL OFL files verified and staged into a unique ignored build-review folder, without publishing a release asset;
- document-scoped U+1F4C8 PDF mapping under ReportLab 4.5.1, 9/9 units PASS, exact emoji extraction and identical raster bytes;
- build-only source preflight 7/7 PASS; simulated frozen package resource path 8/8 PASS plus six reviewed assets, `BUILD_REVIEW_RESOURCE_PATH_CONTRACT_PASS`.

The previous eight-case proof was a simulated module-relative directory test. It expressly returned `actual_frozen_sidecar=NOT_TESTED` and `actual_pyinstaller_add_data=NOT_CONFIGURED`. It **cannot** close actual PyInstaller onefile resource availability.

This increment builds and runs one truly frozen executable **containing only a narrowly scoped, standalone font-resource verifier**, rather than triggering the full heavy analytical sidecar/installer build. Even success remains a DevQA resource proof, not production-sidecar acceptance.

## File inventory

- `tools/p2_pdf_frozen_font_worker.py`: imports only dormant `backend.pdf_font_resources` and Python standard library; rejects ordinary unfrozen Python and requires `sys.frozen` plus `sys._MEIPASS`, module-under-extraction proof, exact `backend/assets/pdf_fonts` location, **exactly six expected files**, independent supplied SHA-256,size and three OFL text checks. Emits one bounded JSON object without file paths, font bytes, user rows, token or traceback.
- `tools/p2_pdf_frozen_font_onefile_devqa.py`: controller; verifies the **existing** completed review receipt and all six source Git identities; confirms local installed PyInstaller version **6.x only**; creates a fresh isolated ignored `build/p2-pdf-frozen-resource-probe/probe-<random>/`. Copies only six already-verified source files into a fresh six-file build-input directory; rechecks each copy. This avoids PyInstaller treating literal `[wdth,wght]` and `[wght]` in individual Noto font filenames as glob patterns. Packages that exact six-file directory into `backend/assets/pdf_fonts` using one `--add-data`, runs the resulting onefile executable from an otherwise empty and different working directory, sends expected measured development SHA-256s through bounded stdin, and verifies genuine frozen-process JSON, exact six-file match and zero exit code. Rechecks original and staged hashes after build. Records the isolated .exe hash/size and observed build/worker times. Does **not** claim peak RAM was measured.
- `tests/test_p2_pdf_frozen_font_onefile.py`: **eight authored, tiny synthetic unit contracts** for unfrozen refusal, correct directory-based add-data, traversal/duplicate refusal, absent/old PyInstaller, strict scoped-positive result, failing frozen worker, changed source before build, and missing executable. Unit mocks are **not** a substitute for the Windows real onefile run.
- `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat`: runs only eight new tiny synthetic contracts under existing `.venv-live`, then checks whether PyInstaller 6 is already installed in `.venv-live` or the previously existing `.venv`. It **never runs pip or creates a venv**. If neither environment has PyInstaller 6, it prints `BLOCKED` and does not build. If present, it requests explicit Y/N consent before calling the controller's `--build` flag.
- `.gitignore` explicitly blocks `/build/p2-pdf-frozen-resource-probe/` source-control inclusion.

## Failure prevention and operational boundaries

1. **Byte provenance:** The actual upstream source identities from the pinned Google Fonts commit and local six-asset OFL receipts are reverified; production-independent **release SHA-256 authorisation is still NOT granted**. The child checks the same measured six bytes from inside its PyInstaller extraction. Never present the development receipt as a vendor signature or license approval.
2. **No destructive output:** The controller uses a new random ignored build run and refuses existing directories rather than removing/overwriting prior work; no actual user project or app paths are used. It intentionally does not remove a failed run because its diagnostics and executable may be needed for inspection. Do not distribute these files.
3. **Bounded environment:** Build, cache and extraction TEMP/TMP are scoped inside the fresh run; refuse if less than 750 MiB free build disk; hard subprocess timeouts; no system font install, PIP, network download, model load, local user datasets or Tauri launcher. A blocked build is not a false PASS.
4. **Exact acceptance:** `SCOPED_FROZEN_RESOURCE_PROBE_PASS` requires PyInstaller to return zero, a real nonempty .exe, unchanged source and staged input SHA-256s, a frozen worker launched from a separate CWD, full six-file integrity+OFL verification in `sys._MEIPASS` and correct status. A unit-only green result, simply built executable, a malformed worker response or nonzero worker exit **must not PASS**.
5. **Privacy:** Console prints result status, stage, installed PyInstaller version, hash and size of the QA executable and bounded timings. It should not expose underlying absolute path, dev fonts or user datasets. Do not upload font binaries, frozen executables or raw PyInstaller caches. If blocked, provide only safe console output first.
6. **Remaining uncertainty:** The real default `desktop/Build_Python_Sidecar.ps1` still uses `backend/desktop_runner.py` and does NOT bundle fonts; release-side hashes, actual sidecar runtime, Tauri/NSIS, peak memory and startup performance under full workload, report paragraph/table/chart Unicode, concurrent real PDF requests, screen/printer visual/copy fidelity all remain **NOT_TESTED**.

## One new owner action, after pulling the established feature branch

Run `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat` **once, without Administrator elevation if possible**. It will run eight new synthetic tests, check existing Python build environments, then require explicit consent before a resource-only onefile build. Authorise `Y` only if you approve an isolated copy/build of the six previously reviewed public OFL resources. **Do not rerun** the earlier 8/8 simulated-path, 7/7 preflight, six-file staging, 9/9 CMap, mixed or disclosure launchers.

Share its final screenshot/result JSON only. If `PyInstallerMissing` or no installed 6.x venv, the correct outcome is `BLOCKED`, no install or unauthorized fallback. A successful run supports advancing to a **separate, explicit actual production-sidecar font embedding plan**, then tightly scoped real PDF paragraph/table/chart integration and page-by-page Windows visual acceptance. Do not mark P2 Unicode fixed or P8 release complete.

## Actual owner Windows run: 8/8 synthetic contracts PASS; frozen probe BLOCKED by missing PyInstaller 6 (26 October 2026)

**Observed console screenshot:** `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat` completed `Ran 8 tests in 0.222s` followed by `OK` (all eight focused contracts passed). It then reported `BLOCKED: PyInstaller 6 not found in existing .venv-live or .venv` and correctly exited without downloading, installing or freezing anything. **Accept 8/8 as scoped unit validation; actual PyInstaller onefile worker remains NOT RUN and NOT VERIFIED.** The output is a missing build dependency, not evidence of a broken CMap helper, corrupt fonts or production report regression. Do not run the same old launcher again unchanged and expect a different result.

**Approved-for-review recovery design, requiring fresh operator consent:** The official PyInstaller PyPI listing confirms `pyinstaller==6.22.3` is a published 6.x release and `pyinstaller-hooks-contrib==2026.9` is a published contemporary hooks release. Their paired versions are now explicitly pinned **for development tooling only**, not for the PilotODIN product. Sources: https://pypi.org/project/pyinstaller/ and https://pypi.org/project/pyinstaller-hooks-contrib/2026.9/. This is a limited supply-chain dependency; transitive PyPI wheels remain pip-resolved and **no hash-locked release-approval is claimed**.

New `tools/p2_pdf_pyinstaller_tooling_devqa.py` has a guarded `--prepare` operation. It creates **only** `build/p2-pdf-frozen-resource-probe/tooling-venv` (Git ignored) using an existing `.venv-live` Python; it never installs in `.venv-live`, `.venv`, system Python or project runtime. PIP invocation uses isolated mode, only official `https://pypi.org/simple`, binary wheels, pinned PyInstaller/hooks versions, bounded subprocess timeouts, no pip cache and no input; requires user approval. It does not touch user projects, original staged font files, normal PyInstaller sidecar script or actual releases. An incomplete or mismatched pre-existing tooling directory remains `BLOCKED`; the tool never deletes or silently overwrites it.

`tests/test_p2_pdf_pyinstaller_tooling.py` supplies **five NEW synthetic tests**, authored and structurally reviewed but **NOT executed on the owner's Windows**. Their tests check pinned package/index choices, no-write missing environment inspection, isolated venv setup flags, no overwrite, and clean blocked result for failed install. The new `Run_PilotODIN_P2_Prepare_Freezer_Tooling_DevQA.bat` runs these five cases, inspects any existing isolated tooling, asks **explicit first Y/N consent** before optional package download/install, and only upon a successful pinned version check invokes the existing `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat`. That existing launcher now also detects this third dedicated private tooling venv and requests **separate second Y/N approval** to build and run the onefile probe. A denied consent or missing Internet means BLOCKED, not FAIL and not a product issue.

**One next owner action:** After pulling the current feature branch while preserving local files, run only `Run_PilotODIN_P2_Prepare_Freezer_Tooling_DevQA.bat` once in normal (non-admin if feasible) Windows. Read the two authorisation prompts carefully: first for the development-only PyPI tooling installation, second for the optional frozen probe build. Do **not** manually install PyInstaller globally or rerun the older font, CMap, mixed report, 7/7, 8/8 resource path suites. Share safe console results, not fonts/executables/wheels. Even `SCOPED_FROZEN_RESOURCE_PROBE_PASS` would still mean only the standalone onefile resource seam, **not** the actual PilotODIN sidecar, licence release approval, Unicode PDF visual acceptance or final P2 completion.

## Second actual owner Windows run: private PyInstaller READY but source preflight BLOCKED (26 October 2026)

**Actual latest screenshot:** `Run_PilotODIN_P2_Prepare_Freezer_Tooling_DevQA.bat` advanced successfully through preparation to the nested `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat`. Its eight then-current mocked regression tests finished `Ran 8 tests in 0.153s`, `OK`. The launcher printed `Existing PyInstaller 6 found` and the owner explicitly consented `Y` to the isolated proof. The controller then returned `P2 ACTUAL ONEFILE RESOURCE DEVQA: BLOCKED`, `stage=source_or_build_preflight`, `failure_class=ValueError`, `actual_frozen_probe=NOT_VERIFIED` and `actual_pilotodin_sidecar=NOT_TESTED`. Crucially, the output did **not** include `Running isolated PyInstaller 6 ONEFILE DevQA build`, proving the build subprocess had not started. No reason to redownload fonts, recreate the review folder or reinstall PyInstaller.

**Source-level root-cause diagnosis (high confidence, still awaiting rerun evidence):** The previous launcher selected the dedicated PyInstaller-only venv's `python.exe` to run the **whole controller**, not just its PyInstaller builder. `verified_review_files` invokes `review_staged_copy` -> `audited_sources` -> `p2_pdf_font_asset_gate.verify`, which imports **ReportLab** to inspect font glyphs. The private tooling venv installs only PyInstaller/hooks and their dependencies and is not expected to have ReportLab. `verify` catches a failed ReportLab import as `REPORTLAB_FONT_REJECTED`, then `audited_sources` raises a generic `ValueError`. That is consistent with the observed source-preflight stage and lack of build output, but the screenshot does **not** expose the inner exception, so do not claim it was instrumentally confirmed on the owner's machine.

**Minimal correction, no app mutation:** The corrected `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat` invokes `tools/p2_pdf_frozen_font_onefile_devqa.py --build` using the already working **`.venv-live`** interpreter that has the ReportLab font-compatibility dependency. The controller's `build_arguments` now explicitly executes PyInstaller using the separately verified private `build/p2-pdf-frozen-resource-probe/tooling-venv/Scripts/python.exe`. `detect_existing_pyinstaller` delegates to the exact pinned-version, exact sys.prefix `inspect_tooling` check; it never installs packages. This separates source/font analysis and binary packaging instead of installing extra packages or changing existing app environments. The outer exception now emits `prerequisite_phase` (e.g. `verified_source_review` versus `isolated_build_location`) without leaking absolute paths or requiring a full traceback.

**Focused regression:** `tests/test_p2_pdf_frozen_font_onefile.py` now contains **nine** methods, including a new static launcher-to-controller environment boundary test. The earlier eight cases were observed passing before the fix; the revised **nine-case suite and corrected actual frozen build have not yet run on the owner's Windows**. The consent-based frozen launcher has no automatic download or package installation and asks for Y again before attempting a new uniquely named run; old partial runs are retained for diagnosis.

**One next owner action:** Preserve local changes, pull latest feature branch, run ONLY `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat` once (no need to repeat tooling preparation). Share console output only. A green `SCOPED_FROZEN_RESOURCE_PROBE_PASS` would establish only standalone onefile bundled-resource verification, not the actual PilotODIN production sidecar, installed app, Unicode PDF, release-approved hashes or P8 completion. On another `BLOCKED`, use `stage`, `prerequisite_phase` or worker failure class to make a specific correction instead of rerunning unrelated accepted suites.

## Actual owner Windows acceptance: isolated ONEFILE resource worker PASSED (26 October 2026)

**New owner console screenshot reviewed.** The corrected `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat` proceeded through the separately verified PyInstaller tooling, owner answered `Y`, and the console printed both `Running isolated PyInstaller 6 ONEFILE DevQA build (not the app)` and `Executing frozen worker from a different empty working directory`. Final result:

| Console field | Actual result |
| --- | --- |
| `state` | `SCOPED_FROZEN_RESOURCE_PROBE_PASS` |
| `stage` | `completed` |
| `actual_frozen_probe` | `PASS` |
| `bundled_six_files_verified` | `true` |
| `mapped_location` | `backend/assets/pdf_fonts` |
| `pyinstaller` | `6.22.3` |
| `exe_bytes` | `21192456` |
| `exe_sha256` | `f2de1fc0d29f6ff027ba42140b554280904867975b0e3f8382ae562b0cec7bc` |
| `build_seconds` / `frozen_start_seconds` | `10.58` / `0.86` |
| `run_id` | `probe-21a035f3a0a34e95830b7a5b2d999de4` |
| `peak_memory` | `NOT_MEASURED` |
| `actual_pilotodin_sidecar` / `actual_installer` | `NOT_TESTED` / `NOT_TESTED` |
| `release_font_approval` | `NOT_GRANTED` |
| `product_unicode_acceptance` | `NOT_TESTED` |
| `release_policy` | `BUILD_REVIEW_ONLY_NOT_DISTRIBUTABLE` |

**Accept ONLY:** An actual PyInstaller 6.22.3 frozen standalone DevQA worker ran successfully from a different CWD and verified all six correctly packaged font/OFL files from its module-relative extraction path, agreeing with the recorded source identity constraints. The latest screenshot is scrolled past the preceding nine-case test summary; the launcher reaches the Y/N and build steps only when that test command exits zero, but the individual updated unit counts are not directly shown in this screenshot. Never present the onefile worker as a frozen copy of PilotODIN's main `backend/desktop_runner.py`.

**Do NOT repeat** the already accepted standalone build, the previous nine-case corrected contracts, the historical mixed-report 3+9/disclosure 5, chart visual, CMap 9, source preflight 7, path 8 or six-file staging solely for documentation. No fonts or binaries may be checked into GitHub or redistributed from this temporary run.

**Next engineering scope:** This ends the *standalone* PyInstaller resource research milestone. The standard `desktop/Build_Python_Sidecar.ps1` still builds `backend/desktop_runner.py` using `.venv`, invokes pip and copies its output to Tauri after smoke. It was **not** used here. Do not silently add `--add-data` to that established release script or run it: it would alter active build environments/outputs. A separately authorized **real-sidecar opt-in build strategy** must address complete backend/scientific dependencies, frozen resource integrity, licence/source trust, SQLite/session isolation, release packaging and no user-data side effects. The design/acceptance record lives in `docs/P2_PDF_PRODUCTION_SIDECAR_FONT_GATE.md`. PDF paragraphs/tables/charts and end-user Unicode visual acceptance remain subsequent steps. P2 overall `REVIEW_REQUIRED`, existing production Unicode PDFs remain `VISUAL_FAIL`.
