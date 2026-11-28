# Public bike-sharing research fixture (no real operational approval)

This fixture is an **unchanged, byte-for-byte copy** of the previously supplied
disposable CSV `PilotODIN_Bike_Daily_PreDay_731.csv`, generated from the user's
public UCI Bike Sharing `day.csv` archive. The committed CSV has **731 rows,
8 columns, 20,701 bytes**, SHA-256:
`51e105f75acf827e5c089a8f30925fe8ab90c59df46201a9d724ad5f67588636`.

**Provenance:** UCI Machine Learning Repository, Bike Sharing Dataset (dataset
275). Original data for the Capital Bikeshare system, Washington DC, 2011–2012.
Creators: Hadi Fanaee-T and João Gama (2013), "Event labeling combining
ensemble detectors and background knowledge", *Progress in Artificial
Intelligence*, DOI 10.1007/s13748-013-0040-3.
https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset

**Source archive:** `bike+sharing+dataset.zip`, SHA-256
`b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401`.
Source `day.csv` SHA-256:
`a6bcf826782d3c0fbfdcbeead17cd0884185a0dafe8ff10cd48a874ee7ba18be`.
UCI lists the dataset under **Creative Commons Attribution 4.0 (CC BY 4.0)**,
https://creativecommons.org/licenses/by/4.0/ . Credit is retained here.

**Research derivative changes:** Rename `dteday` to `date`, `cnt` to
`daily_rentals_target`; retain `season`, `yr`, `mnth`, `holiday`,
`weekday`, `workingday`. Drop `instant` (index), `casual` and
`registered` (components of `cnt`, direct target leakage); drop
`weathersit`, `temp`, `atemp`, `hum`, `windspeed`
(retrospective same-day observations unavailable for a documented pre-day
prediction time). No original UCI record was added or removed.

**Boundary:** Public historical observations are NOT signed-off business
outcomes for an actual Capital Bikeshare decision. The date is retained as a
**time split key, not a predictor** when fitting any separately authorised
model. The `/preparation` endpoint itself does not automatically remove it:
operators must explicitly choose a time split. No training, real business
Gate C approval, native Windows acceptance or deployment is performed in
this test. Dataset values are public historical observations, not uploaded
private customer records.


## P4-53: additive nominal-code research derivative

The optional `public_bike_daily_categorical_preday_731.csv` is **another
user-data-free research view** derived only from the original 731-row
`public_bike_daily_preday_731.csv`. It contains exactly the same `date`,
`daily_rentals_target`, column order, rows, and calendar-code information.
Every nominal numeric code in `season`, `yr`, `mnth`, `holiday`,
`weekday`, `workingday` is converted reversibly into text:
`season_1`, `yr_0`, `mnth_01`, `holiday_0`, `weekday_6`,
`workingday_0` etc. We do not invent semantic labels or operational
availability from category numbers. This prevents the generic numeric-dtype
preprocessing path from automatically treating e.g. season or weekday codes
as continuous magnitudes; it allows the existing categorical one-hot path.

- Derived file SHA-256: `8981926c70d117fd487ce5ac5d0381be30dd159488576646c67978a2d3139a2e`; 51,950 bytes; 731 rows / 8 fields.
- All source totals and dates preserve their exact text values; reverse mapping
  from each code string reproduces original numeric code, tested across all rows.
- Dates must still be explicitly chosen as **Time** split metadata, not
  predictors. The current `/preparation` endpoint still *lists* the date
  in available features prior to split selection.
- `holiday`, `workingday` and possibly season policy still need real
  historical as-of-time availability evidence. The public Capital Bikeshare
  system data documentation (https://capitalbikeshare.com/system-data)
  describes **monthly** published trip history in its current policy,
  not verified daily outcome publication for 2011-2012.
- **No estimator fit, no model score, no operational business authorisation,
  no native app/owner data access**. The typed derivative is not a claim
  that original bike data's category metadata was operationally validated.

Public source: https://archive.ics.uci.edu/dataset/275/bike-sharing-dataset
(UCI lists season, year, month, holiday, weekday and workingday as
categorical/binary variables; CC BY 4.0.)
