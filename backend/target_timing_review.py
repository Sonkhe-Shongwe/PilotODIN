"""Bounded, read-only P4 prediction-time and label-provenance review.

Column headers and user descriptions are *unverified clues*, not proof of
temporal availability, label validity, lawful use, or predictive usefulness.
This module never declares a target safe, approves changes, or runs ML.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import islice

MAX_SCANNED_HEADERS = 100
MAX_HEADER_FLAGS = 5
_WORD_SEPARATORS = re.compile(r"[^a-z0-9]+")
_AFTER_CUE = re.compile(
    r"\b(?:after|afterwards|following|post[- ](?:event|outcome|decision)|"
    r"once (?:the )?(?:case|event|decision|outcome) (?:is )?(?:closed|completed|known)|"
    r"at (?:case )?closure)\b", re.IGNORECASE
)
_LABEL_CUE = re.compile(
    r"\b(?:suspect(?:ed)?|alleged|unverified|reported|self[- ]reported|"
    r"estimated|proxy|flagged)\b", re.IGNORECASE
)
_UNCLEAR_SOURCE = re.compile(
    r"\b(?:unknown|unsure|not sure|not documented|not recorded|unavailable)\b",
    re.IGNORECASE,
)
_LATE_TOKENS = {
    "after", "post", "final", "settled", "resolved", "closed",
    "approved", "paid", "outcome", "label",
}
_DERIVED_TOKENS = {"predicted", "prediction", "probability", "score"}
_CHECKPOINT_QUESTIONS = (
    "Which predictors are genuinely available at the described prediction moment?",
    "Who recorded the label, and does it represent a verified outcome rather than a report or proxy?",
    "Could repeated entities, timestamps or post-outcome updates make validation misleading?",
)


def _normalized(value: str) -> str:
    return _WORD_SEPARATORS.sub("_", value.casefold()).strip("_")


def _header_reason(name: str) -> str | None:
    tokens = set(_normalized(name).split("_"))
    if tokens & _DERIVED_TOKENS or "target_encoded" in _normalized(name):
        return "Header resembles an existing prediction/derived score; verify lineage and availability."
    if tokens & _LATE_TOKENS:
        return "Header could describe a post-decision state; verify when this field was first known."
    return None


def review_prediction_context(
    columns: Iterable[str], target_column: str, user_context: dict | None
) -> dict:
    """Return conservative review cues only; no change to target eligibility."""
    sample = [str(name) for name in islice(columns, MAX_SCANNED_HEADERS + 1)]
    truncated_scan = len(sample) > MAX_SCANNED_HEADERS
    headers = sample[:MAX_SCANNED_HEADERS]
    header_flags = []
    seen = 0
    for name in headers:
        if name == target_column:
            continue
        reason = _header_reason(name)
        if reason:
            seen += 1
            if len(header_flags) < MAX_HEADER_FLAGS:
                header_flags.append({
                    "column": name,
                    "reason": reason,
                    "basis": "header_name_only",
                })
    context = user_context if isinstance(user_context, dict) else None
    prediction_moment = str((context or {}).get("prediction_moment") or "")[:500]
    label_source = str((context or {}).get("label_source") or "")[:500]
    timing_cue = (
        "possible_after_event_wording"
        if context and _AFTER_CUE.search(prediction_moment)
        else "not_determined"
    )
    label_cue = (
        "possibly_unconfirmed_or_proxy"
        if context and _LABEL_CUE.search(label_source)
        else "source_unclear"
        if context and _UNCLEAR_SOURCE.search(label_source)
        else "not_determined"
    )
    return {
        "status": "needs_human_review" if context else "context_missing",
        "verification": "unverified_user_text_and_header_clues",
        "timing_cue": timing_cue,
        "label_cue": label_cue,
        "header_flags": header_flags,
        "header_review_incomplete": seen > MAX_HEADER_FLAGS or truncated_scan,
        "questions": list(_CHECKPOINT_QUESTIONS),
        "note": (
            "Text and field names are not evidence that a predictor existed at decision time "
            "or that a label was independently confirmed. Absence of a warning is not clearance."
        ),
        "safe_to_train_automatically": False,
    }
