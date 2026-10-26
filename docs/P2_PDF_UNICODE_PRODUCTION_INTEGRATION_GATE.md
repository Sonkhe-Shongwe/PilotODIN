# P2 PDF Unicode: Production Integration Gate After Windows CMap Proof

**Date:** 26 October 2026
**Status:** DESIGN GATE — no production renderer, installer, font binary, or data mutation authorized by this document.
**Working branch:** `feature/live-dev-workspace-20261023`

## 1. What is now established

The owner supplied the actual Windows console results of `Run_PilotODIN_P2_PDF_CMap_Scoped_DevQA.bat`:

- `P2 DOCUMENT-SCOPED CMAP DEVQA: SCOPED_EXPERIMENT_PASS`
- 9/9 unit contracts executed, 0 failures, 0 errors, 0 skipped
- Owner `.venv-live` ReportLab version `4.5.1` (different from earlier local developer prototype 4.4.9)
- Baseline extracted Unicode `U+1F4C`, not requested chart-rising emoji `U+1F4C8`
- The document-scoped correction extracted `U+1F4C8` exactly
- Both baseline and corrected rendered pixel SHA-256 are identical:
  `6847ca939fd36889a48634ec959d26b10dd46f02b73b31766278d5fe70e12c11`
- The probe used owner-staged and previously verified Noto Symbols2, no downloaded assets or real projects
- `product_acceptance=NOT_TESTED`, `visual_acceptance=NOT_TESTED` remain true

**Acceptance decision:** Scoped per-document ToUnicode correction is **accepted on Windows for U+1F4C8 and these nine unit contracts**. Prior 3/3 runner + 9/9 P2 mixed reporting, 5/5 disclosure, and the chart pagination synthetic visual fix remain accepted. This is not a production font implementation, installed native product test, general supplementary-plane correctness proof, or full visual PDF PASS.

## 2. Critical actual integration seams and why they matter

### A. Render path

`backend/reports.py::render_pdf` creates a `SimpleDocTemplate` and local ReportLab ParagraphStyles, all relying on default Type1 family fonts. Evidence rows, headings, freeform user narrative, quality limitations, fact tables and method text all pass through the same local `p` helper. The footer explicitly draws Helvetica. This is a narrow seam for per-report Unicode-aware paragraph rendering, **but simply switching its default `fontName` cannot cover mixed scripts**. Embedded primary + CJK + Symbols2 text spans must preserve codepoints and escape user content, without breaking line wrapping, page layout, or immutable evidence.

### B. Charts

`backend/report_charts.py::pdf_chart` creates `reportlab.graphics.shapes.String` for axis labels, group names, category names and caption. These are independent of `ParagraphStyle` fonts and may contain mixed Unicode. Setting the paragraph font alone would leave chart text uncorrected. A single `String` cannot faithfully use several fonts without explicitly splitting/drawing glyph runs, so define a bounded text layout strategy (font selection and measured widths, clipping or disclosure, same numeric values) and test chart headings/values. Keep the now owner-accepted `KeepTogether` chart layout.

### C. Font registry and concurrent exports

The ReportLab global font registry caches dynamic fonts by internal face name. Prior registration of an ordinary `TTFont` can shadow `DocumentUnicodeTTFont` even when using a different requested name; fail-closed identity check has been implemented and the owner Windows scoped experiment passed. **Do not add a global `ttfonts.makeToUnicodeCMap` monkeypatch or clear system font registries in a running FastAPI process.** Define one verified registration lifecycle, unique PDF font names, race-free initialization, and concurrency tests with two real PDFs. A scoped experiment's success does not establish concurrent worker safety.

### D. Offline packaging

