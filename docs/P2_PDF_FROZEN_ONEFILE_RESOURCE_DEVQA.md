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
