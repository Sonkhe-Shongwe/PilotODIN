"""Synthetic C5 staging transaction, never a production staging entrypoint.

Only inert .txt/.bin fixture archives in a newly created, caller-owned test
store. The cooperative writer lock is not a physical sandbox. No CLI, repair,
recursive deletion, native launch, or production resource path.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import uuid
import zipfile

from tools import c5_archive_preflight as archive
from tools.build_input_preflight import (
    Blocked, checked_directory, fields, read_exact, require, strict_json,
)

LIMIT = 1024 * 1024
MAX_FIXTURE_FILES = 32
POINTER = "current.json"
RECEIPT = "receipt.json"
LOCK = ".writer"
GEN = re.compile(r"gen-[0-9a-f]{32}")


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("ascii")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dir_id(path):
    st = checked_directory(path)
    return st.st_dev, st.st_ino


def sync_dir(path):
    # Python has no portable directory fsync on Windows. File fsync and
    # same-directory replace still tested; power-loss durability not claimed.
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                 | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def create_fixture_store(root):
    root = Path(root)
    require(root.name == "c5-synthetic-store", "STAGE_FIXTURE_SCOPE")
    checked_directory(root.parent)
    root.mkdir(mode=0o700)  # never adopt or overwrite an existing store
    sync_dir(root.parent)
    return root


def fixture_members(expected):
    members = archive.expected_inventory(expected)
    require(len(members) <= MAX_FIXTURE_FILES
            and expected["bytes"] <= LIMIT
            and sum(row["bytes"] for row in members.values()) <= LIMIT
            and all(0 < row["bytes"] and name.endswith((".txt", ".bin"))
                    for name, row in members.items()), "STAGE_FIXTURE_SCOPE")
    return members


def read_small(path):
    _, raw = read_exact(path, size=path.lstat().st_size, collect=True, limit=LIMIT)
    return raw


def pointer_bytes(root):
    path = root / POINTER
    try:
        return read_small(path)
    except FileNotFoundError:
        # A missing leaf is acceptable only if it is actually absent.
        require(not os.path.lexists(path), "STAGE_POINTER_UNSAFE")
        return None


def write_new(path, chunks):
    with path.open("xb") as f:
        for chunk in chunks:
            require(f.write(chunk) == len(chunk), "STAGE_SHORT_WRITE")
        f.flush()
        os.fsync(f.fileno())


def member_paths(members):
    dirs = {""}
    for name in members:
        parts = name.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return dirs


def scan_exact(data, members):
    """Bounded exact walk of only expected directories; never follow links."""
    dirs = member_paths(members)
    initial = {}
    for rel in sorted(dirs):
        folder = data / rel
        initial[folder] = dir_id(folder)
        names = {name.rsplit("/", 1)[-1] for name in members
                 if name.rpartition("/")[0] == rel}
        names.update(name.rsplit("/", 1)[-1] for name in dirs if name
                     and name.rpartition("/")[0] == rel)
        seen = set()
        with os.scandir(folder) as entries:
            for entry in entries:
                require(entry.name in names and entry.name not in seen,
                        "STAGE_EXTRA_ENTRY")
                seen.add(entry.name)
        require(seen == names, "STAGE_MISSING_ENTRY")
    for name, expected in members.items():
        actual, _ = read_exact(data / name, size=expected["bytes"], limit=LIMIT)
        require(actual == expected["sha256"], "STAGE_MEMBER_DIGEST")
    for path, initial_id in initial.items():
        require(dir_id(path) == initial_id, "STAGE_DIRECTORY_CHANGED")
    return initial


def verify_generation(root, pointer):
    fields(pointer, {"schema_version", "scope", "generation", "receipt_sha256"})
    require(type(pointer["schema_version"]) is int and pointer["schema_version"] == 1
            and pointer["scope"] == "SYNTHETIC_ONLY"
            and type(pointer["generation"]) is str and GEN.fullmatch(pointer["generation"])
            and type(pointer["receipt_sha256"]) is str
            and archive.HEX64.fullmatch(pointer["receipt_sha256"]),
            "STAGE_POINTER_INVALID")
    folder = root / pointer["generation"]
    checked_directory(folder)
    with os.scandir(folder) as entries:
        seen = set()
        for entry in entries:
            require(entry.name in {"data", RECEIPT}, "STAGE_GENERATION_EXTRA")
            seen.add(entry.name)
    require(seen == {"data", RECEIPT}, "STAGE_GENERATION_MISSING")
    raw = read_small(folder / RECEIPT)
    require(digest(raw) == pointer["receipt_sha256"], "STAGE_RECEIPT_DIGEST")
    doc = strict_json(raw)
    fields(doc, {"schema_version", "scope", "generation", "archive"})
    require(type(doc["schema_version"]) is int and doc["schema_version"] == 1
            and doc["scope"] == "SYNTHETIC_ONLY"
            and doc["generation"] == pointer["generation"], "STAGE_RECEIPT_IDENTITY")
    scan_exact(folder / "data", fixture_members(doc["archive"]))
    return doc


def stage_fixture(root, source, expected, previous):
    """Publish a synthetic generation by compare-and-replace of one pointer.

    Expected archive identity is independently supplied by the fixture caller.
    Caller must exclusively own the fresh store. No production caller or
    implicit recovery. A failed generation is retained, not promoted.
    """
    root = Path(root)
    require(root.name == "c5-synthetic-store", "STAGE_FIXTURE_SCOPE")
    root_id = dir_id(root)
    # Copy expectation before any use; do not accept mutable caller drift.
    expected = strict_json(canonical(expected))
    members = fixture_members(expected)
    raw = archive.verified_candidate_snapshot(Path(source), expected)
    prior = None if previous is None else canonical(previous)
    lock = root / LOCK
    lock_id = None
    replace_attempted = False
    try:
        lock.mkdir(mode=0o700)
        lock_id = dir_id(lock)
        require(dir_id(root) == root_id, "STAGE_ROOT_CHANGED")
        require(pointer_bytes(root) == prior, "STAGE_STALE_POINTER")
        if previous is not None:
            verify_generation(root, strict_json(prior))
        name = "gen-" + uuid.uuid4().hex
        folder = root / name
        folder.mkdir(mode=0o700)
        folder_id = dir_id(folder)
        data = folder / "data"
        data.mkdir(mode=0o700)
        for rel in sorted(member_paths(members) - {""}, key=lambda x: (x.count("/"), x)):
            (data / rel).mkdir(mode=0o700)
        # All raw bytes validated by strict parser before any writes. Use
        # exact immutable snapshot, not a reopened source path or extractall.
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            require(sorted(z.namelist()) == sorted(members), "STAGE_PARSER_DISAGREEMENT")
            for member, row in sorted(members.items()):
                def chunks():
                    total = 0
                    with z.open(member, "r") as reader:
                        while True:
                            chunk = reader.read(archive.CHUNK)
                            if not chunk:
                                break
                            total += len(chunk)
                            require(total <= row["bytes"], "STAGE_MEMBER_SIZE")
                            yield chunk
                    require(total == row["bytes"], "STAGE_MEMBER_SIZE")
                write_new(data / member, chunks())
        directories = scan_exact(data, members)
        for path in sorted(directories, key=lambda x: -len(x.parts)):
            sync_dir(path)
        receipt = canonical({"schema_version": 1, "scope": "SYNTHETIC_ONLY",
                             "generation": name, "archive": expected})
        write_new(folder / RECEIPT, [receipt])  # receipt last in generation
        pointer = {"schema_version": 1, "scope": "SYNTHETIC_ONLY",
                   "generation": name, "receipt_sha256": digest(receipt)}
        verify_generation(root, pointer)
        sync_dir(folder)
        sync_dir(root)
        pending = root / ("pending-" + name + ".json")
        write_new(pending, [canonical(pointer)])
        require(read_small(pending) == canonical(pointer), "STAGE_POINTER_WRITE")
        require(dir_id(root) == root_id and dir_id(folder) == folder_id
                and dir_id(lock) == lock_id and pointer_bytes(root) == prior,
                "STAGE_PUBLICATION_CONFLICT")
        replace_attempted = True
        os.replace(pending, root / POINTER)
        sync_dir(root)
        require(pointer_bytes(root) == canonical(pointer), "STAGE_POINTER_CHANGED")
        return pointer
    except (OSError, Blocked, zipfile.BadZipFile, EOFError):
        raise Blocked("STAGE_PUBLICATION_UNCERTAIN" if replace_attempted
                      else "STAGE_BLOCKED_BEFORE_PUBLICATION") from None
    finally:
        if lock_id is not None:
            try:
                require(dir_id(root) == root_id and dir_id(lock) == lock_id,
                        "STAGE_LOCK_CHANGED")
                lock.rmdir()  # only own empty lock; never delete generations
            except (OSError, Blocked):
                raise Blocked("STAGE_PUBLICATION_UNCERTAIN" if replace_attempted
                              else "STAGE_LOCK_RECONCILIATION_REQUIRED") from None