`desktop/Build_Python_Sidecar.ps1` builds a **PyInstaller --onefile** frozen backend via `backend/desktop_runner.py`, staging `pilotodin-engine.exe` under `frontend/src-tauri/binaries`. The actual ReportLab PDF rendering is inside that Python sidecar. Font binaries must therefore be reliably available to **the sidecar**, preferably as explicitly pinned PyInstaller data resources with deterministic `sys._MEIPASS`/development path logic. Merely adding a Tauri `bundle.resources` entry does not automatically prove the backend can resolve it. `frontend/src-tauri/tauri.conf.json` already stages `resources/licenses/` for the installer; the three SIL OFL licences must ship intact and be visibly attributable. No runtime font download or reliance on OS fonts, user project directories or mutable `PILOTODIN_HOME` assets.

The current owner-verified upstream candidate font sizes total **21,054,524 bytes** (2,049,096 + 17,772,300 + 1,233,128). Candidate bytes are only in local DevQA, not GitHub or release package. Do not silently add these large files or modify PyInstaller/Tauri scripts before approving explicit staging, release location and license policy. Avoid duplicate bundling of binaries into both installer resource folder and PyInstaller sidecar unless justified.

## 3. Proposed smallest controlled implementation, split into gates

**Gate P2-U1: Resource identity and packaging design.**
- Create a pinned application-resource manifest (separate from `CANDIDATES_UNVERIFIED_DO_NOT_SHIP` developer manifest) only after the owner-visible SHA-256s, exact OFL notices and packaging plan are approved.
- Read staged files only in developer tooling and stage into a build-only directory using exact byte hashes. Production must load only its packaged read-only asset directory, never the local DevQA candidate directory.
- Prove the resource is found in development *and* frozen PyInstaller Windows sidecar; missing/altered fonts or licenses must fail closed or produce an explicit unsupported-Unicode response, **never silently substitute text**.
- Measure packaged size, startup extraction, RAM and latency. No installer or old native verification replay until this resource gate is ready.

**Gate P2-U2: Source-safe renderer hookup.**
- Resolve and verify all font assets once via a testable deterministic font context.
- Preserve the same report dictionaries, frozen revision SHA, evidence order, arithmetic and HTML outputs; only change PDF text shaping/display.
- Add codepoint-aware font runs with original Unicode characters (Latin/Greek/Cyrillic/₹ in primary, CJK in SC, `📈` in Symbols2); use properly escaped ReportLab `<font>` spans for paragraphs/tables.
- Handle headings, narrative, table cells, notes and chart captions. For vector charts, use a bounded measured-run drawing helper or consciously disclose unsupported presentation, never invent numeric values.
- Apply `DocumentUnicodeTTFont` to each **registered font** requiring supplementary-plane correction, ensure identity conflicts fail closed, and test two concurrent exports and repeated exports.
- Explicit policy for unsupported and complex emoji sequences / variation selectors / bidirectional scripts. Do not claim universal Unicode or untested shaping.
- Preserve the accepted chart heading/drawing/limitations pagination correction.

**Gate P2-U3: Focused acceptance without replaying unrelated suites.**
- Unit tests: malformed/absent assets, checksum mismatch, font cache race, BMP + supplementary mapping, page geometry, long Unicode labels, repeated and concurrent exports, chart label text/caption behavior, no evidence/report mutation.
- Synthetic PDF text extract for `café`, `São Paulo`, `R²`, `Δ Ω`, `Москва`, `漢字`, `₹`, `📈` and mixed-script samples, including rendered visual glyph check and copied/extracted exact codepoints.
- Verify same-page chart heading/chart/limitations, display omission notices, table continuation, page margins, font size/pagination and no clipped text.
- Only after integrating verified resources in the sidecar: one focused owner Windows report-rendering DevQA plus visual-preview ZIP. Existing 12/12 mixed and 5/5 display tests are already accepted; rerun only impacted tests if a specific dependency is changed.
- Release/install acceptance remains a later independent gate, not implied by synthetic DevQA.

## 4. Explicit non-goals and rollback

No model fitting, Qwen, real datasets, report revision migrations, database schema, saved-fact recalculation, native app overhaul, Tauri UI redesign or unrelated installation work. Do not run destructive operations on `PILOTODIN_HOME`. If any new PDF-only Unicode renderer fails its focused tests, retain the existing reporting source unchanged while diagnosing; do not ship a misleading “Unicode supported” claim. The tested CMap helper remains usable independently.

