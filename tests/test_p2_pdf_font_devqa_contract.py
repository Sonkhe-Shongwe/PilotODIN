"""Pure unit-contract tests for developer-only P2 font probes.

All files are disposable synthetic bytes. Never touch real projects, OS fonts,
downloaded fonts, ML, Tauri or the previously accepted P2 Windows QA suites.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.p2_pdf_font_asset_gate import hash_file, strict_member, verify
from tools.p2_pdf_font_coverage_probe import font_runs


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


if __name__ == "__main__":
    unittest.main()
