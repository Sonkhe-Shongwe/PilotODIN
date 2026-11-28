"""P2-U2d isolated REAL sidecar DevQA contracts. Pure synthetic, no build/network."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import p2_pdf_real_sidecar_font_devqa as qa


def six_assets(root: Path) -> list[dict]:
    root.mkdir(parents=True)
    out = []
    for role in ("regular", "cjk", "symbol"):
        for kind in ("font", "license"):
            name = role + (".ttf" if kind == "font" else "-OFL.txt")
            data = ("synthetic-" + role + "-" + kind).encode()
            (root / name).write_bytes(data)
            out.append({
                "role": role, "kind": kind, "name": name,
                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            })
    return out


class RealSidecarFontDevQAContracts(unittest.TestCase):
    def test_runtime_hook_generated_with_exact_six_code_pins(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            folder = Path(td)
            entries = six_assets(folder / "source")
            template = qa.HOOK_TEMPLATE.read_text(encoding="utf-8")
            hook = folder / "single-hook.py"
            qa.write_hook(template, entries, hook)
            data = hook.read_text(encoding="utf-8")
            self.assertNotIn(qa.HOOK_REPLACE, data)
            self.assertIn("verify_p2_devqa_frozen_resources()", data)
            self.assertIn(entries[0]["sha256"], data)
            compile(data, str(hook), "exec")
            with self.assertRaises(FileExistsError):
                qa.write_hook(template, entries, hook)

    def test_hook_refuses_launch_outside_explicit_disposable_smoke(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            folder = Path(td)
            entries = six_assets(folder / "source")
            generated = qa.HOOK_TEMPLATE.read_text(encoding="utf-8").replace(
                qa.HOOK_REPLACE, "PINNED_ASSETS = " + repr(entries))
            # Unit test only: remove unconditional PyInstaller runtime-hook call,
            # then exercise the fail-closed guard against non-smoke processes.
            self.assertTrue(generated.rstrip().endswith(
                "verify_p2_devqa_frozen_resources()"))
            code = generated.rsplit("verify_p2_devqa_frozen_resources()", 1)[0]
            namespace = {"__name__": "__p2_devqa_contract__"}
            exec(compile(code, "<synthetic-hook>", "exec"), namespace)
            guard = namespace["verify_p2_devqa_frozen_resources"]
            with patch.dict(qa.os.environ, {
                    "PILOTODIN_P2_REAL_SIDECAR_DEVQA": "",
                    "PILOTODIN_HOME": str(folder)}):
                with self.assertRaisesRegex(RuntimeError, "consent marker"):
                    guard()
            with patch.dict(qa.os.environ, {
                    "PILOTODIN_P2_REAL_SIDECAR_DEVQA": "1",
                    "PILOTODIN_HOME": str(folder)}):
                with self.assertRaisesRegex(RuntimeError, "disposable smoke"):
                    guard()

    def test_incomplete_hook_or_bad_asset_set_rejected(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            path = Path(td) / "hook.py"
            with self.assertRaisesRegex(ValueError, "marker"):
                qa.write_hook("PINNED_ASSETS=None", [], path)
            with self.assertRaisesRegex(ValueError, "six"):
                qa.write_hook(qa.HOOK_REPLACE, [{"name": "a"}], path)

    def test_actual_entrypoint_and_full_scientific_flags_no_tauri_staging(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            root = Path(td)
            inp = root / "inputs"
            inp.mkdir()
            hook = root / "hook.py"
            hook.write_text("# inert synthetic")
            with patch.object(qa.sys, "platform", "win32"):
                args = qa.pyinstaller_args(root / "venv" / "python.exe", inp, hook, root)
            self.assertEqual(args[-1], str(qa.ENTRY))
            self.assertEqual(args.count("--add-data"), 1)
            self.assertEqual(args.count("--runtime-hook"), 1)
            self.assertIn("--onefile", args)
            self.assertIn("--collect-all", args)
            self.assertIn("scipy", args)
            self.assertIn("sklearn", args)
            self.assertIn("backend.pdf_font_resources", args)
            self.assertNotIn("--clean", args)
            self.assertNotIn("frontend/src-tauri/binaries", " ".join(args))
            self.assertNotIn("pip", " ".join(args).lower())
            self.assertTrue(args[args.index("--add-data")+1].endswith(
                ":" + qa.EXTRACTED_DEST))

    def test_no_builder_never_starts_freeze_or_smoke(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            root = Path(td)
            source = root / "source"
            assets = six_assets(source)
            run = root / "run"
            run.mkdir()
            with patch.object(qa.shutil, "disk_usage", return_value=type(
                    "Disk", (), {"free": 10**10})()), \
                 patch.object(qa, "inspect_environment",
                              return_value={"state": "BLOCKED"}):
                result = qa.run_real_sidecar(
                    run, source, assets,
                    subprocess_run=lambda *a, **kw: self.fail("Must not build"),
                    smoke=lambda *a, **kw: self.fail("Must not launch"))
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["stage"], "full_builder_import_or_dependency_check")

    def test_actual_smoke_pass_required_after_real_build_result(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            root = Path(td)
            source = root / "source"
            assets = six_assets(source)
            run = root / "run"
            run.mkdir()
            def pretend_build(command, **kwargs):
                self.assertIn("--runtime-hook", command)
                self.assertIn("--add-data", command)
                out = run / "dist" / (qa.NAME + ".exe")
                out.write_bytes(b"synthetic-executable-no-execution")
                return subprocess.CompletedProcess(command, 0)
            def smoke(command, root, timeout):
                self.assertEqual(command[0], str(run / "dist" / (qa.NAME + ".exe")))
                self.assertEqual(qa.os.environ.get("PILOTODIN_P2_REAL_SIDECAR_DEVQA"), "1")
                self.assertEqual(qa.os.environ.get("PILOTODIN_P2_DEVQA_ATTESTATION"),
                                 str((run / "font-attestation.json").resolve()))
                (run / "font-attestation.json").write_text(
                    json.dumps(qa.expected_attestation(assets)), encoding="utf-8")
                return {"passed": True, "auth_required": True,
                        "wrong_origin_rejected": True,
                        "user_storage_isolated": True, "model_started": False}
            with patch.object(qa.shutil, "disk_usage", return_value=type(
                    "Disk", (), {"free": 10**10})()), \
                 patch.object(qa, "inspect_environment",
                              return_value={"state": "EXISTING_BUILDER_REVIEW_REQUIRED"}), \
                 patch.object(qa, "python_for", return_value=Path(qa.sys.executable)), \
                 patch.object(qa, "ENV_DIR", root):
                outcome = qa.run_real_sidecar(run, source, assets,
                                              subprocess_run=pretend_build, smoke=smoke)
            self.assertEqual(outcome["state"], "SCOPED_REAL_SIDECAR_FONT_RUNTIME_PASS")
            self.assertTrue(outcome["actual_scientific_engine"])
            self.assertEqual(outcome["product_unicode_pdf"], "NOT_TESTED")
            self.assertEqual(outcome["release_font_approval"], "NOT_GRANTED")
            self.assertEqual(outcome["runtime_hook_release_status"], "DEVQA_ONLY_NOT_FOR_RELEASE")

    def test_good_smoke_without_hook_attestation_is_fail_not_pass(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            root = Path(td)
            source = root / "source"
            assets = six_assets(source)
            run = root / "run"
            run.mkdir()
            def built(cmd, **kwargs):
                (run / "dist" / (qa.NAME + ".exe")).write_bytes(b"fake")
                return subprocess.CompletedProcess(cmd, 0)
            smoke_response = {"passed": True, "auth_required": True,
                              "wrong_origin_rejected": True,
                              "user_storage_isolated": True, "model_started": False}
            with patch.object(qa.shutil, "disk_usage", return_value=type(
                    "Disk", (), {"free": 10**10})()), \
                 patch.object(qa, "inspect_environment",
                              return_value={"state": "EXISTING_BUILDER_REVIEW_REQUIRED"}), \
                 patch.object(qa, "python_for", return_value=Path(qa.sys.executable)), \
                 patch.object(qa, "ENV_DIR", root):
                result = qa.run_real_sidecar(
                    run, source, assets, subprocess_run=built,
                    smoke=lambda *a, **kw: smoke_response)
            self.assertEqual(result["state"], "FAIL")
            self.assertEqual(result["stage"], "frozen_font_hook_attestation_missing")

    def test_nonzero_freeze_never_smokes_or_passes(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            root = Path(td)
            source = root / "source"
            assets = six_assets(source)
            run = root / "run"
            run.mkdir()
            with patch.object(qa.shutil, "disk_usage", return_value=type(
                    "Disk", (), {"free": 10**10})()), \
                 patch.object(qa, "inspect_environment",
                              return_value={"state": "EXISTING_BUILDER_REVIEW_REQUIRED"}), \
                 patch.object(qa, "python_for", return_value=Path(qa.sys.executable)), \
                 patch.object(qa, "ENV_DIR", root):
                result = qa.run_real_sidecar(
                    run, source, assets,
                    subprocess_run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2),
                    smoke=lambda *a, **kw: self.fail("Must not launch"))
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["stage"], "real_sidecar_pyinstaller")

    def test_smoke_failure_fails_and_restores_consent_marker(self):
        with TemporaryDirectory(prefix="p2-real-engine-contract-") as td:
            root = Path(td)
            source = root / "source"
            assets = six_assets(source)
            run = root / "run"
            run.mkdir()
            prior = qa.os.environ.get("PILOTODIN_P2_REAL_SIDECAR_DEVQA")
            def pretend_build(cmd, **kwargs):
                (run / "dist" / (qa.NAME + ".exe")).write_bytes(b"fake")
                return subprocess.CompletedProcess(cmd, 0)
            with patch.object(qa.shutil, "disk_usage", return_value=type(
                    "Disk", (), {"free": 10**10})()), \
                 patch.object(qa, "inspect_environment",
                              return_value={"state": "EXISTING_BUILDER_REVIEW_REQUIRED"}), \
                 patch.object(qa, "python_for", return_value=Path(qa.sys.executable)), \
                 patch.object(qa, "ENV_DIR", root):
                outcome = qa.run_real_sidecar(
                    run, source, assets, subprocess_run=pretend_build,
                    smoke=lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("synthetic")))
            self.assertEqual(outcome["state"], "FAIL")
            self.assertEqual(outcome["stage"], "real_sidecar_isolated_smoke")
            self.assertEqual(qa.os.environ.get("PILOTODIN_P2_REAL_SIDECAR_DEVQA"), prior)


if __name__ == "__main__":
    unittest.main()