## 5. Exact next engineering action

**Design and implement a developer-only resource packaging preflight contract** for the six owner-verified bytes and their license identity, with a transparent build-only destination, before hooking fonts into `backend/reports.py` or `backend/report_charts.py`. Do not request another owner CMap BAT rerun: its nine-case Windows evidence is accepted. No additional user action is currently required.

## 6. P2-U1 developer-only build font preflight: SOURCE COMMITTED, NOT WINDOWS EXECUTED (26 October 2026)

**Latest change scope:** Implemented `tools/p2_pdf_font_build_preflight.py`, separate from the production renderer and PyInstaller/Tauri configuration. Its default command performs a **read-only** re-audit of the six previously staged files under `%LOCALAPPDATA%\PilotODIN\DevQA\font-candidates` using the existing OFL/Git-blob/ReportLab glyph gate and a second per-file pinned size/Git SHA-1/SHA-256 check. It returns `SOURCE_PREFLIGHT_PASS_NOT_STAGED` on success, never a release claim.

A separate explicit `--stage` option creates one unique review folder under ignored `build/p2-pdf-font-preflight/review-<random-id>/`. Only six pinned font/OFL files are copied. The operation is fail-closed: reject unexpected roles/filenames/traversal, invalid or oversized identities, redirected output paths, corrupt source or copied bytes; stream each bounded copy, compare each copy to its source SHA-256 and pinned Git object, write a review-only `receipt.json`, and publish the folder only after all checks complete. On failure clean only its own new `pending-<random-id>` folder, leaving prior reviews untouched. The receipt explicitly says `BUILD_PREFLIGHT_ONLY_NOT_FOR_RELEASE`, `packaged_sidecar_verified=false`, `product_acceptance=NOT_TESTED` and `sha256_approval=MEASURED_RECEIPTS_NOT_INDEPENDENT_RELEASE_APPROVAL`. The bytes remain build-review material **not a build input to the current installer**.

**Risk boundary:** Font binaries in GitHub have NOT been added, and `.gitignore` now excludes `/build/p2-pdf-font-preflight/` to prevent accidental source-control inclusion. `desktop/Build_Python_Sidecar.ps1`, `frontend/src-tauri/tauri.conf.json`, `backend/reports.py`, `backend/report_charts.py` and the CMap helper are unchanged. The sidecar has **not** yet embedded/fonts-loaded any staged resources. Source SHA-256 receipt measurement is NOT independent upstream hash approval or proof of shipping licence compliance.

**Test-only new coverage:** `tests/test_p2_pdf_font_build_preflight.py` contains seven synthetic methods with temporary non-font byte fixtures and a stub for the independent real font parser gate: no-write source audits, six-copy receipt, corruption before output, pending-copy failure and preservation of existing reviews, repeat-ID collision refusal, traversal/duplicate/oversize rejection, and redirected build path blocking. These seven methods are **authored and source reviewed, not yet owner Windows executed**. No existing accepted P2 or native suite was modified.

**One read-only owner QA launcher:** `Run_PilotODIN_P2_Font_Build_Preflight.bat` runs the seven synthetic methods under the existing `.venv-live` and then the source-only identity audit against already verified local fonts. It **does not invoke `--stage`**, download fonts, install any Python package, build the native app, read product datasets or write a font review folder. On a test failure it stops before the asset gate and shows a blocker. The expected green result is seven completed tests plus `SOURCE_PREFLIGHT_PASS_NOT_STAGED`.

**Next action:** Execute this single read-only owner Windows launcher after pulling the latest feature-branch code. Analyze its actual result first. Only after evidence supports a clean preflight should we approve a separate opt-in build-only `--stage` copy and subsequently design/test PyInstaller resource resolution; **no production Unicode renderer change or release build is justified by preflight success alone**.

## 7. Owner Windows P2-U1 preflight PASSED; opt-in build-review staging ready (26 October 2026)

