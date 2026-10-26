"""Pure synthetic P2 frozen font probe regression; no PyInstaller/build invocation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import p2_pdf_frozen_font_onefile_devqa as probe
from tools.p2_pdf_frozen_font_worker import inspect_frozen_resources


def assets_for(path):
    path.mkdir()
    records = []
    for role in ("regular", "cjk", "symbol"):
        for kind in ("font", "license"):
            name = role + (".ttf" if kind == "font" else "-OFL.txt")
            value = ("fake-" + role + kind).encode()
            (path / name).write_bytes(value)
            records.append({"role": role, "kind": kind, "name": name,
                            "bytes": len(value),
                            "sha256": hashlib.sha256(value).hexdigest()})
    return records


class FrozenFontProbeContracts(unittest.TestCase):
    def test_unfrozen_worker_refuses_false_pass(self):
        with patch("tools.p2_pdf_frozen_font_worker.sys.frozen", False, create=True):
            with self.assertRaisesRegex(ValueError, "bootloader"):
                inspect_frozen_resources({"schema": 1, "assets": []})

    def test_six_separate_add_data_flags_and_no_product_engine(self):
        with TemporaryDirectory(prefix="odin-p2-probe-") as folder:
            root = Path(folder)
            records = assets_for(root / "source")
            with patch("tools.p2_pdf_frozen_font_onefile_devqa.sys.platform", "win32"):
                args = probe.build_arguments(root / "source", records, root / "output")
            self.assertEqual(args.count("--add-data"), 6)
            self.assertIn("--onefile", args)
            self.assertNotIn("--clean", args)
            self.assertNotIn("desktop_runner.py", " ".join(args))
            self.assertTrue(all(":" + probe.EXTRACTED_DEST in args[i + 1]
                                for i, v in enumerate(args) if v == "--add-data"))

    def test_unsafe_or_duplicate_font_paths_are_rejected(self):
        with TemporaryDirectory(prefix="odin-p2-probe-") as folder:
            root = Path(folder)
            records = assets_for(root / "source")
            for bad in ("../a", r"..\a", ".", ""):
                tampered = [dict(x) for x in records]
                tampered[0]["name"] = bad
                with patch("tools.p2_pdf_frozen_font_onefile_devqa.sys.platform", "win32"):
                    with self.assertRaises(ValueError):
                        probe.build_arguments(root, tampered, root)
            tampered = [dict(x) for x in records]
            tampered[1]["name"] = tampered[0]["name"]
            with patch("tools.p2_pdf_frozen_font_onefile_devqa.sys.platform", "win32"):
                with self.assertRaises(ValueError):
                    probe.build_arguments(root, tampered, root)

    def test_pyinstaller_missing_or_old_fails_without_install(self):
        from importlib import metadata
        with patch.object(probe.metadata, "version",
                          side_effect=metadata.PackageNotFoundError("pyinstaller")):
            with self.assertRaisesRegex(RuntimeError, "PyInstallerMissing"):
                probe.detect_existing_pyinstaller()
        with patch.object(probe.metadata, "version", return_value="5.12.0"):
            with self.assertRaisesRegex(RuntimeError, "PyInstaller6Required"):
                probe.detect_existing_pyinstaller()

    def test_correct_strict_frozen_worker_produces_scoped_only_pass(self):
        with TemporaryDirectory(prefix="odin-p2-probe-") as folder:
            root = Path(folder)
            records = assets_for(root / "source")
            output = root / "run"
            output.mkdir()
            calls = []
            def fake_run(args, **kwargs):
                calls.append(args)
                if len(calls) == 1:
                    (output / "dist" / "pilotodin-p2-frozen-font-probe.exe").write_bytes(
                        b"not-a-real-exe")
                    return subprocess.CompletedProcess(args, 0, "", "")
                answer = {"schema": 1, "state": "FROZEN_RESOURCE_VERIFIED",
                          "frozen": True, "inside_pyinstaller_bundle": True,
                          "embedded_file_count": 6,
                          "resource_location": probe.EXTRACTED_DEST,
                          "product_sidecar_tested": False}
                return subprocess.CompletedProcess(args, 0, json.dumps(answer), "")
            with patch.object(probe, "detect_existing_pyinstaller", return_value="6.12"), \
                 patch.object(probe, "build_arguments", return_value=["fake-build"]):
                result = probe.run_onefile_proof(
                    output, records, root / "source", subprocess_run=fake_run)
            self.assertEqual(len(calls), 2)
            self.assertEqual(result["state"], "SCOPED_FROZEN_RESOURCE_PROBE_PASS")
            self.assertEqual(result["actual_pilotodin_sidecar"], "NOT_TESTED")
            self.assertEqual(result["release_font_approval"], "NOT_GRANTED")

    def test_nonzero_worker_never_passes_even_with_valid_json(self):
        with TemporaryDirectory(prefix="odin-p2-probe-") as folder:
            root = Path(folder)
            records = assets_for(root / "source")
            output = root / "run"
            output.mkdir()
            counter = [0]
            def fake_run(args, **kwargs):
                counter[0] += 1
                if counter[0] == 1:
                    (output / "dist" / "pilotodin-p2-frozen-font-probe.exe").write_bytes(b"x")
                    return subprocess.CompletedProcess(args, 0, "", "")
                return subprocess.CompletedProcess(args, 2, json.dumps({
                    "schema": 1, "state": "FROZEN_RESOURCE_VERIFIED",
                    "frozen": True, "inside_pyinstaller_bundle": True,
                    "embedded_file_count": 6,
                    "resource_location": probe.EXTRACTED_DEST,
                    "product_sidecar_tested": False}), "")
            with patch.object(probe, "detect_existing_pyinstaller", return_value="6.12"), \
                 patch.object(probe, "build_arguments", return_value=["fake-build"]):
                result = probe.run_onefile_proof(
                    output, records, root / "source", subprocess_run=fake_run)
            self.assertEqual(result["state"], "FAIL")

    def test_source_mutation_aborts_before_build(self):
        with TemporaryDirectory(prefix="odin-p2-probe-") as folder:
            root = Path(folder)
            records = assets_for(root / "source")
            (root / "source" / "regular.ttf").write_bytes(b"changed")
            output = root / "run"
            output.mkdir()
            with patch.object(probe, "detect_existing_pyinstaller", return_value="6.12"):
                with self.assertRaisesRegex(ValueError, "changed before build"):
                    probe.run_onefile_proof(
                        output, records, root / "source",
                        subprocess_run=lambda *a, **kw: self.fail("must not start build"))

    def test_successful_build_without_exe_cannot_pass(self):
        with TemporaryDirectory(prefix="odin-p2-probe-") as folder:
            root = Path(folder)
            records = assets_for(root / "source")
            output = root / "run"
            output.mkdir()
            with patch.object(probe, "detect_existing_pyinstaller", return_value="6.12"), \
                 patch.object(probe, "build_arguments", return_value=["fake-build"]):
                result = probe.run_onefile_proof(
                    output, records, root / "source",
                    subprocess_run=lambda a, **kw: subprocess.CompletedProcess(a, 0, "", ""))
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["stage"], "executable_missing")


if __name__ == "__main__":
    unittest.main()
