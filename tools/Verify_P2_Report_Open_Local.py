#!/usr/bin/env python3
"""P2 source-contract and frontend build gate for report-open race repair."""
from __future__ import annotations
import json,os,shutil,subprocess,sys,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED,ZipFile

ROOT=Path(__file__).resolve().parents[1]
def main()->int:
    report=Path(tempfile.mkdtemp(prefix="pilotodin-p2-report-open-"))
    isolated=report/"isolated-home"
    isolated.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(isolated)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    node=shutil.which("node.exe") or shutil.which("node")
    npm=shutil.which("npm.cmd") or shutil.which("npm")
    phases=[
      ("p2-report-open-contracts",[node,"--test",
        "tests/p2-report-navigation-contracts.test.cjs",
        "tests/report-workflow-gates.test.cjs",
        "tests/explore-deliver-evidence.test.cjs",
        "tests/a4-native-report-save-contract.test.cjs"],ROOT/"frontend"),
      ("frontend-typescript-vite",[npm,"run","build"],ROOT/"frontend"),
    ]
    records=[]
    for name,cmd,cwd in phases:
        log=report/(name+".log")
        start=time.monotonic()
        if not cmd[0]:
            log.write_text("Missing Node/npm executable.\n",encoding="utf-8")
            rc=-1
        else:
            try:
                with log.open("w",encoding="utf-8",errors="replace") as f:
                    rc=subprocess.run(cmd,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                      stdout=f,stderr=subprocess.STDOUT,timeout=360,check=False).returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                with log.open("a",encoding="utf-8",errors="replace") as f:
                    f.write(type(exc).__name__+": "+str(exc))
                rc=-1
        records.append({"phase":name,"status":"PASS" if rc==0 else "FAIL","exit_code":rc,
                        "elapsed_seconds":round(time.monotonic()-start,2),"log":log.name})
        print(name+": "+records[-1]["status"],flush=True)
        if rc:
            print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-25:]))
    result={
      "scope":"P2 report opening latest-selection race, focused source contracts and TypeScript/Vite",
      "utc":datetime.now(timezone.utc).isoformat(),
      "overall":"PASS" if all(x["status"]=="PASS" for x in records) else "FAIL",
      "phases":records,"synthetic_or_source_contract_tests_only":True,
      "original_datasets_accessed":False,"native_real_ui_race":"NOT_TESTED",
      "model_or_report_revision_writes":"NOT_RUN",
      "qwen_installer_8gb":"NOT_TESTED","historic_suites":"NOT_RERUN"
    }
    (report/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    archive=report.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as z:
        for item in sorted(report.glob("*.log"))+[report/"result.json"]:
            z.write(item,arcname=item.name)
    print("P2 report Open navigation gate:",result["overall"])
    print("One diagnostic ZIP (may contain local paths):",archive)
    return 0 if result["overall"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
