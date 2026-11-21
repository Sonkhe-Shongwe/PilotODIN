#!/usr/bin/env python3
"""P4 business-context persistence acceptance, isolated synthetic-only gate."""
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
    report=Path(tempfile.mkdtemp(prefix="pilotodin-p4-context-"))
    isolated=report / "isolated-home"
    isolated.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(isolated)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    node=shutil.which("node.exe") or shutil.which("node")
    npm=shutil.which("npm.cmd") or shutil.which("npm")
    phases=[
        ("p4-context-backend",
         [sys.executable,"-m","pytest","-q",
          "tests/test_p4_target_business_context.py","tests/test_p4_target_opportunities.py"],
         ROOT),
        ("p4-context-ui-contracts",
         [node,"--test","tests/p4-business-context-contracts.test.cjs",
          "tests/p4-target-opportunities-contracts.test.cjs"],ROOT/"frontend"),
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
        "scope":"P4 project/version-bound user-provided business context and conservative recommendation ordering",
        "utc":datetime.now(timezone.utc).isoformat(),
        "overall":"PASS" if all(p["status"]=="PASS" for p in results) else "FAIL",
        "phases":results,
        "synthetic_tests_only":True,
        "original_datasets_accessed":False,
        "percent_or_eta_inferred":"NO",
        "real_native_tauri_smoke":"NOT_RUN",
        "business_semantics_user_described":"POSSIBLE; NEVER INDEPENDENTLY VERIFIED",
        "real_offline_qwen_8gb":"NOT_TESTED",
        "full_p0_a4_regressions":"NOT_RERUN",
    }
    (report/"result.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
    zip_path=report.with_suffix(".zip")
    with ZipFile(zip_path,"w",ZIP_DEFLATED) as z:
        for file in sorted(report.glob("*.log"))+[report/"result.json"]:
            z.write(file,arcname=file.name)
    print("P4 target opportunity acceptance:",output["overall"])
    print("Existing project datasets/models not modified by this focused check.")
    print("Single diagnostics ZIP (logs may contain local paths):",zip_path)
    return 0 if output["overall"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
