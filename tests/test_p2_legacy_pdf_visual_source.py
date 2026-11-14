"""Source-only safeguards for the separate BE-030 synthetic visual QA launcher.

Does not import the backend, touch user projects, run the PDF renderer,
perform network access, or claim real Windows/visual acceptance.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "Run_P2_Legacy_PDF_Visual_Local.py"
LAUNCHER = ROOT / "Run_PilotODIN_P2_Standard_PDF_Visual.bat"


class P2LegacyPDFVisualSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8-sig")
        cls.launcher = LAUNCHER.read_text(encoding="utf-8-sig")
        ast.parse(cls.script, filename=str(SCRIPT))

    def test_qa_only_isolated_and_release_denied(self):
        s = self.script
        for phrase in (
            'need(os.name == "nt"', 'not os.getenv("PILOTODIN_HOME")',
            'not os.getenv("PILOTODIN_DESKTOP_SESSION")',
            "create_run(default_root(), PHASE, repo=ROOT)",
            'PHASE = "P2-LEGACY-PDF-VISUAL"',
            'os.environ["PILOTODIN_HOME"] = str(home)',
            'os.environ.pop("PILOTODIN_HOME", None)',
            'pdf_release_font_loader.RELEASE_APPROVAL_STATUS == "NOT_GRANTED"',
            "pdf_release_font_loader.RELEASE_PINNED_FILES == ()",
            "client = TestClient(app)",
            'zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED)',
        ):
            self.assertIn(phrase, s)
        self.assertNotRegex(s, re.compile(
            r"(?im)^\s*(?:import requests|from requests|import urllib|from urllib)|"
            r"\b(?:subprocess\.Popen|shutil\.rmtree|os\.remove|os\.unlink|pip install|tauri build)\b"
        ))
        self.assertEqual(s.count("os.startfile("), 1)

    def test_three_frozen_exhibits_and_actual_standard_export_are_verified(self):
        s = self.script
        self.assertIn('("overview", {})', s)
        self.assertIn('("compare", {"x": "Region", "y": "Revenue"})', s)
        self.assertIn('"kind": "bar", "aggregation": "sum"', s)
        self.assertIn('"/api/projects"', s)
        self.assertIn('f"/api/projects/{pid}/reports"', s)
        self.assertIn('f"/api/reports/{rid}/export/pdf?revision=1"', s)
        self.assertIn('f"/api/reports/{rid}/export/html?revision=1"', s)
        self.assertIn('len(set(evidence)) == 3', s)
        self.assertIn('frozen["content_sha256"] == report["content_sha256"]', s)
        self.assertIn('"be_030_owner_visual": "PENDING"', s)
        self.assertIn('pdf_path.write_bytes(pdf.content)', s)
        self.assertIn('view.save(str(outputs / f"P2_BE030_SYNTHETIC_PAGE_', s)
        self.assertIn('source.read_bytes() == CSV', s)
        self.assertNotIn('OWNER_REPORTED_PASS', s)

    def test_launcher_is_explicit_no_install_and_uses_existing_python(self):
        s = self.launcher
        self.assertIn(r'.venv-live\Scripts\python.exe', s)
        self.assertIn('Run_P2_Legacy_PDF_Visual_Local.py', s)
        self.assertIn('if defined PILOTODIN_HOME', s)
        self.assertIn('if defined PILOTODIN_DESKTOP_SESSION', s)
        self.assertIn('OWNER VISUAL REVIEW REQUIRED', s)
        self.assertNotRegex(s, r"(?i)\b(?:pip install|npm install|cargo install|tauri build|rmdir /s)\b")


if __name__ == "__main__":
    unittest.main()
