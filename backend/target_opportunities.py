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
MAX_OTHER_REVIEWABLE = 12
MAX_BLOCKED_EXAMPLES = 5
# P4-14 whole queue budget, independent of loading the approved Quality data.
MAX_QUEUE_ROWS = 5000
MAX_QUEUE_HEADERS = 100
MAX_QUEUE_PREDICTORS = 64
MAX_QUEUE_NAMED_CANDIDATES = 64
MAX_QUEUE_PARTIAL_EXAMPLES = 5
# Bounded read-only scan; never disclose identifier values or claim group identity.
MAX_ENTITY_HEADERS = 100
MAX_ENTITY_COLUMNS = 8
MAX_ENTITY_ROWS = 30000
MAX_ENTITY_FLAGS = 5
# P4-13 single-column inspection budget: sampling is never full approval.
# 5000 x 33 cells bounds the candidate predictor sweep, excluding the
# previously loaded DataFrame and the separate capped name/identifier reviews.
MAX_MANUAL_INSPECT_ROWS = 5000
MAX_MANUAL_INSPECT_PREDICTORS = 32
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
    normalized = _normalized(name)
    tokens = set(normalized.split("_"))
    # Multiword event-time suffixes (created_at, updated_at, etc.) are split
    # into separate tokens and previously escaped TIME_TOKENS. Treat *_at
    # names conservatively as timestamp-like, even when CSV dates are strings.
    return (
        bool(tokens & TIME_TOKENS)
        or normalized.endswith("_at")
        # Categorical datetime values must be temporal too: pandas reports
        # is_datetime64_any_dtype(series) == False for a categorical wrapper.
        # Inspect only the underlying value dtype; do not change source data.
        or pd.api.types.is_datetime64_any_dtype(_value_dtype(series))
    )


def _value_dtype(series: pd.Series):
    """Inspect a categorical column's observed value dtype, not its wrapper.

    pandas' is_numeric_dtype(series) is False for categorical numeric values,
    which must still pass the same nonfinite checks as plain numeric columns.
    This is read-only: category definitions and source values remain intact.
    """
    if isinstance(series.dtype, pd.CategoricalDtype):
        return series.cat.categories.dtype
    return series.dtype


