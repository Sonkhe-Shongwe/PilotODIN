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
