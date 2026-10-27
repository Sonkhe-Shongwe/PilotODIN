# PilotODIN P2 | Single approval decision required before Unicode PDF shipping

**Date:** 27 October 2026  
**Scope:** Release-font and redistribution decision only.  
**Current decision:** `NOT_GRANTED`  
**Do not substitute this request for an actual recorded owner decision or legal review.**

## The precise choice

The proposed release uses **three ORIGINAL UNMODIFIED font binaries** from
`google/fonts@e7db6ca603fd4862010383ff17ffd6cc4ffac1c0`, plus the
THREE complete corresponding `OFL.txt` notices.

| Role | Original binary | Source bytes | OFL notice shipped under proposed filename |
| --- | --- | ---: | --- |
| regular | `NotoSans[wdth,wght].ttf` | 2,049,096 | `NotoSans-OFL.txt` |
| cjk | `NotoSansSC[wght].ttf` | 17,772,300 | `NotoSansSC-OFL.txt` |
| symbol | `NotoSansSymbols2-Regular.ttf` | 1,233,128 | `NotoSansSymbols2-OFL.txt` |

Existing source candidate identities, including original Git blob SHA-1, source commit, exact notice sizes and names, are already recorded in
`tools/p2_pdf_font_candidates.json`. Their identity was rechecked in the owner's
P2-U2g read-only DevQA dossier and they passed the actual opt-in Windows
single-page Unicode visual/extraction experiment. Those checks are **not** a
release approval.

### Conditions being reviewed

The three source notices use **SIL Open Font License 1.1**. Under its terms,
unmodified fonts may generally be bundled with software, including commercial
software, when the required copyright statements and complete licenses are
included; fonts cannot be sold by themselves, and the copyright holders must
not be falsely presented as endorsing PilotODIN.

**Specific caution:** Noto Sans SC's original copyright header declares the
Reserved Font Name **"Source"**. The proposed plan is to ship the unchanged
original binary. Do not convert it to a static face, modify its outline, rename
the internal family to a reserved name, or ship a derivative without a separate
face/RFN compliance review. Noto Sans and Noto Sans Symbols2 have no equivalent
family-specific RFN declaration in the inspected opening headers, but that is
not blanket trademark or endorsement clearance.

Original three notices for direct review:
- https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/notosans/OFL.txt
- https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/notosanssc/OFL.txt
- https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/notosanssymbols2/OFL.txt

OFL text: https://opensource.org/license/OFL-1.1

## Hard technical conditions before enabling end-user export

1. Independently verify each of the final SIX exact release files (not just
   the DevQA copy) against original bytes, size, upstream commit and **SHA-256**.
   Enter final six SHA-256s in a reviewed SOURCE commit. **Not present or
   approved yet**; no substitute hashes can be invented from Git SHA-1.
2. Verify no font binary was converted, renamed internally, subset or modified
   before packaging. Review Noto Sans SC weight/legibility, noting the prior
   `NotoSansSC-Thin` actual PDF result. Keep any face adjustments as a
   separately reviewed choice rather than silently editing the binary.
3. Install all six files in immutable offline sidecar
   `backend/assets/pdf_fonts`, not the user home or system font directory.
   Include full three OFL notices in the application's accessible Third-Party
   Notices and with all redistributed font copies as required.
4. Run one authenticated normal-route saved PDF export, unmodified HTML export,
   missing/corrupt asset deny, repeated/concurrent export, copy/extraction and
   clean offline Windows installed test. Existing U2d/U2f/U2g and synthetic
   visual acceptance should NOT be repeated as isolated tests.

## Owner decision fields: PENDING, not prefilled

- Approval of the **exact original unchanged fonts and licences**: `PENDING`
- Final six-file SHA-256 confirmation and asset paths: `PENDING`
- Noto Sans SC RFN and chosen unchanged variable face review: `PENDING`
- Third-Party Notices distribution location: `PENDING`
- Independent approval evidence/reference and date: `PENDING`

The developer must never set
`backend/pdf_release_font_loader.RELEASE_APPROVAL_STATUS` to
`GRANTED_BY_INDEPENDENT_OWNER_REVIEW` based solely on this request or a
successful DevQA test. No technical source code may impersonate that decision.

## Current source position

The actual `/api/reports/{report_id}/export/pdf` route has already been
connected to `backend.pdf_release_font_loader`. The loader currently has
`RELEASE_APPROVAL_STATUS="NOT_GRANTED"`, `RELEASE_APPROVAL_REFERENCE=""` and
`RELEASE_PINNED_FILES=()`, so normal users still get the legacy PDF renderer,
not the new mixed Unicode font bundle. The route cannot be activated with a
browser parameter or environment variable. No fonts or installer were added.

`tests/test_p2_pdf_release_export_gate.py` (12 source contracts) and
`tests/test_p2_pdf_export_route_integration.py` (8 isolated authenticated
HTTP-route contracts) are authored and grouped into ONE future Windows source
acceptance through `Run_PilotODIN_P2_Offline_Export_Source_DevQA.bat`.
These have NOT been owner Windows-executed. They do not authorize release.

**Until the explicit decision and final immutable package are approved:**
P2 `REVIEW_REQUIRED`; normal mixed-script PDF `VISUAL_FAIL`;
Unicode release `NOT_ACCEPTED`; P8 `NOT_CERTIFIED`.
