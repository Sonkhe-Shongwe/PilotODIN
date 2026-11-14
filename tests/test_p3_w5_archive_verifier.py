"""Offline independent W5 status-only ZIP reviewer fail-closed contracts.

Every archive in this suite is fabricated synthetic test evidence and must NOT
be treated as owner native acceptance.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile
import pytest

from tools.Seed_P3_Native_Quality_W5_Local import source_bytes
from tools.Verify_P3_Native_Quality_W5_Status import (
    ArchiveRefused, PHASE, SUCCESS, inspect_archive, main,
)

RUN="P3-NATIVE-QUALITY-W5-20261106T201010Z-abcdef1234"
HEAD="a"*40
PID="b"*32


def _archive(tmp_path: Path, *, result=None, baseline=None, fixture=None, other=None) -> Path:
    path=tmp_path/(RUN+"-p3-w5-status.zip")
    raw=source_bytes()
    output={
        "phase":PHASE, "state":"REVIEW_REQUIRED",
        "source_head":HEAD, "failure_category":"", "source_worktree":"CLEAN",
        **SUCCESS,
    }
    if result:output.update(result)
    first={
        "schema_version":1,"run_id":RUN,"phase":PHASE,
        "state":"READY_NOT_TESTED","product_acceptance":"NOT_TESTED",
        "rules":{"synthetic_only":True,"no_auto_delete":True,"no_model_or_installer":True},
    }
    if baseline:first.update(baseline)
    last={
        "run_id":RUN,"phase":PHASE,"project_id":PID,"issue_id":"c"*64,
        "source_relative":"datasets/"+"d"*32+".csv",
        "original_sha256":hashlib.sha256(raw).hexdigest(),
        "original_bytes":len(raw),"rows":36,"version":0,"expected_changed_cells":2,
    }
    if fixture:last.update(fixture)
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("result.json",json.dumps(output))
        z.writestr("manifest.json",json.dumps(first))
        z.writestr("p3-native-w5-manifest.json",json.dumps(last))
        if other:z.writestr(other,"USER-DATA-MUST-NOT-ENTER-EVIDENCE")
    return path


def test_valid_synthetic_archive_is_only_status_integrity_pass(tmp_path):
    sample=_archive(tmp_path)
    result=inspect_archive(sample,expected_source=HEAD)
    assert result["verdict"]=="STATUS_ARCHIVE_INTEGRITY_PASS"
    assert result["native_acceptance"]=="PENDING_INDEPENDENT_REVIEW"
    assert result["owner_native_observation"]=="OWNER_REPORTED_PASS_NOT_INDEPENDENTLY_OBSERVED"
    assert result["product_acceptance"]=="NOT_TESTED"
    assert result["source_sha_matches_supplied_expectation"] is True
    assert result["archive_sha256"]==hashlib.sha256(sample.read_bytes()).hexdigest()


def test_expected_untracked_tauri_artifacts_do_not_falsely_fail_archive(tmp_path):
    sample = _archive(tmp_path, result={
        "source_worktree": "TRACKED_CLEAN_EXPECTED_UNTRACKED_TAURI"
    })
    out = inspect_archive(sample, expected_source=HEAD)
    assert out["verdict"] == "STATUS_ARCHIVE_INTEGRITY_PASS"
    assert out["source_worktree_reported"] == "TRACKED_CLEAN_EXPECTED_UNTRACKED_TAURI"
    assert out["native_acceptance"] == "PENDING_INDEPENDENT_REVIEW"


def test_refuses_non_exact_untracked_tauri_status(tmp_path):
    sample = _archive(tmp_path, result={
        "source_worktree": "TRACKED_CLEAN_WITH_OTHER_UNTRACKED"
    })
    with pytest.raises(ArchiveRefused, match="source was not clean"):
        inspect_archive(sample)


def test_refuses_wrong_sha_or_wrong_phase(tmp_path):
    sample=_archive(tmp_path)
    with pytest.raises(ArchiveRefused, match="source SHA"):
        inspect_archive(sample,expected_source="f"*40)
    bad=_archive(tmp_path,result={"phase":"P4-NOT-W5"})
    with pytest.raises(ArchiveRefused, match="phase"):
        inspect_archive(bad)


@pytest.mark.parametrize("changed",[
    {"original_sha256":"0"*64},{"rows":37},
    {"expected_changed_cells":3},{"source_relative":"../owner/records.csv"},
    {"source_relative":"C:/Users/owner/records.csv"},
    {"source_relative":"datasets/../../private.csv"},
    {"project_id":"not-an-id"},{"original_bytes":0},
])
def test_refuses_untrusted_fixture_metadata(tmp_path,changed):
    sample=_archive(tmp_path,fixture=changed)
    with pytest.raises(ArchiveRefused):
        inspect_archive(sample)


@pytest.mark.parametrize("changed",[
    {"source_worktree":"UNCOMMITTED_OWNER_WORK"},
    {"functional_state":"NOT_TESTED"},
    {"native_shutdown_status":"FAIL_NONZERO_EXIT"},
    {"functional_failure_category":"INCOMPLETE"},
    {"owner_native_ui":"NOT_OBSERVED"},
    {"request_audit":"NOT_CHECKED"},
    {"historical_semantic_context":"NOT_CHECKED"},
    {"quality_version":"NOT_CHECKED"},
    {"product_acceptance":"ACCEPTED"},
    {"failure_category":"CONNECTION_ERROR"},
    {"installer":"BUILT"},
])
def test_refuses_false_success_or_forbidden_scope(tmp_path,changed):
    sample=_archive(tmp_path,result=changed)
    with pytest.raises(ArchiveRefused):
        inspect_archive(sample)


def test_functional_pass_still_cannot_certify_failed_native_close(tmp_path):
    archive=_archive(tmp_path,result={
        "state":"FAIL_OR_BLOCKED", "functional_state":"PASS",
        "native_shutdown_status":"FAIL_NONZERO_EXIT", "native_mode":"NOT_TESTED",
        "owner_native_ui":"NOT_OBSERVED",
    })
    assert inspect_archive(archive)["verdict"]=="NOT_ACCEPTED"


def test_does_not_certify_failed_native_test(tmp_path):
    sample=_archive(tmp_path,result={"state":"FAIL_OR_BLOCKED","owner_native_ui":"NOT_OBSERVED"})
    result=inspect_archive(sample)
    assert result["verdict"]=="NOT_ACCEPTED"
    assert result["native_acceptance"]=="PENDING_INDEPENDENT_REVIEW"
    assert main([str(sample)])==2


def test_refuses_embedded_private_file(tmp_path):
    sample=_archive(tmp_path,other="owner.csv")
    with pytest.raises(ArchiveRefused,match="three flat"):
        inspect_archive(sample)


def test_refuses_duplicate_json_keys(tmp_path):
    sample=_archive(tmp_path)
    with zipfile.ZipFile(sample,"r") as z:
        records={name:z.read(name) for name in z.namelist()}
    records["result.json"]=records["result.json"].replace(b'{',b'{"phase":"MALICIOUS",',1)
    with zipfile.ZipFile(sample,"w",zipfile.ZIP_DEFLATED) as z:
        for name,value in records.items():z.writestr(name,value)
    with pytest.raises(ArchiveRefused,match="Duplicate JSON key"):
        inspect_archive(sample)


def test_refuses_baseline_synthetic_policy_waiver(tmp_path):
    sample=_archive(tmp_path,baseline={"rules":{"synthetic_only":False,
        "no_auto_delete":True,"no_model_or_installer":True}})
    with pytest.raises(ArchiveRefused,match="isolation"):
        inspect_archive(sample)


def test_no_zip_extract_or_qa_run_side_effects(tmp_path):
    sample=_archive(tmp_path)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    assert inspect_archive(sample)["verdict"]=="STATUS_ARCHIVE_INTEGRITY_PASS"
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before
