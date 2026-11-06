"""P4 read-only supervised target *opportunities*, not target authorisation.

Only descriptive aggregate evidence and explicit name hints may be used.
The user must confirm label meaning, prediction time, provenance and split
before training. Never fit a model or score target 'predictability' here.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

try:
    from . import engine, target_timing_review
except ImportError:  # Support direct-backend development launches.
    import engine
    import target_timing_review

MAX_SUGGESTIONS = 3
MAX_BLOCKED_EXAMPLES = 5
_NAME_NORMALIZE = re.compile(r"[^a-z0-9]+")

# Explanation phrases are questions, not proven domain facts or scores.
OUTCOME_HINTS = (
    (("fraud", "fraud_reported"), "Could a verified case outcome support an earlier review decision?"),
    (("churn", "attrition"), "Could this label support a retention decision before the event?"),
    (("default", "delinquent"), "Could an appropriately governed decision use a documented future default outcome?"),
    (("returned", "return_flag", "refund"), "Could this label support an operational returns decision?"),
    (("resolved", "resolution", "closed"), "Could this outcome help prioritise timely case resolution?"),
    (("failed", "failure", "defect"), "Could a verified event outcome support earlier preventive action?"),
    (("outcome", "result", "label", "target"), "What decision could be improved by predicting this documented outcome?"),
    (("sales", "revenue", "profit"), "Could a well-defined future value improve a commercial planning decision?"),
    (("price", "cost", "amount", "expense"), "Is there a valid future amount to estimate before it becomes known?"),
    (("status", "reported", "risk"), "Does this status represent an outcome observed after the intended decision time?"),
)

# Candidate generation is intentionally narrower than field-role inference:
# identifiers, timestamps and arbitrary numbers must NOT be recommended.
IDENTIFIER_TOKENS = {
    "id", "uuid", "guid", "identifier", "serial", "sku", "postcode",
    "postal", "zip", "account_number", "claim_number", "policy_number",
}
IDENTIFIER_ENDINGS = ("_id", "_uuid", "_key", "_code", "_number")
# A duration such as time_to_resolution is not necessarily a timestamp.
TIME_TOKENS = {"date", "datetime", "timestamp", "created_at", "updated_at"}
SENSITIVE_TERMS = {
    "gender", "sex", "race", "ethnicity", "religion", "disability",
    "nationality", "pregnancy", "age", "postcode", "postal", "salary_id",
}
LEAKAGE_TERMS = ("post_outcome", "outcome_after", "final_result", "target_encoded", "approved_after")


def _normalized(name: str) -> str:
    return _NAME_NORMALIZE.sub("_", name.casefold()).strip("_")


def _match_outcome(name: str) -> str | None:
    normalized = _normalized(name)
    tokens = normalized.split("_")
    for phrases, question in OUTCOME_HINTS:
        if any(
            normalized == phrase or phrase in tokens or
            (phrase in normalized.split("_") if "_" not in phrase else phrase in normalized)
            for phrase in phrases
        ):
            return question
    return None


def _is_identifier(name: str) -> bool:
    normalized = _normalized(name)
    return normalized in IDENTIFIER_TOKENS or normalized.endswith(IDENTIFIER_ENDINGS)


def _is_date(name: str, series: pd.Series) -> bool:
    tokens = set(_normalized(name).split("_"))
    return bool(tokens & TIME_TOKENS) or pd.api.types.is_datetime64_any_dtype(series)


def _candidate(frame: pd.DataFrame, name: str, question: str, version: int) -> dict:
    series = frame[name]
    rows = len(series)
    labelled = int(series.notna().sum())
    missing = rows-labelled
    distinct = int(series.nunique(dropna=True))
    evidence = [
        f"{labelled:,} non-missing labels out of {rows:,} records",
        f"{distinct:,} distinct non-missing label values",
    ]
    blockers: list[str] = []
    risks: list[str] = []
    task: str | None = None
    min_class: int | None = None
    normalized = _normalized(name)
    if normalized.startswith(("predicted_", "prediction_")) or normalized.endswith(
        ("_score", "_probability", "_prediction")
    ) or "target_encoded" in normalized:
        blockers.append(
            "This looks like a prediction, score, probability or target-derived feature, not a verified ground-truth outcome."
        )
    if _is_identifier(name):
        blockers.append("The header resembles a record identifier, not an outcome.")
    if _is_date(name, series):
        blockers.append("A date/time column is not a supported supervised target for this MVP.")
    if labelled < 30:
        blockers.append("Local modelling requires at least 30 labelled rows.")
    if distinct < 2:
        blockers.append("The target has fewer than two observed labels.")
    if distinct >= max(10, int(labelled*.98)) and not pd.api.types.is_numeric_dtype(series):
        blockers.append("High-cardinality text is likely a record key or free text rather than a supported label.")
    if not blockers:
        try:
            task = engine.infer_task(series)
        except ValueError as exc:
            blockers.append(str(exc))
    if task == "classification":
        counts = series.value_counts(dropna=True)
        min_class = int(counts.min()) if not counts.empty else 0
        evidence.append(f"Smallest observed class: {min_class:,} rows")
        if min_class < 6:
            blockers.append("Each classification class requires at least 6 labelled rows.")
    if task == "regression":
        try:
            values = pd.to_numeric(series.dropna(), errors="coerce")
            if not np.isfinite(values.to_numpy(dtype=float)).all():
                blockers.append("Regression labels must be finite numeric values.")
        except (ValueError, TypeError, OverflowError):
            blockers.append("Regression labels could not be validated as finite numeric values.")
    predictors = [c for c in frame.columns if c != name and
                  frame[c].notna().any() and frame[c].nunique(dropna=True) > 1]
    if not predictors:
        blockers.append("No non-constant, non-empty candidate predictor remains.")
    if labelled > engine.MAX_ML_LABELLED_ROWS:
        blockers.append(
            f"{labelled:,} labelled rows exceed the current {engine.MAX_ML_LABELLED_ROWS:,}-row local ML cap."
        )
    if any(x in normalized for x in LEAKAGE_TERMS):
        risks.append("Header indicates possible post-outcome leakage or a derived label.")
    if any(x in normalized.split("_") for x in SENSITIVE_TERMS):
        risks.append("A potentially sensitive label requires additional governance review.")
    if "fraud" in normalized:
        risks.append("A reported or suspected fraud flag is not proof of confirmed fraud.")
    if missing:
        risks.append("Labels are missing for some rows; investigate selection and labelling bias.")
    risks.extend([
        "Confirm the business decision, label origin and exact prediction moment before proceeding.",
        "Verify that predictors exist before the outcome and choose group/time validation if records depend on each other.",
    ])
    return {
        "column": name,
        "quality_version": version,
        "task_hypothesis": task if not blockers else None,
        "technical_status": "reviewable" if not blockers else "blocked",
        "business_relevance": "unverified",
        "possible_decision_question": question,
        "labelled_rows": labelled,
        "missing_labels": missing,
        "distinct_labels": distinct,
        "smallest_class": min_class,
        "observed_evidence": evidence,
        "blockers": blockers,
        "review_warnings": risks,
        "safe_to_train_automatically": False,
    }


def _assessment_axes(candidate: dict) -> dict:
    """Two independent evidence states, never numeric success or business-value scores."""
    has_description = candidate.get("user_context") is not None
    technical_state = (
        "structurally_reviewable" if candidate["technical_status"] == "reviewable"
        else "structurally_blocked"
    )
    return {
        "technical": {
            "state": technical_state,
            "basis": "observed_aggregates_and_structural_screening",
            "labelled_rows": candidate["labelled_rows"],
            "distinct_labels": candidate["distinct_labels"],
            "smallest_class": candidate["smallest_class"],
            "limitations": (
                "Structural screening does not verify when predictors existed, "
                "leakage-free validation, or achievable model performance."
            ),
        },
        "decision": {
            "state": "user_described_unverified" if has_description else "undocumented",
            "basis": "user_description_only" if has_description else "no_user_description",
            "limitations": (
                "Decision usefulness, ethical or legal suitability, and label truth "
                "have not been independently verified."
            ),
        },
        "review_required": True,
        "safe_to_train_automatically": False,
    }


def recommend(frame: pd.DataFrame, version: int, user_contexts: dict | None = None) -> dict:
    if not frame.columns.is_unique:
        raise ValueError("Target recommendations require unique column names")
    user_contexts = user_contexts or {}
    suggestions = []
    blocked = []
    for col in frame.columns:
        name = str(col)
        question = _match_outcome(name)
        if question is None:
            continue
        candidate = _candidate(frame, name, question, version)
        if name in user_contexts:
            # User statements provide described decision context; never
            # assert their truth, legal basis, leakage safety or readiness.
            candidate["user_context"] = {
                **user_contexts[name],
                "verification_state": "user_described_not_independently_verified",
            }
            candidate["business_relevance"] = "user_described_unverified"
        else:
            candidate["user_context"] = None
        # Read-only review cues, not a technical eligibility override or approval.
        candidate["risk_review"] = target_timing_review.review_prediction_context(
            frame.columns, name, candidate["user_context"]
        )
        candidate["assessment_axes"] = _assessment_axes(candidate)
        (suggestions if candidate["technical_status"] == "reviewable" else blocked).append(candidate)
    # Observed labelled support is a deterministic ordering aid, not a
    # validation score or a claim of decision value/predictive performance.
    suggestions.sort(key=lambda item: (
        0 if item["user_context"] is not None else 1,
        -item["labelled_rows"],
        item["column"].casefold(),
    ))
    blocked.sort(key=lambda item: item["column"].casefold())
    top = suggestions[:MAX_SUGGESTIONS]
    return {
        "version": version,
        "ranking_basis": "Structural eligibility first; user-described contexts appear first, then observed label support. User text is unverified and not a business-value score. No model trained.",
        "suggestions": top,
        "blocked_examples": blocked[:MAX_BLOCKED_EXAMPLES],
        "eligible_count": len(suggestions),
        "blocked_count": len(blocked),
        "abstained": not bool(top),
        "abstention_reason": (
            "No named outcome with sufficient technically supported labels was found. "
            "Use descriptive analysis or define and verify a real business target yourself."
            if not top else None
        ),
        "business_context_state": "user_described_unverified" if any(item["user_context"] for item in top) else "unverified",
        "note": (
            "A saved user description is not independently verified and cannot override technical blockers. "
            "Suggestions are unverified hypotheses, not approved labels or training recommendations. "
            "Explicit user target selection and all existing backend training/validation gates remain required."
        ),
        "privacy": "Read-only aggregate counts and column names only; no raw label values or rows returned.",
    }
