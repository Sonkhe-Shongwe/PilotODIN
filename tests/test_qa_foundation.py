"""Synthetic DevQA foundation checks; never touch the real user workspace."""
import hashlib
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from qa_foundation import default_root, create_run, preflight_text, scan_files, verify_existing

class QAFoundationTests(unittest.TestCase):
    def test_default_root(self):
        with TemporaryDirectory() as temp:
            self.assertEqual(default_root({"LOCALAPPDATA": temp}), Path(temp) / "PilotODIN" / "DevQA")
        with self.assertRaises(ValueError): default_root({})

    def test_new_manifest_no_false_acceptance(self):
        with TemporaryDirectory() as temp:
            run, manifest = create_run(Path(temp) / "qa", "P2-TEST", Path(temp) / "repo")
            self.assertEqual(manifest["product_acceptance"], "NOT_TESTED")
            self.assertEqual(manifest["state"], "READY_NOT_TESTED")
            self.assertEqual(len(manifest["risk_register"]), 7)
            for name in ("workspace", "fixtures", "exports", "logs", "diagnostics"):
                self.assertTrue((run / name).is_dir())

    def test_unique_run_keeps_previous(self):
        with TemporaryDirectory() as temp:
            base = Path(temp) / "qa"
            first, _ = create_run(base, "P2", Path(temp) / "repo")
            (first / "exports" / "keep").write_text("original")
            second, _ = create_run(base, "P2", Path(temp) / "repo")
            self.assertNotEqual(first, second)
            self.assertEqual((first / "exports" / "keep").read_text(), "original")

    def test_rejects_relative_or_overlapping_roots(self):
        with TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            for root in (repo, repo / "internal", Path("relative/root"), Path(temp)):
                with self.assertRaises(ValueError): create_run(root, "P2", repo)

    def test_powershell_home_protection(self):
        self.assertEqual(preflight_text(Path("x.ps1"), "$home = 'x'\n")[0]["id"], "PS-RESERVED")
        self.assertEqual(preflight_text(Path("x.ps1"), "$isolatedWorkspaceHome='x'\n"), [])

    def test_path_pdf_cleanup_risks(self):
        sample = '$chosen=Read-Host "folder"\nTest-Path -LiteralPath $chosen\n$referenceHash=Get-FileHash x.pdf\nStart-Process x'
        self.assertEqual({x["id"] for x in preflight_text(Path("x.ps1"), sample)},
                         {"SAVE-PATH", "PDF-RENDER", "CLEANUP"})

    def test_python_syntax_and_scope(self):
        with TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "invalid.py").write_text("def x(:\n")
            findings, blocked = scan_files(repo, ["invalid.py"])
            self.assertEqual((findings[0]["id"], blocked), ("PY-SYNTAX", 1))
            with self.assertRaises(ValueError): scan_files(repo, ["../outside.py"])

    def test_init_json_for_windows_launcher(self):
        import io
        import json
        from contextlib import redirect_stdout
        from qa_foundation import main
        with TemporaryDirectory() as temp:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["init", "--phase", "P2-NATIVE-CHAIN",
                             "--qa-root", str(Path(temp) / "qa"), "--json"])
            payload = json.loads(out.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "READY_NOT_TESTED")
            self.assertEqual(payload["product_acceptance"], "NOT_TESTED")
            self.assertTrue((Path(payload["run_dir"]) / "manifest.json").is_file())
            self.assertTrue(Path(payload["exports_dir"]).is_dir())
            self.assertEqual(Path(payload["exports_dir"]).parent, Path(payload["run_dir"]))

    def test_output_verifier_requires_original_basename(self):
        with TemporaryDirectory() as temp:
            run, _ = create_run(Path(temp) / "qa", "P2", Path(temp) / "repo")
            expected = hashlib.sha256(b"native").hexdigest()
            (run / "exports" / "report(3).pdf").write_bytes(b"native")
            self.assertEqual(verify_existing(run, {"report_rev2.pdf": expected})[0]["status"], "MISSING")
            (run / "exports" / "report_rev2.pdf").write_bytes(b"wrong")
            self.assertEqual(verify_existing(run, {"report_rev2.pdf": expected})[0]["status"], "SHA_MISMATCH")

    def test_strict_saved_file_identity(self):
        with TemporaryDirectory() as temp:
            run, _ = create_run(Path(temp) / "qa", "P2", Path(temp) / "repo")
            content = b"synthetic export"
            (run / "exports" / "report.pdf").write_bytes(content)
            result = verify_existing(run, {"report.pdf": hashlib.sha256(content).hexdigest(),
                                           "report.html": "0" * 64})
            self.assertEqual([x["status"] for x in result], ["PASS", "MISSING"])
            self.assertEqual((run / "exports" / "report.pdf").read_bytes(), content)
            with self.assertRaises(ValueError): verify_existing(run, {"../bad.pdf": "0" * 64})

    def test_refuse_linked_export_directory(self):
        with TemporaryDirectory() as temp:
            run, _ = create_run(Path(temp) / "qa", "P2", Path(temp) / "repo")
            outside = Path(temp) / "outside"
            outside.mkdir()
            (run / "exports").rmdir()
            try:
                (run / "exports").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Creating directory symlinks is not permitted on this OS")
            with self.assertRaisesRegex(ValueError, "linked QA"):
                verify_existing(run, {"report.pdf": "0" * 64})

    def test_discovery_failure_produces_blocked_diagnostic(self):
        import json
        from qa_foundation import check_setup
        with TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            run, outcome = check_setup("FAULT", Path(temp) / "qa", repo=repo, scan=["missing.py"])
            self.assertEqual(outcome["state"], "BLOCKED")
            self.assertEqual(outcome["product_acceptance"], "NOT_TESTED")
            stored = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["state"], "BLOCKED")
            self.assertEqual(stored["product_acceptance"], "NOT_TESTED")
            self.assertTrue((run / "diagnostics" / "result.json").is_file())
            self.assertTrue(Path(outcome["diagnostic_zip"]).is_file())


if __name__ == "__main__":
    unittest.main()
