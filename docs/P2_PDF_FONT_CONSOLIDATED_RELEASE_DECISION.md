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
