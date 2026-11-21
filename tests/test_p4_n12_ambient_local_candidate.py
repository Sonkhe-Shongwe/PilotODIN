"""N12 QA-only LOCALAPPDATA/APPDATA candidate, source/fixture scope only."""
import os
from pathlib import Path

import pytest

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_ambient_local_candidate as candidate
from qa.p4_research import n12_app_journey as journey


def given(tmp_path):
    root = tmp_path / "pilotodin-n12-build-123-journey"
    root.mkdir()
    profile = root / "webview"
    profile.mkdir()
    (profile / journey.APP_TEMP_DIR).mkdir()
    before = {
        "LOCALAPPDATA": str(tmp_path / "original-host-local"),
        "APPDATA": str(tmp_path / "original-host-roaming"),
        "WEBVIEW2_USER_DATA_FOLDER": str(profile),
        "TEMP": str(profile / journey.APP_TEMP_DIR),
        "TMP": str(profile / journey.APP_TEMP_DIR),
        "TMPDIR": str(profile / journey.APP_TEMP_DIR),
    }
    return profile, before


def test_default_produces_identical_inherited_app_data_environment(tmp_path):
    profile, base = given(tmp_path)
    app = journey.app_environment(base, profile, "first")
    assert app["LOCALAPPDATA"] == base["LOCALAPPDATA"]
    assert app["APPDATA"] == base["APPDATA"]
    assert app["WEBVIEW2_USER_DATA_FOLDER"] == str(profile)
    assert not (profile / candidate.LOCAL_DIR).exists()
    assert candidate.public_receipt(base)["variant"] == "unchanged-baseline"


def test_opt_in_sets_only_app_local_and_roaming_beneath_disposable_profile(tmp_path):
    profile, base = given(tmp_path)
    base[candidate.FLAG] = candidate.CANDIDATE
    assert candidate.prepare(profile, tmp_path) == {
        "candidate": "prepared", "native_verified": False,
        "write_policy_broadened": False,
    }
    app = journey.app_environment(base, profile, "first")
    assert app["LOCALAPPDATA"] == str(profile / candidate.LOCAL_DIR)
    assert app["APPDATA"] == str(profile / candidate.ROAMING_DIR)
    assert app["TEMP"] == base["TEMP"]
    assert app["TMP"] == base["TMP"]
    assert app["TMPDIR"] == base["TMPDIR"]
    assert app["WEBVIEW2_USER_DATA_FOLDER"] == str(profile)
    assert base["LOCALAPPDATA"] != app["LOCALAPPDATA"]
    assert base["APPDATA"] != app["APPDATA"]
    assert candidate.public_receipt(base)["native_filesystem_containment"] == "NOT_VERIFIED"
    assert "original-host-local" not in str(candidate.public_receipt(base))


@pytest.mark.parametrize("bad", ["1", "true", "ISOLATED_QA_ROOT", "candidate", ""])
def test_invalid_modes_fail_closed_except_empty_is_baseline(tmp_path, bad):
    profile, base = given(tmp_path)
    base[candidate.FLAG] = bad
    if bad == "":
        assert candidate.enabled(base) is False
    else:
        with pytest.raises(trace.EvidenceValidationError, match="variant-unrecognised"):
            journey.app_environment(base, profile, "first")


def test_candidate_refuses_unprepared_directories(tmp_path):
    profile, base = given(tmp_path)
    base[candidate.FLAG] = candidate.CANDIDATE
    with pytest.raises(trace.EvidenceValidationError, match="directory-unverified"):
        journey.app_environment(base, profile, "first")


@pytest.mark.parametrize("key", ["TEMP", "TMP", "TMPDIR"])
def test_candidate_refuses_nonprofile_temp_without_widening_write_policy(tmp_path, key):
    profile, base = given(tmp_path)
    candidate.prepare(profile, tmp_path)
    base[candidate.FLAG] = candidate.CANDIDATE
    base[key] = base["LOCALAPPDATA"]
    with pytest.raises(trace.EvidenceValidationError, match="temp-unverified"):
        journey.app_environment(base, profile, "first")


def test_candidate_refuses_profile_outside_runner(tmp_path):
    profile, _ = given(tmp_path)
    other = tmp_path / "unrelated-runner"
    other.mkdir()
    with pytest.raises(trace.EvidenceValidationError, match="outside-runner"):
        candidate.prepare(profile, other)


def test_candidate_refuses_reuse_of_existing_target_and_never_overwrites(tmp_path):
    profile, _ = given(tmp_path)
    (profile / candidate.LOCAL_DIR).mkdir()
    with pytest.raises(trace.EvidenceValidationError, match="already-exists"):
        candidate.prepare(profile, tmp_path)


def test_candidate_refuses_mismatched_profile_identity(tmp_path):
    profile, base = given(tmp_path)
    candidate.prepare(profile, tmp_path)
    base[candidate.FLAG] = candidate.CANDIDATE
    base["WEBVIEW2_USER_DATA_FOLDER"] = str(tmp_path / "different")
    with pytest.raises(trace.EvidenceValidationError, match="profile-unverified"):
        candidate.apply_to_app_env(base, profile)


def test_candidate_refuses_symlink_marked_directory_even_without_real_windows_symlink(
        tmp_path, monkeypatch):
    profile, base = given(tmp_path)
    candidate.prepare(profile, tmp_path)
    base[candidate.FLAG] = candidate.CANDIDATE
    local = profile / candidate.LOCAL_DIR
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink",
                        lambda self: self == local or original(self))
    with pytest.raises(trace.EvidenceValidationError, match="directory-unverified"):
        candidate.apply_to_app_env(base, profile)


def test_only_app_environment_receives_candidate_override(tmp_path):
    profile, base = given(tmp_path)
    candidate.prepare(profile, tmp_path)
    base[candidate.FLAG] = candidate.CANDIDATE
    app = journey.app_environment(base, profile, "first")
    backend = journey.backend_environment(base)
    driver = journey.driver_environment(base, profile.parent)
    assert app["LOCALAPPDATA"] != backend["LOCALAPPDATA"] == driver["LOCALAPPDATA"]
    assert app["APPDATA"] != backend["APPDATA"] == driver["APPDATA"]


def test_candidate_never_mutates_global_environment(tmp_path):
    profile, base = given(tmp_path)
    candidate.prepare(profile, tmp_path)
    base[candidate.FLAG] = candidate.CANDIDATE
    prev = dict(os.environ)
    result = candidate.apply_to_app_env(base, profile)
    assert dict(os.environ) == prev
    assert base["LOCALAPPDATA"] != result["LOCALAPPDATA"]
