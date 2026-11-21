#!/usr/bin/env python3
"""P2 repair-only owner check for the one stale navigation source-contract file."""
from __future__ import annotations

import json, os, shutil, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    output=Path(tempfile.mkdtemp(prefix="pilotodin-p2-read-repair-"))
    home=output/"isolated-home"
    home.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(home)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    node=shutil.which("node.exe") or shutil.which("node")
    log=output/"p2-navigation-contract-repair.log"
    started=time.monotonic()
    if node is None:
        log.write_text("Node is not installed or not in PATH.\n",encoding="utf-8")
        rc=-1
    else:
        try:
            with log.open("w",encoding="utf-8",errors="replace") as stream:
                rc=subprocess.run([node,"--test","tests/p2-report-navigation-contracts.test.cjs"],
                    cwd=ROOT/"frontend",env=env,stdin=subprocess.DEVNULL,
                    stdout=stream,stderr=subprocess.STDOUT,timeout=120,check=False).returncode
        except (OSError,subprocess.TimeoutExpired) as exc:
            with log.open("a",encoding="utf-8",errors="replace") as stream:
                stream.write(type(exc).__name__+": "+str(exc))
            rc=-1
    result={
        "scope":"P2 read-safety repair-only; stale project-reset source contract",
        "utc":datetime.now(timezone.utc).isoformat(),
        "overall":"PASS" if rc==0 else "FAIL",
        "phases":[{"phase":"p2-navigation-contract-repair",
                   "status":"PASS" if rc==0 else "FAIL",
                   "exit_code":rc,"elapsed_seconds":round(time.monotonic()-started,2),
                   "log":log.name}],
        "previous_batch_24_of_25_node_tests":"PASS_FROM_UPLOADED_INITIAL_DIAGNOSTIC_NOT_RERUN",
        "previous_typescript_vite":"PASS_FROM_UPLOADED_INITIAL_DIAGNOSTIC_NOT_RERUN",
        "previous_composer_batch_18_of_18":"PASS_FROM_PREVIOUS_UPLOADED_DIAGNOSTIC_NOT_RERUN",
        "original_datasets_accessed":False,
        "real_react_dom_or_native_export":"NOT_TESTED",
        "cloud_model_installer":"NOT_RUN"
    }
    (output/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    archive=output.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as z:
        for item in (log,output/"result.json"):
            z.write(item,arcname=item.name)
    print("P2 navigation contract repair:",result["overall"],flush=True)
    if rc:
        print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-28:]))
    print("One diagnostic ZIP (local paths may appear):",archive)
    print("Previous successful Node and TS/Vite phases retained, not rerun.")
    return 0 if rc==0 else 1

if __name__=="__main__":
    raise SystemExit(main())
