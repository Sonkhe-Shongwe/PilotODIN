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
