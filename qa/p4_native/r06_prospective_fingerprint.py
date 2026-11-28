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

from .n12_trace import (
    EvidenceValidationError, UTC, etw_capture_contract, etw_events, etw_payload_ticks,
    evidence_stage, fingerprint, require, utc_ticks, utc_time, windows_path,
)

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


def endpoint_pair(before_path: Path, after_path: Path) -> tuple[dict, dict]:
    before, after = load_capture(before_path), load_capture(after_path)
    require(before["root_id"] == after["root_id"], "endpoint roots differ")
    require(before["ended_utc"] < after["started_utc"], "endpoint captures overlap or are reversed")
    return before, after


def compare(before_path: Path, after_path: Path) -> bool:
    before, after = endpoint_pair(before_path, after_path)
    return before["digest"] == after["digest"]


def verify_etw_envelope(manifest_path: Path, events_path: Path, before: dict, after: dict) -> None:
    """Verify the supplied trace brackets both full scans and matches its manifest."""
    with evidence_stage("ETW envelope"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        start, end = before["started_utc"], after["ended_utc"]
        issues = set()
        etw_capture_contract(manifest, start, end, issues)
        require(not issues, "ETW reported event or buffer loss")
        capture = manifest["etw"]
        bounds = (etw_payload_ticks(capture["start_utc"]), etw_payload_ticks(capture["end_utc"]))
        # The native collector's UTC timestamps can have a seventh fractional digit.
        require(bounds[0] <= utc_ticks(start) < utc_ticks(end) <= bounds[1],
                "ETW capture does not bracket both endpoint scans")
        for _ in etw_events(events_path, bounds, capture["events_sha256"]):
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capture", help="print one timestamped fingerprint to stdout")
    comparison = commands.add_parser("compare", help="compare two endpoint captures")
    comparison.add_argument("before", type=Path)
    comparison.add_argument("after", type=Path)
    comparison.add_argument("--etw", nargs=2, metavar=("MANIFEST", "EVENTS"), type=Path,
                            help="also check the ETW capture envelope against both scans")
    args = parser.parse_args()
    try:
        if args.command == "capture":
            require(os.name == "nt", "capture requires Windows")
            local = Path(os.environ["LOCALAPPDATA"])
            windows_path(str(local))
            print(json.dumps(capture(local / ORIGINAL_APP_ID), indent=2))
            return 0
        before, after = endpoint_pair(args.before, args.after)
    except EvidenceValidationError as exc:
        print(f"R06 BLOCKED: {exc}.", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, RecursionError) as exc:
        print(f"R06 BLOCKED: inaccessible or invalid evidence ({type(exc).__name__}).", file=sys.stderr)
        return 2
    matches = before["digest"] == after["digest"]
    report = {
        "endpoint_status": "MATCH" if matches else "DIFFERENT",
        "continuous_trace": "NOT_EVALUATED",
    }
    if args.etw:
        try:
            verify_etw_envelope(*args.etw, before, after)
        except EvidenceValidationError as exc:
            report["etw_envelope_status"] = "BLOCKED"
            print(f"R06 BLOCKED: {exc}.", file=sys.stderr)
        except RecursionError:
            report["etw_envelope_status"] = "BLOCKED"
            print("R06 BLOCKED: ETW evidence nesting exceeds the parser limit.", file=sys.stderr)
        else:
            report["etw_envelope_status"] = "VERIFIED"
    print(json.dumps(report))
    if not matches:
        return 1
    return 2 if report.get("etw_envelope_status") == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())
