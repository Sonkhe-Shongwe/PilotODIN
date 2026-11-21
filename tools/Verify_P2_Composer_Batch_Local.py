#!/usr/bin/env python3
"""One P2 controlled batch: behavioral guard and affected UI regressions, then build."""
from __future__ import annotations
import json,os,shutil,subprocess,sys,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED,ZipFile

ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    folder=Path(tempfile.mkdtemp(prefix="pilotodin-p2-composer-batch-"))
    home=folder/"isolated-home"
    home.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(home)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    node=shutil.which("node.exe") or shutil.which("node")
    npm=shutil.which("npm.cmd") or shutil.which("npm")
    phases=[
     ("p2-composer-behavior-and-regressions",[node,"--test",
      "tests/p2-report-composer-behavior.test.cjs",
      "tests/p2-report-navigation-contracts.test.cjs",
      "tests/report-workflow-gates.test.cjs",
      "tests/explore-deliver-evidence.test.cjs",
      "tests/a4-native-report-save-contract.test.cjs"],ROOT/"frontend"),
     ("frontend-typescript-vite",[npm,"run","build"],ROOT/"frontend"),
    ]
    results=[]
    for name,cmd,cwd in phases:
        log=folder/(name+".log")
        started=time.monotonic()
        if not cmd[0]:
            log.write_text("Missing locally installed Node/npm executable.\n",encoding="utf-8")
            rc=-1
        else:
            try:
                with log.open("w",encoding="utf-8",errors="replace") as stream:
                    rc=subprocess.run(cmd,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                      stdout=stream,stderr=subprocess.STDOUT,timeout=360,check=False).returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                with log.open("a",encoding="utf-8",errors="replace") as stream:
                    stream.write(type(exc).__name__+": "+str(exc))
                rc=-1
        results.append({"phase":name,"status":"PASS" if rc==0 else "FAIL","exit_code":rc,
          "elapsed_seconds":round(time.monotonic()-started,2),"log":log.name})
        print(name+": "+results[-1]["status"],flush=True)
        if rc:print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-30:]))
    report={
      "scope":"P2 controlled batch: Save after draft edits, Quality capture after selection edits, truthful refresh failures",
      "utc":datetime.now(timezone.utc).isoformat(),
      "overall":"PASS" if all(x["status"]=="PASS" for x in results) else "FAIL",
      "phases":results,
      "synthetic_behavioral_controller_tests_and_source_contracts_only":True,
      "react_dom_browser_integration":"NOT_EXECUTED",
      "user_projects_or_reports_modified":False,
      "native_windows_export":"NOT_RERUN",
      "qwen_installer_e2_8gb":"NOT_TESTED"
    }
    (folder/"result.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    archive=folder.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as z:
        for p in sorted(folder.glob("*.log"))+[folder/"result.json"]:
            z.write(p,arcname=p.name)
    print("P2 composer controlled batch:",report["overall"])
    print("One diagnostic ZIP (local paths may appear):",archive)
    return 0 if report["overall"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
