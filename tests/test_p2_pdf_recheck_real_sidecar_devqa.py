"""New P2-U2d follow-up contracts only. No real exe, pip or network."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import p2_pdf_recheck_real_sidecar_devqa as recheck
from tools import p2_pdf_real_sidecar_font_devqa as old
from tools.p2_pdf_font_asset_gate import hash_file, MAX_ASSET_BYTES


def six_synthetic_assets(directory: Path) -> list[dict]:
    directory.mkdir()
    entries = []
    for role in ("regular", "cjk", "symbol"):
        for kind in ("font", "license"):
            name = role + (".ttf" if kind == "font" else "-OFL.txt")
            blob = ("synthetic-only-" + role + "-" + kind).encode()
            (directory / name).write_bytes(blob)
            entries.append({"role": role, "kind": kind, "name": name,
                            "bytes": len(blob),
                            "sha256": hashlib.sha256(blob).hexdigest()})
    return entries


class PreviouslyFrozenSidecarRecheckContracts(unittest.TestCase):
    def test_scientific_executable_above_font_asset_cap_fingerprints(self):
        with TemporaryDirectory(prefix="p2-recheck-hash-") as td:
            exe = Path(td) / "scientific-engine.exe"
            with exe.open("wb") as sink:
                sink.truncate(MAX_ASSET_BYTES + 1)
            with self.assertRaises(ValueError):
                hash_file(exe)  # Existing font-only helper MUST remain bounded.
            size, digest = old.fingerprint_frozen_executable(exe)
            self.assertEqual(size, MAX_ASSET_BYTES + 1)
            self.assertEqual(len(digest), 64)

    def test_unreasonable_executable_size_is_rejected_without_reading(self):
        with TemporaryDirectory(prefix="p2-recheck-hash-") as td:
            exe = Path(td) / "too-large.exe"
            exe.write_bytes(b"too-long-for-synthetic-limit")
            # Test the cap with a temporary small threshold. Never allocate
            # an actual >1 GiB test file on the owner's Windows laptop.
            with patch.object(old, "MAX_FROZEN_EXE_BYTES", 4):
                with self.assertRaisesRegex(ValueError, "bounded size"):
                    old.fingerprint_frozen_executable(exe)

    def test_reject_non_run_id_without_accessing_files(self):
        for bad in ("../user-home", "run-other", "run-" + "g" * 32,
                    "run-" + "a" * 31, "run-" + "A" * 32):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(ValueError, "InvalidRunIdentifier"):
                    recheck.inspect_stored_run(bad)

    def test_read_only_review_rejects_missing_old_hook_receipt(self):
        with TemporaryDirectory(prefix="p2-recheck-old-") as td:
            root = Path(td)
            rid = "run-" + "a" * 32
            prior = root / rid
            (prior / "inputs").mkdir(parents=True)
            (prior / "dist").mkdir()
            src = root / "reviewed"
            entries = six_synthetic_assets(src)
            for entry in entries:
                (prior / "inputs" / entry["name"]).write_bytes(
                    (src / entry["name"]).read_bytes())
            (prior / "dist" / (old.NAME + ".exe")).write_bytes(b"fake")
            generated = old.HOOK_TEMPLATE.read_text(encoding="utf-8").replace(
                old.HOOK_REPLACE, "PINNED_ASSETS = " + repr(entries))
            (prior / "p2-devqa-runtime-hook.py").write_text(
                generated, encoding="utf-8")
            manifest = root / "synthetic_manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            with patch.object(recheck, "RECHECK_ROOT", root), \
                 patch.object(recheck, "MANIFEST_PATH", manifest), \
                 patch.object(recheck, "verified_review_files",
                              return_value=(src, entries)):
                with self.assertRaisesRegex(ValueError, "PriorDevQAArtifactsIncomplete"):
                    recheck.inspect_stored_run(rid)
                (prior / "font-attestation.json").write_text(
                    json.dumps(old.expected_attestation(entries)), encoding="utf-8")
                exe, found, size, digest = recheck.inspect_stored_run(rid)
            self.assertEqual(size, 4)
            self.assertEqual(len(found), 6)
            self.assertEqual(len(digest), 64)
            self.assertEqual(exe.name, old.NAME + ".exe")

    def test_success_needs_fresh_attestation_and_real_smoke_flags(self):
        with TemporaryDirectory(prefix="p2-recheck-new-") as td:
            root = Path(td)
            exe = root / "already-built.exe"
            exe.write_bytes(b"fake")
            entries = [{"name": "font.ttf", "bytes": 4, "sha256": "a" * 64}]
            sha = hashlib.sha256(b"fake").hexdigest()
            rid = "run-" + "b" * 32

            def successful_smoke(cmd, requested_root, startup):
                self.assertEqual(cmd, [str(exe)])
                self.assertEqual(requested_root, old.ROOT)
                proof_path = Path(recheck.os.environ["PILOTODIN_P2_DEVQA_ATTESTATION"])
                self.assertEqual(proof_path.name, "font-attestation.json")
                self.assertEqual(recheck.os.environ["PILOTODIN_P2_REAL_SIDECAR_DEVQA"], "1")
                proof_path.write_text(json.dumps(old.expected_attestation(entries)))
                return {"passed": True, "auth_required": True,
                        "wrong_origin_rejected": True,
                        "user_storage_isolated": True, "model_started": False}

            with patch.object(recheck, "RECHECK_ROOT", root), \
                 patch.object(recheck, "inspect_stored_run",
                              return_value=(exe, entries, 4, sha)):
                result = recheck.recheck_existing_run(rid, smoke=successful_smoke)
            self.assertEqual(result["state"], "SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS")
            self.assertTrue(result["reused_existing_frozen_build"])
            self.assertEqual(result["exe_sha256"], sha)
            self.assertEqual(result["native_installer"], "NOT_TESTED")
            self.assertEqual(result["product_unicode_pdf"], "NOT_TESTED")

    def test_smoke_without_new_hook_receipt_stays_fail(self):
        with TemporaryDirectory(prefix="p2-recheck-no-proof-") as td:
            root = Path(td)
            exe = root / "already-built.exe"
            exe.write_bytes(b"fake")
            rid = "run-" + "c" * 32
            with patch.object(recheck, "RECHECK_ROOT", root), \
                 patch.object(recheck, "inspect_stored_run",
                              return_value=(exe, [], 4, "a" * 64)):
                result = recheck.recheck_existing_run(
                    rid, smoke=lambda *args: {
                        "passed": True, "auth_required": True,
                        "wrong_origin_rejected": True, "user_storage_isolated": True,
                        "model_started": False})
            self.assertEqual(result["state"], "FAIL")
            self.assertEqual(result["stage"], "fresh_frozen_hook_attestation_missing")

    def test_failed_smoke_restores_parent_process_markers(self):
        with TemporaryDirectory(prefix="p2-recheck-error-") as td:
            root = Path(td)
            exe = root / "built.exe"
            exe.write_bytes(b"fake")
            rid = "run-" + "d" * 32
            before = {key: recheck.os.environ.get(key) for key in
                      ("PILOTODIN_P2_REAL_SIDECAR_DEVQA",
                       "PILOTODIN_P2_DEVQA_ATTESTATION")}
            with patch.object(recheck, "RECHECK_ROOT", root), \
                 patch.object(recheck, "inspect_stored_run",
                              return_value=(exe, [], 4, "a" * 64)):
                result = recheck.recheck_existing_run(
                    rid, smoke=lambda *args: (_ for _ in ()).throw(ValueError("synthetic")))
            self.assertEqual(result["state"], "FAIL")
            self.assertEqual(result["stage"], "reused_real_sidecar_isolated_smoke")
            self.assertEqual({key: recheck.os.environ.get(key) for key in before}, before)


if __name__ == "__main__":
    unittest.main()
