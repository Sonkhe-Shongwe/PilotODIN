"""Disarmed C5 PDFium equivalence plan and stage controls.

No transport, subprocess, package import, installation, CI or activation path.
This module prepares exact standard-tool command arguments for a future separately
approved executor. A valid plan or stage receipt is NOT execution authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = "qa/c5_pdfium/staged_equivalence_plan_20261126.json"
PLAN_PIN = "f81c0bfe8b09cc226f1d566d8366f454a9f4dd4e"
LIVE_ENABLED = False
PROFILE_IDS = ("windows-x64-cp311-source-test", "linux-x64-cp311-source-test")
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
WHEEL_URL = re.compile(r"https://files\.pythonhosted\.org/packages/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/[A-Za-z0-9_.+-]+\.whl")
TOTALS = {"A": (19, 148773093, 21), "B": (83, 166813645, 83)}
PROFILE_TOTALS = {
    PROFILE_IDS[0]: {"A": (10, 41213475), "B": (41, 78047853)},
    PROFILE_IDS[1]: {"A": (9, 107559618), "B": (42, 88765792)},
}
SMOKE_ROOTS = frozenset(("pytest", "packaging", "iniconfig", "pluggy", "pygments",
                         "pillow", "pypdfium2"))
FONT_REQUIRED_NODES = ("font:scoped_cmap_unit", "font:baseline_extraction_mismatch",
                       "font:corrected_extraction_exact", "font:same_engine_rgb_identity",
                       "font:actual_unicode_exact", "font:actual_unicode_continuation",
                       "font:actual_unicode_line_bounds", "font:context_order_and_bounds",
                       "font:coverage_outcomes")
REQUIRED_ENV = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
                "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pinned(path, expected):
    target = ROOT / path
    need(target.is_file() and not target.is_symlink(), "PIN_PATH")
    raw = target.read_bytes()
    need(hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
         == expected, "PIN_MISMATCH")
    return raw


def strict_json(raw):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, "NONFINITE_JSON"))


def read_plan():
    plan = strict_json(pinned(PLAN_PATH, PLAN_PIN))
    need(plan["schema"] == 2 and plan["status"] == "DISARMED_PROPOSAL_ONLY",
         "PLAN_NOT_DISARMED")
    need(tuple(p["id"] for p in plan["profiles"]) == PROFILE_IDS, "PROFILE_SET")
    need(plan["scheduling"] == {"mode": "WINDOWS_A_B_THEN_LINUX_A_B",
         "local_stage_a_required": True, "linux_requires_windows_terminal_pass": True,
         "final_requires_both_complete": True, "shared_binary_artifacts": False}, "SCHEDULING")
    need(plan["pre_use_disposition"] == {"status": "UNRESOLVED", "pin": None,
         "mandatory_before_any_consumption": True}, "DISPOSITION_NOT_DISARMED")
    for path, digest in plan["source_pins"].items():
        pinned(path, digest)
    for stage, (count, size, gets) in TOTALS.items():
        limit = plan["limits"]["stage_a" if stage == "A" else "stage_b"]
        need(limit == {"archive_uses": count, "body_bytes": size, "max_gets": gets},
             "STAGE_LIMIT")
    need(plan["limits"]["combined"] == {"archive_uses": 102, "body_bytes": 315586738,
                                        "max_gets": 104}, "COMBINED_LIMIT")
    for profile in plan["profiles"]:
        pid = profile["id"]
        rows = profile["rows"]
        need(len(rows) == 51 and len({r["filename"] for r in rows}) == 51,
             "PROFILE_ARTIFACT_SET")
        wheels = [r for r in rows if r["kind"] == "wheel"]
        need(len(wheels) == 49 and len({r["name"] for r in wheels}) == 49,
             "PROFILE_WHEEL_SET")
        need(sum(r["kind"] == "interpreter" for r in rows) == 1 and
             sum(r["kind"] == "pip" for r in rows) == 1, "TOOLCHAIN_SET")
        for row in rows:
            need(row["stage"] in ("A", "B") and type(row["bytes"]) is int and
                 row["bytes"] > 0 and SHA256.fullmatch(row["sha256"]), "ARTIFACT_IDENTITY")
            if row["kind"] in ("pip", "wheel"):
                need(WHEEL_URL.fullmatch(row["url"]) and
                     row["url"].endswith("/" + row["filename"]), "WHEEL_URL")
            if row["kind"] == "wheel":
                need(SHA256.fullmatch(row["metadata_sha256"]), "METADATA_IDENTITY")
            if row["kind"] != "wheel":
                need(row["stage"] == "A", "TOOLCHAIN_STAGE")
        smoke = {r["name"] for r in wheels if r["stage"] == "A"}
        need(smoke == SMOKE_ROOTS | ({"colorama"} if pid.startswith("windows") else set()),
             "SMOKE_CLOSURE")
        need("pymupdf" not in {r["name"] for r in wheels}, "OLD_ENGINE")
        for stage in ("A", "B"):
            selected = [r for r in rows if r["stage"] == stage]
            need((len(selected), sum(r["bytes"] for r in selected)) ==
                 PROFILE_TOTALS[pid][stage], "PROFILE_STAGE_TOTAL")
        lock = pinned("backend/locks/" + pid + ".txt", profile["lock_blob"]).decode("ascii")
        expected = {f"{r['name']}{'[standard]' if r['name'] == 'uvicorn' else ''}=={r['version']} "
                    f"--hash=sha256:{r['sha256']}" for r in wheels}
        actual = {line for line in lock.splitlines() if line and not line.startswith(("#", "--"))}
        need(len(actual) == 49 and actual == expected, "LOCK_PROJECTION")
    ids = plan["stage_a"]["expected_node_ids"]
    need(len(ids) == len(set(ids)) == plan["stage_a"]["expected_count"] == 19,
         "SMOKE_TEST_SET")
    return plan


def smoke_lock(plan, profile_id):
    """Only the exact Stage A wheel projection, not a new production lock."""
    profile = next(p for p in plan["profiles"] if p["id"] == profile_id)
    rows = sorted((r for r in profile["rows"] if r["kind"] == "wheel" and r["stage"] == "A"),
                  key=lambda row: row["name"])
    return "--no-index\n--only-binary=:all:\n--require-hashes\n\n" + "".join(
        f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\n" for r in rows)


def pip_arguments(python, wheelhouse, lock, report):
    """Exact argument templates; executor must verify absolute isolated paths."""
    base = (str(python), "-I", "-B", "-m", "pip", "--isolated",
            "--disable-pip-version-check", "--no-input", "--keyring-provider", "disabled")
    install = base + ("install", "--no-index", "--only-binary=:all:", "--require-hashes",
                      "--no-cache-dir", "--find-links", str(wheelhouse), "-r", str(lock))
    return {"dry_run": install + ("--dry-run", "--ignore-installed", "--report", str(report)),
            "install": install, "check": base + ("check",)}


def stage_a_arguments(plan, python):
    return (str(python), "-B", "-m", "pytest", "-p", "no:cacheprovider",
            "--strict-markers", "-q", plan["stage_a"]["test_file"])


def stage_b_arguments(plan, python):
    """One fresh disposable fixture home per regular/contract module invocation.

    Mixed report worker needs its original dedicated fresh run manifest and is
    deliberately not included in these generic pytest invocations.
    """
    base = (str(python), "-B", "-m", "pytest", "-p", "no:cacheprovider",
            "--strict-markers", "-q")
    stage = plan["stage_b"]
    return tuple(base + (path,) for path in
                 stage["regular_modules"] + stage["contract_modules"] + stage["selected_nodes"])


def pure_rehearsal_arguments(plan, python):
    base = (str(python), "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q")
    p = plan["pure_rehearsal"]
    return base + (p["test_file"], p["guard_node"], p["executor_tests"])


def stage_b_eligible(plan, report, *, profile, generation, source):
    """Local Stage A must pass completely before local Stage B. No authority."""
    need(isinstance(generation, str) and SHA256.fullmatch(generation) and
         isinstance(source, str) and SHA1.fullmatch(source), "GENERATION_IDENTITY")
    expected = {plan["stage_a"]["test_file"] + "::" + node
                for node in plan["stage_a"]["expected_node_ids"]}
    need(isinstance(report, dict) and set(report) == {
        "profile", "generation", "source", "stage", "state", "collected", "passed",
        "failed", "skipped", "xfailed", "native_sha256", "pre_use_disposition_sha256"
    }, "REPORT_FIELDS")
    need(profile in PROFILE_IDS and report["profile"] == profile, "REPORT_PROFILE")
    need(report["generation"] == generation and report["source"] == source and
         report["stage"] == "A" and report["state"] == "PASS", "REPORT_IDENTITY")
    for key in ("collected", "passed"):
        nodes = report[key]
        need(isinstance(nodes, list) and len(nodes) == len(expected) and set(nodes) == expected,
             "REPORT_NODE_SET")
    need(report["failed"] == report["skipped"] == report["xfailed"] == [], "REPORT_NOT_PASS")
    target = next(p for p in plan["profiles"] if p["id"] == profile)
    need(len(target["native"]) == 1 and
         report["native_sha256"] == target["native"][0]["sha256"] and
         isinstance(report["pre_use_disposition_sha256"], str) and
         SHA256.fullmatch(report["pre_use_disposition_sha256"]), "REPORT_NATIVE_IDENTITY")
    return True


def terminal_profile(plan, receipt, *, profile, generation, source):
    """Reconcile complete A and B status shape; authentic provenance is separate."""
    need(isinstance(receipt, dict) and set(receipt) == {
        "profile", "generation", "source", "attempt", "state", "stage_a",
        "stage_b", "archive_uses", "body_bytes", "requests", "cleanup"
    }, "TERMINAL_FIELDS")
    need(receipt["profile"] == profile and receipt["generation"] == generation and
         receipt["source"] == source and type(receipt["attempt"]) is int and
         receipt["attempt"] == 1 and receipt["state"] == "PASS" and
         receipt["cleanup"] == "OWNED_SCRATCH_REMOVED", "TERMINAL_IDENTITY")
    stage_b_eligible(plan, receipt["stage_a"], profile=profile,
                     generation=generation, source=source)
    commands = (plan["stage_b"]["regular_modules"] + plan["stage_b"]["contract_modules"] +
                plan["stage_b"]["selected_nodes"])
    expected = commands + ["mixed:contract", "mixed:mixed", "font:equivalence"]
    b = receipt["stage_b"]
    need(isinstance(b, dict) and set(b) == set(expected), "STAGE_B_CASE_SET")
    all_nodes = set()
    for selection in expected:
        row = b[selection]
        need(isinstance(row, dict) and set(row) == {"collected", "passed", "state"} and
             row["state"] == "PASS", "STAGE_B_STATE")
        nodes = row["collected"]
        need(isinstance(nodes, list) and nodes and all(isinstance(n, str) and n for n in nodes)
             and len(nodes) == len(set(nodes)) and row["passed"] == nodes, "STAGE_B_NODE_SET")
        need(not all_nodes.intersection(nodes), "STAGE_B_DUPLICATE")
        all_nodes.update(nodes)
        if selection.startswith("tests/"):
            need(all(n.startswith(selection + "::") or n == selection or
                     ("::" in selection and n.startswith(selection + "["))
                     for n in nodes), "STAGE_B_FOREIGN_NODE")
        if selection.startswith("mixed:"):
            need(len(nodes) == (3 if selection.endswith("contract") else 9), "MIXED_COUNT")
        if selection == "font:equivalence":
            need(tuple(nodes) == FONT_REQUIRED_NODES, "FONT_PREDICATE_SET")
    totals = PROFILE_TOTALS[profile]
    need(type(receipt["archive_uses"]) is int and receipt["archive_uses"] == 51 and
         type(receipt["body_bytes"]) is int and
         receipt["body_bytes"] == totals["A"][1] + totals["B"][1] and
         type(receipt["requests"]) is int and 51 <= receipt["requests"] <= 52,
         "TERMINAL_BUDGET")
    return True


def linux_eligible(plan, windows, *, generation, source):
    return terminal_profile(plan, windows, profile=PROFILE_IDS[0],
                            generation=generation, source=source)


def final_eligible(plan, receipts, *, generation, source):
    need(isinstance(receipts, list) and len(receipts) == 2, "TERMINAL_SET")
    for profile, receipt in zip(PROFILE_IDS, receipts):
        terminal_profile(plan, receipt, profile=profile, generation=generation, source=source)
    need(receipts[0]["stage_a"]["pre_use_disposition_sha256"] ==
         receipts[1]["stage_a"]["pre_use_disposition_sha256"], "DISPOSITION_GENERATION")
    return True


def require_live_authority():
    # There is intentionally no activation implementation in this draft.
    # A future separately reviewed executor must bind exact commit, one-use
    # approval, actual verified linkage/rights and runner generation before use.
    raise RuntimeError("C5_PDFIUM_STAGED_EQUIVALENCE_DISARMED")


if __name__ == "__main__":
    require_live_authority()
