# P2 PDF Unicode Font Coverage: Risk-First Remediation Plan

**Date:** 26 October 2026
**Status:** PLANNED, NOT IMPLEMENTED OR ACCEPTED.
**Branch:** `feature/live-dev-workspace-20261023`.
**Related:** `docs/P2_PDF_VISUAL_ACCEPTANCE.md`. Do not revisit the accepted 12/12 mixed report or 5/5 disclosure suites without a demonstrated impacted seam.

## 1. Reproduced failure and separate accepted pagination outcome

Original owner sample from `P2-PDF-VISUAL-20261026T133301Z-1585d963d1-visual-preview.zip` (37 pages) showed visibly substituted / missing Greek, Cyrillic, CJK, rupee and emoji glyphs on Unicode PDF page 1, while Latin-accented `café` and `São Paulo` rendered.

A narrow chart-heading KeepTogether fix was subsequently committed without modifying fonts. Its owner Windows rerun `P2-PDF-VISUAL-20261026T135824Z-c71f56fbf0` structurally PASSED (standard 8 pages, dense 22, Unicode 7). The new preview ZIP SHA-256 is `042143349dc00eae6dd179b73fb55a21f57a61f3e2dbdca34a6037e0f6102233`, matching the diagnostic. ZIP CRC, all 12 member SHA-256 values and scenario filenames verified. Full PDFs visually inspected via rendered contact sheets and focused page detail. **The chart heading, actual Sum of Revenue by Region drawing and Chart limitations now share a page:** standard p3, dense p3/p10/p17, Unicode p3. Chart pagination correction is therefore **VISUALLY VERIFIED for this synthetic gate**. No general clipping or row/figure collision observed in these pages.

**Unicode remains VISUAL_FAIL:** `unicode.pdf` page 1 still visibly uses black-box placeholders or wrong symbols, and extracted exact-text presence is false for `Δ`, `Москва`, `漢字`, `₹`, `📈`; Latin `café`, `São Paulo`, `R²` remain extractable. Source Greek `Δ Ω` may be replaced by semantically different mathematical `∆ Ω`. No Unicode correction has been applied.

## 2. Root cause and engineering constraints

`backend/reports.py::render_pdf` obtains default ReportLab paragraph styles with Helvetica-like Type 1 fonts; these have limited script coverage and may substitute Symbol/ZapfDingbats. `backend/report_charts.py::pdf_chart` separately creates vector text using ReportLab drawing String without a bundled Unicode font. A fix only in paragraph styles is insufficient for chart labels and headings. The existing repository tree contains no bundled .ttf/.otf assets. Production is a local-first Windows desktop app, so depending on fonts installed on the user's OS is not reproducible.

Official references to verify during implementation:
- ReportLab `TTFont` and `pdfmetrics.registerFont` support embedding Unicode TrueType outlines: https://docs.reportlab.com/reportlab/userguide/ch3_fonts/
- Noto font architecture provides separate Latin/Greek/Cyrillic and other-script families, licensed under SIL OFL: https://github.com/notofonts/noto-docs/blob/main/docs/website/use.md
- Noto Emoji includes special color-emoji formats; browser support is not proof ReportLab can embed/render them: https://github.com/googlefonts/noto-emoji

## 3. Recommended controlled solution, without speculative font changes

**Stage 0, licensing and assets:** Select explicit pinned, redistributable SIL OFL assets with verified SHA-256, complete license text and attribution, and confirm the actual TTF outlines can be parsed by the pinned ReportLab build. A Noto Sans Latin/Greek/Cyrillic family is a candidate for primary text. For CJK, select a small tested compatible subset/family only after checking artifact size and embedding feasibility. Do not copy fonts from Windows or assume a system font is installed. Do not include font files without verified licensing and bundling paths in the Tauri/release process. Emoji color glyphs require a separate compatibility decision: test monochrome TTF viability or a clearly labeled deliberate placeholder; do not assume a color font will work with ReportLab TTFont.

