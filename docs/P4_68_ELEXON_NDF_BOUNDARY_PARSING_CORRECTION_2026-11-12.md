# PilotODIN P4-68 | Elexon NDF national boundary parsing fix

**Date:** 12 November 2026. User-supplied Windows PowerShell screenshots were inspected as observed operational research output. Original source: current GitHub P4-67 at `d72f56721ac5ea6ee32487b85c939df058f1ad31`.

## Observed independently fetched JSON, user-side

- Original request documented by prior P4-67 script: one HTTPS GET for publication-window 2025-06-14. Owner-side script output reported `response_provenance=DIRECT_OFFICIAL_ELEXON_HTTPS_REQUEST`; raw JSON saved as `elexon_ndf_2025-06-14_original.json`, response SHA-256 `6c0e7264766d71a0dbab9e64fe1eb176f8df5ab92abfd2e92b500d69069014e1`. **The raw JSON bytes have not been independently received or authenticated within this session**, so do not promote the owner-observed response to independently replicated source data.
- Terminal log: 2,816 Elexon records total, 1,531 records for `settlementDate=2025-06-15`; 1,531 were all `dataset=NDF` and `boundary=N`. Sample was `publishTime=2025-06-14T23:47:00Z`, periods 3, 4 and 5, demands 18,840 / 18,658 / 18,130 MW. This later publication sample does not prove presence/absence of a separate 08:45 UTC NESO day-ahead vintage.
- The original P4-67 filter `boundary not in (None, "", "National")` discarded all 1,531 relevant rows, leaving zero candidate vintages and the misleading verdict `NO_ELEXON_NDF_DATA_FOR_TARGET_DAY_IN_RESPONSE`. Exact defect shown by observed data and source, not inferred lack of Elexon data.

## Bounded corrective scope

- P4-68 adds the official national `N` code to accepted national-boundary values; non-national codes still rejected. Results also expose the number of accepted target rows, separate from invalid target rows. There is **no synthetic merging of half-hourly forecasts from different publication instants**; each `publishTime` remains its own candidate group.
- Pre-fix local regression **2/14 FAIL** (national code improperly rejected and mixed partial code failed to be counted); post-fix **14/14 PASS**. No application backend/frontend or old production profile modified; synthetic tests, no network.
- The user's real `elexon_ndf_2025-06-14_original.json` is **not available in this conversation**. The next evidence action is one **offline**, no-fetch comparison using that preserved raw file; matching all 48 period values and derived UTC publish timestamp would be field-matching evidence only. The offline mode cannot independently authenticate provenance and therefore exits nonzero by design. If the genuine historical vintage is missing or differs, the result must stay failed/unverified, with no forced correction.
- No claim of authentic cross-source value match or independent operational decision utility; original Gate C **UNVERIFIED**, P4 active, R01–R06 open, historical original whole-app-data STRICT FAIL unchanged, P5 unauthorised, P8 uncertified.

## Relevant official source

- Elexon BMRS NDF dataset official docs: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/NDF
- Official Elexon legacy BMRS API and Data Push User Guide documents National boundary code `N`: https://assets.elexon.co.uk/wp-content/uploads/2018/09/28160411/BMRS-API-Data-Push-User-Guide.pdf
