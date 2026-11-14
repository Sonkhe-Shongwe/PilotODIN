#!/usr/bin/env python3
"""P5 focused Windows regression: atomic training slot and interrupted statuses.

No real user projects; no Qwen, installer, native Save As or full P0 replay.
"""
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
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    report=Path(tempfile.mkdtemp(prefix="pilotodin-p5-slot-"))
    isolated=report / "test-only-home"
    isolated.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(isolated)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    node=shutil.which("node.exe") or shutil.which("node")
    phases=[
        ("p5-sqlite-and-p1-admission",
         [sys.executable,"-m","pytest","-q",
          "tests/test_p5_ml_training_slot.py",
          "tests/test_p1_resource_admission.py"],
         ROOT),
        ("p5-frontend-source-contracts",
         [node,"--test","tests/p5-ml-training-slot-contracts.test.cjs"],
         ROOT / "frontend"),
    ]
    outcome=[]
    for name,command,cwd in phases:
        started=time.monotonic()
        log=report / (name+".log")
        if not command[0]:
            log.write_text("Required local runtime unavailable.\n",encoding="utf-8")
            rc=-1
        else:
            try:
                with log.open("w",encoding="utf-8",errors="replace") as output:
                    result=subprocess.run(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                                          stdout=output,stderr=subprocess.STDOUT,
                                          timeout=240,check=False)
                rc=result.returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                with log.open("a",encoding="utf-8") as output:
                    output.write(type(exc).__name__+": "+str(exc))
                rc=-1
        row={"phase":name,"result":"PASS" if rc==0 else "FAIL",
             "exit_code":rc,"seconds":round(time.monotonic()-started,2),
             "log":log.name}
        outcome.append(row)
        print(name+": "+row["result"],flush=True)
        if rc:
            print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-24:]))
    result={
        "scope":"P5 single-slot low-memory ML admission + worker restart recovery",
        "checked_utc":datetime.now(timezone.utc).isoformat(),
        "result":"PASS" if all(p["result"]=="PASS" for p in outcome) else "FAIL",
        "phases":outcome,
        "synthetic_data_only":True,
        "frontend_application_changed":False,
        "native_tauri_inference_test":"NOT_RUN",
        "durable_general_scheduler":"NOT_IMPLEMENTED",
        "all_p0_a4_regressions":"NOT_RERUN",
        "qwen_offline_8gb_certificate":"NOT_TESTED",
    }
    (report/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    archive=report.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as z:
        for file in sorted(report.glob("*.log"))+[report/"result.json"]:
            z.write(file,arcname=file.name)
    print("PilotODIN P5 focused regression:",result["result"])
    print("Safe isolated synthetic tests; no original datasets or models were changed.")
    print("Diagnostic ZIP (logs can contain local paths):",archive)
    return 0 if result["result"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