def _candidate(frame: pd.DataFrame, name: str, question: str, version: int) -> dict:
    series = frame[name]
    target_value_dtype = _value_dtype(series)
    # Empty or whitespace-only strings are not observed outcome labels.
    # Inspect a local view; never modify the original Quality snapshot.
    blank_text = series.map(lambda value: isinstance(value, str) and not value.strip())
    # "Y" and "Y " are not reliable distinct outcome classes. Do not
    # silently trim a real label; exclude padded strings from this temporary
    # screen and require an explicit Quality correction before target review.
    padded_text = series.map(
        lambda value: isinstance(value, str)
        and bool(value.strip()) and value != value.strip()
    )
    labels = series.mask(blank_text | padded_text)
    rows = len(series)
    labelled = int(labels.notna().sum())
    missing = rows-labelled
    distinct = int(labels.nunique(dropna=True))
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
    if bool(blank_text.any()):
        blockers.append(
            "Blank or whitespace-only target labels must be cleaned in Quality "
            "before this column can be reviewed as a supervised outcome."
        )
    if bool(padded_text.any()):
        blockers.append(
            "Leading or trailing whitespace in target labels must be corrected "
            "in Quality before this column can be reviewed as a supervised outcome."
        )
    if _is_date(name, series):
        blockers.append("A date/time column is not a supported supervised target for this MVP.")
    if labelled < 30:
        blockers.append("Local modelling requires at least 30 labelled rows.")
    if distinct < 2:
        blockers.append("The target has fewer than two observed labels.")
    # Numeric infinity values are non-missing in pandas and can otherwise
    # masquerade as two well-supported classification classes. Fail closed
    # BEFORE infer_task() handles the two-distinct-values shortcut.
    if pd.api.types.is_complex_dtype(target_value_dtype):
        blockers.append("Complex-valued target labels are not supported.")
    elif pd.api.types.is_numeric_dtype(target_value_dtype) and labelled:
        try:
            finite_values = labels.dropna().to_numpy(dtype=float)
            if not np.isfinite(finite_values).all():
                blockers.append("Numeric target labels must be finite; infinity is not a valid observed outcome.")
        except (TypeError, ValueError, OverflowError):
            blockers.append("Numeric target labels could not be verified as finite values.")
    if distinct >= max(10, int(labelled*.98)) and not pd.api.types.is_numeric_dtype(target_value_dtype):
        blockers.append("High-cardinality text is likely a record key or free text rather than a supported label.")
    if not blockers:
        try:
            task = engine.infer_task(labels)
        except ValueError as exc:
            blockers.append(str(exc))
    if task == "classification":
        counts = labels.value_counts(dropna=True)
        min_class = int(counts.min()) if not counts.empty else 0
        evidence.append(f"Smallest observed class: {min_class:,} rows")
        if min_class < 6:
            blockers.append("Each classification class requires at least 6 labelled rows.")
    if task == "regression":
        try:
            values = pd.to_numeric(labels.dropna(), errors="coerce")
            if not np.isfinite(values.to_numpy(dtype=float)).all():
                blockers.append("Regression labels must be finite numeric values.")
        except (ValueError, TypeError, OverflowError):
            blockers.append("Regression labels could not be validated as finite numeric values.")
    # A predictor varying only on rows WITHOUT a known label cannot supply
    # supervised learning evidence. Screen the labelled records, not the
    # entire dataset; this is still only structural, never leakage approval.
    # Empty and whitespace-only text also cannot provide real variation.
    # Build a local masked view, never changing the approved Quality frame.
    labelled_frame = frame.loc[labels.notna()]

    def has_observed_variation(column: str) -> bool:
        values = labelled_frame[column]
        if pd.api.types.is_numeric_dtype(_value_dtype(values)):
            # Infinity is not usable predictor variation. A nonfinite-only
            # column, or one finite value plus infinity, must not make a
            # target look structurally reviewable. Do not alter Quality data.
            finite_or_missing = values.map(
                lambda value: pd.isna(value) or bool(np.isfinite(value))
            )
            values = values.where(finite_or_missing)
        elif pd.api.types.is_object_dtype(values) or pd.api.types.is_string_dtype(values):
            # Spelling differences caused only by leading/trailing whitespace
            # are not reliable predictor variation. Mask locally rather than
            # normalising or editing an approved dataset version.
            blank_or_padded_text = values.map(
                lambda value: isinstance(value, str)
                and (not value.strip() or value != value.strip())
            )
            values = values.mask(blank_or_padded_text)
        return values.nunique(dropna=True) > 1

    # Identifier-like headers may be unique per record but are not reliable
    # standalone predictive inputs. Exclude them from the minimum usable
    # predictor evidence, while retaining the full read-only source frame.
    predictors = [c for c in frame.columns
                  if c != name and not _is_identifier(str(c))
                  and has_observed_variation(c)]
    if not predictors:
        # Keep the stable diagnostic for the bounded manual-review path,
        # which rewrites it to avoid claiming completeness after truncation.
        blockers.append("No non-constant, non-empty candidate predictor remains.")
        if any(_is_identifier(str(c)) for c in frame.columns if c != name):
            blockers.append(
                "Predictor evidence was evaluated after excluding identifier-like headers."
            )
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


