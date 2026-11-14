"""Source contract smoke for P2 DevQA Windows runner; no Windows execution."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def source(name):
    return (ROOT / name).read_text(encoding="utf-8-sig")

class P2DevQAContract(unittest.TestCase):
    def test_isolated_only(self):
        s=source("tools/Verify_P2_DevQA_Native_Chain_Local.ps1")
        self.assertIn("$QaRunDir",s)
        self.assertIn("Refusing a run outside the managed DevQA runs folder",s)
        self.assertIn("product_acceptance -ne 'NOT_TESTED'",s)
        self.assertIn("$env:PILOTODIN_HOME=$isolatedWorkspaceHome",s)
        self.assertIn("CARGO_NET_OFFLINE='true'",s)

    def test_strict_default_export_location(self):
        s=source("tools/Verify_P2_DevQA_Native_Chain_Local.ps1")
        self.assertIn("$saveTarget=Join-Path $session 'exports'",s)
        self.assertIn("$chosen=$saveTarget",s)
        self.assertNotIn("Paste the ACTUAL folder where",s)
        self.assertIn("Test-Path -LiteralPath $htmlFile -PathType Leaf",s)
        self.assertIn("Test-Path -LiteralPath $pdfFile -PathType Leaf",s)
        self.assertIn("IsPathRooted($inputFolder)",s)
        self.assertIn("$driveAbsolute",s)
        self.assertIn("$uncAbsolute",s)
        self.assertIn("fully qualified Windows path",s)
        self.assertIn("MISSING exact required file",s)

    def test_strict_hash_and_original_source(self):
        s=source("tools/Verify_P2_DevQA_Native_Chain_Local.ps1")
        self.assertIn("if($referenceHash -ne $expected)",s)
        self.assertIn("Get-FileHash -LiteralPath $path -Algorithm SHA256",s)
        self.assertIn("Mark 'p2-real-report-native-saved-byte-integrity'",s)
        self.assertIn("Mark 'p2-synthetic-source-unchanged'",s)
        self.assertIn("$files=@($reportFile,$manifestPath,$qaManifestPath",s)

    def test_no_prod_command_change(self):
        s=source("frontend/src/p2NativeLiveReport.tsx")
        self.assertIn("createRoot(mount!).render(<ReportWorkspace",s)
        self.assertIn("return original(url.toString(),init)",s)
        html=source("frontend/p2_native_live_report_test.html")
        self.assertIn('id="qa-save-folder"',html)

    def test_export_filename_cors_end_to_end_contract(self):
        backend=source("backend/main.py")
        front=source("frontend/src/api.ts")
        seeded=source("tools/Seed_P2_Native_Live_Chain_Local.py")
        rust=source("frontend/src-tauri/src/lib.rs")
        # The transport exposes the filename, and the caller refuses guesses.
        self.assertIn('expose_headers=["Content-Disposition"]', backend)
        self.assertIn("access-control-expose-headers", seeded)
        self.assertIn("headers={\"Origin\":browser_origin}", seeded)
        self.assertIn("Report filename header is unavailable", front)
        self.assertIn("filename!==expectedFilename", front)
        self.assertNotIn("??`pilotodin_report.${format}`", front)
        self.assertIn(".set_file_name(filename)", rust)

    def test_bootstrap_no_early_product_pass(self):
        s=source("tools/Start_P2_DevQA_Native_Chain_Local.ps1")
        self.assertIn("init --phase P2-NATIVE-CHAIN --json",s)
        self.assertIn("test_qa_foundation.py",s)
        self.assertIn("test_p2_devqa_contract.py",s)
        self.assertIn("Language.Parser]::ParseFile",s)
        self.assertIn("DevQA workspace allocator",s)
        self.assertIn("product_acceptance='NOT_TESTED'",s)
        self.assertIn("Failure-Diagnostic",s)

if __name__ == "__main__":
    unittest.main()
