"""CI-only, read-only audit of generated B5 export receipts and original bytes."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path


def main(pid):
    if (os.environ.get("CI") != "true" or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("P1_REAL_HTTP_E2E") != "1"):
        raise RuntimeError("Disposable CI required")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[0-9]+",run_id) or not re.fullmatch(r"[a-f0-9]{32}",pid):
        raise RuntimeError("Invalid fixture identity")
    runner = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    home = Path(os.environ["PILOTODIN_HOME"])
    if home != runner / ("pilotodin-p1-real-http-"+run_id) or home.resolve(strict=True)!=home:
        raise RuntimeError("Invalid disposable workspace")
    db=home/"pilotodin.sqlite3"
    if db.is_symlink() or not db.is_file():
        raise RuntimeError("Missing fixture database")
    with sqlite3.connect(db.as_uri()+"?mode=ro",uri=True) as con:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        row=con.execute("SELECT p.filename,p.dataset_path,q.original_sha256,q.current_version "
                        "FROM projects p JOIN quality_state q ON p.id=q.project_id WHERE p.id=?",
                        (pid,)).fetchone()
        if row is None or row[0] not in ("pilotodin_b5_browser.csv","pilotodin_b5_disconnect.csv"):
            raise RuntimeError("Not a B5 fixture")
        source=Path(row[1])
        if (source.parent!=home/"datasets" or source.is_symlink()
                or source.parent.resolve(strict=True)!=source.parent
                or not re.fullmatch(r"[a-f0-9]{32}\.csv",source.name)):
            raise RuntimeError("Unsafe fixture source")
        records=con.execute("SELECT operation_id,format,state,expected_bytes,sha256,reason_code "
                            "FROM export_publications_v1 WHERE subject_id=? ORDER BY created_at LIMIT 5",
                            (pid,)).fetchall()
        if len(records)>=5:
            raise RuntimeError("Unexpected receipt count")
        history=con.execute("SELECT version,event,operations_json FROM quality_versions WHERE project_id=? LIMIT 2",
                            (pid,)).fetchall()
    digest=hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            digest.update(block)
    scratch=home/"export_tmp"
    if scratch.exists() and scratch.resolve(strict=True)!=scratch:
        raise RuntimeError("Unsafe scratch directory")
    items=[]
    for op,fmt,state,size,sha,reason in records:
        if not re.fullmatch(r"[a-f0-9]{32}",op) or fmt not in ("csv","xlsx"):
            raise RuntimeError("Invalid receipt")
        path=scratch/("pilotodin-"+op+"."+fmt)
        items.append({"format":fmt,"state":state,"size":size,"sha256":sha,
                      "reason":reason,"scratch_exists":os.path.lexists(path)})
    print(json.dumps({"receipts":items,"original_matches":digest.hexdigest()==row[2],
                      "version":row[3],"original_history":history==[(0,"original","[]")]}))


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise RuntimeError("Expected fixture project ID")
    main(sys.argv[1])
