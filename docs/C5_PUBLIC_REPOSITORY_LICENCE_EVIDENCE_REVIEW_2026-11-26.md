# PilotODIN | Existing public repository licence and evidence review

**26 November 2026 | C-D08-R2-PUBLIC-ROUTE.** Owner reaffirmed repository strategy in the current conversation: existing full PilotODIN development repository remains public during development; after completion, make the full repository private and create a separate public demonstration repository. No additional private repository or vault required by default. No current change to visibility, repository, release scope or execution authority. Prior [readiness audit](./C5_R2_FINAL_READINESS_AUDIT_2026-11-26.md) retained as historical evidence; its default private-route recommendation is superseded. A private future repository does not undo already public disclosure, and does not determine dependency licence compatibility.

## 1. Exact pinned declaration review

Read existing Git blobs only, no wheel acquisition: [remaining plan](../qa/c5_wheel_metadata/wheel_missing_plan_20261126.json) 9938c0f8cc5be3e118dec2eff953cae94f4b5a76, [platform candidates](../qa/c5_wheel_metadata/platform_lock_candidates_45703125465.json) 6b27407f4b24942c385179bb253f692370f21df7, [production graph](../qa/c5_wheel_metadata/production_graph_receipt_45705552265.json) 70cdac979b732aadfad0c51d7e159a60840cc1ef. 63 unique wheel filenames across 51 package/version pairs; 36 explicit expressions, 27 without expression; 55 have at least one declared notice path and 8 have none; 99 declared paths counted across wheels, not distinct files or actual captured notices. All 63 still require actual archive verification. Existing five preserved notices unchanged.

| Expression | Wheels |
| --- | ---: |
| Not declared | 27 |
| BSD-3-Clause | 15 |
| MIT | 12 |
| BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 2 |
| Apache-2.0 | 2 |
| MIT-CMU | 2 |
| Apache-2.0 OR BSD-2-Clause | 1 |
| BSD-2-Clause | 1 |
| PSF-2.0 | 1 |