**Actual Windows screenshot reviewed:** The owner ran `Run_PilotODIN_P2_Font_Build_Preflight.bat` in the existing `.venv-live` and saw **seven tests executed with `OK`, zero reported failures/errors**. Its source audit returned `SOURCE_PREFLIGHT_PASS_NOT_STAGED` with `asset_count=6`, `font_bytes=21054524`, `source_verified=true`, `product_acceptance=NOT_TESTED` and `sidecar_packaging=NOT_TESTED`. The BAT explicitly said build staging was not performed. **Accept this seven-test and source-integrity preflight gate on Windows**; do not repeat it unless related source or environment changes.

**Next strictly controlled step (new launcher source committed, Windows execution PENDING):** `Run_PilotODIN_P2_Font_Build_Stage_DevQA.bat` provides an explicit Y/N choice before invoking the existing `tools/p2_pdf_font_build_preflight.py --stage`. It re-verifies all six pinned local DevQA assets and OFL notices, then copies them into a new uniquely named ignored `build/p2-pdf-font-preflight/review-<id>` folder. Copy results are checked against the pinned Git object identities and the independently measured source SHA-256; a review-only `receipt.json` is created only when all six files are accounted for. No downloads, system font installation, model fitting, real projects, frozen engine/installer build or production PDF changes. The operator's refusal triggers no copy. The BAT does not repeat the now accepted seven contract tests.

**Acceptance boundary:** Successful opt-in staging means `BUILD_PREFLIGHT_ONLY_NOT_FOR_RELEASE`, **not** font publication approval, fully independent external SHA-256 provenance, PyInstaller `--add-data` inclusion, frozen sidecar availability, production Unicode PDF correction or final release. The build-review directory is excluded from Git. The installer resource plan and production renderer remain unchanged. Do not point production at the ignored review folder.

**One next owner action:** Pull the live `feature/live-dev-workspace-20261023` branch while preserving local changes. Run `Run_PilotODIN_P2_Font_Build_Stage_DevQA.bat` once, authorize Y only if comfortable making a local ignored build-review copy, and share only the console result / receipt metadata. Do not upload font binaries. After that result is checked, the next engineering task is **deterministic frozen Python sidecar resource resolution and concurrency-aware registration**, followed by production PDF text/chart integration and focused visual testing. Overall P2 remains `REVIEW_REQUIRED`.

## 8. Owner Windows six-file build-review staging PASS; frozen-font path contract authored (26 October 2026)

**Actual owner screenshot:** `Run_PilotODIN_P2_Font_Build_Stage_DevQA.bat` was executed with explicit Y consent. The tool returned `BUILD_PREFLIGHT_ONLY_NOT_FOR_RELEASE`, `asset_count=6`, `source_verified=true`, `product_acceptance=NOT_TESTED`, and `receipt=receipt.json`. The launcher printed “Six files copied and individually verified” into a unique ignored `build/p2-pdf-font-preflight/review-<id>` folder. **Accept the owner’s six-file build-review staging boundary.** It is not a release package and does not establish sidecar or PDF font availability. Do not rerun staging just to obtain the same evidence or upload the font binaries.

**Next architecture check (read-only, SOURCE COMMITTED, WINDOWS PENDING):** Official PyInstaller 6 runtime documentation states that when packaged, backend package modules receive a module-relative `__file__` path inside the bundle extraction directory. `--add-data` can preserve an expected destination path relative to the package. Our selected future path is therefore `backend/assets/pdf_fonts/`, which must be populated by an explicitly approved sidecar `--add-data` mapping when the real build phase begins. It is **not** the old ignored build-review path, Windows Fonts, a DevQA directory or a Tauri-only runtime resource. Source: https://pyinstaller.org/en/stable/runtime-information.html and https://pyinstaller.org/en/stable/spec-files.html.

