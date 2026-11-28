#!/usr/bin/env python3
"""P5 safe cancellation and soft deadline; isolated synthetic-only Windows gate."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    report=Path(tempfile.mkdtemp(prefix="pilotodin-p5-cancel-"))
    isolated=report / "isolated-home"
    isolated.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(isolated)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    node=shutil.which("node.exe") or shutil.which("node")
    npm=shutil.which("npm.cmd") or shutil.which("npm")
    phases=[
        ("p5-training-cancellation-backend",
         [sys.executable,"-m","pytest","-q",
          "tests/test_p5_training_cancellation.py","tests/test_p5_training_progress.py",
          "tests/test_p5_ml_training_slot.py","tests/test_p1_resource_admission.py"],
         ROOT),
        ("p5-training-cancellation-node",
         [node,"--test","tests/p5-training-cancellation-contracts.test.cjs",
          "tests/p5-training-progress-contracts.test.cjs",
          "tests/p5-ml-training-slot-contracts.test.cjs"],ROOT/"frontend"),
        ("frontend-typescript-vite",[npm,"run","build"],ROOT/"frontend"),
    ]
    results=[]
    for name,cmd,cwd in phases:
        started=time.monotonic()
        log=report / (name+".log")
        if not cmd[0]:
            log.write_text("Missing required local tool.\n",encoding="utf-8")
            rc=-1
        else:
            try:
                with log.open("w",encoding="utf-8",errors="replace") as output:
                    result=subprocess.run(cmd,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                                          stdout=output,stderr=subprocess.STDOUT,
                                          timeout=360,check=False)
                rc=result.returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                with log.open("a",encoding="utf-8",errors="replace") as output:
                    output.write(type(exc).__name__+": "+str(exc))
                rc=-1
        row={"phase":name,"status":"PASS" if rc==0 else "FAIL",
             "exit_code":rc,"elapsed_seconds":round(time.monotonic()-started,2),
             "log":log.name}
        results.append(row)
        print(name+": "+row["status"],flush=True)
        if rc:
            print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-24:]))
    output={
        "scope":"P5 cooperative queued/running cancellation and optional soft deadlines",
        "utc":datetime.now(timezone.utc).isoformat(),
        "overall":"PASS" if all(p["status"]=="PASS" for p in results) else "FAIL",
        "phases":results,
        "synthetic_tests_only":True,
        "original_datasets_accessed":False,
        "training_stop_is_cooperative":"YES",
        "real_native_tauri_smoke":"NOT_RUN",
        "durable_general_scheduler_or_safe_cancellation":"NOT_IMPLEMENTED",
        "real_offline_qwen_8gb":"NOT_TESTED",
        "full_p0_a4_regressions":"NOT_RERUN",
    }
    (report/"result.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
    zip_path=report.with_suffix(".zip")
    with ZipFile(zip_path,"w",ZIP_DEFLATED) as z:
        for file in sorted(report.glob("*.log"))+[report/"result.json"]:
            z.write(file,arcname=file.name)
    print("P5 training cancellation acceptance:",output["overall"])
    print("Existing project datasets/models not modified by this focused check.")
    print("Single diagnostics ZIP (logs may contain local paths):",zip_path)
    return 0 if output["overall"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