**Stage 1, central coverage API:** Add one narrowly scoped PDF font helper resolving a pinned bundled path, registering paragraph regular/bold plus chart font names, identifying which code points each font maps and choosing explicit spans/fallbacks. Preserve original Unicode in the saved frozen report and HTML; any PDF unsupported-glyph fallback must be conspicuously disclosed rather than silent loss or misleading replacement. Handle rich-text escaping and paragraph line breaking safely. Source reports stay immutable and all numeric values/order identical.

**Stage 2, isolate scripts:** Verify Latin, Greek and Cyrillic first; then controlled CJK/range fallback; then ₹ and emoji. Avoid introducing complex shaping/RTL without a separate tested architecture. Warn explicitly if a script cannot be faithfully reproduced, and distinguish a font-availability failure (`BLOCKED`) from a confirmed product rendering regression (`FAIL`). Freeze glyph choices and font licenses before full release.

**Stage 3, tests:** Use synthetic sample checks for `café`, `São Paulo`, `R²`, `Δ Ω`, `Москва`, `漢字`, `₹` and `📈`; cross-check extracted Unicode AND visibly rasterized glyphs. Assert no `black square` substitution, fake whitespace, unexpected glyph mapping or clipped spans. Check large paragraphs, heading hierarchy, table row boundaries, chart axis and value labels with mixed scripts. Add negative tests for unsupported code points and absent/corrupted assets, with clear warning/recovery rather than false PASS. Test actual packaged Windows offline build resource paths, memory and PDF size.

**Stage 4, acceptance:** Generate fresh disposable preview PDFs using the same isolated visual gate and compare against the *current accepted pagination baseline*. Only require affected renderer tests, plus focused existing chart/disclosure contract checks if the relevant seam changes. Obtain actual viewed-PDF evidence and preserve status ZIP separation. Move Unicode `VISUAL_FAIL` to `VISUAL_PASS` only when supported scripts/glyphs display faithfully and unsupported ones are reported honestly. Full P2 product/installed-app release remains a separate gate.

## 4. Stop conditions and scope decisions

- No font binaries or production font code should be added before confirming exact assets, licensing, parser compatibility, licensing/distribution effects and the intended unsupported-emoji behavior.
- Never claim full Unicode support based on one font, one test string or PyMuPDF extraction alone.
- Do not change training/model APIs, report numbers, evidence ordering, frozen JSON/SHA, HTML semantics, SQL schema, native Save As or unrelated UI.
- Windows owner should **not rerun** the just-passed chart visual gate or previously accepted suites while Stage 0 is being researched.

## 5. Stage 0 concrete research and local compatibility prototype (26 October 2026)

**Verified live state before this change:** `feature/live-dev-workspace-20261023` at `99e37d976610878fcf1e8f09e921a731e4e6d754`. No new owner PDF test or production renderer patch was performed in this increment. The visual failure on owner Windows remains OPEN.

**Authoritative source checks (research, not yet redistributed binaries):**
- Google's `google/fonts/ofl/notosans/OFL.txt` confirms Noto Sans copyright and SIL Open Font License 1.1 permitting embedding/bundling with the required notice: https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/OFL.txt
- Noto Sans SC has its own SIL OFL text and Adobe Reserved Font Name `Source` in the license; derived/subset builds must respect these conditions: https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/OFL.txt
- Official Google Fonts Noto Sans SC variable font (`ofl/notosanssc/NotoSansSC[wght].ttf`) is approximately **16.9 MB**, potentially substantial for an 8 GB-target desktop app: https://github.com/google/fonts/blob/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf
- ReportLab's official user guide explicitly documents `TTFont` plus `pdfmetrics.registerFont` for embedded Unicode TrueType fonts. **Variable-font compatibility, font shaping, CJK and emoji are not implicitly guaranteed**: https://www.reportlab.com/docs/reportlab-userguide.pdf
- Noto docs confirm there is no single universal Noto font, and Noto Emoji monochrome does not cover every emoji; ReportLab color-emoji rendering must not be assumed: https://notofonts.github.io/noto-docs/website/use/

