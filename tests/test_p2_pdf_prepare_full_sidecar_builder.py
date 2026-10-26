"""P2-U2c full builder preparation contracts; no real pip/download/venv invoked."""
from __future__ import annotations

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import p2_pdf_prepare_full_sidecar_builder as prep


def versions():
    return {name: "1.2.3" for name in prep.RUNTIME}


class FullSidecarBuilderSafetyContracts(unittest.TestCase):
    def test_private_gitignored_location_does_not_overlap_app_venvs(self):
        self.assertIn("p2-sidecar-env", str(prep.ENV_DIR))
        self.assertNotEqual(prep.ENV_DIR, prep.ROOT / ".venv-live")
        self.assertNotEqual(prep.ENV_DIR, prep.ROOT / ".venv")
        self.assertEqual(prep.OFFICIAL_INDEX, "https://pypi.org/simple")
        self.assertEqual((prep.PINNED_PYINSTALLER, prep.PINNED_HOOKS),
                         ("6.22.3", "2026.9"))

    def test_only_known_backend_requirements_can_be_used(self):
        with TemporaryDirectory(prefix="odin-full-builder-") as temp:
            source = Path(temp) / "requirements.txt"
            source.write_text("\n".join(prep.REQUIRED_LINES) + "\n")
            with patch.object(prep, "REQUIREMENTS", source):
                prep.check_requirements()
                source.write_text(source.read_text() + "--extra-index-url https://bad.invalid\n")
                with self.assertRaisesRegex(ValueError, "BackendRequirementsChanged"):
                    prep.check_requirements()

    def test_direct_pins_and_uvicorn_standard_extra_kept(self):
        pins = prep.pins_for(versions())
        self.assertIn("uvicorn[standard]==1.2.3", pins)
        self.assertIn("scipy==1.2.3", pins)
        self.assertIn("pyinstaller==6.22.3", pins)
        self.assertIn("pyinstaller-hooks-contrib==2026.9", pins)
        self.assertEqual(len(pins), 13)
        with self.assertRaisesRegex(ValueError, "IncompleteRuntimeVersionSet"):
            prep.pins_for({"numpy": "1.2.3"})
        with self.assertRaisesRegex(ValueError, "BadVersionPin"):
            prep.pins_for({**versions(), "numpy": "2;--target C:\\"})

    def test_read_only_inspection_missing_env_makes_no_dir(self):
        with TemporaryDirectory(prefix="odin-full-builder-") as temp:
            root = Path(temp) / "missing"
            with patch.object(prep, "ENV_DIR", root):
                self.assertEqual(prep.inspect_environment()["state"], "ABSENT")
                self.assertFalse(root.exists())

    def test_preexisting_incomplete_env_never_repaired(self):
        with TemporaryDirectory(prefix="odin-full-builder-") as temp:
            root = Path(temp) / "preexisting"
            root.mkdir()
            (root / "keep.txt").write_text("do not delete")
            with patch.object(prep.sys, "platform", "win32"), \
                 patch.object(prep, "ENV_DIR", root), \
                 patch.object(prep, "check_requirements"), \
                 patch.object(prep, "live_versions", return_value=versions()), \
                 patch.object(prep, "_run", side_effect=AssertionError("no installer")):
                result = prep.prepare()
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["stage"], "existing_incomplete_venv")
            self.assertEqual((root / "keep.txt").read_text(), "do not delete")

    def test_opt_in_prepare_targets_only_new_env_and_official_wheels(self):
        with TemporaryDirectory(prefix="odin-full-builder-") as temp:
            root = Path(temp) / "private-builder"
            env = root / "venv"
            commands = []
            def fake(argv, seconds):
                commands.append(argv)
                if "venv" in argv and "-m" in argv:
                    (env / "Scripts").mkdir(parents=True)
                    (env / "Scripts" / "python.exe").write_bytes(b"synthetic-python")
                return subprocess.CompletedProcess(argv, 0, "", "")
            with patch.object(prep.sys, "platform", "win32"), \
                 patch.object(prep, "BUILD_ROOT", root), \
                 patch.object(prep, "ENV_DIR", env), \
                 patch.object(prep, "check_requirements"), \
                 patch.object(prep, "live_versions", return_value=versions()), \
                 patch.object(prep, "_run", side_effect=AssertionError("default run should not occur")), \
                 patch.object(prep.shutil, "disk_usage", return_value=(10**10, 10**10, 10**10)):
                outcome = prep.prepare(runner=fake)
            self.assertEqual(outcome["state"], "DEVQA_FULL_BUILDER_PREPARED")
            self.assertEqual(len(commands), 4)
            self.assertEqual(commands[0][-1], str(env))
            install = commands[1]
            self.assertIn("--only-binary=:all:", install)
            self.assertIn("--isolated", install)
            self.assertIn("--no-input", install)
            self.assertEqual(install[install.index("--index-url")+1], prep.OFFICIAL_INDEX)
            self.assertIn("pyinstaller==6.22.3", install)
            self.assertIn("reportlab==1.2.3", install)
            self.assertFalse(outcome["sidecar_built"])

    def test_package_resolution_failure_blocks_without_attempted_build(self):
        with TemporaryDirectory(prefix="odin-full-builder-") as temp:
            root = Path(temp) / "private-builder"
            env = root / "venv"
            commands = []
            def fake(argv, seconds):
                commands.append(argv)
                if "venv" in argv and "-m" in argv:
                    (env / "Scripts").mkdir(parents=True)
                    (env / "Scripts" / "python.exe").write_bytes(b"synthetic-python")
                    return subprocess.CompletedProcess(argv, 0, "", "")
                return subprocess.CompletedProcess(argv, 17, "", "")
            with patch.object(prep.sys, "platform", "win32"), \
                 patch.object(prep, "BUILD_ROOT", root), \
                 patch.object(prep, "ENV_DIR", env), \
                 patch.object(prep, "check_requirements"), \
                 patch.object(prep, "live_versions", return_value=versions()), \
                 patch.object(prep.shutil, "disk_usage", return_value=(10**10, 10**10, 10**10)):
                outcome = prep.prepare(runner=fake)
            self.assertEqual(outcome["state"], "BLOCKED")
            self.assertEqual(outcome["stage"], "full_runtime_wheel_resolution_or_install")
            self.assertEqual(len(commands), 2)
            self.assertFalse(any("PyInstaller" in str(cmd) for cmd in commands))


if __name__ == "__main__":
    unittest.main()
