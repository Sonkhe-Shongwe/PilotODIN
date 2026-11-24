"""Read-only source map for N12 protected-writer vs actual desktop integration.

This is a source-contract review only. It does not execute Windows, inspect
owner files, assert default WebView2 token identity, or grant native acceptance.
"""
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
FILES = {
    "rust": "frontend/src-tauri/src/lib.rs",
    "config": "frontend/src-tauri/tauri.conf.json",
    "runner": "backend/desktop_runner.py",
    "qa_ambient": "qa/p4_research/n12_ambient_local_candidate.py",
    "token_probe": "qa/p4_research/n12_token_capability_preflight.py",
    "fixture": "qa/p4_research/n12_protected_fixture_contract.py",
}
SCOPE = "n12-product-tree-isolation-source-review-v1"


def load_sources(root=ROOT):
    """Read only explicitly listed tracked source paths, never an owner-data root."""
    return {name: (root / path).read_text(encoding="utf-8")
            for name, path in FILES.items()}


def _function(source, name):
    match = re.search(r"(?m)^(?:async )?fn " + re.escape(name) + r"\(", source)
    if match is None:
        return ""
    # Only audit the named Rust function, not comments or a different worker.
    tail = source[match.start():]
    boundary = re.search(r"(?m)^(?:(?:pub )?(?:async )?fn |const )", tail[len(match.group(0)):])
    return tail[:len(match.group(0)) + boundary.start()] if boundary else tail


def _all(source, *fragments):
    return all(fragment in source for fragment in fragments)


def review_source_topology(sources):
    """Return fixed-label evidence gaps; string checks are NOT runtime proof."""
    issues = []
    if type(sources) is not dict or set(sources) != set(FILES) or any(
            type(value) is not str for value in sources.values()):
        return _report(["source-input-invalid"])
    rust = sources["rust"]
    backend = _function(rust, "launch_backend")
    ai = _function(rust, "launch_bundled_ai")
    checks = {
        "desktop-webview-builder": _all(
            rust, "pub fn run()", "tauri::Builder::default()"),
        "backend-shell-child": _all(
            backend, '.shell().sidecar("pilotodin-engine")', "command.spawn()",
            '.current_dir(&data_dir)', '.env("PILOTODIN_HOME",',
            '.env("TEMP", worker_temp.as_os_str())',
            '.env("TMP", worker_temp.as_os_str())',
            '.env("TMPDIR", worker_temp.as_os_str())',
            ".set_process_group(true)"),
        "inference-shell-child": _all(
            ai, '.shell().sidecar("pilotodin-inference")', "command.spawn()",
            '.current_dir(&runtime_dlls)',
            '.env("TEMP", worker_temp.as_os_str())',
            '.env("TMP", worker_temp.as_os_str())',
            '.env("TMPDIR", worker_temp.as_os_str())',
            ".set_process_group(true)"),
        "application-owned-worker-home": _all(
            rust, "app.path().app_local_data_dir()", "worker_temp_directory(",
            '"backend-temp"', '"inference-temp"'),
        "desktop-backend-session": _all(
            sources["runner"], "PILOTODIN_DESKTOP_SESSION",
            "PILOTODIN_HOME", 'host="127.0.0.1"'),
        "qa-only-ambient-variant": _all(
            sources["qa_ambient"], "QA-only", "apply_to_app_env(",
            '"LOCALAPPDATA"', '"APPDATA"', '"native_filesystem_containment": "NOT_VERIFIED"'),
        "read-only-token-capability": _all(
            sources["token_probe"], "inspect_api_surface(",
            '"restricted_writer_launched": False',
            '"file_protection_verified": False',
            '"native_N12_acceptance": "NOT_EVALUATED"'),
        "generated-writer-only-fixture": _all(
            sources["fixture"], "restricted-primary-token",
            '"owner_native_execution_authorized": False',
            '"native_N12_acceptance": "NOT_EVALUATED"'),
    }
    try:
        config = json.loads(sources["config"])
    except (ValueError, TypeError):
        config = {}
    windows = config.get("app", {}).get("windows", []) if type(config) is dict else []
    checks["configured-webview-main"] = (
        type(windows) is list
        and any(type(row) is dict and row.get("label") == "main" for row in windows)
        and config.get("identifier") == "com.pilotodin.studio"
    )
    checks["declared-sidecar-pair"] = (
        type(config) is dict
        and type(config.get("bundle")) is dict
        and config["bundle"].get("externalBin") == [
            "binaries/pilotodin-engine", "binaries/pilotodin-inference"]
    )
    # This is a precise reviewed-source fingerprint check, not a claim that
    # third-party Tauri or WebView2 runtime cannot restrict its own children.
    if any(marker in rust for marker in (
            "CreateRestrictedToken", "CreateProcessAsUserW",
            "SetNamedSecurityInfoW", "CREATE_RESTRICTED_TOKEN")):
        issues.append("product-security-launch-source-changed-review-required")
    issues.extend(label + "-source-drift" for label, present in checks.items() if not present)
    return _report(issues)


def _report(issues):
    """No caller-supplied claim can produce containment or N12 PASS."""
    return {
        "scope": SCOPE,
        "review_status": "SOURCE_MATCH" if not issues else "SOURCE_DRIFT_BLOCKED",
        "issues": sorted(set(issues)),
        "generated_writer_restriction": "CONTROL_ONLY_NOT_PRODUCT_PROOF",
        "tauri_parent_token_evidence": "NOT_COLLECTED",
        "webview2_process_token_evidence": "NOT_COLLECTED",
        "backend_worker_token_evidence": "NOT_COLLECTED",
        "inference_worker_token_evidence": "NOT_COLLECTED",
        "fileio_complete_runtime_evidence": "NOT_COLLECTED",
        "qa_ambient_redirect_native_effect": "NOT_VERIFIED",
        "conclusion": "PRODUCT_PROCESS_TREE_CONTAINMENT_NOT_DEMONSTRATED",
        "decision": "DO_NOT_PROMOTE_RESTRICTED_WRITER_TO_R02_5",
        "windows_token_or_acl_operations_performed": False,
        "native_app_launched": False,
        "native_N12_acceptance": "NOT_EVALUATED",
        "file_mutation_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }


def main():
    try:
        result = review_source_topology(load_sources())
    except (OSError, ValueError, UnicodeError):
        result = _report(["review-source-unavailable"])
    print(json.dumps(result, sort_keys=True))
    return 0 if result["review_status"] == "SOURCE_MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
