"""C5 read-only profile policy and candidate wheel identity primitives.

A valid policy is still BLOCKED. There is intentionally no READY or install
command, environment override, automatic resolver, or real acquisition route.
The candidate wheel verifier establishes byte identity only, not graph,
archive metadata, license truth, supported tags, or execution authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = "contracts/build_input_policy_v1.json"
MAX_POLICY_BYTES = 1024 * 1024
MAX_WHEELS = 512
SOURCE_PATHS = {
    "backend/requirements.txt",
    "backend/requirements-test.txt",
    "frontend/package-lock.json",
    "frontend/package.json",
    "frontend/src-tauri/Cargo.lock",
    "frontend/src-tauri/Cargo.toml",
    "third_party/tauri-plugin-shell-2.6.0/UPSTREAM.json"
}
PROFILES = {
    "windows-x64-cp311-production-build": ("windows", "cp311", "production-build", "backend/locks/windows-x64-cp311-production-build.txt", ["interpreter_distribution","pip_distribution","selected_wheel_graph","wheel_metadata_and_tags","wheel_artifact_sha256","license_inventory","pyinstaller_and_hooks","node_npm_toolchain","rust_msvc_sdk_toolchain","vendored_crate_bytes","runtime_model_and_dll_inventory","webview2_and_nsis_inputs","offline_bundler_consumption"]),
    "windows-x64-cp311-source-test": ("windows", "cp311", "source-test", "backend/locks/windows-x64-cp311-source-test.txt", ["interpreter_distribution","pip_distribution","selected_wheel_graph","wheel_metadata_and_tags","wheel_artifact_sha256","license_inventory"]),
    "linux-x64-cp311-source-test": ("linux", "cp311", "source-test", "backend/locks/linux-x64-cp311-source-test.txt", ["interpreter_distribution","pip_distribution","selected_wheel_graph","wheel_metadata_and_tags","wheel_artifact_sha256","license_inventory"]),
    "windows-x64-browser-dev": ("windows", "unresolved", "browser-dev", None, ["interpreter_distribution","pip_distribution","selected_wheel_graph","wheel_metadata_and_tags","wheel_artifact_sha256","license_inventory","node_npm_toolchain","installed_tree_identity","legacy_environment_compatibility"]),
}
# Exact reviewed definitions at 0df12bb, separate from the historical v1
# policy schema. A matching definition does not authorise its consumption.
REVIEWED_LOCK_PINS = {
    "backend/locks/windows-x64-cp311-production-build.txt": ("c28770c27a8e4add9037c1aeab20044880c4eaef", 4665),
    "backend/locks/windows-x64-cp311-source-test.txt": ("ff4393192ee3d752c6f790eebb98f042e316301f", 5263),
    "backend/locks/linux-x64-cp311-source-test.txt": ("29f97e0fc36f5ea3065c16f9bb812f34ddfb98f1", 5261),
}
WHEEL_FIELDS = {
    "name", "version", "filename", "bytes", "sha256", "source",
    "metadata_source", "license_expression", "license_review",
}
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VERSION = re.compile(r"[0-9][A-Za-z0-9_.+!]*")
TAG = re.compile(r"[a-z0-9_]+-[a-z0-9_]+-[a-z0-9_]+")
FILENAME = re.compile(r"[A-Za-z0-9_]+-[0-9][A-Za-z0-9_.+!]*(?:-[0-9][A-Za-z0-9_]*)?-[a-z0-9_.]+-[a-z0-9_.]+-[a-z0-9_.]+\.whl")
DEVICE = re.compile(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)")


class Blocked(ValueError):
    """Deterministic refusal; do not print private paths or untrusted bytes."""


def require(condition, reason):
    if not condition:
        raise Blocked(reason)


def fields(obj, keys):
    require(type(obj) is dict and set(obj) == set(keys), "UNEXPECTED_FIELDS")


def strict_json(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_POLICY_BYTES, "POLICY_SIZE")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def reject_constant(_):
        raise Blocked("NONFINITE_JSON")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise Blocked("MALFORMED_JSON") from None


def reparse(info):
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def checked_directory(path):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not reparse(info), "UNSAFE_DIRECTORY")
    return info


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink)


def read_exact(path, *, size, collect=False, limit=None, prefix_bytes=0):
    """Open a bounded regular single-link file and detect observable drift."""
    require(type(size) is int and size > 0, "INVALID_SIZE")
    require(type(prefix_bytes) is int and 0 <= prefix_bytes <= 65536
            and not (collect and prefix_bytes), "INVALID_PREFIX_LIMIT")
    if limit is not None:
        require(size <= limit, "INPUT_TOO_LARGE")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and not reparse(before)
            and before.st_nlink == 1 and before.st_size == size,
            "UNSAFE_OR_WRONG_SIZE")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        require(identity(opened) == identity(before) and stat.S_ISREG(opened.st_mode)
                and not reparse(opened), "FILE_CHANGED")
        digest = hashlib.sha256()
        chunks = [] if collect else None
        prefix = bytearray() if prefix_bytes else None
        remaining = size
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            require(bool(chunk), "SHORT_READ")
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
            if prefix is not None and len(prefix) < prefix_bytes:
                prefix.extend(chunk[:prefix_bytes - len(prefix)])
            remaining -= len(chunk)
        require(not os.read(fd, 1), "FILE_GREW")
        after = path.lstat()
        require(identity(os.fstat(fd)) == identity(opened)
                and identity(after) == identity(opened) and not reparse(after),
                "FILE_CHANGED")
        payload = b"".join(chunks) if chunks is not None else bytes(prefix) if prefix is not None else None
        return digest.hexdigest(), payload
    finally:
        os.close(fd)


def source_file(root, relative):
    """Only fixed repo-relative source paths, no traversal or directory links."""
    require(relative in SOURCE_PATHS or relative in REVIEWED_LOCK_PINS
            or relative == POLICY_PATH, "UNKNOWN_SOURCE_PATH")
    checked_directory(root)
    path = root
    parts = relative.split("/")
    for part in parts[:-1]:
        path /= part
        checked_directory(path)
    path /= parts[-1]
    return path


def validate_policy(doc):
    fields(doc, {"schema_version", "source_commit", "source_inputs",
                 "vendored_shell_tree", "profiles"})
    require(type(doc["schema_version"]) is int and doc["schema_version"] == 1,
            "UNSUPPORTED_POLICY_VERSION")
    for key in ("source_commit", "vendored_shell_tree"):
        require(type(doc[key]) is str and HEX40.fullmatch(doc[key]), "INVALID_SOURCE_ID")
    rows = doc["source_inputs"]
    require(type(rows) is list and len(rows) == len(SOURCE_PATHS), "SOURCE_INVENTORY")
    seen = set()
    for row in rows:
        fields(row, {"path", "git_blob_sha1", "bytes"})
        name = row["path"]
        require(type(name) is str and name in SOURCE_PATHS and name not in seen,
                "SOURCE_INVENTORY")
        seen.add(name)
        require(type(row["git_blob_sha1"]) is str and HEX40.fullmatch(row["git_blob_sha1"])
                and type(row["bytes"]) is int and 0 < row["bytes"] <= 2 * MAX_POLICY_BYTES,
                "INVALID_SOURCE_ID")
    rows = doc["profiles"]
    require(type(rows) is list and len(rows) == len(PROFILES), "PROFILE_INVENTORY")
    seen = set()
    for row in rows:
        fields(row, {"id", "platform", "arch", "python_abi_candidate", "purpose",
                     "planned_lock", "status", "blockers"})
        key = row["id"]
        require(type(key) is str and key in PROFILES and key not in seen, "PROFILE_INVENTORY")
        seen.add(key)
        platform, abi, purpose, lock, blockers = PROFILES[key]
        require(row["platform"] == platform and row["arch"] == "x64"
                and row["python_abi_candidate"] == abi and row["purpose"] == purpose
                and row["planned_lock"] == lock and row["status"] == "BLOCKED"
                and row["blockers"] == blockers, "PROFILE_MUST_REMAIN_BLOCKED")
    return doc


def audit_policy(root=ROOT):
    """Verify pinned canonical Git text source bytes, not installed artifacts."""
    path = source_file(root, POLICY_PATH)
    _, raw = read_exact(path, size=path.lstat().st_size, collect=True,
                        limit=MAX_POLICY_BYTES)
    doc = validate_policy(strict_json(raw))
    for row in doc["source_inputs"]:
        path = source_file(root, row["path"])
        _, raw = read_exact(path, size=path.lstat().st_size, collect=True,
                            limit=2 * MAX_POLICY_BYTES)
        # A Git Windows text checkout may use CRLF. Compare canonical Git blob
        # identity only; this is explicitly not a raw wheel/toolchain digest.
        canonical = raw.replace(b"\r\n", b"\n")
        if len(raw) == row["bytes"]:
            canonical = raw
        digest = hashlib.sha1(b"blob " + str(len(canonical)).encode("ascii")
                              + b"\0" + canonical).hexdigest()
        require(len(canonical) == row["bytes"] and digest == row["git_blob_sha1"],
                "SOURCE_PIN_MISMATCH")
    # The lock files are independently pinned, not trusted just because a
    # BLOCKED profile names them. The existing CLI remains read-only.
    require({row["planned_lock"] for row in doc["profiles"]
             if row["planned_lock"] is not None} == set(REVIEWED_LOCK_PINS),
            "REVIEWED_LOCK_INVENTORY")
    for relative, (expected_blob, expected_size) in REVIEWED_LOCK_PINS.items():
        try:
            path = source_file(root, relative)
            _, raw = read_exact(path, size=path.lstat().st_size, collect=True,
                                limit=MAX_POLICY_BYTES)
        except (Blocked, OSError):
            raise Blocked("REVIEWED_LOCK_UNREADABLE") from None
        canonical = raw.replace(b"\r\n", b"\n")
        digest = hashlib.sha1(b"blob " + str(len(canonical)).encode("ascii")
                              + b"\0" + canonical).hexdigest()
        require(len(canonical) == expected_size and digest == expected_blob,
                "REVIEWED_LOCK_PIN_MISMATCH")
    return doc


def normalized_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def validate_candidate_wheels(rows, accepted_tags):
    """Validate a separately reviewed expected inventory, not infer compatibility."""
    require(type(accepted_tags) in (set, frozenset) and 0 < len(accepted_tags) <= 4096
            and all(type(tag) is str and TAG.fullmatch(tag) for tag in accepted_tags),
            "UNREVIEWED_TAG_SET")
    require(type(rows) is list and 0 < len(rows) <= MAX_WHEELS, "WHEEL_INVENTORY")
    names, filenames = set(), set()
    for row in rows:
        fields(row, WHEEL_FIELDS)
        name, version, filename = row["name"], row["version"], row["filename"]
        require(type(name) is str and NAME.fullmatch(name) and name not in names,
                "DUPLICATE_OR_INVALID_DISTRIBUTION")
        names.add(name)
        require(type(version) is str and len(version) <= 128 and VERSION.fullmatch(version),
                "INVALID_WHEEL_VERSION")
        require(type(filename) is str and len(filename) <= 240 and FILENAME.fullmatch(filename)
                and not DEVICE.match(filename) and filename.casefold() not in filenames,
                "INVALID_OR_DUPLICATE_WHEEL_FILENAME")
        filenames.add(filename.casefold())
        parts = filename[:-4].split("-")
        require(len(parts) in (5, 6), "INVALID_WHEEL_FILENAME")
        distribution, wheel_version = parts[:2]
        require(normalized_name(distribution) == name and wheel_version == version,
                "WHEEL_NAME_VERSION_MISMATCH")
        if len(parts) == 6:
            require(re.fullmatch(r"[0-9][A-Za-z0-9_]*", parts[2]), "INVALID_BUILD_TAG")
        tags = [part.split(".") for part in parts[-3:]]
        require(all(0 < len(group) <= 16 for group in tags), "INVALID_WHEEL_TAG")
        expanded = {"-".join(tag) for tag in itertools.product(*tags)}
        require(all(TAG.fullmatch(tag) for tag in expanded)
                and bool(expanded & accepted_tags), "INCOMPATIBLE_WHEEL_TAG")
        require(type(row["bytes"]) is int and row["bytes"] > 0
                and type(row["sha256"]) is str and HEX64.fullmatch(row["sha256"]),
                "INVALID_WHEEL_DIGEST_OR_SIZE")
        source = row["source"]
        require(type(source) is str and re.fullmatch(
            r"https://files\.pythonhosted\.org/packages/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/"
            + re.escape(filename), source), "UNREVIEWED_WHEEL_ORIGIN")
        require(row["metadata_source"] == f"https://pypi.org/pypi/{name}/{version}/json",
                "UNREVIEWED_METADATA_ORIGIN")
        for key in ("license_expression", "license_review"):
            value = row[key]
            require(type(value) is str and 0 < len(value.strip()) <= 200
                    and value.strip().lower() not in {"unknown", "none", "pending", "unreviewed"}
                    and all(32 <= ord(c) < 127 for c in value), "MISSING_LICENSE_REVIEW")
    return rows


def _scan_wheelhouse(root, expected):
    """Both passes use the same bounded, exact, case-sensitive inventory."""
    actual = set()
    with os.scandir(root) as entries:
        for entry in entries:
            require(len(actual) < len(expected) and entry.name in expected,
                    "UNEXPECTED_WHEELHOUSE_ENTRY")
            require(entry.name not in actual, "DUPLICATE_WHEELHOUSE_ENTRY")
            actual.add(entry.name)
    require(actual == set(expected), "MISSING_WHEELHOUSE_ENTRY")
    return actual


def verify_candidate_wheel_bytes(wheelhouse, rows, accepted_tags):
    """Flat exact-inventory read only. No archive extraction or subprocess."""
    validate_candidate_wheels(rows, accepted_tags)
    root = Path(wheelhouse)
    try:
        before = checked_directory(root)
        expected = {row["filename"]: row for row in rows}
        actual = _scan_wheelhouse(root, expected)
        result = {}
        for filename, row in expected.items():
            digest, _ = read_exact(root / filename, size=row["bytes"])
            require(digest == row["sha256"], "WHEEL_DIGEST_MISMATCH")
            result[filename] = digest
        require(_scan_wheelhouse(root, expected) == actual, "WHEELHOUSE_CHANGED")
        require(identity(checked_directory(root)) == identity(before), "WHEELHOUSE_CHANGED")
        return result
    except OSError:
        raise Blocked("WHEELHOUSE_UNREADABLE") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--audit-policy", action="store_true")
    modes.add_argument("--profile", choices=sorted(PROFILES))
    args = parser.parse_args(argv)
    try:
        doc = audit_policy()
        if args.audit_policy:
            print("C5_BLOCKED_POLICY_VALID: four candidate profiles; no installation authority")
            return 0
        row = next(row for row in doc["profiles"] if row["id"] == args.profile)
        print(json.dumps({"profile": row["id"], "status": "BLOCKED",
                          "blockers": row["blockers"]}, sort_keys=True))
        return 2
    except (Blocked, OSError):
        print("C5_PROFILE_POLICY_BLOCKED: missing, drifted or invalid source policy",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