| # | Exact wheel filename | Declared expression | Declared paths | Legacy metadata signals | In production graph | Triage |
| ---: | --- | --- | ---: | --- | --- | --- |
| 1 | `charset_normalizer-3.5.3-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl` | Not declared | 1 | No classifier; legacy text present | No | Legacy / exact text review |
| 2 | `charset_normalizer-3.5.3-cp311-cp311-win_amd64.whl` | Not declared | 1 | No classifier; legacy text present | Yes | Legacy / exact text review |
| 3 | `click-8.5.1-py3-none-any.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |
| 4 | `cloudpickle-3.1.3-py3-none-any.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |
| 5 | `colorama-0.4.6-py2.py3-none-any.whl` | Not declared | 1 | BSD License | No | Legacy / exact text review |
| 6 | `et_xmlfile-2.0.0-py3-none-any.whl` | Not declared | 3 | MIT License; legacy text present | Yes | Legacy / exact text review |
| 7 | `fastapi-0.165.0-py3-none-any.whl` | MIT | 1 | No classifier | Yes | Declared / exact text review |
| 8 | `h11-0.16.0-py3-none-any.whl` | Not declared | 1 | MIT License; legacy text present | Yes | Legacy / exact text review |
| 9 | `httpcore-1.0.9-py3-none-any.whl` | BSD-3-Clause | 1 | BSD License | No | Declared / exact text review |
| 10 | `httpcore2-2.16.2-py3-none-any.whl` | BSD-3-Clause | 1 | BSD License | No | Declared / exact text review |
| 11 | `httptools-0.9.0-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl` | MIT | 3 | No classifier | No | Declared / exact text review |
| 12 | `httptools-0.9.0-cp311-cp311-win_amd64.whl` | MIT | 3 | No classifier | Yes | Declared / exact text review |
| 13 | `httpx-0.28.1-py3-none-any.whl` | Not declared | 0 | BSD License; legacy text present | No | Legacy / exact text review; no declared paths |
| 14 | `httpx2-2.16.2-py3-none-any.whl` | BSD-3-Clause | 1 | BSD License | No | Declared / exact text review |
| 15 | `idna-3.20-py3-none-any.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |
| 16 | `iniconfig-2.3.1-py3-none-any.whl` | MIT | 1 | No classifier | No | Declared / exact text review |
| 17 | `joblib-1.6.0-py3-none-any.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |
| 18 | `narwhals-2.29.0-py3-none-any.whl` | MIT | 1 | No classifier | Yes | Declared / exact text review |
| 19 | `numpy-2.4.6-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl` | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 17 | No classifier | No | Composite / exact path review |
| 20 | `numpy-2.4.6-cp311-cp311-win_amd64.whl` | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 17 | No classifier | Yes | Composite / exact path review |
| 21 | `openpyxl-3.1.5-py2.py3-none-any.whl` | Not declared | 1 | MIT License; legacy text present | Yes | Legacy / exact text review |
| 22 | `opentelemetry_api-1.45.2-py3-none-any.whl` | Apache-2.0 | 1 | No classifier | Yes | Declared / exact text review |
| 23 | `packaging-26.4-py3-none-any.whl` | Apache-2.0 OR BSD-2-Clause | 3 | No classifier | Yes | Composite / exact path review |
| 24 | `pandas-2.3.3-cp311-cp311-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl` | Not declared | 0 | BSD License; legacy text present | No | Legacy / exact text review; no declared paths |
| 25 | `pandas-2.3.3-cp311-cp311-win_amd64.whl` | Not declared | 0 | BSD License; legacy text present | Yes | Legacy / exact text review; no declared paths |
| 26 | `pefile-2024.8.26-py3-none-any.whl` | Not declared | 1 | Freezer pin; legacy field not in candidate table | Yes | Legacy / exact text review |
| 27 | `pillow-13.0.0-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl` | MIT-CMU | 1 | No classifier | No | Declared / exact text review |
| 28 | `pillow-13.0.0-cp311-cp311-win_amd64.whl` | MIT-CMU | 1 | No classifier | Yes | Declared / exact text review |
| 29 | `pluggy-1.7.0-py3-none-any.whl` | Not declared | 1 | MIT License; legacy text present | No | Legacy / exact text review |
| 30 | `pydantic-2.14.4-py3-none-any.whl` | MIT | 1 | No classifier | Yes | Declared / exact text review |
| 31 | `pydantic_core-2.50.5-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl` | MIT | 1 | No classifier | No | Declared / exact text review |
| 32 | `pydantic_core-2.50.5-cp311-cp311-win_amd64.whl` | MIT | 1 | No classifier | Yes | Declared / exact text review |
| 33 | `pygments-2.21.0-py3-none-any.whl` | BSD-2-Clause | 2 | No classifier | No | Declared / exact text review |
| 34 | `pyinstaller-6.22.3-py3-none-win_amd64.whl` | Not declared | 1 | Freezer pin; legacy field not in candidate table | Yes | Legacy / exact text review |
| 35 | `pyinstaller_hooks_contrib-2026.9-py3-none-any.whl` | Not declared | 1 | Freezer pin; legacy field not in candidate table | Yes | Legacy / exact text review |
| 36 | `pymupdf-1.28.2-cp310-abi3-manylinux_2_28_x86_64.whl` | Not declared | 0 | No classifier; legacy text present | No | Legacy / exact text review; no declared paths |
| 37 | `pymupdf-1.28.2-cp310-abi3-win_amd64.whl` | Not declared | 0 | No classifier; legacy text present | No | Legacy / exact text review; no declared paths |
| 38 | `pytest-9.2.0-py3-none-any.whl` | MIT | 1 | No classifier | No | Declared / exact text review |
| 39 | `python_dateutil-4.0.0-py3-none-any.whl` | BSD-3-Clause | 2 | No classifier | Yes | Declared / exact text review |
| 40 | `python_dotenv-1.2.4-py3-none-any.whl` | Not declared | 1 | No classifier; legacy text present | Yes | Legacy / exact text review |
| 41 | `python_multipart-0.0.34-py3-none-any.whl` | Apache-2.0 | 1 | Apache Software License | Yes | Declared / exact text review |
| 42 | `pytz-2026.6-py2.py3-none-any.whl` | Not declared | 1 | MIT License; legacy text present | Yes | Legacy / exact text review |
| 43 | `pywin32_ctypes-0.2.3-py3-none-any.whl` | Not declared | 0 | Freezer pin; legacy field not in candidate table | Yes | Legacy / exact text review; no declared paths |
| 44 | `pyyaml-6.0.4-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl` | Not declared | 1 | MIT License; legacy text present | No | Legacy / exact text review |
| 45 | `pyyaml-6.0.4-cp311-cp311-win_amd64.whl` | Not declared | 1 | MIT License; legacy text present | Yes | Legacy / exact text review |
| 46 | `reportlab-4.5.1-py3-none-any.whl` | Not declared | 1 | BSD License; legacy text present | Yes | Legacy / exact text review |
| 47 | `scikit_learn-1.9.1-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl` | BSD-3-Clause | 1 | No classifier | No | Declared / exact text review |
| 48 | `scikit_learn-1.9.1-cp311-cp311-win_amd64.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |
| 49 | `scipy-1.17.1-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl` | Not declared | 0 | BSD License; legacy text present | No | Legacy / exact text review; no declared paths |
| 50 | `scipy-1.17.1-cp311-cp311-win_amd64.whl` | Not declared | 0 | BSD License; legacy text present | Yes | Legacy / exact text review; no declared paths |
| 51 | `setuptools-84.2.1-py3-none-any.whl` | MIT | 1 | Freezer pin; legacy field not in candidate table | Yes | Declared / exact text review |
| 52 | `starlette-1.10.0-py3-none-any.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |
| 53 | `threadpoolctl-3.8.0-py3-none-any.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |
| 54 | `truststore-0.10.5-py3-none-any.whl` | MIT | 1 | No classifier | No | Declared / exact text review |
| 55 | `typing_extensions-4.16.0-py3-none-any.whl` | PSF-2.0 | 1 | No classifier | Yes | Declared / exact text review |
| 56 | `typing_inspection-0.4.5-py3-none-any.whl` | MIT | 1 | No classifier | Yes | Declared / exact text review |
| 57 | `tzdata-2026.6-py2.py3-none-any.whl` | Not declared | 2 | No classifier; legacy text present | Yes | Legacy / exact text review |
| 58 | `uvicorn-0.54.0-py3-none-any.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |
| 59 | `uvloop-0.23.0-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl` | Not declared | 2 | Apache Software License; MIT License; legacy text present | No | Legacy / exact text review |
| 60 | `watchfiles-1.3.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl` | Not declared | 1 | MIT License; legacy text present | No | Legacy / exact text review |
| 61 | `watchfiles-1.3.0-cp310-abi3-win_amd64.whl` | Not declared | 1 | MIT License; legacy text present | Yes | Legacy / exact text review |
| 62 | `websockets-17.4-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl` | BSD-3-Clause | 1 | No classifier | No | Declared / exact text review |
| 63 | `websockets-17.4-cp311-cp311-win_amd64.whl` | BSD-3-Clause | 1 | No classifier | Yes | Declared / exact text review |

