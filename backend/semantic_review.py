"""P3-03 Option A: explicit owner attestations of *unverified* field hypotheses.

Never infer truth, alter a dataset, select a target or initiate AI work.
The hash binds consent to the exact currently displayed role/basis/reason.
"""
from __future__ import annotations

from hashlib import sha256
import json

DECISIONS = ("acceptable", "needs_correction", "cannot_assess")


def fingerprint(column: str, hypothesis: dict) -> str:
    fields = {
        "column": column,
        "role": hypothesis["role"],
        "basis": hypothesis["basis"],
        "reason": hypothesis["reason"],
    }
    return sha256(json.dumps(fields, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")).hexdigest()


def candidates(frame, version: int) -> list[dict]:
    try:
        from . import semantic_profile
    except ImportError:
        import semantic_profile
    result = []
    for field in semantic_profile.overview(frame, version)["fields"]:
        for hypothesis in field["hypotheses"]:
            result.append({
                "column": field["column"],
                "role": hypothesis["role"],
                "basis": hypothesis["basis"],
                "reason": hypothesis["reason"],
                "hypothesis_hash": fingerprint(field["column"], hypothesis),
            })
    return result


def selected_candidate(items: list[dict], column: str, role: str,
                       digest: str) -> dict | None:
    for item in items:
        if item["column"] == column and item["role"] == role and item["hypothesis_hash"] == digest:
            return item
    return None
