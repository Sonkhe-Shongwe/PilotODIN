"""C5 independent inference-input verification; never acquires or stages assets.

Production is blocked: no reviewed complete expected inventory is available.
The candidate helper is for isolated, externally reviewed expected inventories
and synthetic tests only. A stage receipt is never its own trust root.
No CLI accepts expected digests, paths, or authority from the environment.
"""
from __future__ import annotations

from pathlib import Path
import os
import re
import sys

if __package__ in (None, ""):
    # Direct script invocation has desktop/, not repository root, on sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_input_preflight import (
    Blocked, DEVICE, HEX64, checked_directory, fields, identity,
    read_exact, require, strict_json, _scan_wheelhouse,
)

MODEL_FILE = "qwen3-1.7b-q4_k_m.gguf"
MODEL_ALIAS = "pilotodin-qwen3-1.7b"
SERVER_FILE = "pilotodin-inference-x86_64-pc-windows-msvc.exe"
RECEIPT = "model-manifest.json"
REQUIRED_NOTICES = {
    "llama.cpp-MIT-LICENSE.txt", "Qwen3-Apache-2.0-LICENSE.txt",
    "THIRD-PARTY-SOURCES.txt",
}
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_DIRECTORY_FILES = 512  # structural refusal bound, not an asset capacity claim
PE_PREFIX = 65536


def verify(root: Path) -> None:
    """Production preflight deliberately refuses before reading staged paths."""
    raise Blocked("C5_INFERENCE_PROVENANCE_BLOCKED")


def _check_row(row):
    fields(row, {"bytes", "sha256"})
    require(type(row["bytes"]) is int and row["bytes"] > 0
            and type(row["sha256"]) is str and HEX64.fullmatch(row["sha256"]),
            "INVALID_EXPECTED_ASSET_IDENTITY")


def _check_named_rows(rows, suffix):
    require(type(rows) is dict and 0 < len(rows) <= MAX_DIRECTORY_FILES,
            "EMPTY_OR_OVERSIZED_EXPECTED_INVENTORY")
    seen = set()
    pattern = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,119}" + re.escape(suffix),
                         re.ASCII | re.IGNORECASE)
    for name, row in rows.items():
        require(type(name) is str and pattern.fullmatch(name)
                and not DEVICE.match(name) and name.casefold() not in seen,
                "UNSAFE_OR_DUPLICATE_ASSET_NAME")
        seen.add(name.casefold())
        _check_row(row)


def expected_receipt(expected):
    """Validate externally supplied expectation shape and derive v1 receipt."""
    fields(expected, {"model", "server", "dlls", "notices"})
    _check_row(expected["model"])
    _check_row(expected["server"])
    _check_named_rows(expected["dlls"], ".dll")
    _check_named_rows(expected["notices"], ".txt")
    require(REQUIRED_NOTICES <= set(expected["notices"]),
            "REQUIRED_NOTICE_MISSING")
    return {
        "schema_version": 1, "model_file": MODEL_FILE,
        "model_alias": MODEL_ALIAS, "model_sha256": expected["model"]["sha256"],
        "server_sha256": expected["server"]["sha256"],
        "runtime_dll_sha256": {name: row["sha256"] for name, row in expected["dlls"].items()},
    }


def _gguf_header(prefix):
    require(len(prefix) >= 8 and prefix[:4] == b"GGUF"
            and int.from_bytes(prefix[4:8], "little") in (2, 3),
            "INVALID_GGUF_HEADER")


