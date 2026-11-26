"""Pure source and fixture contracts for the disarmed staged executor."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from qa.c5_pdfium import staged_executor as executor
from qa.c5_pdfium import staged_equivalence as stages
from qa.c5_pdfium import pytest_receipt as receipt_hook
from tools import pdf_test_inspection as pdf


def test_disarmed_executor_refuses_before_side_effects():
    assert executor.LIVE_ENABLED is False and executor.DISPOSITION_PIN is None
    with patch.object(executor.subprocess, "Popen") as process, \
            patch.object(executor.tempfile, "TemporaryDirectory") as scratch:
        for action in (
            lambda: executor.main(),
            lambda: executor.run_profile(stages.PROFILE_IDS[0], "a"*64, "b"*40),
            lambda: executor.read_disposition({}, {}),
            lambda: executor.Acquisition({}, None, None, {}),
            lambda: executor.run(("forbidden",), env={}, cwd=None),
            lambda: executor.verified_existing_interpreter({}, {}),
            lambda: executor.inspect_distribution(None, {}, {}),
            lambda: executor.frontend_witness(None, {}, {}, [], None),
            lambda: executor.font_witness(None, None, {}, {}, [], None),
            lambda: executor.native_linkage(None, None, None, None, None),
            lambda: executor.verify_loaded_native(None, None, None, None),
            lambda: executor.resolve_install(None, None, None, None, None, None),
        ):
            with pytest.raises(RuntimeError, match="DISARMED"):
                action()
        process.assert_not_called()
        scratch.assert_not_called()
    with pytest.raises(RuntimeError, match="FONT_EQUIVALENCE_UNRESOLVED"):
        executor.require_font_authority()


def test_malformed_fixture_refuses_before_direct_native_import():
    from tests import test_c5_pdfium_inspection_equivalence as fixture
    import builtins
    original = builtins.__import__
    calls = []

    def track(name, *args, **kwargs):
        if name == "pypdfium2" or name.startswith("pypdfium2_raw"):
            calls.append(name)
            raise AssertionError("native import before guard")
        return original(name, *args, **kwargs)

    with patch.object(pdf, "PDFIUM_TEST_EXECUTION_ENABLED", False), \
            patch("builtins.__import__", side_effect=track):
        with pytest.raises(RuntimeError, match="DISARMED"):
            fixture.test_malformed_with_eof_requires_reader_refusal()
    assert not calls


def test_response_framing_and_archive_paths():
    assert executor.response_headers(b"HTTP/1.1 200 OK\r\nContent-Length: 12\r\n\r\n") == (200, 12, None)
    assert executor.response_headers(b"HTTP/1.1 302 Found\r\nContent-Length: 0\r\nLocation: https://example.invalid/x\r\n\r\n")[0:2] == (302, 0)
    for raw in (
        b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Encoding: gzip\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\nHTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n",
    ):
        with pytest.raises(ValueError):
            executor.response_headers(raw)
    assert executor.archive_member_path("python/bin/python") == "python/bin/python"
    for name in ("../bad", "/root", "foo\\bar", "a/CON", "a/alternate:stream"):
        with pytest.raises(ValueError):
            executor.archive_member_path(name)


def test_resolution_requires_exact_local_archive_and_complete_graph(tmp_path):
    house = tmp_path / "wheels"
    house.mkdir()
    row = {"name": "pytest", "version": "9.2.0", "filename": "pytest-9.2.0-py3-none-any.whl",
           "sha256": "f" * 64}
    item = {"metadata": {"name": "pytest", "version": "9.2.0"},
            "download_info": {"url": (house / row["filename"]).as_uri(),
                              "archive_info": {"hashes": {"sha256": row["sha256"]}}},
            "is_direct": False}
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"install": [item]}), encoding="ascii")
    assert executor.reconcile_resolution(report, [row], house)
    for wrong in ([], [item, item], [dict(item, is_direct=True)],
                  [dict(item, download_info=dict(item["download_info"],
                                                  url="https://example.invalid/" + row["filename"]))]):
        report.write_text(json.dumps({"install": wrong}), encoding="ascii")
        with pytest.raises(ValueError):
            executor.reconcile_resolution(report, [row], house)


def test_status_hook_rejects_incomplete_setup_call_teardown(tmp_path, monkeypatch):
    node = "tests/test_fixture.py::test_one"
    monkeypatch.setattr(receipt_hook, "_collected", [node])
    monkeypatch.setattr(receipt_hook, "_reports", {node: [
        ("setup", "passed", False), ("call", "passed", False)]})
    monkeypatch.setattr(receipt_hook, "_errors", False)
    path = tmp_path / "receipt.json"
    monkeypatch.setenv("C5_PDFIUM_TEST_STATUS", str(path))
    receipt_hook.pytest_sessionfinish(None, 0)
    data = json.loads(path.read_text(encoding="ascii"))
    assert data["failed"] == [node] and data["passed"] == []


def test_completion_inventory_never_acquires_python_installer():
    plan = stages.read_plan()
    assert plan["limits"]["combined"] == {"archive_uses": 174, "body_bytes": 368577782,
                                           "max_gets": 174}
    assert plan["limits"]["python_redirect_hops_per_platform"] == 0
    for profile in plan["profiles"]:
        assert profile["existing_interpreter"]["provenance"] == "UNRESOLVED_MUST_BE_INDEPENDENTLY_VERIFIED"
        assert len(profile["rows"]) == 87
        assert all(row["kind"] != "interpreter" for row in profile["rows"])
        assert profile["existing_interpreter"]["historical_archive"] not in {
            row["filename"] for row in profile["rows"]}


def test_supplemental_identity_algorithms(tmp_path):
    import hashlib
    path = tmp_path / "test.tgz"
    raw = b"synthetic fixture"
    path.write_bytes(raw)
    for row in (
        {"kind": "npm", "bytes": len(raw), "sha512": hashlib.sha512(raw).hexdigest()},
        {"kind": "node", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
        {"kind": "font", "bytes": len(raw), "git_blob_sha1": hashlib.sha1(
            b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()},
    ):
        executor.exact_file(path, row)
        algorithm, _ = executor.identity(row)
        invalid = dict(row, **{algorithm: "0" * len(row[algorithm])})
        with pytest.raises(ValueError, match="ARTIFACT_IDENTITY"):
            executor.exact_file(path, invalid)


def test_font_worker_refuses_before_native_or_owner_path():
    from qa.c5_pdfium import font_witness
    with patch.object(pdf, "require_pdfium") as native:
        with pytest.raises(RuntimeError, match="DISARMED"):
            font_witness.run("actual", None)
        native.assert_not_called()
