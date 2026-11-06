# PilotODIN P2 | Single approval decision required before Unicode PDF shipping

**Date:** 27 October 2026  
**Scope:** Release-font and redistribution decision only.  
**Current decision:** `NOT_GRANTED`  
**Do not substitute this request for an actual recorded owner decision or legal review.**

## 6 November 2026 | Independent upstream OFL and face metadata review, no release grant

**Reviewed scope:** This is a **read-only, external-source verification**, not an owner approval or a new font source asset delivery. The exact upstream `google/fonts` Git commit `e7db6ca603fd4862010383ff17ffd6cc4ffac1c0` was queried directly for the original **three OFL.txt notice text files** and corresponding `METADATA.pb` source records. All three notices matched the existing candidate dossier's byte counts and original Git blob SHA-1s. No font binary was fetched, transformed, installed or redistributed; **none of the final six release SHA-256s is thereby established**.

| Upstream original file | Git blob SHA-1 independently verified | Text bytes | First copyright/RFN finding |
| --- | --- | ---: | --- |
| `ofl/notosans/OFL.txt` | `6843f31878c9945e1e71e1baa275546b4eefead8` | 4,396 | Copyright 2022 The Noto Project Authors |
| `ofl/notosanssc/OFL.txt` | `1c9f43281b8f216c5461fe9ac729afbade7724e4` | 4,388 | Copyright 2014–2021 Adobe; Reserved Font Name **Source** |
| `ofl/notosanssymbols2/OFL.txt` | `7c95767f5c669c448148e7e6c8fc4ee2c85128b1` | 4,383 | Copyright 2022 The Noto Project Authors |

**Original upstream metadata, same pinned commit:** `ofl/notosans/METADATA.pb` blob `87f93924f3fa3dbdfd2a5e38329d409159fa5126` identifies regular variable file `NotoSans[wdth,wght].ttf`, PostScript `NotoSans-Regular`. `ofl/notosanssc/METADATA.pb` blob `2da7e54d742a000810c6ec99ffae919158d9d4d6` identifies `NotoSansSC[wght].ttf`, `post_script_name=NotoSansSC-Thin`, declared `weight=400`, variable `wght` axis 100–900 and the **Source** RFN. `ofl/notosanssymbols2/METADATA.pb` blob `431ed8ccedced5b20f439d4df26871a98e68b6b2` identifies `NotoSansSymbols2-Regular.ttf` and PostScript `NotoSansSymbols2-Regular`. Metadata describes the upstream family and does **not** verify chosen ReportLab drawing weight or final packaged bytes.