def _pe_header(prefix, *, dll):
    """Basic PE32+ AMD64 identity, not executable validity or Authenticode."""
    require(len(prefix) >= 64 and prefix[:2] == b"MZ", "INVALID_PE_HEADER")
    offset = int.from_bytes(prefix[60:64], "little")
    require(64 <= offset and offset + 26 <= len(prefix)
            and prefix[offset:offset + 4] == b"PE\0\0", "INVALID_PE_HEADER")
    machine = int.from_bytes(prefix[offset + 4:offset + 6], "little")
    optional_size = int.from_bytes(prefix[offset + 20:offset + 22], "little")
    characteristics = int.from_bytes(prefix[offset + 22:offset + 24], "little")
    magic = int.from_bytes(prefix[offset + 24:offset + 26], "little")
    require(machine == 0x8664 and magic == 0x20b and optional_size >= 2
            and offset + 24 + optional_size <= len(prefix)
            and bool(characteristics & 0x0002)
            and bool(characteristics & 0x2000) == dll, "INVALID_PE_X64_ROLE")


def _verify_file(path, row, kind):
    digest, prefix = read_exact(path, size=row["bytes"],
                                prefix_bytes=PE_PREFIX if kind in ("server", "dll")
                                else 8 if kind == "model" else 0)
    require(digest == row["sha256"], "ASSET_DIGEST_MISMATCH")
    if kind == "model":
        _gguf_header(prefix)
    elif kind in ("server", "dll"):
        _pe_header(prefix, dll=kind == "dll")


def verify_candidate_bundle(root: Path, expected) -> None:
    """Read-only point-in-time checks on a fresh isolated candidate tree.

    Expected identities must originate outside the tree under review. This
    helper does not authenticate its caller, a license, or provenance. It
    cannot authorize production, staging, or execution. No arbitrary parent
    root is considered owned merely because this function checks descendants.
    The sidecar/binaries directory is shared; only its fixed inference EXE
    is in this inventory. Model, runtime and notice directories are exact.
    """
    receipt = expected_receipt(expected)
    root = Path(root)
    try:
        dirs = {}
        for rel in ("", "frontend", "frontend/src-tauri",
                    "frontend/src-tauri/resources",
                    "frontend/src-tauri/resources/models",
                    "frontend/src-tauri/resources/llama-runtime",
                    "frontend/src-tauri/resources/licenses",
                    "frontend/src-tauri/binaries"):
            path = root / rel
            dirs[path] = identity(checked_directory(path))
        tauri = root / "frontend" / "src-tauri"
        models = tauri / "resources" / "models"
        dlls = tauri / "resources" / "llama-runtime"
        notices = tauri / "resources" / "licenses"
        inventories = [(models, {MODEL_FILE, RECEIPT}),
                       (dlls, set(expected["dlls"])),
                       (notices, set(expected["notices"]))]
        for directory, names in inventories:
            _scan_wheelhouse(directory, names)
        manifest = models / RECEIPT
        _, raw = read_exact(manifest, size=manifest.lstat().st_size,
                            collect=True, limit=MAX_RECEIPT_BYTES)
        actual = strict_json(raw)
        require(type(actual) is dict and type(actual.get("schema_version")) is int
                and actual == receipt, "INDEPENDENT_RECEIPT_MISMATCH")
        _verify_file(models / MODEL_FILE, expected["model"], "model")
        _verify_file(tauri / "binaries" / SERVER_FILE, expected["server"], "server")
        for filename, row in expected["dlls"].items():
            _verify_file(dlls / filename, row, "dll")
        for filename, row in expected["notices"].items():
            _verify_file(notices / filename, row, "notice")
        # Re-read bounded receipt and rescan all exact directories after hashing.
        _, final = read_exact(manifest, size=len(raw), collect=True,
                              limit=MAX_RECEIPT_BYTES)
        require(final == raw, "RECEIPT_CHANGED")
        for directory, names in inventories:
            _scan_wheelhouse(directory, names)
        for path, original in dirs.items():
            require(identity(checked_directory(path)) == original,
                    "ASSET_DIRECTORY_CHANGED")
    except OSError:
        raise Blocked("INFERENCE_INPUT_UNREADABLE") from None


if __name__ == "__main__":
    try:
        verify(Path(__file__).resolve().parents[1])
    except Blocked as exc:
        print("OFFLINE INFERENCE PRE-FLIGHT BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