def _repeated_identifier_evidence(frame: pd.DataFrame) -> dict:
    """Observe repeated identifier-like *values*, not verified entity identity.

    A bounded leading-row scan reports aggregate duplicate occurrences only.
    Not finding repeats is never evidence that a random split is valid.
    """
    columns = list(frame.columns)
    names = [name for name in columns[:MAX_ENTITY_HEADERS]
             if _is_identifier(str(name))]
    sample = frame.iloc[:MAX_ENTITY_ROWS]
    repeated = []
    for name in names[:MAX_ENTITY_COLUMNS]:
        present = sample[name].dropna()
        distinct = int(present.nunique(dropna=True))
        extra = int(len(present) - distinct)
        if extra > 0 and len(repeated) < MAX_ENTITY_FLAGS:
            repeated.append({
                "column": str(name),
                "nonmissing_observations": int(len(present)),
                "distinct_observed_values": distinct,
                "additional_occurrences": extra,
            })
    return {
        "rows_examined": int(len(sample)),
        "total_rows": int(len(frame)),
        "identifier_headers_examined": min(len(names), MAX_ENTITY_COLUMNS),
        "scan_truncated": (
            len(frame) > MAX_ENTITY_ROWS or
            len(columns) > MAX_ENTITY_HEADERS or
            len(names) > MAX_ENTITY_COLUMNS or
            len(repeated) >= MAX_ENTITY_FLAGS
        ),
        "repeated": repeated,
        "basis": "bounded_observed_values_in_identifier_like_headers",
        "interpretation": (
            "Repeated values may indicate dependent records. Column names do "
            "not prove entity identity, and absence of repeats does not "
            "verify random-split independence."
        ),
    }


