"""P2 release-gated user PDF export contracts.

Only synthetic tiny files, no Noto/font binary, HTTP, real project DB,
PyInstaller, installer, license approval or user data. Prior accepted U2d/U2f,
U2g and actual PDF visual suites are NOT repeated here.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from backend import pdf_release_font_loader as loader
from backend.pdf_font_resources import (
    PDFResourceError, verify_pdf_font_files,
)

ROLES = ("regular", "cjk", "symbol")


def fake_pins() -> tuple:
    return tuple((role, kind, role + (".ttf" if kind == "font" else "-OFL.txt"),
                  8, "a" * 64)
                 for role in ROLES for kind in ("font", "license"))


class OfflineApprovedReleaseContracts(unittest.TestCase):
    def setUp(self):
        self.assertEqual(loader.RELEASE_APPROVAL_STATUS, "NOT_GRANTED")
        self.assertEqual(loader.RELEASE_PINNED_FILES, ())
        self.assertEqual(loader.RELEASE_APPROVAL_REFERENCE, "")

    def approved(self):
        """Source-only mock approval, never saved to application config."""
        return (
            patch.object(loader, "RELEASE_APPROVAL_STATUS",
                         "GRANTED_BY_INDEPENDENT_OWNER_REVIEW"),
            patch.object(loader, "RELEASE_APPROVAL_REFERENCE",
                         "QA/source-reviewed-2026"),
            patch.object(loader, "RELEASE_PINNED_FILES", fake_pins()),
        )

    def test_default_pdf_calls_legacy_renderer_without_loading_fonts(self):
        revision = {"frozen": True}
        renderer = Mock(return_value=b"unchanged baseline bytes")
        with patch.object(loader, "_verified_context") as verify:
            output = loader.render_export_pdf(revision, renderer)
        self.assertEqual(output, b"unchanged baseline bytes")
        renderer.assert_called_once_with(revision)
        verify.assert_not_called()

    def test_environment_cannot_enable_source_only_approval(self):
        with patch.dict(os.environ, {"PILOTODIN_PDF_FONT_APPROVED": "true",
                                    "PILOTODIN_P2_REAL_SIDECAR_DEVQA": "1"}):
            self.assertFalse(loader.release_pdf_enabled())
            with patch.object(loader, "_verified_context") as verify:
                loader.render_export_pdf({}, lambda report: b"legacy")
            verify.assert_not_called()

    def test_partial_approval_does_not_silently_fallback(self):
        with patch.object(loader, "RELEASE_APPROVAL_STATUS",
                          "GRANTED_BY_INDEPENDENT_OWNER_REVIEW"):
            self.assertTrue(loader.release_pdf_enabled())
            with self.assertRaises(loader.PDFReleaseFontError):
                loader.render_export_pdf({}, lambda report: b"legacy")

    def test_unapproved_status_never_creates_release_context(self):
        with self.assertRaisesRegex(loader.PDFReleaseFontError, "approval absent"):
            loader._approved_records()

    def test_six_identity_validation_and_duplicate_detection(self):
        a, b, c = self.approved()
        with a, b, c:
            self.assertEqual(len(loader._approved_records()), 6)
            changed = fake_pins()[:-1] + (fake_pins()[0],)
            with patch.object(loader, "RELEASE_PINNED_FILES", changed):
                with self.assertRaises(loader.PDFReleaseFontError):
                    loader._approved_records()
            with patch.object(loader, "RELEASE_PINNED_FILES", fake_pins()[:5]):
                with self.assertRaises(loader.PDFReleaseFontError):
                    loader._approved_records()

    def test_malformed_sha_or_approval_reference_refused(self):
        a, b, c = self.approved()
        with a, b, c:
            invalid = list(fake_pins())
            invalid[0] = (*invalid[0][:4], "not-a-sha")
            with patch.object(loader, "RELEASE_PINNED_FILES", tuple(invalid)):
                with self.assertRaises(loader.PDFReleaseFontError):
                    loader._approved_records()
            with patch.object(loader, "RELEASE_APPROVAL_REFERENCE", ""):
                with self.assertRaises(loader.PDFReleaseFontError):
                    loader._approved_records()

    def test_unsafe_release_asset_basename_rejected_before_file_access(self):
        a, b, c = self.approved()
        with a, b, c:
            for unsafe in ("../escaped.ttf", "subfolder/font.ttf",
                           "unreviewed\\\\font.ttf", ".",
                           "Noto.ttf?download=1"):
                with self.subTest(unsafe=unsafe):
                    invalid = list(fake_pins())
                    invalid[0] = (invalid[0][0], invalid[0][1],
                                  unsafe, invalid[0][3], invalid[0][4])
                    with patch.object(loader, "RELEASE_PINNED_FILES",
                                      tuple(invalid)):
                        with self.assertRaises(loader.PDFReleaseFontError):
                            loader._approved_records()

    def test_ignored_build_proofs_and_unsigned_release_fonts(self):
        root = Path(__file__).resolve().parents[1]
        ignore_lines = {
            ln.strip() for ln in (root / ".gitignore").read_text(
                encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
        }
        self.assertIn("/build/", ignore_lines)
        self.assertIn("/backend/assets/pdf_fonts/", ignore_lines)
        self.assertEqual(loader.RELEASE_APPROVAL_STATUS, "NOT_GRANTED")
        self.assertEqual(loader.RELEASE_PINNED_FILES, ())

    def test_mutated_approved_resource_refuses_export(self):
        """Verify existing secure SHA/notice reader, not any new source font."""
        with tempfile.TemporaryDirectory(prefix="p2-release-check-") as td:
            root = Path(td)
            entries = []
            for role in ROLES:
                for kind in ("font", "license"):
                    name = role + (".ttf" if kind == "font" else "-OFL.txt")
                    content = (b"SIL OPEN FONT LICENSE 1.1\nSynthetic test notice"
                               if kind == "license" else b"Synthetic TTF only")
                    (root / name).write_bytes(content)
                    entries.append({
                        "role": role, "kind": kind, "name": name,
                        "bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    })
            verified = verify_pdf_font_files(entries, resource_root=root)
            self.assertEqual(len(verified), 6)
            font = root / "regular.ttf"
            font.write_bytes(b"Synthetic TTF onlx")
            with self.assertRaises(PDFResourceError):
                verify_pdf_font_files(entries, resource_root=root)

    def test_missing_or_redirected_font_does_not_fallback(self):
        with tempfile.TemporaryDirectory(prefix="p2-release-missing-") as td:
            root = Path(td)
            entries = [{
                "role": role, "kind": kind,
                "name": role + (".ttf" if kind == "font" else "-OFL.txt"),
                "bytes": 8, "sha256": "b" * 64,
            } for role in ROLES for kind in ("font", "license")]
            with self.assertRaises(PDFResourceError):
                verify_pdf_font_files(entries, resource_root=root)

    def test_approved_but_unavailable_resource_returns_safe_error(self):
        a, b, c = self.approved()
        with a, b, c, patch.object(
                loader, "verify_pdf_font_files",
                side_effect=PDFResourceError("private path is unavailable")):
            renderer = Mock(return_value=b"NOT APPROVED")
            with self.assertRaisesRegex(loader.PDFReleaseFontError,
                                        "Missing or altered"):
                loader.render_export_pdf({}, renderer)
            renderer.assert_not_called()

    def test_enabled_path_passes_explicit_verified_context(self):
        sentinel = object()
        a, b, c = self.approved()
        renderer = Mock(return_value=b"synthetic Unicode")
        with a, b, c, patch.object(loader, "_verified_context",
                                   return_value=sentinel):
            result = loader.render_export_pdf({"synthetic": True}, renderer)
        self.assertEqual(result, b"synthetic Unicode")
        renderer.assert_called_once_with({"synthetic": True},
                                          unicode_context=sentinel)

    def test_enabled_renderer_failure_is_not_silently_legacy(self):
        a, b, c = self.approved()
        with a, b, c, patch.object(loader, "_verified_context",
                                   return_value=object()):
            with self.assertRaisesRegex(loader.PDFReleaseFontError, "failed"):
                loader.render_export_pdf({}, lambda *a, **k:
                                         (_ for _ in ()).throw(ValueError("invalid glyph")))

    def test_concurrent_enabled_exports_are_serialized(self):
        a, b, c = self.approved()
        events = []
        guard = threading.Lock()
        active = [0]
        errors = []

        def renderer(report, *, unicode_context):
            with guard:
                active[0] += 1
                events.append(active[0])
            time.sleep(.01)
            with guard:
                active[0] -= 1
            return b"rendered"

        def worker():
            try:
                if loader.render_export_pdf({}, renderer) != b"rendered":
                    raise AssertionError("unexpected result")
            except Exception as exc:
                errors.append(type(exc).__name__)

        with a, b, c, patch.object(loader, "_verified_context",
                                   return_value=object()):
            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=3)
            self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(errors, [])
        self.assertEqual(events, [1, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()
