# PilotODIN 1.0 | P4-51 Public UCI bike data disposable import and Prepare inspection

**Date:** 12 November 2026. **Source/test commit:** [`ca24e9859766c0cef4daceaac58093d00d2aecb9`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/ca24e9859766c0cef4daceaac58093d00d2aecb9). **Exact-source workflow:** [#43188757652](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43188757652), completed success, 3/3 jobs.

## User request and true boundary

The user agreed to import the pre-day UCI Bike Sharing CSV into a new disposable PilotODIN project and inspect a regression hypothesis and preparation warnings, while preserving the original Windows installation and source data. This was executed using **an actual FastAPI TestClient import against the current GitHub backend source in a disposable GitHub Actions runner**. It did NOT create a project in the user's installed Windows desktop or run a native Tauri/WebView2 build, nor test the bike CSV through the browser UI. Do not mislabel it as owner-native acceptance.

## Recorded public-data lineage and test setup

- Uploaded public historical source: UCI Bike Sharing, daily `day.csv`, 2011–2012 Capital Bikeshare. Original data credited to Hadi Fanaee-T and João Gama (2013). Attribution and licence: [tests/fixtures/README_public_bike_daily_preday_731.md](../tests/fixtures/README_public_bike_daily_preday_731.md). UCI archive CC BY 4.0.
- User-prepared derivative is checked into `tests/fixtures/public_bike_daily_preday_731.csv` as exact verified bytes: SHA-256 `51e105f75acf827e5c089a8f30925fe8ab90c59df46201a9d724ad5f67588636`, Git blob `49369dc29a5a076d3c6267190a4cea8dccf6ce3a`, **20,701 bytes**, **731 rows**, 8 columns, no blanks, unique daily dates. Original ZIP preserved, no source rows altered.
- The columns are `date`, `season`, `yr`, `mnth`, `holiday`, `weekday`, `workingday`, `daily_rentals_target`. `casual` and `registered` excluded as arithmetic components of `cnt`. Historical same-day `temp`, `atemp`, `hum`, `windspeed`, `weathersit` excluded because their day-ahead availability has not been proven.
- `tests/test_p4_bike_public_import.py` uses `tmp_path` with a brand-new `HOME/datasets`, `HOME/models`, and SQLite; never imports another user's project, rewrites old app data or trains a model. It verifies SHA and source immutability before and after the request.

## Actual automated API results (public bike data, current source)

| Step | Observed/tested outcome |
| --- | --- |
| `POST /api/projects` multipart upload | HTTP **201**; new disposable project saved, exact CSV bytes persisted under temp `datasets/` |
| Import profile | **731 rows, 8 columns, zero missing cells, zero duplicate full rows**, `daily_rentals_target` among name hints |
| Quality working source | Version **0** with frame matching parsed original derived CSV |
| `GET /api/projects/{id}/target-opportunities?expected_version=0` | HTTP **200**, complete (not truncated) scan, `daily_rentals_target` **reviewable**, **regression** hypothesis, 731 labelled, 0 missing, **no automatic target selection/training**, business relevance **unverified** |
| `GET /api/projects/{id}/target-opportunities/inspect` | HTTP **200**, same reviewable regression under bounded manual scan, no truncation, `training_authorised=false` |
| `GET /api/projects/{id}/preparation?target=daily_rentals_target` | HTTP **200**, regression plan, **7 available predictors**, 7 feature-audit entries, 0 missing target, warnings include time/group validation need |
| Side effects and isolation | Experiment list remains empty, temp model folder remains empty, input fixture SHA unchanged; only new temp test-project files were written |

**Safety caveat:** The Prepare endpoint lists `date` among available features. For a valid day-ahead demonstration the operator must explicitly choose **Time** validation with **`date`** split key, which backend training excludes from predictors. A random split or including date without a time-aware strategy would not establish generalisable future performance. **No training was authorised, requested or performed here**, so the split was not actually exercised on this dataset.

## Complete exact-source CI distinction

[Actions #43188757652](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43188757652) at `ca24e98`:

- Linux Python suite **164 PASS**, including the *one* new actual public-bike import/Target/Prepare API integration test.
- Node source/UI contract suite **45 PASS, 0 fail**, TypeScript/Vite application build **PASS**.
- **9 disposable real-HTTP Chromium tests PASS**, run against their separately generated synthetic target review fixtures. **No claim** that these browser tests navigated the bike CSV or native Windows.
- Windows host preservation/WebView safety scripts **PASS** with fake files under PowerShell 7.6.9 and 5.1.20348.5773, NOT owner original application data.

No Tauri native EXE compilation, installer, Qwen inference, owner-machine Windows test, real business acceptance, live operational benefit or real-data model training.

## Gate C and project phase decision

This historical public data shows a credible **regression hypothesis**, a source-backed target definition and feasible read-only product import. It does not supply independent real Capital Bikeshare decision-owner consent, contemporaneous as-of-time operations features, the cost/benefit of acting on predictions, live station capacity/resource decisions, or an approved lawful/fair operational intervention. **Gate C remains UNVERIFIED**. No model score/performance estimate has been produced by PilotODIN.

Original P4-R06 historical strict app-data full-tree FAIL (320 backed-up files versus 346 observed, 74 WebView/cache *candidates*, writer UNKNOWN) remains binding. Native N1–N12, physical 8 GB offline Qwen and Prepare/UX owner Windows acceptance remain separate. Owner earlier rejected closure by waiver. **P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**

**Next safe step:** If further evidence is wanted, review and explicitly approve a separate *disposable*, time-split model experiment (not implied by this import), or seek independent operational decision-owner evidence. Neither would erase R06 or certify native Windows release.