**Local, disposable proof-of-concept (NOT PilotODIN production/Windows acceptance):** Using a local open Noto Sans Regular TTF as an explicit developer input, ReportLab successfully `registerFont(TTFont(...))` and embedded a TrueType subset in a synthetic one-page PDF. PyMuPDF extraction preserved **exactly** `café`, `São Paulo`, `R²`, `Δ Ω`, `Москва` and `₹`. Direct font glyph-map inspection found **2840 covered Unicode code points** and confirmed `漢`, `字` and `📈` are **not present**, so their appearance cannot be solved by the Latin/Greek/Cyrillic font alone. This is a genuine proof of the first-script implementation path, not proof of acceptable CJK, emoji, distribution licensing or Windows packaged behavior. No fonts were committed or shared.

**New test-only utility:** `tools/p2_pdf_font_coverage_probe.py`, commit `3eca7e2c7ba32c12217c06e08e930cb599ce2e18`. The probe accepts **explicit developer-selected local TTF paths** (`--regular`, optional `--cjk`, `--emoji`), rejects missing/oversized/linked paths, uses ReportLab font glyph maps to avoid false claims, renders a temporary synthetic PDF in memory and checks six exact-text cases with PyMuPDF. Output contains only basename, size, SHA-256 and sample statuses. `UNSUPPORTED`/`MISMATCH` causes nonzero exit; no user dataset/project, API server, model fit, network request, installer or font installation is involved. This is a developer compatibility tool, **not a new required owner BAT or production support**. Do not claim full font coverage based on a single font.

**Decision / remaining gate:** Stage 0 is **PARTIALLY VERIFIED**: OFL license paths and ReportLab primary-font proof validated; exact approved distributable font binaries, pinned hashes, SC TTF weight/static compatibility, CJK glyph subset requirements, emoji policy, release bundling and same-page chart text font support remain open. Avoid adding a font-name-only production change, silently substituting characters or implementing unsupported fallback. The next source work is to establish an exact versioned asset manifest and verify *each* candidate through the developer probe before touching `backend/reports.py` and `backend/report_charts.py`. Check Windows/offline sidecar packaging and current resources path when the assets are fixed.

## 6. Controlled candidate identity gate and multi-font fallback experiment (26 October 2026)

**Continuity:** Live feature branch was `add61b481cd9f2ab643ff716e5104d8f4a828c4f` when this increment began. Previously accepted 12/12 mixed, 5/5 display, chart pagination and Windows native Save As gates remain unchanged. Unicode production rendering still **VISUAL_FAIL**. No font binaries, dependency installation, backend renderer or Tauri resource changes have been made.

**Official upstream identity snapshot:** Queried the public `google/fonts` repository's `main` at commit `e7db6ca603fd4862010383ff17ffd6cc4ffac1c0` (23 October 2026). Its source tree provides candidate files with **immutable Git blob SHA-1 IDs and exact byte sizes**, and the matching per-family license blobs:

| Role | Upstream font file | Bytes | Git blob SHA-1 |
|---|---|---:|---|
| Primary | `ofl/notosans/NotoSans[wdth,wght].ttf` | 2,049,096 | `75575046c015ff623a848096a15779867ba71453` |
| CJK | `ofl/notosanssc/NotoSansSC[wght].ttf` | 17,772,300 | `fb0637bafbcd804fe32152370a1225990745b4bc` |
| Symbol | `ofl/notosanssymbols2/NotoSansSymbols2-Regular.ttf` | 1,233,128 | `caf89dd0e60e23ac39ce18da823095959d409437` |

All three are from directories with **SIL OFL 1.1 license** texts, which the asset gate requires beside the fonts. Combined source-font size is about **20.1 MiB** before any preprocessing or installer compression. These are only **candidate identities**, not approved fonts shipped with PilotODIN. Git blob hashes are not SHA-256; after acquiring actual binaries, record both identities and independent SHA-256 before approval. Source licensing requires copying the **exact** notices; any derived fonts must respect reserved names. Variable Noto Sans/SC files may need a deterministic, separately assessed conversion to static TrueType weight 400, not a silent renamed derivative.