**Licence interpretation boundary:** The [OSI SIL OFL 1.1 text](https://opensource.org/license/OFL-1.1) expressly permits original and modified fonts to be bundled with software provided the copyright notice and licence accompany each copy and the RFN restriction is respected for **modified versions** (see licence conditions 2 and 3). The proposal remains **unchanged upstream originals**, not derived/renamed fonts. This is a general licence reading, **not an independent legal opinion, release clearance or actual owner approval**. The reserved `Source` name remains a review item if anyone proposes a conversion/renaming/derivative. The previous real synthetic PDF's thin CJK appearance requires a deliberate unchanged-variable-font face/weight presentation decision before release.

**What remains unavailable and must not be fabricated:** No immutable **final six release SHA-256/size/path** attestations from actual distribution-ready bytes; no signed independent owner/legal review reference; no chosen final CJK appearance decision; no proven accessible in-app Third-Party Notices location and full three-notice distribution; no packaged offline installed Unicode PDF, concurrent export or corrupt-asset native evidence. The preexisting `28/28` source and authenticated HTTP Windows test result is accepted **at its original scope** and must not be rerun merely to repeat this source notice review. `backend.pdf_release_font_loader.RELEASE_APPROVAL_STATUS="NOT_GRANTED"`, empty reference and empty pins remain mandatory. The legacy PDF path stays active. **No font binaries or licence files were committed in this review.**

**Next binding decision:** Independent owner/designated reviewer either (a) documents explicit approval of the exact original unchanged three fonts plus three full notices, chosen SC face and accessible notice distribution, and separately approves final actual six-file SHA-256 identities before a deliberate release-asset source commit; or (b) **defers end-user mixed Unicode PDF** while retaining legacy export. Neither branch is silently selected here. P2 remains **ACTIVE / REVIEW_REQUIRED** with the Unicode release dependency **BLOCKED ON OWNER DECISION**; no installer or phase transition is authorised.

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


## Source staging and integrated Windows route QA (27 October 2026)

A new `.gitignore` guard now protects the entire root `/build/` directory, including previous and future synthetic PDFs which may embed subsets of development fonts, plus unapproved `/backend/assets/pdf_fonts/`. The repository previously failed to ignore newer proof subdirectories, so these files could have appeared in GitHub Desktop staging. Do not upload font binaries, individual original OFL files, proof PDFs or private review receipts. Any later explicitly approved asset delivery must be a separate reviewed release-source/package change, never an incidental `git add` of ignored DevQA assets.

The pending release loader now rejects unsafe proposed font basenames before opening resources. The single consolidated `Run_PilotODIN_P2_Offline_Export_Source_DevQA.bat` suite contains **23 focused tests (14 source integrity + 9 real in-process authenticated HTTP)**, including unchanged synthetic *actual* PDF and HTML export through the normal default route, no data mutation, incorrect release/unsafe path refusal and safe partial-approval 503 responses. The existing **manual** Windows backend GitHub Actions workflow references the same isolated runner; no workflow was dispatched or Windows run accepted in this checkpoint. Test results remain **PENDING**, not green by assumption.

No release approval reference, independent final six SHA-256 identities or final copyright/notice face decision is present. `RELEASE_APPROVAL_STATUS="NOT_GRANTED"` remains mandatory; no source-only test can grant font redistribution. The previously accepted one-page DevQA Unicode PDF visual/copy/extraction proof remains accepted without rerun. User-facing Unicode PDFs, concurrent packaged exports and P8 native installer remain unapproved.


## Production sidecar conditional font bundle seam (27 October 2026)

A new **default-denied**, source-controlled packaging preflight has been integrated into the EXISTING `desktop/Build_Python_Sidecar.ps1` (no new installer). The script calls `tools/p2_pdf_release_bundle_preflight.py` *before pip/PyInstaller*. It reads `backend/pdf_release_font_loader`'s status/reference/immutable six-file SHA-256 source policy and reuses the same `backend/pdf_font_resources.verify_pdf_font_files` module-relative checks as the authenticated PDF route. It is **READ ONLY** and cannot grant approval.

- **Current NOT_GRANTED/empty manifest:** Preflight returns `NOT_APPROVED_LEGACY_ENGINE_ONLY` with `include_font_resources=false`. The old scientific Python sidecar build arguments and legacy PDF export behavior are preserved; **NO Unicode font files or OFL notices are included by default**.
- **Future independently approved source change only:** With exact 3 font and 3 full notice files, source-pinned final SHA-256, reviewed approval reference, and all six files passing module-relative verification in `backend/assets/pdf_fonts`, it may return `APPROVED_PACKAGING_SOURCE_READY`. The original PyInstaller builder then includes the *single* six-file resource directory at its canonical `backend/assets/pdf_fonts` destination via `--add-data`. That is a technical conditional step, **not** legal review or proof of actual installer access to Third-Party Notices.
- **Incomplete or inconsistent status/assets:** Hard pre-build `BLOCKED`, never automatically copying developer-only fonts, downloading, converting variable files, using user data/home, or pretending unapproved shipping is allowed.

Five new focused source contracts were added to the existing `tests/test_p2_pdf_release_export_gate.py`, now **19 authored**. The authenticated in-process HTTP route suite still has **9 authored**, totalling **28** in the preexisting single `Run_PilotODIN_P2_Offline_Export_Source_DevQA.bat`. The manual Windows backend GitHub Actions workflow already references the same runner. **All 28 remain pending owner Windows / CI execution**, and no preflight or PyInstaller build has yet run on an approved font set. This is not release/installer acceptance.

Pending: independent owner/legal final OFL/RFN/face decision, exact all-six SHA-256, safely accessible third-party notices, verified frozen/installed offline resource resolution, actual user-facing mixed Unicode PDF, corrupted/missing asset, repeat/concurrent export and P8 tests. `RELEASE_APPROVAL_STATUS=NOT_GRANTED` is unchanged.


## 28-case actual owner Windows API and packaging-source acceptance (27 October 2026)

Owner ran the consolidated `Run_PilotODIN_P2_Offline_Export_Source_DevQA.bat` on their Windows computer. Screenshot shows `SCOPED_OFFLINE_EXPORT_ROUTE_SOURCE_PASS` with **28/28** exact focused contract cases: `offline_source=19` and `actual_http_route=9`. The in-process real FastAPI export endpoint, synthetic legacy PDF/HTML snapshot, desktop session guard, immutable report forwarding, source release-policy boundary, conditional packager preflight and missing/bad identities passed their currently authored source tests. No real user data, private fonts or old P2 font proof were used or repeated. The acceptance covers *source-only/in-process mock and synthetic API tests*, not a built/frozen or installed executable. Real concurrent PDF exports remain `NOT_TESTED`.

This now **supersedes older pending 12/8, 14/9 and 19/9 test references elsewhere in this historical decision record**. The scope is accepted and no rerun is required. The release decision fields ABOVE are still entirely `PENDING`: owner success in 28 API and source tests neither grants OFL redistribution approval nor provides final six approved SHA-256s. There are still no release assets in `backend/assets/pdf_fonts` and `RELEASE_APPROVAL_STATUS=NOT_GRANTED`. No normal user-facing Unicode PDF or installer has passed release acceptance.

**Next substantive action is an independent original-font/notice/face/release-hash decision**, not additional source-only font testing. Once explicit signoff exists, deliberately stage the six exact binaries/notices via reviewed source and carry out one real offline packaged authenticated Unicode PDF/repeat/concurrent/visual/corrupt-asset verification. Keep existing fonts, sidecar DevQA tests and the already visually accepted one-page Unicode proof closed.
