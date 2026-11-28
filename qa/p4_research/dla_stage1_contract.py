"""DLA Stage 1 isolated source contract. No launcher, acquisition or CLI.

The production preflight remains blocked. Nothing in this module grants
authority, authenticates a reviewer, or proves real process settlement.
"""
from __future__ import annotations

import hashlib
import json

from desktop import verify_inference_assets as assets
from tools import c5_archive_preflight as zipcheck
from tools.build_input_preflight import Blocked, fields, require

ARCHIVE_BYTES = 18406491
ARCHIVE_SHA = "c0cec8825843957cae6620f927eb6eb9f7f4680da3206910932ea9075f91b405"
GRANITE_SHA = "0a8d6a7373602fadfba274a640ba784b86cc6847f1c67f1b0a90fa2ec266b7fb"
GRANITE_BYTES = None  # immutable publisher pointer not independently confirmed
GRANITE_FILE = "granite-4.0-h-350m-Q4_K_M.gguf"
GRANITE_ALIAS = "pilotodin-granite-4.0-h-350m"
LIQUID = ("LFM2.5-350M-Q4_K_M.gguf", 229312224,
          "7e6f72643caafc9a68256686638c4d7916f2cec76d1df478d4c3ddcd95a6aed4")
FLOOR = 2 * 1024 ** 3
CASE_NAMES = ("dataset_overview", "rate_with_denominator", "unknown_cause",
              "no_training_claim", "long_context_overview")
PLAN_NAMES = ("filtered_median", "grouped_missingness", "labelled_rate", "all_row_rate")
NOTICE_NAMES = {"llama.cpp-MIT-LICENSE.txt", "Granite-Apache-2.0-LICENSE.txt",
                "THIRD-PARTY-SOURCES.txt"}


def _inspect_snapshot(raw, size, digest):
    """Pure bounded parser seam. Test fixtures are not publisher evidence."""
    require(type(raw) is bytes and type(size) is int
            and zipcheck.EOCD.size < size <= zipcheck.MAX_ARCHIVE
            and len(raw) == size and hashlib.sha256(raw).hexdigest() == digest,
            "DLA_ARCHIVE_IDENTITY")
    try:
        return zipcheck._snapshot_members(raw, None)
    except (ValueError, zipcheck.struct.error, zipcheck.zlib.error):
        raise Blocked("DLA_ARCHIVE_MALFORMED") from None


def inspect_pinned_runtime_snapshot(raw):
    """Return observations from an independently pinned archive, NOT approval.

    A future separately authorised caller must own custody, authenticate
    source, retain notices, and obtain independent review before using these
    observations as expected identities in a distinct staging generation.
    No file, network, extraction or execution capability here.
    """
    return _inspect_snapshot(raw, ARCHIVE_BYTES, ARCHIVE_SHA)


def _check_granite_expectation(expected, exact_size):
    fields(expected, {"model", "server", "dlls", "notices"})
    assets._check_row(expected["model"])
    assets._check_row(expected["server"])
    assets._check_named_rows(expected["dlls"], ".dll")
    assets._check_named_rows(expected["notices"], ".txt")
    require(type(exact_size) is int and exact_size > 0,
            "DLA_GRANITE_POINTER_UNCONFIRMED")
    require(expected["model"] == {"bytes": exact_size, "sha256": GRANITE_SHA},
            "DLA_MODEL_IDENTITY")
    require(NOTICE_NAMES <= set(expected["notices"]), "DLA_NOTICE_MISSING")


def granite_preflight(expected):
    """Disarmed even if a caller supplies invented inventory or rights."""
    _check_granite_expectation(expected, GRANITE_BYTES)
    raise Blocked("DLA_INDEPENDENT_REVIEW_AND_EXECUTION_NOT_BOUND")