**New committed developer tooling, zero production dependency:**
- `tools/p2_pdf_font_candidates.json` pins the upstream commit, expected sizes, Git blob hashes and distinct license identities; state `CANDIDATES_UNVERIFIED_DO_NOT_SHIP`.
- `tools/p2_pdf_font_asset_gate.py` checks only explicitly supplied offline local files: size, Git blob hash, SHA-256, matching complete OFL notice, ReportLab `TTFont` parse and required test code points. Returns `CANDIDATE_FILE_AND_CMAP_PROBE_PASS` only for this limited format/cmap gate, not visual or product acceptance. Does not download or copy assets, touch user data, or alter app installation. Unexpected, corrupted, linked or incomplete assets must BLOCK.
- `tools/p2_pdf_font_coverage_probe.py` now splits mixed-script text into explicit glyph-bearing font runs, keeps original characters, escapes ReportLab inline markup, and checks exact PyMuPDF extraction including a mixed sentence. A cmap hit is not mistaken for successful PDF text round-tripping.
- `tests/test_p2_pdf_font_devqa_contract.py` contains three new pure synthetic contract test methods for Git blob digest calculation, safe font fallback segmentation, and rejection of malformed asset roots/manifests. These developer tests have been authored, **not run within the user's Windows `.venv-live`**. They are not added to previously accepted runner totals.

**Local ReportLab mixed-script experiment (disposable system fonts, NOT planned distribution assets):** With Noto Sans Regular + a different CJK TrueType face + Noto Sans Symbols2, ReportLab paragraph font-run markup rendered `café São Paulo R² Δ Ω Москва 漢字 ₹ 📈`. PyMuPDF extracted the Latin, Greek, Cyrillic, CJK and rupee text exactly. However the rendered monochrome `📈` image mapped to **`Ὄ`** in extracted PDF text rather than original `📈`, despite the symbol font's cmap claiming a glyph. Thus **true emoji accessibility/search/copy fidelity is still FAIL**. A supplementary-plane ToUnicode limitation remains and cannot be covered up by glyph presence or visual appearance. Final glyph mapping requires explicit investigation; consider clearly labeled Unicode-name text fallback if codepoint fidelity cannot be achieved without a different PDF text engine. Never silently replace source text in frozen report revisions.

**Unresolved engineering gates, before any production patch:**
1. Obtain exact candidate binaries and OFL files under an approved developer process; independently verify IDs and SHA-256, and test the variable fonts with pinned ReportLab.
2. Measure script/font run selection for paragraph, table cells, headings, vector-chart titles, labels and legends, with no numeric or evidence mutation.
3. Decide emoji policy guaranteeing visibly honest and accessible text; do not claim semantic preservation from a monochrome shape alone.
4. Design frozen/offline Windows bundled resource paths, fonts/licenses inclusion and 8 GB peak-memory check. Avoid installing to OS fonts or fetching fonts at runtime.
5. Produce an isolated font-specific Windows visual PDF gate only **after** the genuine bundled-font renderer patch, with explicit no-regression/Unicode expectations.

**Verification truth:** Public upstream file metadata/licensing and local mixed-script proof were inspected; the manifest and developer-only source files are committed/re-fetched, but **their tests and exact official candidate font binaries have not been executed together**. No production Unicode fix or owner rerun has occurred. Preserve P2 overall `REVIEW_REQUIRED` and Unicode `VISUAL_FAIL`.

## 7. Explicit pinned-font staging safeguard, still awaiting exact binary execution (26 October 2026)

**Current source-only step:** Font binaries could not be retrieved into the available engineering container: direct external HTTP/DNS access was unavailable, and the connected GitHub file adapter can inspect textual metadata but does not materialize oversized binary font blobs. **This is a tooling access boundary, not proof that Google's source assets are invalid.** No speculative download or font/license copying was substituted.

