"""P2-U2a opt-in tooling contracts. No pip, downloads or venv creation here."""
from __future__ import annotations

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import p2_pdf_pyinstaller_tooling_devqa as prep


class IsolatedFreezerToolingContracts(unittest.TestCase):
    def test_pinned_known_packages_and_official_index_only(self):
        self.assertEqual(prep.INSTALLER_VERSION, "6.22.3")
        self.assertEqual(prep.HOOKS_VERSION, "2026.9")
        self.assertEqual(prep.OFFICIAL_INDEX, "https://pypi.org/simple")
        self.assertIn("p2-pdf-frozen-resource-probe", str(prep.TOOLING))
        self.assertNotIn(".venv-live", str(prep.TOOLING))

    def test_inspection_missing_venv_is_blocked_without_files(self):
        with TemporaryDirectory(prefix="odin-freezer-tooling-test-") as folder:
            path = Path(folder) / "never-created-tooling"
            answer = prep.inspect_tooling(path)
            self.assertEqual(answer["state"], "BLOCKED")
            self.assertFalse(path.exists())

    def test_dedicated_environment_only_and_pinned_install_flags(self):
        with TemporaryDirectory(prefix="odin-freezer-tooling-test-") as folder:
            root = Path(folder) / "isolated-tooling"
            calls = []
            def fake_run(command, *, seconds):
                calls.append(list(command))
                if "-m" in command and "venv" in command:
                    destination = Path(command[-1])
                    (destination / "Scripts").mkdir(parents=True)
                    (destination / "Scripts" / "python.exe").write_bytes(b"fake-python")
                return subprocess.CompletedProcess(command, 0, "", "")
            with patch.object(prep.sys, "platform", "win32"), \
                 patch.object(prep, "_run", side_effect=fake_run), \
                 patch.object(prep, "inspect_tooling",
                              return_value={"state": "ISOLATED_PYINSTALLER_READY"}):
                answer = prep.prepare_tooling(root)
            self.assertEqual(answer["state"], "ISOLATED_PYINSTALLER_READY")
            self.assertEqual(len(calls), 2)
            self.assertIn("venv", calls[0])
            self.assertEqual(calls[0][-1], str(root))
            self.assertIn("--isolated", calls[1])
            self.assertIn("--no-input", calls[1])
            self.assertIn("--only-binary=:all:", calls[1])
            self.assertEqual(calls[1][calls[1].index("--index-url") + 1],
                             "https://pypi.org/simple")
            self.assertIn("pyinstaller==6.22.3", calls[1])
            self.assertIn("pyinstaller-hooks-contrib==2026.9", calls[1])

    def test_existing_tooling_is_not_overwritten_or_repaired(self):
        with TemporaryDirectory(prefix="odin-freezer-tooling-test-") as folder:
            root = Path(folder) / "already-there"
            root.mkdir()
            (root / "KEEP").write_text("preserve")
            with patch.object(prep.sys, "platform", "win32"), \
                 patch.object(prep, "inspect_tooling",
                              return_value={"state": "BLOCKED", "stage": "preexisting"}), \
                 patch.object(prep, "_run",
                              side_effect=AssertionError("must not run creation")):
                answer = prep.prepare_tooling(root)
            self.assertEqual(answer["state"], "BLOCKED")
            self.assertEqual((root / "KEEP").read_text(), "preserve")

    def test_install_failure_remains_blocked_and_isolated(self):
        with TemporaryDirectory(prefix="odin-freezer-tooling-test-") as folder:
            root = Path(folder) / "isolated-tooling"
            def fake_run(command, *, seconds):
                if "venv" in command:
                    (root / "Scripts").mkdir(parents=True)
                    (root / "Scripts" / "python.exe").write_bytes(b"synthetic")
                    return subprocess.CompletedProcess(command, 0, "", "")
                return subprocess.CompletedProcess(command, 17, "", "")
            with patch.object(prep.sys, "platform", "win32"), \
                 patch.object(prep, "_run", side_effect=fake_run):
                answer = prep.prepare_tooling(root)
            self.assertEqual(answer["state"], "BLOCKED")
            self.assertEqual(answer["stage"], "pypi_tooling_install")
            self.assertEqual(answer["exit_code"], 17)


if __name__ == "__main__":
    unittest.main()