**Dormant resource contract:** `backend/pdf_font_resources.py` locates `assets/pdf_fonts` beside its own module (works with source and frozen module-relative locations), with no fallback to mutable user data, the working directory, network or system fonts. Its `verify_pdf_font_files` uses caller-supplied **independently pinned production SHA-256s** and enforces exactly six regular/CJK/symbol font/OFL files, bounded sizes, simple filenames, no path redirects, digest match and intact licence notices. It does **not** register ReportLab fonts or modify the product. A receipt alone is explicitly insufficient to authorize release hashes. This code is **not imported into `backend/reports.py`, `backend/report_charts.py` or the sidecar startup**.

**Developer verification:** `tests/test_p2_pdf_font_resources.py` contains **eight new synthetic contract methods** with disposable tiny files, checking simulated PyInstaller module-relative resource lookup, missing-resource refusal, six-file read-only integrity, corruption, independent hashes rather than adjacent receipt, name/traversal/size/duplicate rejection, missing OFL notice and repeated concurrent reads without registry mutation. `tools/p2_pdf_font_resource_path_devqa.py` reads exactly one previously completed build-review folder, checks the original six-file receipt against the pinned Google Fonts identities, independently rehashes the six files and invokes the dormant layout verifier, without copying any actual fonts or building an executable. `Run_PilotODIN_P2_Frozen_Font_Path_DevQA.bat` runs the eight synthetic unit methods plus that read-only receipt check under the existing Windows `.venv-live`. It explicitly says the actual PyInstaller `--add-data` mapping has **not been configured** and the frozen binary is **NOT_TESTED**.

**Verification truth:** Those four files were committed and source-retrieved for structural review, but the eight methods and newly added read-only Windows gate **have not been executed on the owner's machine**. No PyInstaller build, Tauri configuration, production Unicode renderer, model fitting or real data were touched. Current milestone P2 remains `REVIEW_REQUIRED`, production Unicode PDF still `VISUAL_FAIL`. Build review staging is accepted for its limited purpose only.

**One next owner action:** Preserve local GitHub Desktop changes, pull `feature/live-dev-workspace-20261023` and run only `Run_PilotODIN_P2_Frozen_Font_Path_DevQA.bat` once. Share console text/screenshot, not font files. Expected outcome is eight unit methods passing and `BUILD_REVIEW_RESOURCE_PATH_CONTRACT_PASS` with `actual_frozen_sidecar=NOT_TESTED`. On completion, decide on an explicit `--add-data` resource packaging integration and a small real frozen-sidecar proof, not a blind full installer rebuild or unrelated test replay.

## 9. Owner Windows future PyInstaller font-path contract PASS; actual frozen-sidecar packaging remains OPEN (26 October 2026)

**Actual owner screenshot, current accepted gate:** `Run_PilotODIN_P2_Frozen_Font_Path_DevQA.bat` completed `Ran 8 tests in 0.138s` and `OK`. The follow-on read-only staged-copy receipt check reported `P2 FROZEN FONT PATH DEVQA: BUILD_REVIEW_RESOURCE_PATH_CONTRACT_PASS`, `verified_font_and_license_files=6`, `proposed_pyinstaller_add_data_destination="backend/assets/pdf_fonts"`, `source_review_receipt="receipt.json"`. It also expressly reports `actual_frozen_sidecar=NOT_TESTED`, `actual_pyinstaller_add_data=NOT_CONFIGURED`, `product_acceptance=NOT_TESTED` and `unicode_visual_acceptance=NOT_TESTED`. **Accept exactly the eight synthetic tests and six copied-resource identity/receipt checks. Do not claim the resource has been embedded in a frozen executable.**

**Source code truth at this gate:** `backend/pdf_font_resources.py` exists as an independent, dormant integrity and module-relative path helper. `backend/reports.py`, `backend/report_charts.py`, `backend/desktop_runner.py`, `desktop/Build_Python_Sidecar.ps1`, Tauri configuration and production font binaries remain unchanged. The six asset files exist only in isolated DevQA and a uniquely named Git-ignored build-review folder. These are not approved release assets. Do not run an installer or invoke the unchanged seven-case build preflight, six-file staging, previous nine-case CMap probe, mixed-report or display suites again on unchanged source.

