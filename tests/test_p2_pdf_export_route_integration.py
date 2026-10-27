"""Focused REAL FastAPI export-route checks with a disposable local project home.

Runner sets PILOTODIN_P2_EXPORT_ROUTE_DEVQA=1 and PILOTODIN_HOME before this
test imports backend.main. No real user SQLite/project file, user datasets,
Noto font binaries, network requests or installation. TestClient is in-process.
A normal broad test discovery SKIPS these tests instead of importing the live
backend with its default project-home location.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

SAFE = os.environ.get("PILOTODIN_P2_EXPORT_ROUTE_DEVQA") == "1"
HOME = Path(os.environ.get("PILOTODIN_HOME", "") or ".")
PROJECT_MARKER = HOME / ".pilotodin-p2-export-route-devqa"

# Avoid importing backend.main at module load; it initializes SQLite tables.
@unittest.skipUnless(SAFE and HOME.is_absolute() and
                     PROJECT_MARKER.is_file(),
                     "Requires one-shot isolated P2 release-export runner")
class P2ActualReportExportRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (SAFE and HOME.is_absolute() and PROJECT_MARKER.is_file()):
            raise RuntimeError("Disposable P2 API home was not established")
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend import reports, pdf_release_font_loader
        cls.client = TestClient(app)
        cls.reports = reports
        cls.loader = pdf_release_font_loader

    def setUp(self):
        self.report_id = "a" * 32
        self.path_pdf = f"/api/reports/{self.report_id}/export/pdf"
        self.path_html = f"/api/reports/{self.report_id}/export/html"
        self.saved = {"id": self.report_id, "revision": 7,
                      "title": "Synthetic report only"}

    def test_pdf_route_calls_existing_gated_entry_once(self):
        content = b"%PDF-1.4\nsynthetic-route-only"
        with patch.object(self.reports, "load", return_value=self.saved) as load, \
             patch.object(self.reports, "render_pdf_for_export",
                          return_value=content) as export, \
             patch.object(self.reports, "render_html") as html, \
             patch.dict(os.environ, {"PILOTODIN_DESKTOP_SESSION": ""}):
            response = self.client.get(self.path_pdf + "?revision=7")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)
        self.assertTrue(response.headers["content-type"].startswith("application/pdf"))
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("rev7.pdf", response.headers["content-disposition"])
        load.assert_called_once_with(self.report_id, 7)
        export.assert_called_once_with(self.saved)
        html.assert_not_called()

    def test_html_route_is_not_sent_through_pdf_loader(self):
        content = b"<html><body>synthetic-only</body></html>"
        with patch.object(self.reports, "load", return_value=self.saved), \
             patch.object(self.reports, "render_html", return_value=content) as html, \
             patch.object(self.reports, "render_pdf_for_export") as pdf, \
             patch.dict(os.environ, {"PILOTODIN_DESKTOP_SESSION": ""}):
            response = self.client.get(self.path_html)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)
        self.assertTrue(response.headers["content-type"].startswith("text/html"))
        html.assert_called_once_with(self.saved)
        pdf.assert_not_called()

    def test_source_gate_still_delivers_unchanged_legacy_bytes(self):
        old = b"%PDF-1.4\nunchanged-legacy"
        self.assertEqual(self.loader.RELEASE_APPROVAL_STATUS, "NOT_GRANTED")
        with patch.object(self.reports, "render_pdf", return_value=old) as legacy, \
             patch.object(self.loader, "_verified_context") as resource_probe:
            result = self.reports.render_pdf_for_export(self.saved)
        self.assertEqual(result, old)
        legacy.assert_called_once_with(self.saved)
        resource_probe.assert_not_called()

    def test_real_ascii_pdf_and_html_use_same_immutable_synthetic_revision(self):
        """One actual non-mocked legacy renderer through the real HTTP API."""
        import copy
        import fitz
        snapshot = {
            "id": self.report_id, "revision": 7,
            "title": "Synthetic Regional Revenue",
            "narrative": "Unmodified source-only analytical evidence.",
            "dataset_versions": [1], "content_sha256": "f" * 64,
            "evidence": [{
                "id": "b" * 32, "operation": "compare", "dataset_version": 1,
                "tool_version": "source-contract", "computed_at": "2026-10-27T00:00:00Z",
                "objective": "Compare Revenue between two synthetic regions.",
                "params": {"x": "Region", "y": "Revenue"},
                "result": {
                    "data": [{"label": "Region A", "value": 20.0},
                             {"label": "Region B", "value": 10.0}],
                    "visual": {"type": "bar", "x": "Region", "y": "Revenue",
                               "aggregation": "median",
                               "data": [{"label": "Region A", "value": 20.0},
                                        {"label": "Region B", "value": 10.0}]}
                },
            }],
            "limitations": ["Synthetic fixture, no user information."],
        }
        original = copy.deepcopy(snapshot)
        with patch.object(self.reports, "load", return_value=snapshot), \\
             patch.object(self.loader, "_verified_context") as candidate_font, \\
             patch.dict(os.environ, {"PILOTODIN_DESKTOP_SESSION": ""}):
            pdf = self.client.get(self.path_pdf)
            html = self.client.get(self.path_html)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(html.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        with fitz.open(stream=pdf.content, filetype="pdf") as doc:
            extracted = " ".join(p.get_text() for p in doc)
            self.assertIn(snapshot["title"], extracted)
            self.assertIn(snapshot["content_sha256"], extracted)
            self.assertIn("20.0", extracted)
            self.assertIn("10.0", extracted)
        self.assertIn(snapshot["title"], html.text)
        self.assertIn(snapshot["content_sha256"], html.text)
        self.assertEqual(snapshot, original)
        candidate_font.assert_not_called()

    def test_enabled_without_approved_pins_returns_safe_503_not_pdf(self):
        with patch.object(self.reports, "load", return_value=self.saved), \
             patch.object(self.loader, "RELEASE_APPROVAL_STATUS",
                          "GRANTED_BY_INDEPENDENT_OWNER_REVIEW"), \
             patch.object(self.loader, "RELEASE_PINNED_FILES", ()), \
             patch.object(self.reports, "render_pdf") as legacy, \
             patch.dict(os.environ, {"PILOTODIN_DESKTOP_SESSION": ""}):
            response = self.client.get(self.path_pdf)
        self.assertEqual(response.status_code, 503)
        self.assertIn("Verified Unicode PDF resources unavailable",
                      response.json()["detail"])
        self.assertNotIn("path", response.text.lower())
        self.assertFalse(response.content.startswith(b"%PDF"))
        legacy.assert_not_called()

    def test_desktop_session_requires_token_and_rejects_bad_origin(self):
        marker = "synthetic-not-a-real-session-token"
        headers = {"x-pilotodin-session": marker,
                   "origin": "http://tauri.localhost"}
        with patch.object(self.reports, "load", return_value=self.saved), \
             patch.object(self.reports, "render_pdf_for_export",
                          return_value=b"%PDF-1.4\nsynthetic") as pdf, \
             patch.dict(os.environ, {"PILOTODIN_DESKTOP_SESSION": marker}):
            unauthorized = self.client.get(self.path_pdf)
            untrusted = self.client.get(self.path_pdf,
                 headers={**headers, "origin": "https://untrusted.invalid"})
            authorized = self.client.get(self.path_pdf, headers=headers)
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(untrusted.status_code, 403)
        self.assertEqual(authorized.status_code, 200)
        pdf.assert_called_once_with(self.saved)
        self.assertNotIn(marker, authorized.content.decode("utf-8", errors="ignore"))

    def test_invalid_export_format_is_rejected_before_report_load(self):
        with patch.object(self.reports, "load") as load, \
             patch.dict(os.environ, {"PILOTODIN_DESKTOP_SESSION": ""}):
            response = self.client.get(
                f"/api/reports/{self.report_id}/export/exe")
        self.assertEqual(response.status_code, 404)
        load.assert_not_called()

    def test_invalid_revision_does_not_resolve_saved_report(self):
        with patch.object(self.reports, "load") as load, \
             patch.dict(os.environ, {"PILOTODIN_DESKTOP_SESSION": ""}):
            response = self.client.get(self.path_pdf + "?revision=0")
        self.assertEqual(response.status_code, 422)
        load.assert_not_called()

    def test_no_actual_user_db_or_font_resource_was_created(self):
        self.assertTrue(PROJECT_MARKER.is_file())
        self.assertEqual(self.loader.RELEASE_PINNED_FILES, ())
        self.assertFalse((HOME / "assets" / "pdf_fonts").exists())
        self.assertTrue(str(HOME).startswith(str(Path(tempfile.gettempdir()))))


if __name__ == "__main__":
    unittest.main()
