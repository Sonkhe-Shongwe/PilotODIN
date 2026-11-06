#!/usr/bin/env python3
"""P1 isolated staged-upload regression gate, no live project data."""
from __future__ import annotations
import json,os,subprocess,sys,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED,ZipFile

ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    output=Path(tempfile.mkdtemp(prefix="pilotodin-p1-import-stage-"))
    home=output/"isolated-home"
    home.mkdir()
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(home)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    log=output/"p1-import-staging-backend.log"
    command=[sys.executable,"-m","pytest","-q",
             "tests/test_p1_upload_atomic_staging.py",
             "tests/test_p1_import_recovery.py"]
    started=time.monotonic()
    try:
        with log.open("w",encoding="utf-8",errors="replace") as stream:
            exit_code=subprocess.run(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                   stdout=stream,stderr=subprocess.STDOUT,timeout=360,check=False).returncode
    except (OSError,subprocess.TimeoutExpired) as exc:
        with log.open("a",encoding="utf-8",errors="replace") as stream:
            stream.write(type(exc).__name__+": "+str(exc))
        exit_code=-1
    result={
      "scope":"P1 atomic upload staging with isolated injected failure and prior rollback regression",
      "utc":datetime.now(timezone.utc).isoformat(),
      "overall":"PASS" if exit_code==0 else "FAIL",
      "phases":[{"phase":"p1-upload-staging-python",
                 "status":"PASS" if exit_code==0 else "FAIL",
                 "exit_code":exit_code,
                 "elapsed_seconds":round(time.monotonic()-started,2),
                 "log":log.name}],
      "synthetic_tests_only":True,
      "original_datasets_accessed":False,
      "frontend_native_tauri":"NOT_RUN",
      "qwen_e2_or_8gb":"NOT_RUN",
      "full_regression":"NOT_RERUN"
    }
    (output/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    archive=output.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as z:
        for p in (log,output/"result.json"):
            z.write(p,arcname=p.name)
    print("P1 isolated import staging:",result["overall"])
    if exit_code:print("\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-25:]))
    print("One diagnostics ZIP (may contain local paths):",archive)
    return 0 if exit_code==0 else 1

if __name__=="__main__":
    raise SystemExit(main())
