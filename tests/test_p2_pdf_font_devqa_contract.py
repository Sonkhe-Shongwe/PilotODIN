"""Pure unit-contract tests for developer-only P2 font probes.

All files are disposable synthetic bytes. Never touch real projects, OS fonts,
downloaded fonts, ML, Tauri or the previously accepted P2 Windows QA suites.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import socket
import ssl
import unittest
from unittest.mock import patch
import urllib.error

from tools.p2_pdf_font_asset_gate import hash_file, strict_member, verify
from tools.p2_pdf_font_coverage_probe import font_runs
from tools.p2_pdf_font_stage_candidates import (
    stage_one, CandidateStageError, describe_candidate_failure)
from tools.p2_pdf_font_local_review import review


class FontDevQAContract(unittest.TestCase):
    def test_git_blob_hash_and_sha256_are_independent(self):
        with TemporaryDirectory(prefix="odin-font-contract-") as temp:
            f = Path(temp) / "synthetic.bin"
            f.write_bytes(b"synthetic-font-contract-only")
            size, sha256, git_blob = hash_file(f)
            self.assertEqual(size, len(f.read_bytes()))
            self.assertEqual(sha256, hashlib.sha256(f.read_bytes()).hexdigest())
            self.assertEqual(
                git_blob,
                hashlib.sha1(b"blob " + str(size).encode("ascii") +
                             b"\0" + f.read_bytes()).hexdigest())

    def test_font_runs_use_original_codepoints_and_fallback(self):
        coverage = {
            "regular": set(map(ord, "A ΔΩ Москва ₹")),
            "cjk": set(map(ord, "漢字")),
            "emoji": {ord("📈")},
        }
        original = "A 漢字 📈 Δ"
        runs, missing = font_runs(original, coverage)
        self.assertEqual(missing, [])
        self.assertEqual("".join(part for _, part in runs), original)
        self.assertEqual([f for f, _ in runs],
                         ["regular", "cjk", "regular", "emoji", "regular"])

        broken, missing = font_runs("A 未", coverage)
        self.assertEqual(missing, [ord("未")])
        self.assertEqual("".join(part for _, part in broken), "A ")

    def test_candidate_root_rejects_redirects_and_bad_manifest(self):
        with TemporaryDirectory(prefix="odin-asset-contract-") as temp:
            root = Path(temp)
            (root / "safe.ttf").write_bytes(b"not-a-font")
            self.assertEqual(strict_member(root, "safe.ttf"), root / "safe.ttf")
            for name in ("../safe.ttf", "/tmp/safe.ttf", ".", "..", ""):
                with self.assertRaises(ValueError, msg=name):
                    strict_member(root, name)
            with self.assertRaises(ValueError):
                verify(root, {"schema": 1, "status": "CANDIDATES_UNVERIFIED_DO_NOT_SHIP",
                              "source_commit": "a" * 40, "assets": []})


    def test_pinned_staging_reuses_verified_bytes_without_network(self):
        with TemporaryDirectory(prefix="odin-font-stage-contract-") as temp:
            root = Path(temp)
            payload = b"synthetic-not-a-real-font"
            blob = hashlib.sha1(b"blob " + str(len(payload)).encode() +
                                b"\0" + payload).hexdigest()
            class Response(BytesIO):
                def geturl(self):
                    return ("https://raw.githubusercontent.com/google/fonts/" +
                            "a" * 40 + "/ofl/notosans/sample.ttf")
            def opener(url, timeout):
                self.assertEqual(timeout, 45)
                self.assertTrue(url.startswith("https://raw.githubusercontent.com/"))
                return Response(payload)
            expected = stage_one(root, "a" * 40, "ofl/notosans/sample.ttf",
                                 "sample.ttf", len(payload), blob, opener)
            self.assertEqual(expected["source"], "pinned_download")
            self.assertEqual((root / "sample.ttf").read_bytes(), payload)
            def forbidden(url, timeout):
                self.fail("Staged asset must not be downloaded again")
            existing = stage_one(root, "a" * 40, "ofl/notosans/sample.ttf",
                                 "sample.ttf", len(payload), blob, forbidden)
            self.assertEqual(existing["source"], "existing_verified")

    def test_staging_mismatched_asset_cannot_publish_or_leave_partial(self):
        with TemporaryDirectory(prefix="odin-font-stage-fail-") as temp:
            root = Path(temp)
            class Response(BytesIO):
                def geturl(self):
                    return ("https://raw.githubusercontent.com/google/fonts/" +
                            "a" * 40 + "/ofl/notosans/sample.ttf")
            bad_blob = "a" * 40
            with self.assertRaises(CandidateStageError) as failure:
                stage_one(root, "a" * 40, "ofl/notosans/sample.ttf",
                          "sample.ttf", 5, bad_blob, lambda *_args, **_kw: Response(b"hello"))
            self.assertEqual(failure.exception.stage, "identity_verification")
            self.assertEqual(list(root.iterdir()), [])
            with self.assertRaises(CandidateStageError) as bad_path:
                stage_one(root, "a" * 40, "ofl/notosans/sample.ttf",
                          "../traversal", 5, bad_blob,
                          lambda *_args, **_kw: Response(b"hello"))
            self.assertEqual(bad_path.exception.stage, "metadata_validation")
            self.assertEqual(list(root.iterdir()), [])

    def test_dns_failure_identifies_asset_and_public_source(self):
        with TemporaryDirectory(prefix="odin-font-dns-") as temp:
            root = Path(temp)
            def offline(_url, timeout):
                self.assertEqual(timeout, 45)
                raise urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))
            with self.assertRaises(CandidateStageError) as captured:
                stage_one(root, "a" * 40, "ofl/notosans/sample.ttf",
                          "sample.ttf", 6, "a" * 40, offline)
            result = describe_candidate_failure(captured.exception, "a" * 40)
            self.assertEqual(result["asset"], "sample.ttf")
            self.assertEqual(result["stage"], "connection")
            self.assertEqual(result["reason_category"], "DNS_RESOLUTION")
            self.assertEqual(result["reason_class"], "gaierror")
            self.assertTrue(result["source_url"].startswith(
                "https://raw.githubusercontent.com/google/fonts/"))
            self.assertFalse(list(root.iterdir()))

    def test_http_tls_and_proxy_network_diagnostics_are_classified(self):
        cases = [
            (urllib.error.HTTPError("https://raw.githubusercontent.com/",
                                    503, "Service Unavailable", {}, None),
             "HTTP_STATUS", 503),
            (urllib.error.URLError(
                ssl.SSLCertVerificationError(1, "certificate verify failed")),
             "TLS_CERTIFICATE", None),
            (urllib.error.URLError(
                "Tunnel connection failed: 407 Proxy Authentication Required"),
             "PROXY_OR_GATEWAY", None),
            (urllib.error.URLError(TimeoutError("timed out")),
             "TIMEOUT", None),
        ]
        for cause, expected, status in cases:
            with self.subTest(expected=expected):
                item = CandidateStageError("sample.ttf",
                                           "ofl/notosans/sample.ttf",
                                           "connection", cause)
                result = describe_candidate_failure(item, "a" * 40)
                self.assertEqual(result["reason_category"], expected)
                self.assertEqual(result["http_status"], status)
                self.assertEqual(result["product_acceptance"], "NOT_TESTED")

    def test_network_diagnostics_redact_proxy_credentials(self):
        cause = urllib.error.URLError(
            "Tunnel connection failed: https://user:password@proxy.invalid/"
            "?token=private-secret")
        error = CandidateStageError("sample.ttf", "ofl/notosans/sample.ttf",
                                    "connection", cause)
        result = describe_candidate_failure(error, "a" * 40)
        self.assertEqual(result["reason_category"], "PROXY_OR_GATEWAY")
        self.assertNotIn("private-secret", result["reason_excerpt"])
        self.assertNotIn("user:password", result["reason_excerpt"])
        self.assertIn("[URL REDACTED]", result["reason_excerpt"])


    def test_offline_candidate_review_preserves_visual_acceptance_boundary(self):
        with TemporaryDirectory(prefix="odin-font-offline-") as folder:
            root = Path(folder)
            manifest = {"assets": [
                {"role": "regular", "filename": "regular.ttf"},
                {"role": "cjk", "filename": "cjk.ttf"},
                {"role": "symbol", "filename": "symbol.ttf"},
            ]}
            cmap = {"state": "CANDIDATE_FILE_AND_CMAP_PROBE_PASS",
                    "font_assets": [
                        {"role": role, "format_gate": "GLYPHS_PRESENT",
                         "missing_or_error": []}
                        for role in ("regular", "cjk", "symbol")
                    ]}
            sample = {"samples": {"latin": {"state": "EXTRACTED_EXACT"},
                                   "mixed": {"state": "MISMATCH"}}}
            with patch("tools.p2_pdf_font_local_review.verify", return_value=cmap), \
                 patch("tools.p2_pdf_font_local_review.audit", return_value=sample):
                result = review(root, manifest)
            self.assertEqual(result["state"], "CANDIDATE_REVIEW_REQUIRED")
            self.assertEqual(result["asset_integrity"],
                             "VERIFIED_PINNED_FONT_AND_LICENSE_BYTES")
            self.assertEqual(result["exact_pdf_extraction"]["mixed"], "MISMATCH")
            self.assertEqual(result["visual_acceptance"], "NOT_TESTED")

    def test_offline_candidate_review_never_calls_network(self):
        with TemporaryDirectory(prefix="odin-font-offline-pass-") as folder:
            root = Path(folder)
            manifest = {"assets": [
                {"role": "regular", "filename": "regular.ttf"},
                {"role": "cjk", "filename": "cjk.ttf"},
                {"role": "symbol", "filename": "symbol.ttf"},
            ]}
            cmap = {"state": "CANDIDATE_FILE_AND_CMAP_PROBE_PASS",
                    "font_assets": [
                        {"role": role, "format_gate": "GLYPHS_PRESENT",
                         "missing_or_error": []}
                        for role in ("regular", "cjk", "symbol")
                    ]}
            exact = {"samples": {"mixed": {"state": "EXTRACTED_EXACT"}}}
            with patch("tools.p2_pdf_font_local_review.verify", return_value=cmap), \
                 patch("tools.p2_pdf_font_local_review.audit", return_value=exact):
                result = review(root, manifest)
            self.assertEqual(result["state"], "CANDIDATE_EXTRACTION_PASS_VISUAL_PENDING")
            self.assertEqual(result["visual_acceptance"], "NOT_TESTED")


if __name__ == "__main__":
    unittest.main()
