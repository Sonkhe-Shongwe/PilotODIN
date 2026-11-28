"""Synthetic contracts for P2-U2b build-environment metadata audit only."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools import p2_pdf_sidecar_build_readiness as gate


def _details(folder: Path, *, missing=()):
    packages = {key: None if key in missing else "1.2.3" for key in gate.PROBE_NAMES}
    return {
        "prefix": str(folder.resolve()), "version": [3, 12, 6],
        "machine": "AMD64", "bits": 64, "packages": packages,
    }


def _make_python(folder: Path) -> None:
    (folder / "Scripts").mkdir(parents=True)
    (folder / "Scripts" / "python.exe").write_bytes(b"synthetic-inert-file")


class SidecarBuildReadinessContracts(unittest.TestCase):
    def test_absent_venv_returns_absent_without_creating_it(self):
        with TemporaryDirectory(prefix="odin-sidecar-readiness-") as temp:
            candidate = Path(temp) / "uncreated"
            self.assertEqual(gate.inspect_interpreter(candidate), {"state": "ABSENT"})
            self.assertFalse(candidate.exists())

    def test_inspection_is_metadata_only_and_does_not_run_pip(self):
        with TemporaryDirectory(prefix="odin-sidecar-readiness-") as temp:
            folder = Path(temp) / "test-python"
            _make_python(folder)
            arguments = []
            def stub(argv, **kwargs):
                arguments.append(argv)
                return subprocess.CompletedProcess(argv, 0, json.dumps(_details(folder)), "")
            outcome = gate.inspect_interpreter(folder, run=stub)
            self.assertEqual(outcome["state"], "INSPECTED")
            self.assertEqual(outcome["architecture_bits"], 64)
            self.assertFalse(outcome["runtime_missing"])
            self.assertEqual(len(arguments), 1)
            self.assertEqual(arguments[0][1:4], ["-I", "-B", "-c"])
            self.assertNotIn("pip", arguments[0])
            self.assertNotIn("PyInstaller", arguments[0])
            self.assertNotIn("install", arguments[0])

    def test_prefix_mismatch_and_invalid_json_fail_closed(self):
        with TemporaryDirectory(prefix="odin-sidecar-readiness-") as temp:
            folder = Path(temp) / "test-python"
            _make_python(folder)
            for payload, code, expected in (
                (json.dumps({**_details(folder), "prefix": str(Path(temp) / "other")}), 0,
                 "python_prefix_mismatch"),
                ("not-json", 0, "python_probe_invalid_json"),
                ("", 2, "python_metadata_probe_failed"),
            ):
                with self.subTest(expected=expected):
                    result = gate.inspect_interpreter(folder, run=lambda args, **kw:
                        subprocess.CompletedProcess(args, code, payload, ""))
                    self.assertEqual(result["state"], "BLOCKED")
                    self.assertEqual(result["reason"], expected)

    def test_missing_packages_are_reported_not_installed(self):
        with TemporaryDirectory(prefix="odin-sidecar-readiness-") as temp:
            folder = Path(temp) / "test-python"
            _make_python(folder)
            result = gate.inspect_interpreter(folder, run=lambda args, **kw:
                subprocess.CompletedProcess(args, 0, json.dumps(_details(
                    folder, missing=("reportlab", "scipy", "pyinstaller"))), ""))
            self.assertEqual(result["state"], "INSPECTED")
            self.assertIn("reportlab", result["runtime_missing"])
            self.assertIn("scipy", result["runtime_missing"])
            self.assertIn("pyinstaller", result["freezer_missing"])
            self.assertIsNone(result["reportlab_version"])

    def test_complete_audit_still_refuses_build_acceptance(self):
        sample = {"state": "INSPECTED", "runtime_missing": [], "freezer_missing": []}
        decisions = {"live": dict(sample), "existing_build": {"state": "ABSENT"},
                     "private_freezer": dict(sample)}
        result = gate.assess(decisions, 4 * 1024**3)
        self.assertEqual(result["state"], "READINESS_AUDIT_COMPLETE_BUILD_DESIGN_REQUIRED")
        self.assertFalse(result["actual_sidecar_built"])
        self.assertFalse(result["actual_sidecar_fonts_verified"])
        self.assertEqual(result["product_unicode_acceptance"], "NOT_TESTED")
        self.assertEqual(result["peak_memory"], "NOT_MEASURED")

    def test_low_disk_or_unreadable_critical_environment_not_promoted(self):
        base = {"state": "INSPECTED"}
        decisions = {"live": dict(base), "existing_build": {"state": "ABSENT"},
                     "private_freezer": dict(base)}
        result = gate.assess(decisions, 1000)
        self.assertFalse(result["sufficient_disk_for_design"])
        self.assertFalse(result["actual_sidecar_built"])
        decisions["live"] = {"state": "BLOCKED"}
        self.assertEqual(gate.assess(decisions, 3000000000)["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
