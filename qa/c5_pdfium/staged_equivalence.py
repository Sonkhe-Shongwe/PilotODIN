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
PLAN_PIN = "d411a9fd04e9711a7fff043710bf6bac7505b103"
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
    need(plan["schema"] == 1 and plan["status"] == "DISARMED_PROPOSAL_ONLY",
         "PLAN_NOT_DISARMED")
    need(tuple(p["id"] for p in plan["profiles"]) == PROFILE_IDS, "PROFILE_SET")
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
            "--disable-pip-version-check", "--no-input")
    install = base + ("install", "--no-index", "--only-binary=:all:", "--require-hashes",
                      "--no-cache-dir", "--find-links", str(wheelhouse), "-r", str(lock))
    return {"dry_run": install + ("--dry-run", "--report", str(report)),
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


def stage_b_eligible(plan, reports, *, generation, source):
    """Validate status structure only; future executor must authenticate receipts.

    Both targets must pass every exact Stage A node in the same generation.
    A report, even one matching this shape, grants NO execution authority.
    """
    need(isinstance(generation, str) and SHA256.fullmatch(generation) and
         isinstance(source, str) and SHA1.fullmatch(source), "GENERATION_IDENTITY")
    need(isinstance(reports, list) and len(reports) == 2, "STAGE_A_REPORT_SET")
    expected = {plan["stage_a"]["test_file"] + "::" + node
                for node in plan["stage_a"]["expected_node_ids"]}
    seen = set()
    for report in reports:
        need(set(report) == {"profile", "generation", "source", "stage", "state",
                             "collected", "passed", "failed", "skipped", "xfailed",
                             "native_sha256", "pre_use_disposition_sha256"}, "REPORT_FIELDS")
        pid = report["profile"]
        need(pid in PROFILE_IDS and pid not in seen, "REPORT_PROFILE")
        seen.add(pid)
        need(report["generation"] == generation and report["source"] == source and
             report["stage"] == "A" and report["state"] == "PASS", "REPORT_IDENTITY")
        for key in ("collected", "passed"):
            nodes = report[key]
            need(isinstance(nodes, list) and len(nodes) == len(expected) and set(nodes) == expected,
                 "REPORT_NODE_SET")
        need(report["failed"] == report["skipped"] == report["xfailed"] == [],
             "REPORT_NOT_PASS")
        profile = next(p for p in plan["profiles"] if p["id"] == pid)
        need(len(profile["native"]) == 1 and
             report["native_sha256"] == profile["native"][0]["sha256"] and
             isinstance(report["pre_use_disposition_sha256"], str) and
             SHA256.fullmatch(report["pre_use_disposition_sha256"]), "REPORT_NATIVE_IDENTITY")
    return seen == set(PROFILE_IDS)


def require_live_authority():
    # There is intentionally no activation implementation in this draft.
    # A future separately reviewed executor must bind exact commit, one-use
    # approval, actual verified linkage/rights and runner generation before use.
    raise RuntimeError("C5_PDFIUM_STAGED_EQUIVALENCE_DISARMED")


if __name__ == "__main__":
    require_live_authority()
