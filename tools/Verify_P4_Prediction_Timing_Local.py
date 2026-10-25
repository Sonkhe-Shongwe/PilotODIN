#!/usr/bin/env python3
"""Isolated P4 risk-review gate: changed Python, Node contracts and TS/Vite."""
from __future__ import annotations

import json, os, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]

def main() -> int:
    folder=Path(tempfile.mkdtemp(prefix="pilotodin-p4-timing-"))
    isolated=folder/"isolated-home"
    isolated.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(isolated)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    node=shutil.which("node.exe") or shutil.which("node")
    npm=shutil.which("npm.cmd") or shutil.which("npm")
    phases=[
        ("p4-timing-backend",[sys.executable,"-m","pytest","-q",
            "tests/test_p4_prediction_timing_review.py",
            "tests/test_p4_target_business_context.py",
            "tests/test_p4_target_opportunities.py"],ROOT),
        ("p4-timing-node",[node,"--test",
            "tests/p4-prediction-timing-contracts.test.cjs",
            "tests/p4-business-context-contracts.test.cjs",
            "tests/p4-target-opportunities-contracts.test.cjs"],ROOT/"frontend"),
        ("frontend-typescript-vite",[npm,"run","build"],ROOT/"frontend"),
    ]
    results=[]
    for name,command,cwd in phases:
        start=time.monotonic()
        log=folder/(name+".log")
        if not command[0]:
            log.write_text("Missing local Node/npm executable.\n",encoding="utf-8")
            rc=-1
        else:
            try:
                with log.open("w",encoding="utf-8",errors="replace") as output:
                    rc=subprocess.run(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                                      stdout=output,stderr=subprocess.STDOUT,
                                      timeout=360,check=False).returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                with log.open("a",encoding="utf-8",errors="replace") as output:
                    output.write(type(exc).__name__+": "+str(exc))
                rc=-1
        results.append({"phase":name,"status":"PASS" if rc==0 else "FAIL",
                        "exit_code":rc,"elapsed_seconds":round(time.monotonic()-start,2),
                        "log":log.name})
        print(name+": "+results[-1]["status"],flush=True)
        if rc:
            print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-26:]))
    report={
        "scope":"P4 read-only prediction timing/label provenance questions",
        "utc":datetime.now(timezone.utc).isoformat(),
        "overall":"PASS" if all(row["status"]=="PASS" for row in results) else "FAIL",
        "phases":results,"synthetic_tests_only":True,"original_datasets_accessed":False,
        "model_training":"NOT_RUN","native_tauri_smoke":"NOT_RUN",
        "verified_business_meanings":"NOT_CLAIMED",
        "e2_offline_qwen_8gb":"NOT_RUN","older_p0_p5_suites":"NOT_RERUN"
    }
    (folder/"result.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    archive=folder.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as z:
        for file in sorted(folder.glob("*.log"))+[folder/"result.json"]:
            z.write(file,arcname=file.name)
    print("P4 timing review gate:",report["overall"])
    print("One diagnostics ZIP (may contain local paths):",archive)
    return 0 if report["overall"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
