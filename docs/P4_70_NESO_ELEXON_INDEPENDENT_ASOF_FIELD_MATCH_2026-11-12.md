# PilotODIN P4-70 | Independently reproduced NESO/Elexon historical as-of forecast comparison

**Date:** 12 November 2026. **Evidence:** uploaded public source bytes examined independently. **Scope:** one historic research date only. Not a model experiment, prospective trial, official NESO operational approval or Gate C signoff.

## Exact independent input identity

| Original public file uploaded by owner | Bytes | SHA-256 |
| --- | ---: | --- |
| NESO `1b-incentive.csv` | 9,740,124 | `a9992f87a766f3cf3307b24cc7c9940e797bdea855427e6e31647984e27bdc0f` |
| Elexon `elexon_ndf_2025-06-14_original.json` | 483,669 | `6c0e7264766d71a0dbab9e64fe1eb176f8df5ab92abfd2e92b500d69069014e1` |

The Elexon JSON hash **matches the user's earlier real HTTPS retrieval log** and the independently uploaded bytes, strengthening chain of custody. However, an independent Elexon HTTPS re-fetch was not performed here, no authenticated original-server signed receipt exists, and the raw public JSON/CSV are **not committed to this repository**. Do not equate reproducible downloaded bytes with a cryptographic provider certification or exhaustive historical archive.

## Independently reproduced as-of comparison

- Target: **2025-06-15** on the GB local settlement day, with **48** valid period identifiers. NESO source header `Publish_Datetime=2025-06-14T09:45:00Z` is **documented as a GMT/BST local wall-clock label despite a literal `Z`**; the selected research cutoff is **2025-06-14T08:45:00Z UTC**, not an established business decision cutoff.
- Elexon archived JSON has **2,816 total NDF rows**, with **1,531** valid period-coded `settlementDate=2025-06-15` and national `boundary=N`. **198** valid rows are at or before this hypothetical cutoff; **1,333** target-day records are future revisions and **excluded**.
- Independent second stdlib Python calculation confirmed **every one of the 1,531 target records' `startTime` values** aligns with the correct UK-local settlement period UTC start. Selected latest-in-time non-conflicting records provide **48/48 unique periods and exact NESO forecast MW values**, **0 mismatches**, **0 missing**, **0 conflicting latest timestamp**, **0 invalid target rows**.
- **38** chosen values, periods **11–48**, have Elexon `publishTime=2025-06-14T07:45:00Z`; **10** chosen values, periods **1–10**, have `publishTime=2025-06-14T08:16:00Z`. At 08:15:59 UTC only 38/48 matched; at 08:16:00 UTC all 48/48 matched. This observation shows **the forecast vector was reconstructible from one-day published Elexon entries 29 minutes before the source-derived cutoff**, **not** that the whole NESO forecast was issued as one simultaneous event.
- The earlier owner-side P4-69 result **48/48** is now independently reproduced from the uploaded raw files, not merely inferred from screenshots. Existing **25/25** local synthetic tests independently re-ran and passed; standalone P4-69 still deliberately exits 2 even on observational equality to prevent false acceptance.

## Remaining essential evidence boundary

This single historic as-of field match establishes a **real source-provenance feasibility sample**; it does not certify every vintage across 2021-2026, source availability at an approved operational decision cutoff, historical correction policies, independent operational pilot user/permission, quality improvement relative to NESO baseline, measured intervention utility/cost/fairness, or P4 native Windows/offline 8 GB acceptance.

**P4 ACTIVE; P4-R01–R06 OPEN; original business Gate C UNVERIFIED; historical original entire app-local-data-tree STRICT FAIL unchanged; P5 NOT AUTHORISED; P8 NOT CERTIFIED.** No model fit, GitHub CI dispatch, app source changes, native build, installer, original owner data access or risk waiver.

**Next justified evidence:** only with independently grounded real operational decision authority, broaden source-as-of checks or define a prospective explicitly approved decision evaluation. Do not repeat data fetches merely to produce additional metrics. The single-day source check **does not** give permission to train, dispatch CI, or proceed to P5.
