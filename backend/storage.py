"""Single-user local project store (metadata in SQLite; local artifacts by generated IDs)."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(os.environ.get("PILOTODIN_HOME", str(Path(__file__).resolve().parents[1] / "data"))).resolve()
HOME.mkdir(parents=True,exist_ok=True)
(HOME / "datasets").mkdir(exist_ok=True)
(HOME / "models").mkdir(exist_ok=True)
DB_PATH = HOME / "pilotodin.sqlite3"


def connect():
    con=sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory=sqlite3.Row
    return con


def init():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, filename TEXT NOT NULL,
            file_ext TEXT NOT NULL, dataset_path TEXT NOT NULL,
            profile TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            status TEXT NOT NULL, config TEXT NOT NULL,
            results TEXT, error TEXT, selected_model TEXT,
            final_results TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        """)


def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex


def save_project(name, filename, ext, path, profile):
    ident=uid()
    with connect() as con:
        con.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?)",
                    (ident,name,filename,ext,str(path),json.dumps(profile),now()))
    return ident


def get_project(pid):
    with connect() as con:
        row=con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row: return None
    return {**dict(row),"profile":json.loads(row["profile"])}


def list_projects():
    with connect() as con:
        rows=con.execute("SELECT id,name,filename,created_at FROM projects ORDER BY created_at DESC").fetchall()
    return [dict(x) for x in rows]


def new_experiment(pid, config):
    eid=uid()
    with connect() as con:
        con.execute("INSERT INTO experiments (id,project_id,status,config,created_at) VALUES (?,?,?,?,?)",
                    (eid,pid,"queued",json.dumps(config),now()))
    return eid



class TrainingSlotBusy(RuntimeError):
    """A queued or running experiment already owns the constrained ML slot."""


def new_experiment_with_capacity(pid, config):
    """Atomically reserve the one NEW heavy-training slot in Low-memory mode.

    Uses SQLite BEGIN IMMEDIATE across connections so competing FastAPI
    requests cannot both observe the same empty queue and insert a job.
    The busy path writes no new experiment; existing work is left intact.
    All projects share a single constrained slot on this local workstation.
    """
    eid = uid()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        busy = con.execute(
            "SELECT id FROM experiments WHERE status IN ('queued','running') LIMIT 1"
        ).fetchone()
        if busy is not None:
            raise TrainingSlotBusy("Another ML training operation is queued or running.")
        con.execute(
            "INSERT INTO experiments (id,project_id,status,config,created_at) VALUES (?,?,?,?,?)",
            (eid,pid,"queued",json.dumps(config),now()),
        )
    return eid


def claim_queued_experiment(eid):
    """Only a genuinely queued worker can become running (compare-and-set)."""
    with connect() as con:
        changed=con.execute(
            "UPDATE experiments SET status='running' WHERE id=? AND status='queued'",
            (eid,),
        )
        return changed.rowcount == 1


def finish_running_experiment(eid, status, *, results=None, error=None):
    """Never overwrite a completed, interrupted or otherwise terminal run."""
    if status not in ("completed", "failed"):
        raise ValueError("Only terminal ML statuses are accepted")
    with connect() as con:
        changed=con.execute(
            "UPDATE experiments SET status=?, results=?, error=? "
            "WHERE id=? AND status='running'",
            (status,json.dumps(results) if results is not None else None,error,eid),
        )
        return changed.rowcount == 1


def recover_interrupted_experiments():
    """At a fresh backend startup, abandoned queued/running work cannot resume.

    No unfinished run is reported as complete. New experiments require a
    user action and fresh validation; no model artifact is automatically used.
    This is a single-process lifecycle recovery step, not a distributed lock.
    """
    with connect() as con:
        changed=con.execute(
            "UPDATE experiments SET status='failed', results=NULL, "
            "error='Training interrupted by application restart. Review and start a new experiment.' "
            "WHERE status IN ('queued','running')"
        )
        return changed.rowcount


def get_experiment(eid):
    with connect() as con:
        r=con.execute("SELECT * FROM experiments WHERE id=?",(eid,)).fetchone()
    if r is None: return None
    return {**dict(r),"config":json.loads(r["config"]),
            "results":json.loads(r["results"]) if r["results"] else None,
            "final_results":json.loads(r["final_results"]) if r["final_results"] else None}


def recent_experiments(pid):
    with connect() as con:
        rows=con.execute("SELECT id,status,selected_model,created_at FROM experiments WHERE project_id=? ORDER BY created_at DESC LIMIT 15",(pid,)).fetchall()
    return [dict(x) for x in rows]


def mark(eid, status, results=None, error=None):
    with connect() as con:
        con.execute("UPDATE experiments SET status=?, results=?, error=? WHERE id=?",
                    (status,json.dumps(results) if results is not None else None,error,eid))


def select_model(eid,model,final_results):
    with connect() as con:
        con.execute("UPDATE experiments SET selected_model=?,final_results=? WHERE id=? AND selected_model IS NULL",
                    (model,json.dumps(final_results),eid))
        return con.total_changes==1

init()
