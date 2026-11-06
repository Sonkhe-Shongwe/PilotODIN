#!/usr/bin/env python3
"""Isolated P2 report read/navigation batch: real TS gate behaviors plus relevant UI checks."""
from __future__ import annotations

import json,os,shutil,subprocess,sys,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    output=Path(tempfile.mkdtemp(prefix="pilotodin-p2-report-read-"))
    isolated=output/"isolated-home"
    isolated.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(isolated)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    node=shutil.which("node.exe") or shutil.which("node")
    npm=shutil.which("npm.cmd") or shutil.which("npm")
    phases=[
      ("p2-read-behavior-and-affected-regressions",[node,"--test",
        "tests/p2-report-read-safety.test.cjs",
        "tests/p2-report-composer-behavior.test.cjs",
        "tests/p2-report-navigation-contracts.test.cjs",
        "tests/report-workflow-gates.test.cjs",
        "tests/explore-deliver-evidence.test.cjs",
        "tests/a4-native-report-save-contract.test.cjs"],ROOT/"frontend"),
      ("frontend-typescript-vite",[npm,"run","build"],ROOT/"frontend"),
    ]
    result=[]
    for name,cmd,cwd in phases:
        started=time.monotonic()
        log=output/(name+".log")
        if not cmd[0]:
            log.write_text("Missing locally installed Node/npm executable.\n",encoding="utf-8")
            rc=-1
        else:
            try:
                with log.open("w",encoding="utf-8",errors="replace") as stream:
                    rc=subprocess.run(cmd,cwd=cwd,env=env,
                        stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                        timeout=360,check=False).returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                with log.open("a",encoding="utf-8",errors="replace") as stream:
                    stream.write(type(exc).__name__+": "+str(exc))
                rc=-1
        result.append({"phase":name,"status":"PASS" if rc==0 else "FAIL",
                       "exit_code":rc,"elapsed_seconds":round(time.monotonic()-started,2),
                       "log":log.name})
        print(name+": "+result[-1]["status"],flush=True)
        if rc:
            print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-30:]))
    summary={
      "scope":"P2 evidence-list latest read, superseded export, and edited-during-Open guard",
      "utc":datetime.now(timezone.utc).isoformat(),
      "overall":"PASS" if all(x["status"]=="PASS" for x in result) else "FAIL",
      "phases":result,
      "tests":"Executable TypeScript pure guard with deferred promises; existing Node source regression contracts; TypeScript/Vite",
      "original_project_data_touched":False,
      "native_tauri_real_ui":"NOT_RUN",
      "model_training_or_qwen":"NOT_RUN",
      "historic_p0_p1_p3_p4_p5":"NOT_RERUN"
    }
    (output/"result.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    archive=output.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as z:
        for file in sorted(output.glob("*.log"))+[output/"result.json"]:
            z.write(file,arcname=file.name)
    print("P2 report read-safety batch:",summary["overall"])
    print("One diagnostics ZIP (may contain local paths):",archive)
    return 0 if summary["overall"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
