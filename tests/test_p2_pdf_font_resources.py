"""Pure synthetic font resource layout contracts; no real fonts or installer.

Creates tiny temporary files that mimic the fixed PyInstaller package layout.
Does not touch the owner's staged 21 MB binaries, reports or user projects.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.pdf_font_resources import (
    PDFResourceError, resolve_pdf_font_root, verify_pdf_font_files
)


def _fixture(folder):
    module = folder / "extracted" / "backend" / "pdf_font_resources.py"
    module.parent.mkdir(parents=True)
    module.write_text("# synthetic module location, not imported\n")
    assets = module.parent / "assets" / "pdf_fonts"
    assets.mkdir(parents=True)
    entries = []
    for role in ("regular", "cjk", "symbol"):
        for kind in ("font", "license"):
            name = role + (".ttf" if kind == "font" else "-OFL.txt")
            body = (role + " tiny pretend font bytes").encode() if kind == "font" else (
                "SIL OPEN FONT LICENSE 1.1\nSynthetic test only: " + role).encode()
            (assets / name).write_bytes(body)
            entries.append({
                "role": role, "kind": kind, "name": name, "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            })
    return module, assets, entries


class PDFPackagedFontResourceContracts(unittest.TestCase):
    def test_simulated_onefile_module_relative_location(self):
        with TemporaryDirectory(prefix="odin-resource-layout-") as folder:
            module, root, _ = _fixture(Path(folder))
            self.assertEqual(resolve_pdf_font_root(module_file=module), root)

    def test_missing_package_never_falls_back_to_system_or_user_data(self):
        with TemporaryDirectory(prefix="odin-resource-layout-") as folder:
            path = Path(folder) / "backend" / "pdf_font_resources.py"
            with self.assertRaises(PDFResourceError):
                resolve_pdf_font_root(module_file=path)
            with self.assertRaises(PDFResourceError):
                verify_pdf_font_files([], resource_root=Path(folder))

    def test_all_six_integrity_checked_without_mutation(self):
        with TemporaryDirectory(prefix="odin-resource-layout-") as folder:
            _, root, entries = _fixture(Path(folder))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            found = verify_pdf_font_files(entries, resource_root=root)
            self.assertEqual(len(found), 6)
            self.assertEqual(set(found), {
                "regular_font", "regular_license", "cjk_font", "cjk_license",
                "symbol_font", "symbol_license"})
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_corruption_and_missing_asset_fail_closed(self):
        with TemporaryDirectory(prefix="odin-resource-layout-") as folder:
            _, root, entries = _fixture(Path(folder))
            (root / "cjk.ttf").write_bytes(b"incorrect but present")
            with self.assertRaises(PDFResourceError):
                verify_pdf_font_files(entries, resource_root=root)
            (root / "cjk.ttf").unlink()
            with self.assertRaises(PDFResourceError):
                verify_pdf_font_files(entries, resource_root=root)

    def test_untrusted_receipt_cannot_replace_pinned_hashes(self):
        with TemporaryDirectory(prefix="odin-resource-layout-") as folder:
            _, root, entries = _fixture(Path(folder))
            (root / "receipt.json").write_text('{"sha256":"untrusted"}')
            (root / "regular.ttf").write_bytes(b"tampered")
            with self.assertRaises(PDFResourceError):
                verify_pdf_font_files(entries, resource_root=root)

    def test_reject_name_traversal_duplicate_or_size_manipulation(self):
        with TemporaryDirectory(prefix="odin-resource-layout-") as folder:
            _, root, entries = _fixture(Path(folder))
            for bad in (
                {"name": "../escape.ttf"},
                {"name": r"..\escape.ttf"},
                {"bytes": 1},
                {"sha256": "wrong"},
                {"kind": "unknown"},
            ):
                with self.subTest(bad=bad):
                    records = [dict(x) for x in entries]
                    records[0].update(bad)
                    with self.assertRaises(PDFResourceError):
                        verify_pdf_font_files(records, resource_root=root)
            records = [dict(x) for x in entries]
            records[1]["role"], records[1]["kind"] = records[0]["role"], records[0]["kind"]
            with self.assertRaises(PDFResourceError):
                verify_pdf_font_files(records, resource_root=root)

    def test_missing_or_altered_ofl_notice_is_rejected(self):
        with TemporaryDirectory(prefix="odin-resource-layout-") as folder:
            _, root, entries = _fixture(Path(folder))
            path = root / "symbol-OFL.txt"
            body = b"Not an OFL notice"
            path.write_bytes(body)
            for x in entries:
                if x["name"] == path.name:
                    x["bytes"] = len(body)
                    x["sha256"] = hashlib.sha256(body).hexdigest()
            with self.assertRaisesRegex(PDFResourceError, "OFL"):
                verify_pdf_font_files(entries, resource_root=root)

    def test_repeated_concurrent_verification_has_no_registry_mutation(self):
        with TemporaryDirectory(prefix="odin-resource-layout-") as folder:
            _, root, entries = _fixture(Path(folder))
            with ThreadPoolExecutor(max_workers=4) as pool:
                outcomes = list(pool.map(
                    lambda _: verify_pdf_font_files(entries, resource_root=root),
                    range(8)))
            self.assertEqual(len(outcomes), 8)
            self.assertTrue(all(set(x) == set(outcomes[0]) for x in outcomes))


if __name__ == "__main__":
    unittest.main()
