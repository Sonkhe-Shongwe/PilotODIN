# PilotODIN P4-67 | Independent vintage comparison verifier, no live cross-source outcome

**Date:** 12 November 2026. **Mode:** locally tested research verifier and exact uploaded-source sample. **No actual Elexon historical API payload** could be retrieved from the available browsing/container network, so **zero independent forecast records have been compared** and **Gate C remains UNVERIFIED**.

## Authentic checkpoint

- Active GitHub checkpoint entering P4-67: `610708aef8b6e8070bd42276ed67d1578765a547` on `feature/live-dev-workspace-20261023`.
- P4-65 original owner-supplied NESO CSV exact bytes: 9,740,124 bytes, SHA-256 `a9992f87a766f3cf3307b24cc7c9940e797bdea855427e6e31647984e27bdc0f`.
- Chosen *unexceptional* test target: 2025-06-15, 48 settlement periods; NESO's **printed local GMT/BST publication label** is `2025-06-14T09:45:00Z`. UK summer time interpretation implies `2025-06-14T08:45:00Z` UTC, **derived from NESO alone and not independently matched**. Period 1 is **19,640 MW**, period 2 **19,083 MW**.
- Official published feed: Elexon NDF dataset endpoint, `https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/NDF`, `https://developer.data.elexon.co.uk/`. It documents publish-time filters, National Demand forecasts and publication timestamps. Exact `data.elexon.co.uk` API responses are inaccessible via this session's web and shell environments. This is an **access limitation**, not evidence that Elexon has no historical records.

## Implemented bounded research instrumentation

- A standalone stdlib-only, no-model Python verifier `qa/p4_neso/verify_vintage.py`, with tests `qa/p4_neso/test_verify_vintage.py` and usage in `qa/p4_neso/README.md`.
- Fixed read-only user-input SHA-256, single-day official Elexon API request, HTTPS host redirect refusal, raw JSON preservation only when explicitly requested, max response size, publication-time and settlement-period matching, DST-conscious local NESO to UTC mapping, full MW equality checks, suspicious schema rejection, explicit provenance tiers and strict nonzero exit for offline JSON matches.
- **11/11 synthetic tests PASS locally** (including a mocked HTTP response, never a real network response); Python byte-compilation PASS; one **read-only direct check of the owner's actual CSV** confirms target 2025-06-15, 48 periods, 09:45 printed local publication, and MW values 19,640/19,083 for periods 1/2. This does not create an independent Elexon match.
- `--fetch` live network attempt was **not performed by this script** in the current environment. Prior public API access via web/container reported inaccessible (including DNS resolution failure in the runtime). No fabricated downloaded data or false positive.

## Verdict and later use

**Tool: locally synthetic-verified, field-level logic only. Independent Elexon vintage match: NOT TESTED. Original real-business Gate C: UNVERIFIED.** Do not conflate documentation or synthetic tests with acceptance.

One separate future non-invasive public data retrieval and snapshot could supply a limited matching record, but requires Elexon reachability; a genuine decision owner, agreed prediction moment, independent as-of inputs, a measured human decision intervention, privacy/fairness assessment and owner review would still be absent. No model training, product code, manual CI dispatch, native build, installer, original app-data path or installed PilotODIN modification in this step.

**Binding P4 disposition:** P4 ACTIVE, P4-R01–R06 OPEN, original whole app-local-data historical STRICT FAIL (320 vs 346 files, writer UNKNOWN) unchanged; P5 NOT AUTHORISED; P8 NOT CERTIFIED.
