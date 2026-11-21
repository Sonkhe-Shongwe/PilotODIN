"""Source-only WebView2 storage mechanism and falsification map for N12 R02.5.

Checks reviewed source seams and documents independent evidence requirements.
No imports of launcher code, Windows calls, browser launches, or private file reads.
No input can award native acceptance or prove the cause of a prior write.
"""
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCOPE = "n12-webview-storage-source-mechanism-v1"
FILES = {
    "production_config": "frontend/src-tauri/tauri.conf.json",
    "qa_config": "frontend/src-tauri/tauri.p4-isolated-native-dev.conf.json",
    "rust_supervisor": "frontend/src-tauri/src/lib.rs",
    "n12_journey": "qa/p4_research/n12_app_journey.py",
    "no_cdp": "qa/p4_research/n12_no_cdp_native_path.py",
    "qa_ambient": "qa/p4_research/n12_ambient_local_candidate.py",
}
HYPOTHESES = (
    {
        "id": "H1-ambient-variable",
        "question": "Do browser-owned outside writes follow inherited LOCALAPPDATA or APPDATA?",
        "discriminator": "same scoped binary and runtime; independent browser process identity, startup environment, exact path-family shift under QA-only ambient variant",
        "negative_control": "identical UDF, temp, browser arguments and protected policy; no claim when collector coverage is incomplete",
    },
    {
        "id": "H2-effective-udf",
        "question": "Was WebView2's effective UDF different from the QA-requested UDF?",
        "discriminator": "independently corroborate effective UDF, source-pinned environment and relevant policy/registry overrides for the actual browser process",
        "negative_control": "requested WEBVIEW2_USER_DATA_FOLDER alone never proves an effective UDF or complete file isolation",
    },
    {
        "id": "H3-runtime-other-storage",
        "question": "Are independently attributed browser operations outside a verified correct UDF?",
        "discriminator": "independent FileIO operation and resolved path tied to original browser/child handle and capture bounds",
        "negative_control": "no attribution to Crashpad, cache, OS Known Folder or WebView runtime without actual path and owner",
    },
    {
        "id": "H4-debug-netlog",
        "question": "Are outside writes specific to the debugging/netlog QA launch variant?",
        "discriminator": "same source/runtime and independently calibrated comparable browser-flag receipts; debug/no-CDP differences are not controlled by themselves",
        "negative_control": "ProcMon loss-unreviewed A/B comparison cannot establish complete capture or cause",
    },
    {
        "id": "H5-actor-identity",
        "question": "Did the attributed operation belong to the observed scoped WebView2 process lifetime?",
        "discriminator": "original PID+birth, image, parent, captured original handle, Sysmon/ETW identity and FileIO handle/path attribution",
        "negative_control": "no parent-PID-only identity, process-name-only classification, or invented missing WebView2 original handles",
    },
    {
        "id": "H6-completeness",
        "question": "Were capture loss, background paths and lifecycle evidence complete?",
        "discriminator": "independently validated ETW event/buffer loss, FileIO rundown, zero unresolved paths/identities and positive transient-control visibility",
        "negative_control": "matched endpoint fingerprints or diagnostic path credits never establish absence of transient mutation",
    },
)


def read_sources(root=ROOT):
    """Read only explicit repository source locations; never inspect owner data."""
    return {key: (root / name).read_text(encoding="utf-8")
            for key, name in FILES.items()}


