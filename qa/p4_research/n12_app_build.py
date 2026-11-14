"""Stage one approved unpackaged Windows QA build before the trace starts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from qa.p4_native.n12_trace import EvidenceValidationError, local_disposable_path, require


REPO = Path(__file__).resolve().parents[2]
CRATE = REPO / "frontend" / "src-tauri"
TARGET = "x86_64-pc-windows-msvc"
EXE = "pilotodin-desktop.exe"
BRANCH = "feature/live-dev-workspace-20261023"
QA_ID = "com.pilotodin.p4isolatednativedev"
PROTECTED_IDS = ("com.pilotodin.studio", "com.pilotodin.p4nativeqa")
CONSENT = "I_APPROVE_UNPACKAGED_P4_NATIVE_DEV"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def stage_root(source):
    env = os.environ
    require(env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_REF_NAME") == BRANCH
            and env.get("GITHUB_RUN_ATTEMPT") == "1"
            and env.get("PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT") == CONSENT,
            "expected the approved first hosted Windows run")
    run_id = env.get("GITHUB_RUN_ID", "")
    require(re.fullmatch(r"[0-9]+", run_id) and re.fullmatch(r"[0-9a-f]{40}", source)
            and env.get("PILOTODIN_N12_APPROVED_SOURCE") == source,
            "expected a run ID and the approved source SHA")
    root = local_disposable_path(Path(env["RUNNER_TEMP"]) / f"pilotodin-n12-build-{run_id}",
                                 runner_temp_only=True)
    require(git("rev-parse", "HEAD") == source and not git("status", "--porcelain", "--untracked-files=no"),
            "checkout differs from the approved clean source")
    return root


def isolated_config():
    production, previous, isolated = [json.loads((CRATE / filename).read_text(encoding="utf-8"))
                                      for filename in ("tauri.conf.json", "tauri.p4-native-qa.conf.json",
                                                       "tauri.p4-isolated-native-dev.conf.json")]
    bundle = isolated["bundle"]
    require((production["identifier"], previous["identifier"], isolated["identifier"]) == (*PROTECTED_IDS, QA_ID)
            and bundle.get("active") is False and bundle.get("externalBin") == []
            and bundle.get("resources") == [] and "appDirectoriesOverride" not in production["app"]
            and "appDirectoriesOverride" not in isolated["app"]
            and isolated["build"] == {"beforeDevCommand": "npm run dev"}
            and production["build"]["devUrl"] == "http://127.0.0.1:5173",
            "isolated configuration does not match the reviewed QA application")
    require(not any((CRATE / name).exists() for name in (
        "tauri.windows.conf.json", "tauri.windows.conf.json5", "Tauri.windows.toml",
    )), "unexpected platform configuration override")
    return json.dumps(isolated, separators=(",", ":"))


def executable(root):
    return root / "cargo" / TARGET / "debug" / EXE


def stage(root, source):
    require(not any(os.environ.get(key) for key in ("PILOTODIN_HOME", "WEBVIEW2_USER_DATA_FOLDER", "TAURI_CONFIG")),
            "unexpected inherited app data or build configuration")
    for key in ("LOCALAPPDATA", "APPDATA"):
        for identifier in (*PROTECTED_IDS, QA_ID):
            require(not os.path.lexists(Path(os.environ[key]) / identifier), "app data identity already exists")

    config = isolated_config()
    root.mkdir(exist_ok=False)
    target_dir = root / "cargo"
    # Tauri's build script and generate_context! both merge this same overlay.
    # Cargo's build command leaves the executable stopped for the collectors.
    env = {**os.environ, "TAURI_CONFIG": config, "CARGO_TARGET_DIR": str(target_dir)}
    subprocess.run(["cargo", "build", "--bin", "pilotodin-desktop", "--target", TARGET,
                    "--target-dir", str(target_dir)], cwd=CRATE, env=env, check=True)
    require(git("rev-parse", "HEAD") == source and not git("status", "--porcelain", "--untracked-files=no"),
            "source changed during staging")
    binary = local_disposable_path(executable(root), runner_temp_only=True)
    record = {"source_sha": source, "executable_sha256": digest(binary),
              "cargo_lock_sha256": digest(CRATE / "Cargo.lock"), "app_identifier": QA_ID,
              "run_id": os.environ["GITHUB_RUN_ID"]}
    with (root / "build.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
    return record


def verify(root, source, expected_hash):
    binary = local_disposable_path(executable(root), runner_temp_only=True)
    manifest = local_disposable_path(root / "build.json", runner_temp_only=True)
    record = json.loads(manifest.read_text(encoding="utf-8"))
    require(re.fullmatch(r"[0-9a-f]{64}", expected_hash)
            and record["source_sha"] == source and record["app_identifier"] == QA_ID
            and record["run_id"] == os.environ["GITHUB_RUN_ID"]
            and record["cargo_lock_sha256"] == digest(CRATE / "Cargo.lock")
            and record["executable_sha256"] == expected_hash == digest(binary),
            "staged binary provenance, executable hash or dependency lock differs")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("stage", "verify"))
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-exe-sha256")
    args = parser.parse_args()
    if (args.mode == "verify") != (args.expected_exe_sha256 is not None):
        parser.error("--expected-exe-sha256 is required only for verification")
    try:
        root = stage_root(args.source)
        record = (stage(root, args.source) if args.mode == "stage"
                  else verify(root, args.source, args.expected_exe_sha256))
        print(json.dumps(record))
        return 0
    except EvidenceValidationError as exc:
        print(f"N12 build blocked: {exc}.", file=sys.stderr)
        return 2
    except (KeyError, OSError, ValueError, subprocess.SubprocessError):
        print("N12 build staging or verification blocked. Check the runner and staged evidence.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
