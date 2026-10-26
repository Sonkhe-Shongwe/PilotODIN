# P2-U2b | Actual PilotODIN Python Sidecar Font Inclusion Gate

**Decision record:** 26 October 2026, after the owner's real `SCOPED_FROZEN_RESOURCE_PROBE_PASS`.  
**Status:** RISK-REVIEWED PLAN, NOT YET IMPLEMENTED OR EXECUTED.  
**Repo/branch:** `Sonkhe-Shongwe/PilotODIN` / `feature/live-dev-workspace-20261023`.  
**Authority:** `docs/SESSION_HANDOFF_CURRENT.md` and verified source. This document does not authorize an installer build or production font rendering change.

## 1. Exactly what is now proven

The owner successfully executed the standalone PyInstaller 6.22.3 ONEFILE resource probe with six previously verified Noto font/OFL files embedded at `backend/assets/pdf_fonts`. Its frozen-worker result is `SCOPED_FROZEN_RESOURCE_PROBE_PASS`; build time 10.58 s, frozen execution 0.86 s, executable 21,192,456 bytes, and all six files reverified in the unpacked module-relative path. This proves **PyInstaller resource packaging mechanics in the narrow standalone worker**, including filenames with square brackets. It does **not** certify the real `pilotodin-engine`, release-approved font provenance, ReportLab PDF shaping, RAM peak or Tauri/NSIS.

## 2. Verified actual application seams

- `desktop/Build_Python_Sidecar.ps1` presently creates/uses `.venv`, **installs** all `backend/requirements.txt` plus `pyinstaller>=6,<7`, builds **`backend/desktop_runner.py`** into a onefile scientific Python engine and writes into `build/py-dist`. It runs `desktop/verify_packaged_engine.py`, then **overwrites/stages** the binary under `frontend/src-tauri/binaries`. These are inappropriate side effects for an exploratory font gate.
- `backend/desktop_runner.py` checks the Tauri session/home/port env before importing `uvicorn` and `backend.main` and launching a localhost FastAPI server. It does not import `backend/pdf_font_resources.py` or run font validation; the latter remains dormant. A raw build with `--add-data` cannot prove the runtime actually **uses or verifies** those assets.
- `desktop/verify_packaged_engine.py` already provides a useful isolated-smoke pattern: private random token, temporary `PILOTODIN_HOME`/SQLite, loopback health/401/403 tests, and Windows process-tree cleanup. Reuse the contract when a real-sidecar probe is authorised; never point it at an actual user project directory.
- `frontend/src-tauri/tauri.conf.json` expects externally staged sidecars and separately lists resources including licences. A sidecar-only DevQA build must **not** touch Tauri binaries, NSIS, `tauri.conf.json`, existing installer outputs or existing Qwen assets.
- `backend/requirements.txt` includes FastAPI/Uvicorn, pandas, numpy, scikit-learn, openpyxl, joblib, Pydantic and ReportLab, none of which can be assumed present in the tiny private PyInstaller-only tooling venv. The existing `.venv-live` has owner-proven ReportLab, but not necessarily a ready PyInstaller installation. Avoid using `--paths` to borrow compiled packages from a second virtual environment without a reproducible ABI/import-path proof.

## 3. Minimal allowed implementation sequence

**Gate A: No-write dependency and resource readiness.** Add one read-only development check that inspects installed packages, exact Python architecture/version and wheel availability in candidate build environments, available disk/RAM and the reviewed six-file `receipt.json` + pinned upstream Git blob identities. Do not install, download, mutate Python envs or stage binaries. Record all gaps as `BLOCKED` with safe reason classes. Do not regenerate fonts. Keep this gate distinct from user project data.

**Gate B: Explicitly approved reproducible BUILD-ONLY environment.** Prefer a freshly created Git-ignored build-only interpreter with complete native backend dependencies and pinned PyInstaller after comparing cost with existing functioning envs. It must never change `.venv-live` or `.venv`, and any network dependency installation must receive separate user consent. Pin and review the dependency resolution/ABI and disk footprint. Do not assume `--onefile` native/scientific packaging can be recreated using the small-font-probe environment.

