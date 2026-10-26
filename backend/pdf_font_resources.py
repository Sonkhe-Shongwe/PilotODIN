"""PDF font resource location and integrity contract for future PilotODIN sidecar.

DORMANT: not imported by reports.py, report_charts.py, desktop_runner.py or
the installer. Resource files must eventually be bundled at:
    backend/assets/pdf_fonts/
relative to THIS module's __file__. PyInstaller preserves module-relative
__file__ paths for bundled packages. Never fall back to OS-installed fonts,
the working directory, LOCALAPPDATA/DevQA, PILOTODIN_HOME or a network URL.

This validator does not approve font distribution or font rendering.
Production integration must supply independently approved, pinned SHA-256s;
a mutable adjacent receipt is NOT a trusted release-hash authority.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

RESOURCE_PARTS = ("assets", "pdf_fonts")
MAX_SET_BYTES = 25 * 1024 * 1024
MAX_FILE_BYTES = 22 * 1024 * 1024
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\[\],-]*\Z")


class PDFResourceError(ValueError):
    """Safe, intentionally generic error for missing or altered packaged data."""


def _plain_path(path: Path) -> None:
    """Reject symlinks and Windows junctions even at parent levels."""
    for component in (path, *path.parents):
        if component.is_symlink() or (
                component.exists() and
                getattr(os.path, "isjunction", lambda _: False)(component)):
            raise PDFResourceError("Redirected font resource location")


def resolve_pdf_font_root(*, module_file: Path | None = None) -> Path:
    """Locate bundled assets beside backend/pdf_font_resources.py.

    The module_file injection is for isolated synthetic tests ONLY. Production
    callers must omit it. In PyInstaller --onefile, the module resides under
    its own extracted backend package directory.
    """
    location = Path(module_file) if module_file is not None else Path(__file__)
    if not location.is_absolute() or location.name != "pdf_font_resources.py":
        raise PDFResourceError("Unexpected font-loader module location")
    _plain_path(location.parent)
    root = location.parent.joinpath(*RESOURCE_PARTS)
    _plain_path(root)
    if not root.is_dir():
        raise PDFResourceError("Packaged PDF font resources not available")
    return root


def verify_pdf_font_files(entries: list[dict], *,
                          resource_root: Path | None = None) -> dict[str, Path]:
    """Verify six pinned fonts/licenses. Never modify assets or register fonts.

    Caller-supplied entries MUST eventually be code-pinned and independently
    approved for release; this method cannot establish that provenance itself.
    """
    if not isinstance(entries, list) or len(entries) != 6:
        raise PDFResourceError("Expected exactly six pinned PDF font resources")
    roles = set()
    filenames = set()
    total = 0
    checked = {}
    root = resource_root if resource_root is not None else resolve_pdf_font_root()
    if not isinstance(root, Path) or not root.is_absolute():
        raise PDFResourceError("Font resource root must be an absolute path")
    _plain_path(root)
    if not root.is_dir():
        raise PDFResourceError("Packaged PDF font directory missing")
    for item in entries:
        if not isinstance(item, dict):
            raise PDFResourceError("Malformed font resource record")
        role, kind = item.get("role"), item.get("kind")
        name, size, sha = item.get("name"), item.get("bytes"), item.get("sha256")
        if (role not in {"regular", "cjk", "symbol"} or
                kind not in {"font", "license"} or
                not isinstance(name, str) or not _SAFE_NAME.fullmatch(name) or
                name in {".", ".."} or
                not isinstance(size, int) or isinstance(size, bool) or
                size <= 0 or size > MAX_FILE_BYTES or
                not isinstance(sha, str) or not _HEX64.fullmatch(sha)):
            raise PDFResourceError("Malformed pinned font identity")
        if (role, kind) in roles or name in filenames:
            raise PDFResourceError("Duplicate pinned font resource")
        roles.add((role, kind))
        filenames.add(name)
        total += size
        if total > MAX_SET_BYTES:
            raise PDFResourceError("PDF font resource set exceeds limit")
        path = root / name
        _plain_path(path)
        if not path.is_file() or path.stat().st_size != size:
            raise PDFResourceError("Missing or altered packaged font resource")
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != sha:
            raise PDFResourceError("Packaged font resource hash mismatch")
        if kind == "license":
            # An integrity-checked OFL notice must accompany every font.
            try:
                notice = path.read_text(encoding="utf-8")
            except UnicodeError as exc:
                raise PDFResourceError("Unreadable font license") from exc
            if "SIL OPEN FONT LICENSE" not in notice.upper():
                raise PDFResourceError("Missing OFL notice content")
        checked[role + "_" + kind] = path
    if roles != {(role, kind) for role in ("regular", "cjk", "symbol")
                for kind in ("font", "license")}:
        raise PDFResourceError("Incomplete PDF font and license set")
    return checked
