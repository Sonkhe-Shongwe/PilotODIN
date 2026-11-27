# PilotODIN | C-D10 standard read-only APT diagnosis

27 November 2026. Operation C5-CD10-READONLY-APT-DIAGNOSIS-20261127, original parent 2c42aa47fada01dfe326c42207e9bc6b7a950907, write-ahead 667c839c1f7e918954a40b2ef310b4aaa7543dab, executed source 9d67cab0eb5fbb7e914ffa0150cce1f54f7b8d90. Routine scoped development CI only; no new restricted grant, no acquisition or installation. Reused existing disarmed workflow by adding a separately scoped diagnostic job, blob f4119231795fabd3a6dfd271c8df09f050099108, with old metadata job unchanged/false, no checkout or secrets, permissions empty. All 119 other workflow blobs unchanged. Exact source and actual scope reconciled.

## Actual result

[Run 45974012246](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45974012246), attempt 1, overall SUCCESS for diagnostic collection; [job 140421130470](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45974012246/job/140421130470) SUCCESS, original metadata job 140421191185 SKIPPED. Actual image 20261116.133.1 differs from earlier 20261122.23.1; both observed eight installed binutils family packages .10. No holds printed. Standard normal APT cache for all eight shows Installed and Candidate 2.42-4ubuntu2.10, older cached noble-security 2.42-4ubuntu2.8 and noble base 2.42-4ubuntu2. The new .11 version is absent from existing cache. Actual apt-get -s --no-download --no-install-recommends exact eight .11 pins returned 100 with the following retained stderr:

```text
E: Version '2.42-4ubuntu2.11' for 'binutils' was not found
E: Version '2.42-4ubuntu2.11' for 'binutils-common' was not found
E: Version '2.42-4ubuntu2.11' for 'binutils-x86-64-linux-gnu' was not found
E: Version '2.42-4ubuntu2.11' for 'libbinutils' was not found
E: Version '2.42-4ubuntu2.11' for 'libctf0' was not found
E: Version '2.42-4ubuntu2.11' for 'libctf-nobfd0' was not found
E: Version '2.42-4ubuntu2.11' for 'libgprofng0' was not found
E: Version '2.42-4ubuntu2.11' for 'libsframe1' was not found
```

Read-only installed reverse-dependency records include GCC/Clang/dpkg-dev and libc6-dev; observed external requirements are unpinned or minimum-version/old-version-break constraints, not an observed .10-only external hold. Exact-version internal binutils family dependencies accounted for by eight selected packages. No claim all possible solver constraints satisfied. dpkg status endpoint SHA256 a4fa7dda37aa3d17876c45540df65642cc93989a609e188d4c7c70187152a876 unchanged; logged C5_APT_INSTALLATIONS=0, C5_APT_EXPLICIT_NETWORK_REQUESTS=0; this is endpoint and scripted scope evidence, not physical no-egress proof. Diagnostic workflow SUCCESS means error was collected, not that update simulation passed.

## Concrete blocker and next action

Normal existing cache is stale, not an established version incompatibility. Previous authenticated current signed metadata receipt cee63c29e993eda889d45dd6e1fc254808d94d55 establishes eight .11 expected hashes/4358516 package bytes; previous APT cache pin bindings succeeded but simulation stderr was not retained. This newer diagnostic used a different image and lacked .11 in its normal cache, so it cannot establish the cause of that earlier isolated simulation or prove a successful transaction. No repeated normal-cache run without materially new evidence. Next prepare one bounded standard authenticated Ubuntu security-index refresh merged with normal dependency context, preserving existing trusted repository/keys, no broad apt upgrade, no unrelated repositories or package download during simulation; capture precise solver output and only accept the exact eight upgrades, zero unexpected actions. Fresh explicit authority for network and any eventual install; if a reviewed patched provider image appears first, prefer it. No identity-only metadata repeat; retain pins, use refreshed index specifically to resolve the actual normal-context solver. Exact operation still needs review and approval. Existing inspection driver disarmed, process settlement and use-rights gaps remain. No new verifier or generic planning loop. Restore exact disarmed metadata workflow blob d7d62422b3fef1eb0a986c86ae605c466a2db39e; no new consumed grant. C5 4/8, source 14/17, P4 14/20, G2/D/E2 unchanged, all four profiles blocked, P5 not authorised, installer frozen. 43 closed/disarmed grants, zero active, 23 detached records preserved.
