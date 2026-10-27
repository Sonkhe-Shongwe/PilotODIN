# P2 Unicode PDF: Consolidated Font-Face and Distribution Decision

Checkpoint: 26 October 2026. Decision: CONDITIONAL GO for original, unchanged font assets as an engineering strategy; NOT release approval. Owner/legal signoff remains outstanding.

## Source verification and face choice

Upstream: google/fonts at e7db6ca603fd4862010383ff17ffd6cc4ffac1c0, pinned by tools/p2_pdf_font_candidates.json. Source file sizes and Git blob SHA-1 are recorded there. Git blob IDs are not the final release SHA-256s.

| Role | Original font | Bytes | OFL copyright/RFN finding | Engineering choice |
| --- | --- | ---: | --- | --- |
| regular | NotoSans[wdth,wght].ttf | 2,049,096 | Copyright 2022 Noto Project Authors; no RFN in opening header | Original variable font, no derivative |
| cjk | NotoSansSC[wght].ttf | 17,772,300 | Copyright 2014-2021 Adobe; explicit Reserved Font Name 'Source' | Original variable font; DO NOT derive/static-convert without separate RFN approval |
| symbol | NotoSansSymbols2-Regular.ttf | 1,233,128 | Copyright 2022 Noto Project Authors; no RFN in opening header | Original static font |

The three exact original OFL notices at that commit were fetched and inspected. They declare SIL Open Font License 1.1. A missing RFN header statement is not trademark or endorsement clearance. The 'Source' RFN in the Noto Sans SC copyright header is not an outright ban on distributing the unchanged original font.

## Official licence conditions

The SIL OFL 1.1 generally permits distributing original unmodified font files inside apps, including commercial products, provided each copy carries copyright and full licence information. Fonts must remain under OFL, must not be sold alone, modified versions must respect any Reserved Font Names, and the authors must not be falsely presented as endorsers. PDFs created using the fonts are not automatically placed under OFL. Original terms: https://opensource.org/license/OFL-1.1 ; official guidance: https://openfontlicense.org/ .

Exact source licences:
- https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/notosans/OFL.txt
- https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/notosanssc/OFL.txt
- https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/notosanssymbols2/OFL.txt

## Outstanding release approval

The prior P2-U2g Windows audit was accepted for the candidate DevQA dossier, not release authorization. Owner P2-U2f proved exact small synthetic Unicode Paragraph/vector PDF extraction on ReportLab 4.5.1; P2-U2d proved the real frozen scientific sidecar can include six source assets. Neither is production report acceptance.

Independent owner/legal approval of exact full OFL texts, family/face choice including RFN and variable-font strategy, final code-pinned SHA-256 for all SIX font/notice release copies and accessible packaged notices is mandatory. Do not treat DevQA receipt hashes as code-approved release pins. No font conversion, copying, downloading or installer distribution is authorized here.

## Coherent renderer increment

Prepare dormant explicit-opt-in PDF Unicode renderer seams for body/heading/table/limitation and separate vector chart labels while preserving default output and report values. No normal FastAPI route should enable that seam until release licensing and font manifest is approved. Preserve HTML, immutable revision SHA, chart data, pagination, security/privacy, DevQA isolation and accepted Windows evidence. Test new seam with focused synthetic unit cases; one future owner actual product PDF visual/copy gate after approval. Do not rerun prior P2-U2d/U2f/U2g font gates.

Current product Unicode PDF: VISUAL_FAIL. P2: REVIEW_REQUIRED. P8: NOT_CERTIFIED. Release font approval: NOT_GRANTED. This record is an engineering assessment, not a legal sign-off.


## Gated offline user-export implementation (27 October 2026)

New production-code SOURCE integration, not an accepted release:
- `backend/pdf_release_font_loader.py` is the one mandatory source-only approval gate. At this checkpoint `RELEASE_APPROVAL_STATUS = "NOT_GRANTED"`, `RELEASE_APPROVAL_REFERENCE = ""` and `RELEASE_PINNED_FILES = ()`. No HTTP argument, environment variable, user-home receipt or installed OS font can enable it. It cannot use the developer-only six-file manifest as release authority.
- `backend/reports.py::render_pdf_for_export` now delegates to the gate; `backend/main.py` routes its existing authenticated `/api/reports/{report_id}/export/pdf` through this function. Because release approval is absent, normal PDF bytes still use `render_pdf(report)` exactly as before. HTML remains `render_html(report)` unchanged. No new public route or request parameter.
- Once independently approved by an actual reviewed code change, the loader requires **exactly six** code-pinned role/kind/basename/size/SHA-256 tuples, one non-empty independent approval-reference identifier, and six corresponding files under `backend/assets/pdf_fonts` beside the bundled backend module. Existing `verify_pdf_font_files` rejects a missing/redirected/mutated file and verifies full OFL notice text; no fallbacks, downloads, font conversions or source copies are provided.
- The approved path registers `DocumentUnicodeTTFont` using separate noncolliding release face names and real glyph maps, asserts the process ReportLab object identity, and renders with the already owner-verified `UnicodePDFContext`. An in-process lock protects both registration and the entire release Unicode render because ReportLab font allocation is process-global; six file hashes are checked every export. This is a conservative starting design, **not** a proven performance/concurrency certification. A failed approved-font check gives a safe error, never a corrupt or silently downgraded PDF.
- `tests/test_p2_pdf_release_export_gate.py` contains 12 NEW, synthetic-only release gate contracts: unchanged default bytes, environment cannot approve, malformed/missing/duplicate code pins, missing/changed resource, safety of approved context injection, refusal to silently fallback on renderer failure and thread serialization. Tests are AUTHORED, **not yet owner Windows-verified**. No new executable/PDF build or current user report changed.

### Final source edit prerequisite before activation

The following must occur together in a reviewed **new GitHub change** after independent owner/legal decision:
1. Sign off exact THREE unchanged original font binaries and their THREE complete corresponding OFL.txt notices, including Noto Sans SC copyright header's Reserved Font Name `Source`, variable font face selection, public notice access and no author endorsement. Do not silently convert or subset input binaries to create release assets.
2. Code-pin all six exact FINAL basename/byte-size/lowercase SHA-256 values into the release loader, with a traceable independent approval identifier. Original Git blob SHA-1 pins and private DevQA receipts are **not** release authority.
3. Include all six files as read-only sidecar resources relative to `backend/pdf_font_resources.py` and include discoverable licences in the packaged software; no test-only startup hook, source working folders or user-home fallback. Explicitly test standalone/offline extraction.
4. Only then change `RELEASE_APPROVAL_STATUS` to `GRANTED_BY_INDEPENDENT_OWNER_REVIEW` by reviewed SOURCE change, with fail-closed repeated/concurrent/authenticated PDF export and end-user visual/copy/extraction tests. Test 8 GB load and P8 offline installer separately. Any incomplete approval must stay `NOT_GRANTED`.

**Current state remains:** `release_font_approval=NOT_GRANTED`, normal user Unicode PDFs still `VISUAL_FAIL`, P2 `REVIEW_REQUIRED`, P8 `NOT_CERTIFIED`. The earlier single synthetic opt-in Unicode report extraction/visual `SCOPED_SYNTHETIC_DEVQA_VISUAL_PASS` is still accepted and MUST NOT be rerun.
