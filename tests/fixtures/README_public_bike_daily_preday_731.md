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