**Next engineering phase is a real packaging proof, not another simulated path probe:** First independently approve release SHA-256 and exact SIL OFL notices, with one non-user project staging authority. Then create a bounded, opt-in PyInstaller `--add-data` proof that embeds precisely those six approved resources at `backend/assets/pdf_fonts` and exercises `resolve_pdf_font_root` and `verify_pdf_font_files` **inside the actual frozen sidecar**. Check extraction location, corruption/missing resources, no fallback to user data or OS fonts, startup/memory footprint, and clear PASS/FAIL/BLOCKED diagnostics. Keep it distinct from the existing default installer build and do not add an automatic downloader.

Once that **actual frozen build** boundary is proven, integrate owner-accepted `DocumentUnicodeTTFont` with codepoint-aware PDF paragraphs, table cells and vector chart labels; test ReportLab face-name registry collisions and parallel exports, preserve report arithmetic/privacy/immutability, and request one affected Windows synthetic visual/copy/search PDF verification. Full installed/native/offline 8 GB release remains a later independent P8 gate.

**Portfolio reference:** `docs/PILOTODIN_STATUS_REFLECTION_2026-10-26.md` is the concise P0–P8 current assessment and release distinction; `docs/SESSION_HANDOFF_CURRENT.md` defines one immediate next action.

## 10. NEXT scoped gate authored: true isolated onefile font-resource probe (26 October 2026)

**Current accepted evidence remains** the eight/8 simulated module-relative resource tests and six reviewed font/OFL identities from the owner's Windows screenshot. No new PyInstaller run has been observed. The current actual frozen Python sidecar remains `NOT_TESTED` and the production Unicode PDF visual defect remains `VISUAL_FAIL`.

**Committed developer-only proof:** `tools/p2_pdf_frozen_font_worker.py`, `tools/p2_pdf_frozen_font_onefile_devqa.py`, `tests/test_p2_pdf_frozen_font_onefile.py` (**eight synthetic tests**), and `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat`. Full controls, stop rules, consent and source audit are documented in `docs/P2_PDF_FROZEN_ONEFILE_RESOURCE_DEVQA.md`. The launcher checks existing `.venv-live` and `.venv` for installed PyInstaller 6, never performs pip/venv setup, runs its pure tests, requests Y/N consent, and then builds a NEW standalone onefile verifier under a random ignored `build/p2-pdf-frozen-resource-probe/` subfolder. It uses only the six previously verified reviewed font/OFL assets, freshly copies/re-hashes exactly those into a six-file build-input directory, and embeds the directory at `backend/assets/pdf_fonts`. This avoids glob expansion ambiguity for square-bracketed Noto variable-font names. PyInstaller caches/extraction temp are redirected into the same isolated run and at least 750 MiB free build disk is required.

The worker only passes when `sys.frozen`, `sys._MEIPASS`, true bundled module-relative paths, all six file hashes/byte counts/OFL notices and an exact expected set are validated **inside the extracted onefile process**, launched from a different working directory. Its console label is `SCOPED_FROZEN_RESOURCE_PROBE_PASS`. A mere successful PyInstaller build, green eight mocked unit contracts, missing PyInstaller, no executable, bad JSON or nonzero worker exit CANNOT be promoted. No real backend/desktop_runner or installer is run. **These new eight tests and real frozen probe have not yet been executed on the owner's Windows PC**, and no independent release checksum approval is claimed.

**NEXT one owner gate:** Pull feature branch safely, run `Run_PilotODIN_P2_Frozen_Font_OneFile_DevQA.bat` once, and approve Y only if comfortable creating a local build-review executable with the six OFL fonts. Share console text/screenshot, NOT build executables, fonts or raw cache. On green, plan subsequent *actual PilotODIN sidecar* opt-in bundling and the production PDF text/chart integration, after a separate release-authority review. Do not repeat accepted mixed/report/CMap/resource-path/preflight tests. P2 remains `REVIEW_REQUIRED`.