**Gate C: A separate real-sidecar proof, no product staging.** Produce a new, unique, ignored DevQA build directory. Build `backend/desktop_runner.py` with the production-equivalent hidden imports and `sklearn/scipy` collection **plus** one six-file `--add-data` directory from a fresh reverified build input. Do not edit the accepted main PowerShell builder for this test. Prove the six packaged bytes inside the *actual* engine's extracted process using a separate opt-in scoped mechanism, such as a verified PyInstaller runtime hook that validates the bundled font file set before application imports, with a hard fail-closed result if any asset is absent/tampered. The hook may only use code-pinned reviewed development hashes, not blindly trust an adjacent mutable `receipt.json`; it must be removed from any production release until independent source/license approval. Do not add a general environment override, font downloads or mutable home-directory fallback.
 
**Gate D: Native-runtime safety proof.** Run the true frozen engine with temporary session token, randomly reserved loopback port and disposable `PILOTODIN_HOME`. Check prior 401 unauthorized, 403 untrusted Origin, authenticated health/project listing, no model startup, no existing project reads, SQLite handle release and full process-tree shutdown. Ensure resource-verification failure cannot silently degrade into wrong-font PDF output. Verify the actual smoke output and a separate resource attest, not just PyInstaller return code. Record exe size, frozen startup and observed peak memory if instrumented; don't invent memory measurements. 
   
**Gate E: Production rendering integration (separate focused patch).** Only after licensed exact font pack availability in real sidecar is proven, wire the already Windows-accepted `DocumentUnicodeTTFont` with mixed-script font selection into actual `backend/reports.py` paragraphs, tables, footer and vector `backend/report_charts.py` label/caption text. Check ReportLab global face-name alias concurrency, no private rows/holdout predictions, unchanged saved revision hashes, certified arithmetic/denominators, unclipped A4 pages, long CJK strings, emoji extract/copy fidelity and explicit unsupported-sequence policy. Run the smallest affected synthetic reports and manually inspect generated Windows PDFs. These are not implied by any earlier font resource PASS.

**Gate F: Installer/release approval (later):** Separately approve full SIL OFL notice inclusion and verified, independent release SHA-256s/asset manifest; ensure truly offline resource bundling and acceptable memory/size. Actual Windows NSIS clean install and full P8 E-01–E-24 remain independent and unaccepted.

## 4. Failure scenarios the next code must explicitly cover

- Single package absent from selected builder; PyInstaller hooks/cross-env ABI or native DLL missing; build fails after expensive work; reproducibility dependent on an unpinned pip resolution.
- Wrong font filename mapping because `[wdth,wght]` or `[wght]` is expanded as a glob; incomplete six-file copy; file altered between preflight, copy and PyInstaller build; incorrect OFL notice; source directory redirected through a junction.
- PyInstaller resource packaged but never found/read at real runtime; checking a DevQA receipt instead of real extracted data; silent fallback to OS fonts; incorrect sys._MEIPASS vs module relative path.
- Heavy frozen engine loads/scientific imports too slowly or exceeds 8 GB memory; fails native DLL imports, session/port permission, Windows temp directory extraction, lockdown/antivirus protection or disk-pressure handling.
- Test inadvertently overwrites `frontend/src-tauri/binaries`, user SQLite/projects/model files, existing accepted `build/py-dist` or official release outputs.
- ReportLab font cache collision in concurrent exports; silently wrong CJK, emoji, chart axis labels; mixed text wrapping/page clipping or mismatched HTML/PDF facts.
- Error handler converts genuine FAIL into BLOCKED or a test-only PASS into product acceptance; leftover child processes mask SQLite locks or consume resources.

**Rollback:** Do not clean or overwrite existing reviewed folders, user state or release artifacts. Use new unique ignored DevQA outputs, do not stage into the Tauri binary directory, and preserve diagnostics of any partial build with safe, path-free summary. A failed Gate A, B, C or D means **NO production reporting code changes** and **NO installer**.

## 5. Exact next engineering action

**Implement Gate A only:** a read-only, scoped sidecar build-environment readiness contract. First inspect existing `.venv-live`, `.venv` and the isolated private PyInstaller tooling for real package metadata and compatible architecture, without running pip install, writing caches to product directories or invoking the heavy sidecar build. Review its tests for a fail-closed result and the estimated dependency/build cost. Only if Gate A shows an actionable build route should we author a consent-gated Gate B/C proof. No owner action is needed until a specific reviewed new launcher is ready.

**Current acceptance:** Standalone frozen six-resource worker **PASS**. Actual `pilotodin-engine` font packaging **NOT_TESTED**. Production Unicode PDF **VISUAL_FAIL / P2 REVIEW_REQUIRED**. Master Analyst/Scientist and full offline P8 release remain on the documented broader roadmap, not the active work scope.
