"""Pure staged plan contracts; no transport, installation or native imports."""
import copy

import pytest

from qa.c5_pdfium import staged_equivalence as stages


def _reports(plan):
    nodes = [plan["stage_a"]["test_file"] + "::" + node
             for node in plan["stage_a"]["expected_node_ids"]]
    return [{"profile": p["id"], "generation": "a" * 64, "source": "b" * 40,
             "stage": "A", "state": "PASS", "collected": list(nodes), "passed": list(nodes),
             "failed": [], "skipped": [], "xfailed": [],
             "native_sha256": p["native"][0]["sha256"],
             "pre_use_disposition_sha256": "c" * 64} for p in plan["profiles"]]


def test_exact_plan_and_standard_tool_commands():
    plan = stages.read_plan()
    assert stages.LIVE_ENABLED is False
    for profile in plan["profiles"]:
        text = stages.smoke_lock(plan, profile["id"])
        assert "--no-index\n--only-binary=:all:\n--require-hashes" in text
        assert "pypdfium2==5.15.2 --hash=sha256:" in text
        assert "pymupdf" not in text
        assert text.count("--hash=sha256:") == (8 if profile["id"].startswith("windows") else 7)
    args = stages.pip_arguments("python", "wheelhouse", "lock", "report")
    assert "--dry-run" in args["dry_run"] and "--dry-run" not in args["install"]
    assert all("--isolated" in command for command in args.values())
    assert stages.stage_a_arguments(plan, "python")[-1] == plan["stage_a"]["test_file"]
    assert len(stages.stage_b_arguments(plan, "python")) == 19
    with pytest.raises(RuntimeError, match="DISARMED"):
        stages.require_live_authority()


def test_only_complete_same_generation_stage_a_is_eligible_not_authorised():
    plan = stages.read_plan()
    reports = _reports(plan)
    assert stages.stage_b_eligible(plan, reports, generation="a" * 64, source="b" * 40)
    for mutation in ("missing", "duplicate", "foreign", "failed", "skip", "xfail",
                     "partial", "wrong_native", "wrong_source"):
        bad = copy.deepcopy(reports)
        if mutation == "missing":
            bad.pop()
        elif mutation == "duplicate":
            bad[1]["profile"] = bad[0]["profile"]
        elif mutation == "foreign":
            bad[0]["generation"] = "d" * 64
        elif mutation == "failed":
            bad[0]["state"] = "FAIL"
        elif mutation == "skip":
            bad[0]["skipped"] = [bad[0]["passed"][0]]
        elif mutation == "xfail":
            bad[0]["xfailed"] = [bad[0]["passed"][0]]
        elif mutation == "partial":
            bad[0]["passed"].pop()
        elif mutation == "wrong_native":
            bad[0]["native_sha256"] = "d" * 64
        elif mutation == "wrong_source":
            bad[0]["source"] = "d" * 40
        with pytest.raises(ValueError):
            stages.stage_b_eligible(plan, bad, generation="a" * 64, source="b" * 40)
    with pytest.raises(RuntimeError, match="DISARMED"):
        stages.require_live_authority()
