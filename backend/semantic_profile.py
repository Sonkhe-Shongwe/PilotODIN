"""P3 bounded read-only semantic hypotheses from approved dataframe metadata.

Evidence is based on names, dtypes, counts and existing bounded role-shape checks.
This never supplies confirmed business meanings, true event grain, or targets;
all non-observed concepts are explicitly hypotheses and must be reviewed.
"""
from __future__ import annotations

import re
import pandas as pd

try:
    from . import column_intelligence
except ImportError:  # Supports the documented direct-backend uvicorn development mode.
    import column_intelligence

MAX_FIELDS = 80
DOMAIN_SIGNALS = {
    "Insurance": (
        ("claim", "claims"), ("policy", "policy"), ("premium", "premium"),
        ("incident", "incident"), ("coverage", "coverage"),
    ),
    "Retail": (
        ("order", "orders"), ("sku", "sku"), ("product", "products"),
        ("cart", "cart"), ("inventory", "inventory"), ("customer", "customer"),
    ),
    "Education": (
        ("student", "student"), ("learner", "learner"), ("enrol", "enrolment"),
        ("grade", "grade"), ("course", "course"), ("school", "school"),
    ),
    "Banking": (
        ("account", "account"), ("loan", "loan"), ("repayment", "repayment"),
        ("balance", "balance"), ("interest", "interest"),
    ),
    "Manufacturing": (
        ("machine", "machine"), ("equipment", "equipment"), ("batch", "batch"),
        ("fault", "fault"), ("defect", "defect"), ("production", "production"),
    ),
}
IDENTIFIER_NAME = re.compile(
    r"(?:^id$|(?:^|_)(?:id|identifier|uuid|serial|order_id|claim_id|customer_id|policy_number)(?:$|_))"
)
TIME_NAME = re.compile(
    r"(?:^|_)(?:date|timestamp|datetime|created_at|updated_at|incident_date|event_time)(?:$|_)"
)
MONEY_NAME = re.compile(
    r"(?:^|_)(?:amount|price|cost|revenue|premium|salary|fee|expense)(?:$|_)"
)
OUTCOME_NAME = re.compile(
    r"(?:^|_)(?:outcome|result|label|churn|fraud|default|target|status|reported)(?:$|_)"
)


def _tokens(name: str) -> tuple[str, ...]:
    return tuple(token for token in re.split(r"[^a-z0-9]+", name.lower()) if token)


def _domain_hypothesis(names: list[str]) -> dict:
    matches = []
    for domain, signals in DOMAIN_SIGNALS.items():
        sources = []
        concepts = set()
        for name in names:
            tokens = _tokens(name)
            for stem, concept in signals:
                if any(t.startswith(stem) for t in tokens):
                    concepts.add(concept)
                    if name not in sources:
                        sources.append(name)
        # Independent headers matter: one composite header (product_sku)
        # must not count as two independent sources of domain evidence.
        if len(concepts) >= 2 and len(sources) >= 2:
            matches.append((domain, len(sources), sources))
    if not matches:
        return {
            "state": "unknown", "label": None, "evidence_columns": [],
            "reason": "Headers do not provide enough distinct domain clues; business context is required.",
        }
    matches.sort(key=lambda x: x[1], reverse=True)
    if len(matches) > 1 and matches[0][1] == matches[1][1]:
        return {
            "state": "unknown", "label": None, "evidence_columns": [],
            "reason": "Column names suggest multiple domains equally; no domain was assigned.",
        }
    top = matches[0]
    return {
        "state": "hypothesis", "label": top[0],
        "evidence_columns": top[2][:6],
        "reason": "Tentative header-pattern match only. Does not verify industry, purpose or data provenance.",
    }


def _grain_hypothesis(columns: list[dict], rows: int) -> dict:
    # Uniqueness is observed, but row meaning cannot be confirmed from it.
    options = [
        c for c in columns if rows >= 3 and c["missing"] == 0
        and c["unique"] == rows and (
            c["identifier_candidate"] or bool(IDENTIFIER_NAME.search(
                re.sub(r"[^a-z0-9]+", "_", c["name"].lower())))
        )
    ]
    if len(options) == 1:
        name = options[0]["name"]
        return {
            "state": "hypothesis", "identifier_column": name,
            "reason": (
                f"'{name}' has one distinct non-missing value per observed row. "
                "It may be a record key; this does not establish whether a row means a "
                "customer, transaction, claim, visit or other event."
            ),
        }
    if len(options) > 1:
        return {
            "state": "unknown", "identifier_column": None,
            "reason": "Multiple columns uniquely identify rows; business record grain is ambiguous.",
        }
    return {
        "state": "unknown", "identifier_column": None,
        "reason": "No unambiguous complete unique identifier was observed; row grain needs business confirmation.",
    }


def _field_hypotheses(entry: dict) -> list[dict]:
    name = entry["name"]
    normal = re.sub(r"[^a-z0-9]+", "_", name.lower())
    roles = []
    def propose(role: str, basis: str, reason: str):
        roles.append({"role": role, "state": "hypothesis", "basis": basis, "reason": reason})
    if entry["identifier_candidate"]:
        propose("possible_identifier", "name_and_cardinality",
                "Identifier-like name and high distinctness; verify entity and uniqueness.")
    elif IDENTIFIER_NAME.search(normal):
        propose("possible_identifier", "name_only",
                "Identifier-like header, but complete per-row uniqueness has not been verified.")
    if entry["role"] == "datetime":
        propose("possible_time_field", "stored_dtype",
                "Stored as a datetime; recording or event timing is not confirmed.")
    elif TIME_NAME.search(normal) or entry["role"] == "date-like text":
        propose("possible_time_field", "name_or_sample_pattern",
                "Date-related header or sampled text shape; timezone, timing and parsing need review.")
    if MONEY_NAME.search(normal):
        propose("possible_monetary_measure", "name_only",
                "Header suggests money, but currency, units and business meaning are unconfirmed.")
    if OUTCOME_NAME.search(normal):
        propose("possible_outcome", "name_only",
                "Header may describe an outcome; label quality and prediction-time availability are unknown.")
    return roles[:4]


def overview(frame: pd.DataFrame, version: int) -> dict:
    if not frame.columns.is_unique:
        raise ValueError("Semantic overview requires unique column names")
    dictionary = column_intelligence.overview(frame, version)
    columns = dictionary["columns"]
    shown = columns[:MAX_FIELDS]
    names = [c["name"] for c in columns]
    roles = []
    for entry in shown:
        hints = _field_hypotheses(entry)
        if hints:
            roles.append({
                "column": entry["name"],
                "observed": {
                    "dtype": entry["dtype"], "missing": entry["missing"],
                    "unique": entry["unique"], "rows": entry["rows"],
                },
                "hypotheses": hints,
            })
    return {
        "version": version,
        "rows": len(frame),
        "columns_examined": len(shown),
        "columns_total": len(columns),
        "domain": _domain_hypothesis(names),
        "grain": _grain_hypothesis(columns, len(frame)),
        "fields": roles,
        "observed": "Stored dtype, missing count and distinct count are measured on the approved working version.",
        "inferred": "Industry, record grain, timing, units and outcome meaning are unverified hypotheses.",
        "unknown": "Actual business purpose, row entity, unit conventions and label availability cannot be established without user context.",
        "note": "Read-only local heuristics. No raw sample values returned, model training, data changes, inferred confidence scores or automatic target selection.",
    }
