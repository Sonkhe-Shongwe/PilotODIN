"""Opt-in, QA-only candidate for WebView2 ambient user-local writes.

This does not assert that WebView2 honours inherited LOCALAPPDATA/APPDATA.
The production app configuration and strict N12 filesystem scope are unchanged.
Never use this as a native capture approval or a security isolation boundary.
"""
from pathlib import Path
import re

from qa.p4_native import n12_trace as trace

FLAG = "PILOTODIN_N12_QA_AMBIENT_LOCAL_VARIANT"
CANDIDATE = "ISOLATED_QA_ROOTS"
LOCAL_DIR = "ambient-local"
ROAMING_DIR = "ambient-roaming"
EXPECTED_ROOT = re.compile(r"pilotodin-n12-build-[0-9]+-journey")


def enabled(env):
    """An unknown value is a hard error, never an implicit baseline."""
    choice = env.get(FLAG)
    trace.require(choice in (None, "", CANDIDATE),
                  "n12-ambient-local-variant-unrecognised")
    return choice == CANDIDATE


def _profile(profile):
    path = Path(profile)
    trace.require(path.is_dir() and not path.is_symlink()
                  and path.name == "webview"
                  and EXPECTED_ROOT.fullmatch(path.parent.name)
                  and not path.parent.is_symlink(),
                  "n12-ambient-local-profile-unverified")
    return path, path.resolve(strict=True)


def prepare(profile, runner_temp):
    """Create only two new directories *inside* the existing QA profile.

    The existing separately approved N12 journey creates and owns the profile.
    This function is inert unless called by that journey's opt-in branch.
    """
    path, canonical = _profile(profile)
    runner = Path(runner_temp).resolve(strict=True)
    try:
        canonical.relative_to(runner)
    except ValueError as exc:
        raise trace.EvidenceValidationError(
            "n12-ambient-local-outside-runner") from exc
    trace.require(not runner.is_symlink() and path.parent.resolve() == canonical.parent,
                  "n12-ambient-local-parent-unverified")
    children = (path / LOCAL_DIR, path / ROAMING_DIR)
    trace.require(all(not child.exists() and not child.is_symlink()
                      for child in children),
                  "n12-ambient-local-already-exists")
    for child in children:
        child.mkdir()
        trace.require(child.is_dir() and not child.is_symlink()
                      and child.resolve(strict=True).parent == canonical,
                      "n12-ambient-local-directory-unverified")
    return {"candidate": "prepared", "native_verified": False,
            "write_policy_broadened": False}


def apply_to_app_env(env, profile):
    """Redirect only the N12 app process, not backend, driver or production."""
    if not enabled(env):
        return dict(env)
    path, canonical = _profile(profile)
    app_temp = path / "app-temp"
    trace.require(app_temp.is_dir() and not app_temp.is_symlink()
                  and app_temp.resolve(strict=True).parent == canonical,
                  "n12-ambient-local-temp-unverified")
    for key in ("TEMP", "TMP", "TMPDIR"):
        trace.require(env.get(key) == str(app_temp),
                      "n12-ambient-local-temp-unverified")
    trace.require(env.get("WEBVIEW2_USER_DATA_FOLDER") == str(path),
                  "n12-ambient-local-profile-unverified")
    for child_name in (LOCAL_DIR, ROAMING_DIR):
        child = path / child_name
        trace.require(child.is_dir() and not child.is_symlink()
                      and child.resolve(strict=True).parent == canonical,
                      "n12-ambient-local-directory-unverified")
    return {**env,
            "LOCALAPPDATA": str(path / LOCAL_DIR),
            "APPDATA": str(path / ROAMING_DIR)}


def public_receipt(env):
    """Fixed label only: no real user-local paths, SID, PID or profile text."""
    return {
        "scope": "source-only-qa-env-candidate",
        "variant": "isolated-qa-roots" if enabled(env) else "unchanged-baseline",
        "browser_runtime_inheritance": "NOT_VERIFIED",
        "native_filesystem_containment": "NOT_VERIFIED",
        "file_mutation_acceptance": "NOT_EVALUATED",
    }
