"""Read-only endpoint evidence for a separately approved owner Windows run."""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from datetime import datetime
from pathlib import Path

from .n12_trace import EvidenceValidationError, UTC, fingerprint, require, utc_time, windows_path

SCHEMA = "pilotodin-r06-prospective-v1"
ORIGINAL_APP_ID = "com.pilotodin.studio"


def check_tree_root(root: Path) -> None:
    require(root.is_absolute() and ".." not in root.parts, "expected an absolute original-data root")
    for directory in (root, *root.parents):
        info = directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and not (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ), "original-data root traverses a non-directory or reparse point")


def capture(root: Path) -> dict:
    started = datetime.now(UTC)
    check_tree_root(root)
    first = fingerprint(root)
    check_tree_root(root)
    second = fingerprint(root)
    check_tree_root(root)
    require(first["state"] == "directory" and first == second,
            "original-data fingerprint changed during the sequential scans")
    return {
        "schema": SCHEMA,
        "started_utc": started.isoformat(),
        "ended_utc": datetime.now(UTC).isoformat(),
        "root_id": first["root_id"],
        "digest": first["digest"],
    }


def load_capture(path: Path) -> dict:
    with path.open("rb") as stream:
        data = stream.read(4097)
    require(len(data) <= 4096, "endpoint evidence is too large")
    record = json.loads(data.decode("utf-8-sig"))
    require(isinstance(record, dict) and record.keys() == {
        "schema", "started_utc", "ended_utc", "root_id", "digest"
    } and record["schema"] == SCHEMA, "expected a prospective R06 endpoint capture")
    for key in ("root_id", "digest"):
        require(isinstance(record[key], str) and re.fullmatch(r"[0-9a-f]{64}", record[key]),
                "invalid endpoint fingerprint")
    for key in ("started_utc", "ended_utc"):
        require(isinstance(record[key], str), "invalid endpoint timestamp")
        record[key] = utc_time(record[key])
    require(record["started_utc"] <= record["ended_utc"], "endpoint clock order is invalid")
    return record


def compare(before_path: Path, after_path: Path) -> bool:
    before, after = load_capture(before_path), load_capture(after_path)
    require(before["root_id"] == after["root_id"], "endpoint roots differ")
    require(before["ended_utc"] < after["started_utc"], "endpoint captures overlap or are reversed")
    return before["digest"] == after["digest"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capture", help="print one timestamped fingerprint to stdout")
    comparison = commands.add_parser("compare", help="compare two endpoint captures")
    comparison.add_argument("before", type=Path)
    comparison.add_argument("after", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            require(os.name == "nt", "capture requires Windows")
            local = Path(os.environ["LOCALAPPDATA"])
            windows_path(str(local))
            print(json.dumps(capture(local / ORIGINAL_APP_ID), indent=2))
            return 0
        matches = compare(args.before, args.after)
    except EvidenceValidationError as exc:
        print(f"R06 BLOCKED: {exc}.", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, RecursionError) as exc:
        print(f"R06 BLOCKED: inaccessible or invalid evidence ({type(exc).__name__}).", file=sys.stderr)
        return 2
    print(json.dumps({
        "endpoint_status": "MATCH" if matches else "DIFFERENT",
        "continuous_trace": "NOT_EVALUATED",
    }))
    return 0 if matches else 1


if __name__ == "__main__":
    sys.exit(main())