This is declaration triage, not a concluded licence review. Legacy text-present and classifier flags identify evidence to inspect, not proof of licence identity or permission. Freezer rows absent from source-test candidate table are not treated as missing metadata sidecars; their exact bytes remain pinned in the freezer receipt. Each wheel may contain more notice-like files than declared, because inspector also captures heuristic matches (LICENSE, COPYRIGHT, AUTHORS, NOTICE, third-party and dist-info/licenses paths). Names and declarations alone cannot grant publication rights for arbitrary content.

## 2. Technical and legal research (public sources, not new downloads)

- [PyPA core metadata](https://packaging.python.org/en/latest/specifications/core-metadata/) distinguishes a distribution-archive-specific licence expression from project-wide claims; [licensing scenarios](https://packaging.python.org/en/latest/guides/licensing-examples-and-user-scenarios/) and [wheel format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/) describe declared notice placement. Exact wheel identity remains necessary; older missing expression is not evidence of proprietary licence or denial of rights.
- [SPDX licence list](https://spdx.org/licenses/) identifies the declared expressions. MIT/BSD/Apache and other identified licence families generally permit redistribution subject to their individual terms. [MIT-CMU](https://spdx.org/licenses/MIT-CMU.html) and [PSF-2.0](https://spdx.org/licenses/PSF-2.0.html) have their own notice/attribution conditions. An SPDX expression or classifier is a starting point, not a review of bundled third-party notices. AND expressions require combined consideration, OR expressions need the chosen permissible option documented.
- [PyMuPDF upstream](https://pymupdf.readthedocs.io/en/latest/about.html) describes AGPL and commercial licensing. Pinned PyMuPDF 1.28.2 rows have no expression or declared paths; both are source-test-only in current plan and absent from the pinned 43-node production graph. Review actual product use, distribution and exact licence before release; do not infer that changing GitHub visibility resolves AGPL obligations, that this source-test candidate establishes distribution, or that commercial rights are available. No dependency replacement authorised.
- [PyInstaller 6.22.3 licence](https://pyinstaller.org/en/stable/license.html) describes GPL-2.0 with bundling exception and Apache-2.0 portions; assess exact exception, separate hooks package and bundled dependencies, not a blanket licence clearance. NumPy composite expression and 17 paths per wheel, SciPy and pandas missing declared paths, Pillow MIT-CMU and bundled libraries, and legacy freezer declarations warrant targeted review. The 43-node production graph remains non-installable.

## 3. Simplified public evidence route

Keep the existing repo. Distinguish (a) actual archive verification, (b) licence/notice evidence, (c) distribution licence disposition and (d) verified retained build bytes. Public reviewed facts such as exact filenames, versions, expected/observed hashes, sizes, safe structural receipts, manifest/bundle digests and reviewed disposition can be retained as canonical bounded Git records, with exact commit and independent readback. Never put raw wheel bytes, secrets, signed storage URLs, private data or arbitrary member contents in public logs/Git. Git durable retention of reviewed small evidence files is preferable to a new storage service, subject to repo size limits and exact publication approval. An existing owner-controlled backup may be used if separately approved; no new service or owner-local access presumed.

**For actual raw notice documents**, existing final driver currently uploads all captured notice bytes, then independently replays and discards temporary copies. Do not arm that path unchanged on the assumption all notice-like members may be published. Review exact source licence texts and relevant vendored notices from public upstream sources against pinned version/paths; preserve author/copyright/terms without editing permitted bytes. Prefer a narrowly scoped pre-publication decision bound to exact document identity and permitted audience, enforced before the artifact upload (not after). Refuse or hold unresolved notice material; do not treat a broad package licence as a per-file allowlist. For permitted raw documents, preserve canonical evidence bytes and independent digest/settlement in bounded per-document Git records, with reviewed size budget, no-clobber publication, exact readback and independent replay before finite artifact expiry. Avoid bulk base64 logs or duplicate ZIPs in Git. Keep prior five unchanged. No actual publication approved here.

If exact notice clearance cannot reasonably be established ahead of acquisition for a given row, assess a **separate public metadata-only receipt projection** that verifies raw notice hashes locally but publishes only inventory and independent identities, with explicit withheld status. This is a possible fallback, not an implemented or approved substitute: replay of hashes alone cannot independently verify withheld raw notice bytes, so no durable notice acceptance for these rows, and any changed evidence method needs a separate explicit decision. No silent weakening of C-D08 or existing exact raw-replay invariant, no automatic private repo, no speculative new storage platform. Distinguish unresolved exceptions individually. A later owner-approved local custody action or other bounded route is only needed if a demonstrated unresolved exception requires it.

## 4. Immediate next work

No further broad repository/architecture research cycle. Focus on exact upstream licence and notice evidence for the ambiguous legacy and multi-licence rows, then determine a minimal enforceable public upload/retention boundary. Review independent activation expectation provisioning: current connector has no identified variable-setting action; approved operator can supply only exact reviewed non-secret expectation/driver/workflow identities when a future proposal is ready. No current variable values read, no configuration mutation, no creation of repositories. If publication cannot be made safe without a material evidence-method change, present one narrow decision with exact limitations instead of inventing new infrastructure. Existing R2 synthetic CI and resource measurements remain valid within scope; actual R3 remains blocked until fresh exact approval. No new tests, licence clearance, score, actual artifact or archive evidence here.

[Current C5 specification](./PILOTODIN_C5_REPRODUCIBLE_BUILD_INPUTS_IMPLEMENTATION_SPEC_2026-11-25.md) · [Decision index](./ENGINEERING_DECISIONS_CURRENT.md) · [Active journal](./ACTIVE_WORK_JOURNAL.md) · [Evidence ledger](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md).


## 5. Version-tagged source licence follow-up (26 November)

Read-only operation C5-R2-EXACT-UPSTREAM-LICENCE-20261126, baseline [227966c](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/227966c9a333e07a8a200b42c14913cb26ac67aa). Exact upstream release-tag Git blobs were retrieved through the GitHub connector, not wheel archives. This narrows ten package/version pairs covering 15 remaining wheel rows, including all eight rows without declared notice paths. It does not establish that any wheel member is byte-identical to a source document. No raw publication clearance.

| Remaining row(s) from section 1 | Exact upstream tag and source document (Git blob) | Source terms and remaining distinction |
| --- | --- | --- |
| 13 HTTPX 0.28.1 | [LICENSE.md](https://github.com/encode/httpx/blob/0.28.1/LICENSE.md) `ab79d16a3f4c6c894c028d1f7431811e8711b42b` | BSD-3-Clause terms; no declared wheel notice path; inspect exact member inventory rather than infer absent notice. |
| 24–25 pandas 2.3.3 | [LICENSE](https://github.com/pandas-dev/pandas/blob/v2.3.3/LICENSE) `cdfa749dc34df3ff6664acd10a9b2e106ef19599`; [pyproject](https://github.com/pandas-dev/pandas/blob/v2.3.3/pyproject.toml) `d5a7f71391fef6e9797fb82700bb4021ab906984` | BSD-3-Clause primary licence; legacy source packaging references LICENSE; both wheel notice inventories still unknown. |
| 36–37 PyMuPDF 1.28.2 | [COPYING](https://github.com/pymupdf/PyMuPDF/blob/1.28.2/COPYING) `dba13ed2ddf783ee8118c6a581dbf75305f816a3` | AGPLv3 text. Verbatim licence text has distinct copying permission; this is not clearance of the library or other notice members. Source-test-only graph disposition remains; commercial licence not established. |
| 43 pywin32-ctypes 0.2.3 | [LICENSE.txt](https://github.com/enthought/pywin32-ctypes/blob/v0.2.3/LICENSE.txt) `d0ce125fb63c6222084fd0f4b1f5e5057cc73905` | BSD-3-Clause terms, exact source tag resolved after wrong filename/ref returned 404. No declared wheel notice path. |
| 49–50 SciPy 1.17.1 | [LICENSE.txt](https://github.com/scipy/scipy/blob/v1.17.1/LICENSE.txt) `1032aece8a8109d67f238de6865d8b08e750a8c0`; [LICENSES_bundled.txt](https://github.com/scipy/scipy/blob/v1.17.1/LICENSES_bundled.txt) `16d3d3a59b236780c6dd85695a30cb5418ee2c00` | BSD-3-Clause primary terms plus distinct bundled source component terms, including BSD, MIT and Boost. Neither list establishes platform binary wheel notice inventory. |
| 19–20 NumPy 2.4.6 | [LICENSE.txt](https://github.com/numpy/numpy/blob/v2.4.6/LICENSE.txt) `f37a12cc4cccf83af4517809791777e71c1df2a9`; [pyproject](https://github.com/numpy/numpy/blob/v2.4.6/pyproject.toml) `98c6830e0e7b13264f1f1288683a2c252b3b8ca1` | BSD-3-Clause primary terms; build configuration confirms composite expression and dynamically included vendored wheel licences. Source list is not a platform-specific 17-member byte allowlist. |
| 23 packaging 26.4 | [LICENSE](https://github.com/pypa/packaging/blob/26.4/LICENSE) `6f62d44e4ef733c0e713afcd2371fed7f2b3de67`; [LICENSE.BSD](https://github.com/pypa/packaging/blob/26.4/LICENSE.BSD) `42ce7b75c92fb01a3f6ed17eea363f756b7da582`; [LICENSE.APACHE](https://github.com/pypa/packaging/blob/26.4/LICENSE.APACHE) `f433b1a53f5b830a205fd2df78e2b34974656c7b` | Alternative BSD-2-Clause or Apache-2.0; candidate three source documents, not verified wheel bytes. Preserve all captured notices for evidence; distribution choice remains separately recorded. |
| 27–28 Pillow 13.0.0 | [LICENSE](https://github.com/python-pillow/Pillow/blob/13.0.0/LICENSE) `c011511a4ab6bd2bc901608e6b4c0fad95fc410f`; [pyproject](https://github.com/python-pillow/Pillow/blob/13.0.0/pyproject.toml) `d978f394324f634099f3eaf68947d250308b45a2` | MIT-CMU with attribution and publicity conditions; source declares LICENSE, not proof of all bundled binary notices. |
| 34 PyInstaller 6.22.3 | [COPYING.txt](https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/COPYING.txt) `d6caec5ab5778c36bd7e26d8d7a48eba1ac23dee` | GPL-2.0-or-later with bootloader combination exception; runtime hooks/modules Apache-2.0; isolated submodule has MIT alternative. Exception is not a blanket exemption for standalone freezer or other dependencies. |
| 35 hooks-contrib 2026.9 | [LICENSE](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/v2026.9/LICENSE) `99bef9e7dc1e29e876057749037f409516eb0509` | Standard hooks GPL-2.0-or-later; bundled runtime hooks Apache-2.0. Distinguish build input and actual frozen runtime inventory. |

Public-source document identifiers above are Git blob SHA-1, not wheel SHA-256, notice SHA-256 or a raw byte match. No upstream licence text copied into this repository. Remaining 48 rows not newly reviewed in this follow-up. Preserve all earlier declaration triage.

**Concrete public disclosure gate (proposed, not implemented):** pre-review a bounded manifest binding exact wheel filename/hash, canonical notice member path, document byte length/SHA-256, immutable upstream blob and terms, intended public audience and explicit disclosure decision. Obtain raw source bytes independently from pinned upstream blobs before generating the manifest; a source ref, licence expression, filename or text-normalized comparison cannot substitute for byte equality. For each accepted wheel compare the complete independently verified v2 notice inventory (including heuristics) to the reviewed manifest; any absent, unexpected, ambiguous or mismatched material must fail the public-upload gate before bundle output is exposed. No raw content in logs, outputs, or public artifacts on refusal. Do not remove unmatched notices from a supposedly complete replay bundle. Keep historical evidence, prior five, independent replay and all caps unchanged. A successful public disclosure check is distinct from product licence disposition and durable receipt retention.

The current disarmed driver `wheel_hosted_final.py` (c0c019c608660a93bcc88985b12f86e103926534) and workflow (fb307867bcc7cd336a4f1ced979cab72ef4f7a74) lack this public content gate; producer upload remains disabled and would otherwise expose the entire raw bundle. All eight no-declared-path rows and platform-specific vendored content still lack verified wheel member identity. Full reviewed manifest cannot presently be certified from source licence texts alone. Next narrow source-only work: establish exact upstream raw-document identity/path candidates and design/test all-or-nothing public upload refusal on synthetic notices, preserving the existing replay format; determine whether a viable full manifest can be established before any R3 proposal. If actual unseen member identities cannot be resolved within this method, ask for a distinct narrow evidence-discovery/method decision rather than uploading first, repeating a consumed run or treating metadata-only as full raw replay. No live acquisition or variable provisioning. Independent operator expectation/readback/removal remains a separate prerequisite, not a reason to change repository visibility.


## 6. Synthetic public notice publication gate (26 November)

Prepared [a5efc7a](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a5efc7a785aafc171ba73b1ccf54745329c7aabb); implemented in [2b8888d](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2b8888d929aa5233315a336caeeea02acb18b1cb). The existing driver now checks a bounded canonical manifest (2 MiB ceiling), independently pinned SHA-256, exact plan, public audience, full ordered wheel identity inventory and decision references. Each approved notice identity includes canonical path, raw byte length, SHA-256 and reviewed upstream Git blob reference. Actual notice inventory from independently validated v2 receipts must exactly equal reviewed identity list, including heuristic captures; missing, changed or unexpected content refuses before export. Producer checks before export and again during export; independent retriever verifies the same policy after complete replay. Existing receipt format and historical source pins unchanged. Source-level upstream reference is not legal clearance or proof that upstream content equals wheel bytes; an authorised independent review must establish that before pinning. Empty notice lists explicitly assert no notice inventory for that wheel, not blanket permission. Current `PUBLIC_REVIEW_SHA256=None` and `ARMED=False`; actual producer/retriever refuse missing pin before transport even if the separate grant were available. Existing lower-level inert fixture helpers retain optional review for historical synthetic compatibility, not activation authority. No reviewed actual manifest or durable public storage implemented. [Exact synthetic run 45788172645](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45788172645), source [2b8888d](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2b8888d929aa5233315a336caeeea02acb18b1cb): Ubuntu job 139800162154 SUCCESS, 217 tests including 10 new disclosure tests, eleven CLI refusals; Windows job 139800161660 SUCCESS, 217 tests; direct CLI refusal step successful. Collector 139800163978 and retriever 139800163688 SKIPPED. Next resolve actual notice inventory feasibility, independent activation provisioning and durable retention without weakening exact replay; if discovery cannot be completed from available public sources, require separate narrow owner approval. No acquisition or settings change.