def five_cases():
    # Existing evaluator imports these names as desktop script modules.
    from offline_analytics_cases import CASES
    require(tuple(x[0] for x in CASES) == CASE_NAMES[:4], "DLA_CASE_DRIFT")
    _, facts, question, expected = CASES[0]
    return tuple((name, facts, question, expected, "")
                 for name, facts, question, expected in CASES) + (
        ("long_context_overview", facts, question, expected,
         "Synthetic context for the batch-size check.\n" * 100),)


def score_five(responses):
    """Reuse original exact scoring; no constrained grammar substitution."""
    from offline_analytics_cases import score_answer
    require(type(responses) is dict and set(responses) == set(CASE_NAMES),
            "DLA_CASE_INVENTORY")
    scores = {}
    for name, _, _, expected, _ in five_cases():
        row = responses[name]
        fields(row, {"finish_reason", "content"})
        scores[name] = (row["finish_reason"] == "stop" and
                        type(row["content"]) is str and
                        len(row["content"]) <= 16384 and
                        score_answer(row["content"], expected))
    return scores


def score_plans(responses):
    """Separate fixed intent screen; no tool execution or raw data access."""
    expected = {
        "filtered_median": {"operation": "median", "measure": "premium",
                            "filter_column": "outcome", "filter_value": "Yes"},
        "grouped_missingness": {"operation": "grouped_missingness",
                                "measure": "premium", "group_by": "outcome"},
        "labelled_rate": {"operation": "rate", "measure": "outcome",
                          "value": "Yes", "denominator": "labelled"},
        "all_row_rate": {"operation": "rate", "measure": "outcome",
                         "value": "Yes", "denominator": "all_rows"},
    }
    from offline_analytics_cases import score_answer
    require(type(responses) is dict and set(responses) == set(PLAN_NAMES),
            "DLA_PLAN_INVENTORY")
    scores = {}
    for name, answer in responses.items():
        fields(answer, {"finish_reason", "content"})
        scores[name] = (answer["finish_reason"] == "stop" and
                        type(answer["content"]) is str and
                        len(answer["content"]) <= 4096 and
                        score_answer(answer["content"], expected[name]))
    return scores


def admission(available_bytes, alias, lease_held):
    return (type(available_bytes) is int and available_bytes >= FLOOR
            and alias == GRANITE_ALIAS and lease_held is True)


def settled(witness, generation, deadline_ns):
    """Pure reduction of trusted host observations, not an OS witness.

    Never construct these observations from a model, browser or API client.
    Real host binding is outstanding. Deadline is shared and never renewed.
    """
    fields(witness, {"generation", "startup_joined", "leader_terminated",
                     "receiver_closed", "child_dropped", "event_fault",
                     "active_processes", "group_observed_ns",
                     "listener_identity_verified", "listener_absent",
                     "listener_observed_ns"})
    return (
        type(generation) is str and bool(generation)
        and witness["generation"] == generation
        and all(witness[k] is True for k in
                ("startup_joined", "leader_terminated", "receiver_closed",
                 "child_dropped", "listener_identity_verified", "listener_absent"))
        and witness["event_fault"] is False
        and type(witness["active_processes"]) is int
        and witness["active_processes"] == 0
        and all(type(n) is int for n in (deadline_ns, witness["group_observed_ns"],
                                        witness["listener_observed_ns"]))
        and 0 <= witness["group_observed_ns"] <= witness["listener_observed_ns"] < deadline_ns
    )


def redacted_synthetic_result(analytics, plans, witness, generation, deadline_ns):
    """Only fixed names/booleans; never a real candidate PASS or execution token."""
    fields(analytics, set(CASE_NAMES))
    fields(plans, set(PLAN_NAMES))
    require(all(type(v) is bool for v in (*analytics.values(), *plans.values())),
            "DLA_SCORE_SHAPE")
    return {"scope": "SYNTHETIC_SOURCE_ONLY",
            "analytics": dict(analytics), "plans": dict(plans),
            "settlement_predicate": settled(witness, generation, deadline_ns),
            "execution_authorised": False, "candidate_qualified": False}
