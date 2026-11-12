"""Validate manually captured P4 Gate C shadow-study records, without network or writes.

This checks schema and chronology, NOT independent timestamps, owner approval,
workflow authenticity, causal utility, or Gate C acceptance.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_CHANGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
_PRE_FIELDS = {
    "change_id", "recorded_at_utc", "branch", "base_sha", "patch_sha256",
    "changed_paths", "extra_preflight_recommended", "proposed_check", "rationale",
}
_POST_FIELDS = {
    "change_id", "push_at_utc", "workflow_run_id", "workflow", "run_started_at_utc",
    "run_conclusion", "failure_attribution", "attribution_evidence_url",
    "human_debug_minutes", "actual_preflight_minutes",
}
_CONCLUSIONS = {"success", "failure", "cancelled", "skipped", "queued", "unknown"}
_ATTRIBUTIONS = {
    "new_actionable", "pre_existing", "expected_test", "infrastructure",
    "unattributed", "not_applicable",
}


class ValidationError(ValueError):
    """A user-correctable structure or chronological evidence problem."""


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value
    ):
        raise ValidationError(f"{field}: require explicit UTC ISO 8601 ending in Z")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field}: invalid calendar date/time") from exc


def _keys(row: dict[str, Any], expected: set[str], label: str) -> None:
    missing = expected - row.keys()
    extra = row.keys() - expected
    if missing or extra:
        raise ValidationError(
            f"{label}: unexpected or missing keys (missing={sorted(missing)}, "
            f"unexpected={sorted(extra)})"
        )


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValidationError(f"{label}: nonempty unpadded string required")
    return value


def _minutes(value: Any, field: str) -> None:
    if value is not None and (type(value) not in (int, float) or not 0 <= value <= 10080):
        raise ValidationError(f"{field}: use null for unmeasured, or 0..10080 measured minutes")


def validate(pre: list[dict[str, Any]], post: list[dict[str, Any]]) -> dict[str, int]:
    """Validate manually supplied records. Does not mutate input or contact GitHub."""
    seen_pre: dict[str, datetime] = {}
    seen_patches: set[tuple[str, str, str]] = set()
    for row in pre:
        _keys(row, _PRE_FIELDS, "pre")
        cid = _nonempty(row["change_id"], "pre.change_id")
        if not _CHANGE.fullmatch(cid) or cid in seen_pre:
            raise ValidationError("pre.change_id: invalid or duplicate identifier")
        seen_pre[cid] = _utc(row["recorded_at_utc"], "pre.recorded_at_utc")
        _nonempty(row["branch"], "pre.branch")
        if not isinstance(row["base_sha"], str) or not _SHA40.fullmatch(row["base_sha"]):
            raise ValidationError("pre.base_sha: lowercase 40-character Git commit SHA required")
        if not isinstance(row["patch_sha256"], str) or not _SHA64.fullmatch(row["patch_sha256"]):
            raise ValidationError("pre.patch_sha256: lowercase 64-character digest required")
        patch_identity = (row["branch"], row["base_sha"], row["patch_sha256"])
        if patch_identity in seen_patches:
            raise ValidationError("pre: duplicate branch/base/patch identity under different change_id")
        seen_patches.add(patch_identity)
        paths = row["changed_paths"]
        if (not isinstance(paths, list) or not paths or len(paths) > 500 or
                any(not isinstance(x, str) or not x or x.startswith("/") or
                    ".." in Path(x).parts or "\\" in x for x in paths) or
                len(set(paths)) != len(paths)):
            raise ValidationError("pre.changed_paths: distinct safe repository-relative paths required")
        if type(row["extra_preflight_recommended"]) is not bool:
            raise ValidationError("pre.extra_preflight_recommended: boolean required")
        if row["extra_preflight_recommended"]:
            _nonempty(row["proposed_check"], "pre.proposed_check")
        elif row["proposed_check"] is not None:
            raise ValidationError("pre.proposed_check: must be null if not recommended")
        _nonempty(row["rationale"], "pre.rationale")

    # GitHub Actions run IDs identify a single execution globally, not per change.
    seen_runs: set[int] = set()
    push_times: dict[str, datetime] = {}
    censored = failures = completed = 0
    for row in post:
        _keys(row, _POST_FIELDS, "post")
        cid = row["change_id"]
        if not isinstance(cid, str) or cid not in seen_pre:
            raise ValidationError("post.change_id: missing pre-push record")
        pushed = _utc(row["push_at_utc"], "post.push_at_utc")
        if not seen_pre[cid] < pushed:
            raise ValidationError("post.push_at_utc: predecision must precede push")
        if cid in push_times and push_times[cid] != pushed:
            raise ValidationError("post.push_at_utc: one change must have one consistent push timestamp")
        push_times[cid] = pushed
        started = _utc(row["run_started_at_utc"], "post.run_started_at_utc") if row["run_started_at_utc"] is not None else None
        if started is not None and started < pushed:
            raise ValidationError("post.run_started_at_utc: cannot precede push")
        run_id = row["workflow_run_id"]
        if type(run_id) is not int or run_id <= 0 or run_id in seen_runs:
            raise ValidationError("post.workflow_run_id: positive and globally unique across changes")
        seen_runs.add(run_id)
        _nonempty(row["workflow"], "post.workflow")
        conclusion = row["run_conclusion"]
        attribution = row["failure_attribution"]
        if (not isinstance(conclusion, str) or conclusion not in _CONCLUSIONS or
                not isinstance(attribution, str) or attribution not in _ATTRIBUTIONS):
            raise ValidationError("post: unknown conclusion or attribution category")
        if conclusion in {"success", "failure"} and started is None:
            raise ValidationError("post: completed success/failure requires run start timestamp")
        if conclusion == "failure":
            failures += 1
            if attribution == "not_applicable":
                raise ValidationError("post: failed run requires explicit attribution (or unattributed)")
        elif attribution != "not_applicable":
            raise ValidationError("post: non-failure cannot be classified as a defect")
        if attribution not in {"unattributed", "not_applicable"}:
            evidence = _nonempty(row["attribution_evidence_url"], "post.attribution_evidence_url")
            if not evidence.startswith("https://github.com/Sonkhe-Shongwe/PilotODIN/"):
                raise ValidationError("post: attribution evidence must link to this repository")
        elif row["attribution_evidence_url"] is not None:
            _nonempty(row["attribution_evidence_url"], "post.attribution_evidence_url")
        for f in ("human_debug_minutes", "actual_preflight_minutes"):
            _minutes(row[f], f"post.{f}")
        if conclusion in {"cancelled", "skipped", "queued", "unknown"}:
            censored += 1
        else:
            completed += 1
    return {"pre_changes": len(pre), "post_runs": len(post),
            "completed_runs": completed, "failed_runs": failures, "censored_or_unresolved": censored}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as source:
        for lineno, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"{path.name}:{lineno}: malformed JSON") from exc
            if not isinstance(value, dict):
                raise ValidationError(f"{path.name}:{lineno}: object required")
            rows.append(value)
    return rows


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Validate local-only P4 Gate C shadow logs, never edit them")
    cli.add_argument("pre", type=Path, help="Manual pre-push JSONL file")
    cli.add_argument("post", type=Path, help="Manual post-CI JSONL file")
    args = cli.parse_args(argv)
    try:
        counts = validate(_read_jsonl(args.pre), _read_jsonl(args.post))
    except (OSError, ValidationError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    print("VALID STRUCTURE ONLY (not externally attested or Gate C approved): " + json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
