# PilotODIN | B5 V2 one-use Windows synthetic library test proposal

**HISTORICAL: DISARMED, one-use run SUCCESS. Approval consumed; no reruns.** See [terminal receipt](./PILOTODIN_PACKAGE_B5_EVIDENCE_2026-11-24.md) and [closure audit](./DOCUMENTATION_AUDIT_PACKAGE_B_SOURCE_CLOSURE_2026-11-24.md). Exact product `8e3cc9112073b9744ff18ffa3e4e549662504a97`. Four source CI workflows PASS; native code uncompiled. Previous V1 run #45439476190 failed before job creation, approval consumed; its workflow remains disabled and must not be reused. [Evidence ledger](./PILOTODIN_PACKAGE_B5_EVIDENCE_2026-11-24.md).

## Preflight before approval

[New V2 workflow](../.github/workflows/p4-package-b5-native-synthetic-v2-once.yml) contains an ordinary Ubuntu source-only preflight and a disabled Windows job. Preflight [validator](../qa/b5_native_workflow_preflight.rb) parses the full disabled and prospective armed YAML, rejects duplicate keys, checks the trigger, permissions, only two jobs, pinned checkout, exact test names, source object identities and fixture identity. PowerShell AST parser checks all five native script bodies without executing them; Python AST parser checks embedded fixture validator. It emits SHA256 of both entire YAML variants. No cargo execution, native compilation, fixture download or product launch in preflight. Require exact source preflight success and Windows job SKIPPED before requesting approval.

The only permitted prospective activation edit is replacing the one disabled guard line with the exact folded YAML scalar below; use the unique colon-free commit message `B5-NATIVE-SYNTHETIC-V2-20261124-ONE-USE`. Compare entire actual proposed armed YAML SHA256 to the preflight log before publishing, then check expected HEAD and persist approval intent in the active journal. Armed run repeats source preflight; Windows job depends on success. Disarm immediately after dispatch; approval consumed even if zero jobs, no reruns. No change to any other workflow.

```yaml
    if: ${{ false }} # DISARMED V2; fresh exact approval required.
```

```yaml
    if: >-
      ${{ github.run_attempt == 1 && github.event_name == 'push' && github.ref == 'refs/heads/feature/live-dev-workspace-20261023' && github.event.head_commit.message == 'B5-NATIVE-SYNTHETIC-V2-20261124-ONE-USE' }}
```

## Exact proposed scope

One disposable Windows-2022 job, attempt 1; existing locked Cargo dependencies and preinstalled toolchain; exact source checkout, invalid compile-only placeholders and release refusal. Only approved synthetic artifact 14937864793 from lifecycle #45433050726; archive 4860 bytes, SHA256 9ff7eff70d5f27fdc5aba03119f53fe0d719329fdfbb4f85a30cf1e47eee8ae1; manifest producer `7789f84`, actual file hash and size verified. Backend tree and fixture generator are unchanged. No alternative fixture if missing or expired.

One `cargo +stable test --locked --manifest-path frontend/src-tauri/Cargo.toml --target x86_64-pc-windows-msvc --lib -- --exact --include-ignored --test-threads=1` invocation with these seven exact test filters:

- `dataset_attestation::tests::canonical_metadata_rejects_mismatched_filename_and_bounds`
- `dataset_attestation::tests::rejects_duplicate_and_noncanonical_headers`
- `dataset_attestation::tests::python_hmac_vector_and_tampering`
- `dataset_file::tests::rejects_wrong_version_format_size_digest_and_controls`
- `dataset_file::tests::backend_generated_xlsx_fixture_matches_native_contract`
- `dataset_file::tests::publication_failures_do_not_clobber_or_certify_uncertain_destination`
- `dataset_file::tests::new_file_publication_refuses_existing_and_protected_paths`

Includes the superscript-device pure predicate cases added to existing test. Expected seven named successes, zero failure/ignored, exact lock/source unchanged, generated temp empty and owned placeholder cleanup. Library harness linking and execution only, no actual application launch, installer, owner data, real model/runtime downloads, executable upload, capture, policy changes or reruns. Actual dialog/IPC, physical persistence, disk-full and emergency exit remain separate. No P4 acceptance or B5 closure credit from preparation. C stays pending and installer frozen.

## Exact preflight result and approval boundary

[V2 source preflight #45441506809](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45441506809) SUCCESS, exact QA `3609bf27f69c1469262b134af0ad249a9d1e16b3`, job 138613585121 PASS and Windows job 138613848912 SKIPPED. Disabled YAML SHA256 `9c6d24ddb6b79ace16a33260049fd2b05dee6d39828bea7271911f1269d9fd72`; complete prospective armed YAML SHA256 `b9ac0b53b049fc9c9d6a28cbb24c783e08a8e10933dc1a33d8b52da553f2afb5`. Actual log confirms both YAML variants, all five PowerShell ASTs, Python AST, seven exact test names and source/artifact identities. No Windows compilation or execution. Before activation, independently compare exact bytes/hash against the recorded digest. A source parser pass does not guarantee Windows test success. Await fresh exact owner approval; old approvals remain consumed.

## Dispatch receipt

Owner approval recorded at `b7f2dc8`; both complete YAML fingerprints independently matched; exact dispatch `e5f553f411c95ab4c4fc70b0ab44fde6289905fd`, [run #45442066752](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45442066752) in_progress. Restoring exact disabled YAML with this checkpoint. No further activation allowed under this approval. See live handoff and evidence ledger for actual outcome.