def _function(source, name):
    """Read a Python function's actual AST span, not incidental comments elsewhere."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, TypeError, RecursionError):
        return ""
    matching = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == name]
    if len(matching) != 1:
        return ""
    return ast.get_source_segment(source, matching[0]) or ""


def _contains(body, *tokens):
    return all(token in body for token in tokens)


def hypothesis_plan():
    """Fixed source-backed possibilities, not a native receipt or diagnosis."""
    return [{**row, "causality": "UNRESOLVED", "native_evidence": "NOT_COLLECTED"}
            for row in HYPOTHESES]


def _report(issues, configured):
    return {
        "scope": SCOPE,
        "source_status": "SOURCE_MATCH" if not issues else "SOURCE_DRIFT_BLOCKED",
        "issues": sorted(set(issues)),
        "production_window_storage": configured,
        "qa_standard_storage": "UDF_AND_TEMP_DECLARED_DEBUG_NETLOG",
        "qa_no_cdp_storage": "UDF_AND_TEMP_DECLARED_NO_DEBUG_ARGUMENTS",
        "qa_ambient_variant": "DEFAULT_OFF_SOURCE_ONLY_CANDIDATE",
        "qa_ambient_native_effect": "NOT_VERIFIED",
        "effective_udf_observed": False,
        "webview_child_fileio_attributed": False,
        "webview_child_token_verified": False,
        "cause_of_outside_writes": "UNKNOWN",
        "hypotheses": hypothesis_plan(),
        "next_decision": "PIN_SOURCE_AND_DESIGN_INDEPENDENT_NATIVE_DISCRIMINATOR",
        "native_app_launched": False,
        "acl_modified": False,
        "native_N12_acceptance": "NOT_EVALUATED",
        "file_mutation_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }


def inspect_sources(sources):
    issues = []
    if type(sources) is not dict or set(sources) != set(FILES) or any(
            type(value) is not str for value in sources.values()):
        return _report(["source-input-invalid"], "NOT_VERIFIED")
    try:
        conf = json.loads(sources["production_config"])
        overlay = json.loads(sources["qa_config"])
    except (ValueError, TypeError):
        return _report(["tauri-config-invalid"], "NOT_VERIFIED")
    if type(conf) is not dict or type(overlay) is not dict:
        return _report(["tauri-config-invalid"], "NOT_VERIFIED")
    app = conf.get("app")
    qa = overlay.get("app")
    windows = app.get("windows") if type(app) is dict else None
    qa_windows = qa.get("windows") if type(qa) is dict else None
    if (type(windows) is not list or len(windows) != 1 or
            type(windows[0]) is not dict or windows[0].get("label") != "main" or
            conf.get("identifier") != "com.pilotodin.studio"):
        issues.append("production-webview-window-source-drift")
        configured = "NOT_VERIFIED"
    elif "dataDirectory" in windows[0] or "additionalBrowserArgs" in windows[0]:
        issues.append("production-webview-storage-config-review-required")
        configured = "CUSTOM_SETTING_REVIEW_REQUIRED"
    else:
        configured = "NO_EXPLICIT_DATA_DIRECTORY_IN_WINDOW_CONFIG"
    if (type(qa_windows) is not list or len(qa_windows) != 1 or
            type(qa_windows[0]) is not dict or qa_windows[0].get("label") != "main" or
            overlay.get("identifier") != "com.pilotodin.p4isolatednativedev" or
            "dataDirectory" in qa_windows[0] or "additionalBrowserArgs" in qa_windows[0]):
        issues.append("isolated-qa-window-config-source-drift")
    if not _contains(sources["rust_supervisor"],
                     "tauri::Builder::default()", "tauri::generate_context!()",
                     "app.shell().sidecar", "worker_temp_directory("):
        issues.append("rust-launch-source-drift")
    standard = _function(sources["n12_journey"], "app_environment")
    if not _contains(standard, "temporary_environment(", '"WEBVIEW2_USER_DATA_FOLDER"',
                     '"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"',
                     "--remote-debugging-port=9331", "--log-net-log=",
                     "ambient_local.apply_to_app_env("):
        issues.append("standard-n12-webview-env-source-drift")
    temporary = _function(sources["n12_journey"], "temporary_environment")
    if not _contains(temporary, '"TEMP"', '"TMP"', '"TMPDIR"'):
        issues.append("n12-app-temp-source-drift")
    backend = _function(sources["n12_journey"], "backend_environment")
    driver = _function(sources["n12_journey"], "driver_environment")
    if not _contains(backend, '"PYTHONPATH"', '"backend-temp"', '"TEMP"', '"TMP"', '"TMPDIR"'):
        issues.append("standalone-backend-temp-source-drift")
    if not _contains(driver, "temporary_environment(", "DRIVER_TEMP_DIR"):
        issues.append("driver-temp-source-drift")
    no_cdp = _function(sources["no_cdp"], "no_cdp_environments")
    if (not _contains(no_cdp, "journey.temporary_environment(", '"WEBVIEW2_USER_DATA_FOLDER"',
                      "lifecycle.verify_opt_in_environment(")
            or any(value in no_cdp for value in (
                '"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"', "ambient_local.apply_to_app_env("))):
        issues.append("no-cdp-env-source-drift")
    ambient = sources["qa_ambient"]
    flag = _function(ambient, "enabled")
    apply = _function(ambient, "apply_to_app_env")
    if (not _contains(flag, "choice in (None, \"\", CANDIDATE)", "return choice == CANDIDATE")
            or not _contains(apply, '"LOCALAPPDATA"', '"APPDATA"',
                             '"WEBVIEW2_USER_DATA_FOLDER"', '"TEMP"', '"TMP"', '"TMPDIR"')
            or not _contains(ambient, '"native_filesystem_containment": "NOT_VERIFIED"')):
        issues.append("qa-ambient-opt-in-source-drift")
    return _report(issues, configured)


def main():
    try:
        report = inspect_sources(read_sources())
    except (OSError, ValueError, UnicodeError, RecursionError):
        report = _report(["review-source-unavailable"], "NOT_VERIFIED")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["source_status"] == "SOURCE_MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
