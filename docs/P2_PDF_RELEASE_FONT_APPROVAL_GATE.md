# PilotODIN P2 | Unicode PDF Font Release-Approval and Renderer Entry Gate

**Checkpoint:** 26 October 2026, source-only P2-U2e preparation.
**Branch:** `feature/live-dev-workspace-20261023`
**Status:** `RELEASE_FONT_APPROVAL_NOT_GRANTED`; developer-only model of font-run planning. **No font redistribution, new frozen sidecar, production PDF renderer, Tauri installer or user-project change is approved by this document.**

## 1. Scope and source of truth

The owner accepted `SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS` for the **real frozen scientific engine**, its six pinned **DevQA** font/OFL files, and disposable auth/SQLite runtime. That is strong evidence for the test packaging seam but **not** approval to ship the candidate fonts or a working Unicode PDF renderer. The original `backend/reports.py::render_pdf` remains on ReportLab default paragraph fonts and Helvetica footer; `backend/report_charts.py::pdf_chart` uses separate vector `String` shapes. The currently shipped report stays `VISUAL_FAIL` for mixed Unicode until separately corrected and human-reviewed.

The authoritative sources for the DevQA candidates remain `tools/p2_pdf_font_candidates.json` and `docs/P2_PDF_UNICODE_FONT_REMEDIATION_PLAN.md`. Existing `backend/pdf_font_resources.py` is dormant and specifically states that candidate manifests and local receipts cannot serve as independent release provenance.

## 2. Candidate identity snapshot, **NOT** a release manifest

| Intended role | Google Fonts source at pinned source commit | Source bytes | Git blob SHA-1 | Release decision |
|---|---|---:|---|---|
| Primary | `ofl/notosans/NotoSans[wdth,wght].ttf` | 2,049,096 | `75575046c015ff623a848096a15779867ba71453` | `NOT_APPROVED` |
| CJK | `ofl/notosanssc/NotoSansSC[wght].ttf` | 17,772,300 | `fb0637bafbcd804fe32152370a1225990745b4bc` | `NOT_APPROVED` |
| Symbols | `ofl/notosanssymbols2/NotoSansSymbols2-Regular.ttf` | 1,233,128 | `caf89dd0e60e23ac39ce18da823095959d409437` | `NOT_APPROVED` |

Source candidate commit: `google/fonts@e7db6ca603fd4862010383ff17ffd6cc4ffac1c0`. Their separate `OFL.txt` identities and bytes are pinned in the existing candidate manifest. **These are upstream Git blob IDs, not SHA-256s, authorizing evidence or signed release assets.** Local SHA-256s were reverified for DevQA, but release-policy SHA-256s, exact redistributed filenames/weights/notice locations and external license review have NOT been independently approved. Do not invent their values or copy binaries into Git.

## 3. Release go/no-go prerequisites (all must be independently verified)

1. **Legal and provenance:** owner reviews each exact original font and full corresponding SIL OFL notice, copyright and any Reserved Font Name obligations, redistribution method, attribution/distribution locations and any derivative/static-conversion conditions. Record immutable source versions, approved **SHA-256** and **size** of all six final files in a **separate release-only, code-pinned** manifest, with reviewer decision. Never elevate `CANDIDATES_UNVERIFIED_DO_NOT_SHIP` or a mutable local `receipt.json`.
2. **Font parser and glyph/shaping compatibility:** prove ReportLab 4.5.1 compatibility of actual selected TTF/static face(s), explicit glyph maps for Latin/Greek/Cyrillic/rupee/CJK/📈; do not infer them from font names. Resolve whether variable Noto files need separately approved static derivations. Unsupported combining marks, bidi/RTL, variation selectors, regional flags and multi-codepoint emoji sequences must produce explicit unsupported diagnostics, never semantic replacement or false glyph success.
3. **Deterministic offline paths:** plan one read-only packaged `backend/assets/pdf_fonts` within the **real** frozen backend (no OS font or `PILOTODIN_HOME` fallback, download, model, user path, duplicate hidden bundles or test-only startup hook in release). Hash/notice verification fail closed before use. `backend/pdf_font_resources.py` is the existing dormant path contract.
4. **Per-document ReportLab lifecycle:** use the already scoped `DocumentUnicodeTTFont` on every applicable real registered face requiring astral ToUnicode correction, with explicit face-identity conflict checks and bounded initialization/concurrent PDF tests. No process-global font monkeypatch, registry clear or silent aliases. Check table wrapping, repeated exports, chart heading chart/limitations pagination, footer font and PDF copy/extraction.
5. **Owner acceptance:** test first with synthetic immutable reports, verify exact original report dictionaries, evidence arithmetic/order/revision SHA and HTML unchanged, then request **one new focused Windows visual/copy/search Unicode PDF gate** with real user review. Later separately measure 8 GB resource load and offline installer/P8 release behavior. Previously accepted P2-U2d, onefile, CMap, mixed/disclosure and pagination gates are preserved without repetition.

## 4. New **dormant** P2-U2e source boundary

- `backend/pdf_unicode_runs.py` is independent of ReportLab and does **not** import production reports or read actual fonts. It accepts explicit **caller-supplied glyph coverage**, preserves exact text, assigns minimal regular/CJK/symbol runs, escapes paragraph markup, and calculates anchored per-font chart runs from **supplied** measurement results. It rejects unverified glyphs, unsupported complex sequences, controls, insecure font names and text-width overflow. Its computed runs are **not** proof the fonts render or extract correctly.
- `tests/test_p2_pdf_unicode_runs_contract.py` has 13 new synthetic source-level contracts for mixed text, losslessness, escaping, role and face validation, unsupported sequences, bounded lengths, chart centering/measure failure, and no ReportLab dependency. In an isolated local source-only Python invocation 13/13 were green; **not yet verified on the owner's Windows**.
- Production `backend/reports.py`, `backend/report_charts.py`, `backend/pdf_font_resources.py`, `backend/pdf_unicode_cmap.py`, `desktop/Build_Python_Sidecar.ps1`, requirements, launcher and installer remain **unchanged** by this increment. No font, Tauri, PowerShell or mutable dataset was accessed.

## 5. Next precise engineering increment

**Do not jump to production integration.** First add a **developer-only** verified-font-context adapter that consumes the six *existing* pinned DevQA sources and ReportLab's actual glyph maps, passing explicit coverage to `plan_font_runs` and measuring mixed-label width via `pdfmetrics.stringWidth`. Use per-document experimental font registrations with unique identity checks and the accepted document-specific ToUnicode class; never global-patch ReportLab. Prove on **synthetic in-memory PDF** paragraphs and chart labels, including exact extraction and guarded negative cases, without touching live report data or release font assets. If asset/provenance or ReportLab compatibility is unavailable, return `BLOCKED` rather than claiming product Unicode PASS.

Only after successful isolated adapter contracts and the separate **release** source/notice approval should production renderer integration be considered, followed by a focused Windows human PDF visual/copy acceptance. P2 remains `REVIEW_REQUIRED`, Unicode production `VISUAL_FAIL`, and P8 `NOT_CERTIFIED`.
