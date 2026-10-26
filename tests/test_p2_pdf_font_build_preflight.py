"""P2-U1 pure synthetic build-preflight contract. Never stage real fonts.

All source/destination paths use temporary directories. The real candidate
gate is substituted by a deterministic stub only for these contract tests.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.p2_pdf_font_asset_gate import hash_file
from tools.p2_pdf_font_build_preflight import (
    _expected, audited_sources, stage_for_review
)

ROLES = ("regular", "cjk", "symbol")


def fixture(directory: Path):
    assets = []
    for role in ROLES:
        font = role + ".ttf"
        notice = role + "-OFL.txt"
        font_bytes = ("synthetic-font-not-for-distribution-" + role).encode() * 2
        license_bytes = ("SIL OPEN FONT LICENSE synthetic contract " + role).encode() * 14
        info = {}
        for name, content, stem in (
            (font, font_bytes, ""),
            (notice, license_bytes, "license_"),
        ):
            (directory / name).write_bytes(content)
            n, sha256, oid = hash_file(directory / name)
            info[stem + "bytes"] = n
            info[stem + "git_blob_sha1"] = oid
        assets.append({
            "role": role,
            "filename": font, "license_filename": notice,
            "bytes": info["bytes"], "license_bytes": info["license_bytes"],
            "git_blob_sha1": info["git_blob_sha1"],
            "license_git_blob_sha1": info["license_git_blob_sha1"],
        })
    return {
        "schema": 1, "status": "CANDIDATES_UNVERIFIED_DO_NOT_SHIP",
        "source_repo": "google/fonts", "source_commit": "a" * 40,
        "assets": assets,
    }


def fake_gate(source, manifest):
    return {"state": "CANDIDATE_FILE_AND_CMAP_PROBE_PASS"}


class FontBuildPreflightContracts(unittest.TestCase):
    def test_audit_is_read_only_and_exactly_six_assets(self):
        with TemporaryDirectory(prefix="odin-font-u1-") as root:
            source = Path(root)
            manifest = fixture(source)
            before = {p.name: p.read_bytes() for p in source.iterdir()}
            result = audited_sources(source, manifest, checker=fake_gate)
            self.assertEqual(len(result), 6)
            self.assertEqual({item["kind"] for item in result}, {"font", "license"})
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})

    def test_stages_exactly_six_files_and_review_only_receipt(self):
        with TemporaryDirectory(prefix="odin-font-u1-") as root:
            folder = Path(root)
            source, output = folder / "src", folder / "build"
            source.mkdir()
            manifest = fixture(source)
            tag = "b" * 32
            result = stage_for_review(source, output, manifest, checker=fake_gate,
                                      identifier=tag)
            self.assertEqual(result["state"], "BUILD_PREFLIGHT_ONLY_NOT_FOR_RELEASE")
            review = output / ("review-" + tag)
            self.assertEqual(len(list(review.iterdir())), 7)
            receipt = json.loads((review / "receipt.json").read_text())
            self.assertEqual(receipt["license_files_included"], 3)
            self.assertFalse(receipt["packaged_sidecar_verified"])
            self.assertEqual(receipt["product_acceptance"], "NOT_TESTED")
            self.assertEqual(receipt["sha256_approval"],
                             "MEASURED_RECEIPTS_NOT_INDEPENDENT_RELEASE_APPROVAL")
            self.assertTrue(all(hash_file(review / item["name"])[1] == item["sha256"]
                                for item in receipt["assets"]))
            self.assertEqual({p.name for p in source.iterdir()},
                             {p.name for p in review.iterdir() if p.name != "receipt.json"})

    def test_corrupt_source_fails_before_creating_output_directory(self):
        with TemporaryDirectory(prefix="odin-font-u1-") as root:
            folder = Path(root)
            source, output = folder / "src", folder / "build"
            source.mkdir()
            manifest = fixture(source)
            (source / "cjk.ttf").write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                stage_for_review(source, output, manifest, checker=fake_gate,
                                 identifier="c" * 32)
            self.assertFalse(output.exists())

    def test_bad_copy_cleanup_does_not_delete_prior_reviews(self):
        with TemporaryDirectory(prefix="odin-font-u1-") as root:
            folder = Path(root)
            source, output = folder / "src", folder / "build"
            source.mkdir()
            output.mkdir()
            manifest = fixture(source)
            (output / ("review-" + "a" * 32)).mkdir()
            existing = output / ("review-" + "a" * 32)
            (existing / "KEEP").write_text("unchanged")
            actual = hash_file
            def broken_hash(path):
                if path.parent.name.startswith("pending-"):
                    raise ValueError("Synthetic copied-asset failure")
                return actual(path)
            with patch("tools.p2_pdf_font_build_preflight.hash_file",
                       side_effect=broken_hash):
                with self.assertRaises(ValueError):
                    stage_for_review(source, output, manifest, checker=fake_gate,
                                     identifier="d" * 32)
            self.assertEqual(sorted(p.name for p in output.iterdir()), [existing.name])
            self.assertEqual((existing / "KEEP").read_text(), "unchanged")

    def test_preexisting_review_cannot_be_overwritten(self):
        with TemporaryDirectory(prefix="odin-font-u1-") as root:
            folder = Path(root)
            source, output = folder / "src", folder / "build"
            source.mkdir()
            manifest = fixture(source)
            stage_for_review(source, output, manifest, checker=fake_gate,
                             identifier="e" * 32)
            with self.assertRaises(FileExistsError):
                stage_for_review(source, output, manifest, checker=fake_gate,
                                 identifier="e" * 32)

    def test_reject_duplicate_filenames_traversal_and_bad_manifest(self):
        with TemporaryDirectory(prefix="odin-font-u1-") as root:
            manifest = fixture(Path(root))
            manifest["assets"][0]["license_filename"] = "../other.txt"
            with self.assertRaises(ValueError):
                _expected(manifest)
            manifest = fixture(Path(root))
            manifest["assets"][1]["license_filename"] = manifest["assets"][0]["license_filename"]
            with self.assertRaises(ValueError):
                _expected(manifest)
            manifest = fixture(Path(root))
            manifest["assets"][0]["bytes"] = 99_999_999
            with self.assertRaises(ValueError):
                _expected(manifest)

    def test_redirected_build_output_is_rejected(self):
        with TemporaryDirectory(prefix="odin-font-u1-") as root:
            folder = Path(root)
            source, output = folder / "src", folder / "build"
            source.mkdir()
            manifest = fixture(source)
            with patch("tools.p2_pdf_font_build_preflight._not_redirected",
                       side_effect=ValueError("Synthetic junction")):
                with self.assertRaises(ValueError):
                    stage_for_review(source, output, manifest, checker=fake_gate,
                                     identifier="f" * 32)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