def _decision_utility_review(candidate: dict, entity_evidence: dict) -> dict:
    """Separate observed record structure from unverified operational value."""
    described = candidate["user_context"] is not None
    return {
        "state": "independent_evidence_required",
        "action_state": "owner_described_unverified" if described else "undocumented",
        "baseline_comparison_state": "not_established",
        "verified_label_origin": False,
        "verified_prediction_time": False,
        "verified_group_independence": False,
        "measured_decision_benefit": False,
        "entity_repetition": entity_evidence,
        "next_questions": [
            "Who acts on this prediction, and what alternative action is available?",
            "Compared with the existing non-model process, what measured benefit "
            "and costs would justify the intervention?",
            "Who independently verifies the outcome label, and when is it recorded?",
            "Which predictors exist at the real decision moment?",
            "Do repeated entities or time order require grouped or temporal validation?",
        ],
        "training_authorised": False,
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



def _review_priority(candidate: dict, position: int, total: int) -> dict:
    """Explain an investigation queue, never assign target value or safety.

    A description documents a question, not verified outcome provenance.
    Label counts are observations, never modelling success estimates.
    """
    described = candidate["user_context"] is not None
    risk = candidate["risk_review"]
    review_steps = [
        {
            "topic": "decision",
            "state": "described_unverified" if described else "not_documented",
            "action": (
                "Verify the proposed decision and outcome definition against an operational source."
                if described else
                "Describe the exact outcome and decision this prediction would support."
            ),
        },
        {
            "topic": "label_provenance",
            "state": "not_independently_verified",
            "action": "Confirm who recorded the label and whether it is a trustworthy outcome.",
        },
        {
            "topic": "prediction_time",
            "state": "not_independently_verified",
            "action": "Verify the prediction moment and which input fields existed before it.",
        },
        {
            "topic": "validation",
            "state": "not_independently_verified",
            "action": "Check group/time dependence, leakage and a defensible holdout before training.",
        },
    ]
    if candidate["missing_labels"]:
        review_steps.append({
            "topic": "missing_labels",
            "state": "observed_missing_labels",
            "action": "Investigate missing-label selection bias before choosing this target.",
        })
    if (
        risk["timing_cue"] != "not_determined"
        or risk["label_cue"] != "not_determined"
        or risk["header_flags"]
        or risk["header_review_incomplete"]
    ):
        review_steps.append({
            "topic": "possible_leakage_or_provenance",
            "state": "unverified_lexical_clues",
            "action": "Investigate the timing, source or header clues shown in the risk review.",
        })
    return {
        "position": position,
        "total_reviewable": total,
        "group": "described_question_first" if described else "decision_not_described",
        "ordering_reason": (
            "The owner has documented a proposed decision; this is NOT verified business value."
            if described else
            "No proposed decision is recorded; this is NOT evidence of lower business value."
        ),
        "label_support_reason": (
            f"{candidate['labelled_rows']:,} non-missing labels are observed; "
            "support counts are NOT a predictive-success estimate."
        ),
        "required_checks": review_steps,
        "business_value": "not_established",
        "target_safety": "not_established",
        "training_authorised": False,
    }


def recommend(frame: pd.DataFrame, version: int, user_contexts: dict | None = None) -> dict:
    if not frame.columns.is_unique:
        raise ValueError("Target recommendations require unique column names")
    user_contexts = user_contexts or {}
    total_rows, total_headers = frame.shape
    examined_rows = min(total_rows, MAX_QUEUE_ROWS)
    scanned_headers = list(frame.columns[:MAX_QUEUE_HEADERS])
    named_headers = [(str(col), _match_outcome(str(col))) for col in scanned_headers]
    named_headers = [(name, question) for name, question in named_headers if question]
    reasons = []
    if total_rows > examined_rows:
        reasons.append("rows")
    if total_headers > len(scanned_headers):
        reasons.append("headers")
    if total_headers - 1 > MAX_QUEUE_PREDICTORS:
        reasons.append("predictors")
    if len(named_headers) > MAX_QUEUE_NAMED_CANDIDATES:
        reasons.append("candidate_columns")
    incomplete = bool(reasons)
    # Do not rank a partially examined queue. Only the first five named
    # headers get sampled blocker details, not a training-ready status.
    candidates_to_screen = (
        named_headers[:MAX_QUEUE_PARTIAL_EXAMPLES] if incomplete else named_headers
    )
    preview = frame.iloc[:examined_rows, :len(scanned_headers)] if incomplete else frame
    entity_evidence = _repeated_identifier_evidence(preview)
    if incomplete:
        entity_evidence["total_rows"] = total_rows
        entity_evidence["scan_truncated"] = True
        entity_evidence["interpretation"] += (
            " The queue-level preview is incomplete. Absence of repeated "
            "values does not establish independent records."
        )
    resource_review = {
        "scope": "bounded_read_only_queue_screening",
        "rows_examined": examined_rows,
        "total_rows": total_rows,
        "headers_examined": len(scanned_headers),
        "total_headers": total_headers,
        "max_rows": MAX_QUEUE_ROWS,
        "max_headers": MAX_QUEUE_HEADERS,
        "max_candidate_columns": MAX_QUEUE_NAMED_CANDIDATES,
        "max_predictors_per_candidate": MAX_QUEUE_PREDICTORS,
        "named_outcome_headers_seen": len(named_headers),
        "candidate_columns_examined": len(candidates_to_screen),
        "truncated": incomplete,
        "incomplete_reasons": reasons,
        "interpretation": (
            "This incomplete queue scan cannot recommend any target. "
            "Unexamined rows, headers or predictors may change the assessment. "
            "The existing manual chooser has separate bounded inspection."
            if incomplete else
            "All rows and headers were examined for structural screening only. "
            "Prediction utility and suitability are not independently verified."
        ),
    }
    suggestions = []
    blocked = []
    for name, question in candidates_to_screen:
        if incomplete:
            predictor_positions = []
            for index, col in enumerate(scanned_headers):
                if col == name:
                    continue
                predictor_positions.append(index)
                if len(predictor_positions) >= MAX_QUEUE_PREDICTORS:
                    break
            target_index = frame.columns.get_loc(name)
            bounded_indices = sorted([*predictor_positions, target_index])
            screen = frame.iloc[:examined_rows, bounded_indices]
        else:
            screen = frame
        candidate = _candidate(screen, name, question, version)
        if incomplete:
            candidate["blockers"].insert(
                0, "Main target review queue scan was truncated by row, "
                "header, candidate or predictor limits; full eligibility "
                "cannot be established from these partial observations."
            )
            if total_rows > engine.MAX_ML_LABELLED_ROWS:
                candidate["blockers"].append(
                    "The source has more rows than the local ML cap of "
                    f"{engine.MAX_ML_LABELLED_ROWS:,} labelled rows; a full "
                    "label count is required before eligibility can be assessed."
                )
            candidate["technical_status"] = "blocked"
            candidate["task_hypothesis"] = None
            candidate["review_warnings"].insert(
                0, "Label and predictor counts are sample-only; incomplete "
                "screening is not independent validation."
            )
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
        candidate["decision_utility"] = _decision_utility_review(
            candidate, entity_evidence
        )
        (suggestions if candidate["technical_status"] == "reviewable" else blocked).append(candidate)
    # Observed labelled support is a deterministic ordering aid, not a
    # validation score or a claim of decision value/predictive performance.
    suggestions.sort(key=lambda item: (
        0 if item["user_context"] is not None else 1,
        -item["labelled_rows"],
        item["column"].casefold(),
    ))
    blocked.sort(key=lambda item: item["column"].casefold())
    # Rank for HUMAN INVESTIGATION only. This is not a calibrated estimate of
    # usefulness, performance or permission to train; never hide alternative
    # eligible targets just because they fell below the three-card shortlist.
    for position, candidate in enumerate(suggestions, start=1):
        candidate["review_priority"] = _review_priority(
            candidate, position, len(suggestions)
        )
    top = suggestions[:MAX_SUGGESTIONS]
    other = suggestions[MAX_SUGGESTIONS:MAX_SUGGESTIONS + MAX_OTHER_REVIEWABLE]
    return {
        "version": version,
        "queue_resource_review": resource_review,
        "ranking_basis": "Structural eligibility first; user-described contexts appear first, then observed label support. User text is unverified and not a business-value score. No model trained.",
        "ranking_contract": {
            "purpose": "human_review_queue_not_business_value_ranking",
            "ordered_by": [
                "whether_owner_described_decision",
                "observed_nonmissing_label_count",
                "deterministic_column_name",
            ],
            "business_value_verified": False,
            "model_performance_measured": False,
            "automatic_target_selection": False,
        },
        "suggestions": top,
        "other_reviewable": other,
        "omitted_reviewable_count": max(
            0, len(suggestions) - MAX_SUGGESTIONS - MAX_OTHER_REVIEWABLE
        ),
        "blocked_examples": blocked[:MAX_BLOCKED_EXAMPLES],
        "eligible_count": len(suggestions),
        "blocked_count": len(blocked),
        "abstained": not bool(top),
        "abstention_reason": (
            "Incomplete target screening: the bounded queue reached its row, "
            "header, predictor or candidate limit. No target is recommended "
            "from partial evidence. The manual target chooser remains available."
            if incomplete else
            "No named outcome with sufficient technically supported labels was found. "
            "Use descriptive analysis or define and verify a real business target yourself."
            if not top else None
        ),
        "business_context_state": "user_described_unverified" if any(item["user_context"] for item in top) else "unverified",
        "note": (
            "For incomplete screening, blocker counts reflect only the "
            "inspected subset and are not the total number of blocked outcomes. "
            "A saved user description is not independently verified and cannot override technical blockers. "
            "Suggestions are unverified hypotheses, not approved labels or training recommendations. "
            "Explicit user target selection and all existing backend training/validation gates remain required."
        ),
        "privacy": "Read-only aggregate counts and column names only; no raw label values or rows returned.",
    }



def inspect_manual_target(
    frame: pd.DataFrame, version: int, column: str,
    user_contexts: dict | None = None,
) -> dict:
    """Review one explicit manual choice without changing capped queue policy.

    This is a read-only aggregate screen. Neither a header hint nor user
    description verifies label meaning, value, lawful use or training consent.
    """
    if not frame.columns.is_unique:
        raise ValueError("Target inspection requires unique column names")
    if column not in frame.columns:
        raise ValueError("Selected target column is not in the working dataset version")
    question = _match_outcome(column)
    named = question is not None
    # Select at most one target and the first 32 other predictors, regardless
    # of whether the target header is far beyond the first 100 columns.
    # Never scan every predictor's values to decide whether to sample.
    predictor_positions = []
    for index, name in enumerate(frame.columns):
        if name == column:
            continue
        predictor_positions.append(index)
        if len(predictor_positions) == MAX_MANUAL_INSPECT_PREDICTORS:
            break
    inspected_positions = sorted([
        *predictor_positions, frame.columns.get_loc(column)
    ])
    inspected_rows = min(len(frame), MAX_MANUAL_INSPECT_ROWS)
    bounded = frame.iloc[:inspected_rows, inspected_positions]
    truncated = (
        len(frame) > inspected_rows or
        len(frame.columns) - 1 > len(predictor_positions)
    )
    resource_review = {
        "scope": "bounded_single_column_structural_observations",
        "rows_examined": inspected_rows,
        "total_rows": len(frame),
        "columns_examined": len(inspected_positions),
        "total_columns": len(frame.columns),
        "predictor_columns_examined": len(predictor_positions),
        "total_predictor_columns": len(frame.columns) - 1,
        "row_limit": MAX_MANUAL_INSPECT_ROWS,
        "predictor_column_limit": MAX_MANUAL_INSPECT_PREDICTORS,
        "truncated": truncated,
        "interpretation": (
            "Observed label and predictor counts describe only the scanned subset. "
            "Unexamined rows or columns could change the assessment; a limited "
            "scan is structurally blocked pending independent full review."
            if truncated else
            "All rows and columns were scanned for this P4 structural review. "
            "This does not prove operational suitability or training permission."
        ),
    }
    candidate = _candidate(
        bounded, column, question or
        "No supported outcome-name clue; confirm the intended decision.", version
    )
    if truncated:
        candidate["blockers"].insert(
            0, "Single-column structural inspection was truncated by its "
            "row or predictor-column budget; full eligibility is unknown."
        )
        candidate["blockers"] = [
            message.replace(
                "No non-constant, non-empty candidate predictor remains.",
                "No usable predictor was observed in the bounded sample; "
                "unexamined rows or columns may contain a valid predictor."
            ) for message in candidate["blockers"]
        ]
        candidate["technical_status"] = "blocked"
        candidate["task_hypothesis"] = None
        candidate["review_warnings"].insert(
            0, "Partial observations are not a whole-dataset label count or "
            "a verified structural clearance."
        )
    if not named:
        candidate["blockers"].insert(
            0, "No supported outcome-name clue was identified; manual choice is "
            "not a reviewed or verified prediction objective."
        )
        candidate["technical_status"] = "blocked"
        candidate["task_hypothesis"] = None
    description = (user_contexts or {}).get(column)
    if description is not None:
        candidate["user_context"] = {
            **description,
            "verification_state": "user_described_not_independently_verified",
        }
        candidate["business_relevance"] = "user_described_unverified"
    else:
        candidate["user_context"] = None
    candidate["risk_review"] = target_timing_review.review_prediction_context(
        frame.columns, column, candidate["user_context"]
    )
    candidate["assessment_axes"] = _assessment_axes(candidate)
    entity_evidence = _repeated_identifier_evidence(bounded)
    if truncated:
        entity_evidence["total_rows"] = len(frame)
        entity_evidence["scan_truncated"] = True
        entity_evidence["interpretation"] += (
            " Manual inspection also limited row or column coverage; missing "
            "flags do not demonstrate independent records."
        )
    candidate["decision_utility"] = _decision_utility_review(
        candidate, entity_evidence
    )
    return {
        "version": version,
        "column": column,
        "resource_review": resource_review,
        "inspection_scope": "single_manual_column_not_ranked_or_approved",
        "name_hint": "supported_outcome_name" if named else "no_supported_outcome_name",
        "candidate": candidate,
        "training_authorised": False,
        "note": "Observed aggregates are not independently validated outcomes, "
                "training consent or proof of business value.",
    }
