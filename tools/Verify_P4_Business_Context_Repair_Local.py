#!/usr/bin/env python3
"""P4 focused repair: affected Node source contracts and frontend compilation only."""
from __future__ import annotations
import json, os, shutil, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    report = Path(tempfile.mkdtemp(prefix="pilotodin-p4-context-repair-"))
    env = os.environ.copy()
    isolated = report / "isolated-home"
    isolated.mkdir()
    env["PILOTODIN_HOME"] = str(isolated)
    node = shutil.which("node.exe") or shutil.which("node")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    phases = [
        ("p4-context-ui-contracts", [node, "--test",
         "tests/p4-business-context-contracts.test.cjs",
         "tests/p4-target-opportunities-contracts.test.cjs"], ROOT / "frontend"),
        ("frontend-typescript-vite", [npm, "run", "build"], ROOT / "frontend"),
    ]
    results = []
    for name, command, cwd in phases:
        log = report / (name + ".log")
        start = time.monotonic()
        if not command[0]:
            log.write_text("Missing Node or npm in PATH.\n", encoding="utf-8")
            rc = -1
        else:
            try:
                with log.open("w", encoding="utf-8", errors="replace") as output:
                    rc = subprocess.run(command, cwd=cwd, env=env,
                        stdin=subprocess.DEVNULL, stdout=output,
                        stderr=subprocess.STDOUT, timeout=360,
                        check=False).returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                with log.open("a", encoding="utf-8") as output:
                    output.write(type(exc).__name__ + ": " + str(exc))
                rc = -1
        results.append({"phase":name,"status":"PASS" if rc == 0 else "FAIL",
                        "exit_code":rc,"elapsed_seconds":round(time.monotonic()-start,2),
                        "log":log.name})
        print(name + ": " + results[-1]["status"], flush=True)
        if rc:
            print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-24:]))
    data = {
        "scope":"P4 JSX syntax and two updated source contract expectations",
        "utc":datetime.now(timezone.utc).isoformat(),
        "overall":"PASS" if all(p["status"]=="PASS" for p in results) else "FAIL",
        "phases":results,"synthetic_tests_only":True,
        "original_datasets_accessed":False,
        "previous_backend_17_pass":"RETAINED_FROM_OWNER_DIAGNOSTIC_NOT_RERUN",
        "native_tauri_offline_qwen_8gb":"NOT_TESTED",
    }
    (report/"result.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    archive=report.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as z:
        for file in sorted(report.glob("*.log")) + [report/"result.json"]:
            z.write(file,arcname=file.name)
    print("P4 repair:",data["overall"],"\nDiagnostic ZIP:",archive,
          "\nOnly affected UI and build checked; no existing dataset operations.")
    return 0 if data["overall"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
