"""Explicit pytest status hook for the detached staged executor.

No native dependency import or package acquisition. Loaded only by a future
authorised executor. Record node IDs and statuses, never captured output.
"""
import json
import os
from pathlib import Path

_collected = []
_reports = {}
_errors = False


def pytest_collection_finish(session):
    _collected[:] = [item.nodeid for item in session.items]


def pytest_collectreport(report):
    global _errors
    if report.failed or report.skipped:
        _errors = True


def pytest_internalerror(excrepr, excinfo):
    global _errors
    _errors = True


def pytest_runtest_logreport(report):
    _reports.setdefault(report.nodeid, []).append(
        (report.when, report.outcome, hasattr(report, "wasxfail")))


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("C5_PDFIUM_TEST_STATUS")
    if not path:
        return
    passed, failed, skipped, xfailed = [], [], [], []
    collection_only = bool(getattr(getattr(getattr(session, "config", None), "option", None),
                                   "collectonly", False))
    for node in (() if collection_only else _collected):
        reports = _reports.get(node, [])
        if any(x[2] for x in reports):
            xfailed.append(node)
        elif any(x[1] == "skipped" for x in reports):
            skipped.append(node)
        elif reports == [("setup", "passed", False), ("call", "passed", False),
                         ("teardown", "passed", False)]:
            passed.append(node)
        else:
            failed.append(node)
    if _errors or set(_reports) - set(_collected) or (collection_only and _reports):
        failed.append("SESSION_OR_COLLECTION_FAILURE")
    payload = {"collected": _collected, "passed": passed, "failed": failed,
               "skipped": skipped, "xfailed": xfailed, "exitstatus": int(exitstatus),
               "mode": "COLLECTION" if collection_only else "EXECUTION"}
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("ascii")
    target = Path(path)
    if not target.is_absolute() or len(raw) > 4 * 1024**2:
        raise RuntimeError("PYTEST_STATUS_BOUND")
    with target.open("xb") as out:
        out.write(raw)
