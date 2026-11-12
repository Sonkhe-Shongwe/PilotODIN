# PilotODIN P4-67 | NESO versus Elexon NDF vintage verifier

A small **research-only, no-training** Python verifier. It makes at most **one** official Elexon dataset API request for a specified calendar-day publication window. It can also compare against previously saved JSON without making network requests. It does not access PilotODIN runtime/data directories, execute GitHub workflows, train models, install binaries or change the uploaded NESO input.

## Prerequisites

- Python 3.9+ with an available IANA `Europe/London` time-zone database (`tzdata` if your Python/Windows environment does not already provide it). No guessed time offset is ever substituted.
- A **separate, disposable** folder holding the original downloaded `1b-incentive.csv` with frozen SHA-256 `a9992f87a766f3cf3307b24cc7c9940e797bdea855427e6e31647984e27bdc0f`. Never use the original installed PilotODIN application-data folder.
- External network access to `https://data.elexon.co.uk/` only for the optional `--fetch` mode.

## Local tests, no network calls

From the repository root:

```powershell
python -m unittest discover -s qa/p4_neso -p "test_*.py" -v
```

## One small historical official API request

Choose **2025-06-15** (ordinary 48-period day). The API request covers **2025-06-14 UTC**, the previous publication calendar day. The endpoint permits a maximum one-day time window. Save the raw response exclusively in a disposable research directory:

```powershell
python qa/p4_neso/verify_vintage.py --neso "1b-incentive.csv" --target-date 2025-06-15 --fetch --save-json "elexon_ndf_2025-06-14_original.json"
```

- This performs a **single HTTPS GET** to `https://data.elexon.co.uk/bmrs/api/v1/datasets/NDF` with `publishDateTimeFrom`, `publishDateTimeTo`, `format=json`. Redirects outside official Elexon HTTPS fail closed.
- The script only accepts the exact frozen NESO CSV hash and a valid unique 46-/48-/50-period day.
- A successful response is preserved as an exact JSON byte snapshot; the report prints the SHA-256 of those bytes, the original official request URL, and all returned **target-day vintage groups** with value and timestamp agreement.
- For historical **UK summer time**, the NESO `Publish_Datetime` is treated as a **GMT/BST local clock label despite `Z`**, per the source's documentation, not as UTC. If a UK local publication time is ambiguous during the autumn DST transition, verification stops for manual treatment.
- A full field comparison requires the same local-to-UTC publication instant, all expected periods once each, all MW forecast values equal, no invalid target-day records, and a directly retrieved official HTTPS response. A user-supplied local JSON can demonstrate field equality only and is explicitly marked **not independently authenticated**.
- Exit `0`: strict field match found in a direct official HTTPS response (**not Gate C approval**). Exit `2`: no authenticated strict match, unavailable API, invalid input, inconsistent data or unverifiable provenance.
- No claim is made that the API guarantees complete historical vintage retention or that publication equates to availability at an approved business cutoff. Operational suitability, owner authorisation and measured utility remain unverified.

## Offline recheck against a previously captured Elexon response

```powershell
python qa/p4_neso/verify_vintage.py --neso "1b-incentive.csv" --target-date 2025-06-15 --elexon-json "elexon_ndf_2025-06-14_original.json"
```

This mode **does not access the network**. It intentionally exits nonzero even if values and timestamps match because the provenance of the local JSON file cannot be independently authenticated from its content alone. Keep the original raw response, retrieval details, hash and independent chain of custody.

## Evidence restrictions

- Any match supports only the observed fields for **one source vintage/day**, not a blanket as-of proof for the full 2021–2026 dataset.
- It cannot assert PilotODIN's model accuracy, forecast improvement, business savings, trial participation, safety certification or acceptance.
- Historic 2026 outcomes were already inspected in P4-65 and cannot be upgraded to a blind prospective holdout.
- P4 remains active; R01–R06 and original Gate C remain open, P5 unauthorised and P8 uncertified. No intermediate installers.

**If using the standalone ZIP instead of the GitHub repository**, extract it into a disposable folder and invoke `python verify_vintage.py` and `python -m unittest discover -s . -p "test_*.py"`. The code and the CLI parameters are identical; the path prefix `qa/p4_neso/` applies only to the GitHub layout.

## P4-68 correction following owner observed Elexon NDF response

The **official Elexon NDF national boundary is `N`**, not the literal `National` used by P4-67's original strict filter. An owner-side direct HTTPS response for the frozen 2025-06-14 publication window returned **2,816 total records**, **1,531 for target 2025-06-15**, all target records `dataset=NDF` and `boundary=N`. The P4-67 verifier incorrectly rejected those 1,531 rows. P4-68 accepts `N`, preserves existing explicit national encodings, and refuses other zonal codes. This is a **verifier defect**, not an Elexon data failure.

**Run against the saved response (no further API request):**

```powershell
python verify_vintage.py --neso ".\1b-incentive.csv" --target-date 2025-06-15 --elexon-json ".\elexon_ndf_2025-06-14_original.json"
```

The shell path in this example is local to an isolated research folder. **Do not use the original installed PilotODIN app-data path.** Unlike `--fetch`, the local-input mode deliberately **never grants independently authenticated provenance or a Gate C PASS**, even if it reports matching forecast fields. The result lists every distinct published timestamp as a separate candidate, rather than merging partial updates across publication instants. The owner-observed sample at `2025-06-14T23:47:00Z` is not itself evidence of the NESO file's original `2025-06-14 09:45 BST` forecast; compare the complete candidate set and report any discrepancies.

Initial post-fix tests: **14/14 PASS** locally, including two tests that initially failed with the genuine old boundary rule, national-boundary acceptance, non-national rejection, incomplete-vintage non-merging, and all prior safety checks. **No actual saved Elexon JSON was provided to the assistant for direct comparison in this checkpoint.**
