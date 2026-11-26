"""Pure staged plan contracts; no transport, installation or native imports."""
import copy

import unittest

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
    assert "--ignore-installed" in args["dry_run"] and "--ignore-installed" not in args["install"]
    assert all("--keyring-provider" in command and "disabled" in command for command in args.values())
    assert stages.pure_rehearsal_arguments(plan, "python") == (
        "python", "-I", "-B", "-S", str(stages.ROOT / "qa/c5_pdfium/pure_rehearsal.py"))
    assert stages.stage_a_arguments(plan, "python")[-1] == plan["stage_a"]["test_file"]
    assert len(stages.stage_b_arguments(plan, "python")) == 19
    with unittest.TestCase().assertRaisesRegex(RuntimeError, "DISARMED"):
        stages.require_live_authority()


def _terminal(plan, report):
    pid = report["profile"]
    selections = (plan["stage_b"]["regular_modules"] + plan["stage_b"]["contract_modules"] +
                  plan["stage_b"]["selected_nodes"])
    rows = {}
    for selection in selections:
        nodes = [selection if "::" in selection else selection + "::test_fixture"]
        rows[selection] = {"collected": nodes, "passed": list(nodes), "state": "PASS"}
    for kind, count in (("contract", 3), ("mixed", 9)):
        nodes = [f"mixed_{kind}.test_{i}" for i in range(count)]
        rows["mixed:" + kind] = {"collected": nodes, "passed": list(nodes), "state": "PASS"}
    rows["font:equivalence"] = {"collected": list(stages.FONT_REQUIRED_NODES),
                                "passed": list(stages.FONT_REQUIRED_NODES), "state": "PASS"}
    rows["frontend:compatibility"] = {"collected": list(stages.FRONTEND_REQUIRED_NODES),
                                      "passed": list(stages.FRONTEND_REQUIRED_NODES), "state": "PASS"}
    totals = stages.PROFILE_TOTALS[pid]
    return {"profile": pid, "generation": report["generation"], "source": report["source"],
            "attempt": 1, "state": "PASS", "stage_a": report, "stage_b": rows,
            "archive_uses": 87, "body_bytes": totals["A"][1] + totals["B"][1],
            "requests": 87, "cleanup": "OWNED_SCRATCH_REMOVED"}


def test_local_stage_a_gate_and_mandatory_combined_acceptance():
    plan = stages.read_plan()
    reports = _reports(plan)
    gen, source = "a" * 64, "b" * 40
    windows, linux = stages.PROFILE_IDS
    assert stages.stage_b_eligible(plan, reports[0], profile=windows, generation=gen, source=source)
    assert stages.stage_b_eligible(plan, reports[1], profile=linux, generation=gen, source=source)
    for mutation in ("missing", "foreign_profile", "foreign", "failed", "skip", "xfail",
                     "partial", "wrong_native", "wrong_source"):
        bad = copy.deepcopy(reports[0])
        if mutation == "missing":
            bad = None
        elif mutation == "foreign_profile":
            bad["profile"] = linux
        elif mutation == "foreign":
            bad["generation"] = "d" * 64
        elif mutation == "failed":
            bad["state"] = "FAIL"
        elif mutation == "skip":
            bad["skipped"] = [bad["passed"][0]]
        elif mutation == "xfail":
            bad["xfailed"] = [bad["passed"][0]]
        elif mutation == "partial":
            bad["passed"].pop()
        elif mutation == "wrong_native":
            bad["native_sha256"] = "d" * 64
        elif mutation == "wrong_source":
            bad["source"] = "d" * 40
        with unittest.TestCase().assertRaises(ValueError):
            stages.stage_b_eligible(plan, bad, profile=windows, generation=gen, source=source)
    terminals = [_terminal(plan, report) for report in reports]
    assert stages.linux_eligible(plan, terminals[0], generation=gen, source=source)
    assert stages.final_eligible(plan, terminals, generation=gen, source=source)
    for bad in (terminals[:1], terminals[::-1], [terminals[0], terminals[0]]):
        with unittest.TestCase().assertRaises(ValueError):
            stages.final_eligible(plan, bad, generation=gen, source=source)
    for mutation in ("missing_b", "font", "frontend", "cleanup", "attempt", "budget", "partial", "foreign"):
        bad = copy.deepcopy(terminals)
        if mutation == "missing_b":
            bad[0]["stage_b"].pop("mixed:mixed")
        elif mutation == "font":
            bad[0]["stage_b"].pop("font:equivalence")
        elif mutation == "frontend":
            bad[0]["stage_b"].pop("frontend:compatibility")
        elif mutation == "cleanup":
            bad[0]["cleanup"] = "UNKNOWN"
        elif mutation == "attempt":
            bad[0]["attempt"] = 2
        elif mutation == "budget":
            bad[0]["body_bytes"] += 1
        elif mutation == "partial":
            bad[0]["stage_b"]["mixed:mixed"]["passed"].pop()
        elif mutation == "foreign":
            bad[0]["source"] = "d" * 40
        with unittest.TestCase().assertRaises(ValueError):
            stages.linux_eligible(plan, bad[0], generation=gen, source=source)
        with unittest.TestCase().assertRaises(ValueError):
            stages.final_eligible(plan, bad, generation=gen, source=source)
    with unittest.TestCase().assertRaisesRegex(RuntimeError, "DISARMED"):
        stages.require_live_authority()