**Concrete committed changes:** Manifest `tools/p2_pdf_font_candidates.json` now pins **license byte sizes** as well as the previously established Git blob identities: regular OFL 4,396 bytes, SC OFL 4,388 bytes, Symbols2 OFL 4,383 bytes. The new `tools/p2_pdf_font_stage_candidates.py` is a **developer-only**, explicit `--download` opt-in helper (not a production application network feature). It targets only `%LOCALAPPDATA%\PilotODIN\DevQA\font-candidates`, applies the existing safe-root restrictions, checks the immutable upstream commit, constructs requests only to `raw.githubusercontent.com`, rejects off-host redirects, streams no more than each pinned size into a unique temporary file, computes Git blob SHA-1 and SHA-256, and atomically publishes a candidate only after its bytes match. Existing approved bytes can be reused; mismatches and incomplete partial files are refused. After six exact files are present, it invokes the previously committed offline OFL/ReportLab/cmap gate. Its final label is **STAGED_FOR_REVIEW**, never product Unicode acceptance, regardless of candidate success. No font files were added to the repository or application install tree and this helper is never imported by production code.

**Pure contract coverage:** Existing `tests/test_p2_pdf_font_devqa_contract.py` now contains **five** methods (formerly three), adding mocked candidate download/reuse and pin-mismatch/partial cleanup checks. These new methods are **committed and source reviewed, not yet executed in the owner's Windows `.venv-live`**. Their mocks generate only tiny synthetic bytes and perform no network operations or actual font redistribution. No accepted existing P2 mixed/disclosure/native test suites have been modified or repeated.

**Accessible-symbol policy to investigate next:** Monochrome `📈` visibly rendered but extracted to a different Unicode codepoint in the earlier local proof. For P2, a safe interim option is an explicitly disclosed readable textual representation (`CHART INCREASING [U+1F4C8]`) in the PDF *only*, while the frozen source report and HTML retain `📈` unchanged. This is an engineering candidate, **not implemented or accepted**; it should be compared with a truly faithful ToUnicode implementation. Never claim exact glyph fidelity from this fallback or silently emit a wrong codepoint.

**Important blockers:** Official byte/format/license verification of all six staged files remains UNEXECUTED; exact SC variable TTF handling, original versus instantiated font naming, CJK PDF glyph extraction, supplementary-plane emoji ToUnicode, Windows 8 GB/installer path/size and production paragraph/chart rendering remain unverified. Stage 0 cannot be declared fully complete. The safe next action is a controlled developer run of the *new staging utility* under an approved networked Windows or other developer environment, inspect candidate-format results and hashes, then decide which assets to bundle. Do **not** ask the owner to rerun accepted 12/12, 5/5, visual or native Save As suites during staging, and do not change production PDF fonts until the exact candidates are verified.

## 8. Explicit owner-verifiable Stage 0 launcher (26 October 2026)

A one-click **developer-only** Windows launcher was added: `Run_PilotODIN_P2_Font_Candidates_DevQA.bat` (commit `3a554cd5ab6d82308635b3382feb761eef5638d5`). This launcher is **NOT a PilotODIN app feature or installer**. It uses the existing `.venv-live\Scripts\python.exe` with no new installation, clearly describes the approximately 21 MB of source assets, asks for explicit Y/N confirmation, and invokes `tools/p2_pdf_font_stage_candidates.py --download` only if the owner confirms. A refusal performs no download. It writes only the six pinned font/license files to `%LOCALAPPDATA%\PilotODIN\DevQA\font-candidates` and never to application resource directories. The console prints the per-asset SHA-256 and bounded ReportLab format/cmap results, not the font file contents.

**One next owner action, if approving a networked developer check:** Pull the active feature branch while preserving any uncommitted files and run **`Run_PilotODIN_P2_Font_Candidates_DevQA.bat` once**. Approve the public download only if comfortable with this isolated staging. Share a console screenshot (not font binaries) regardless of its outcome. `STAGED_FOR_REVIEW` is a developer candidate result, not PDF Unicode acceptance; a failed variable TTF/SC/emoji gate must be diagnosed before modifying production. If no network or no consent, this stage stays BLOCKED without affecting accepted P2 functionality.

**No previous accepted 12-case mixed, 5-case disclosure, chart-pagination, PDF visual or native Save As launcher should be rerun.** No production renderer/font code or Tauri resources were changed in this staging increment. This new staging launcher and the five developer contract methods have been committed and reviewed at source level but **not executed on Windows**.
