"""Single-user local project store (metadata in SQLite; local artifacts by generated IDs)."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
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
        CREATE TABLE IF NOT EXISTS experiment_progress_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            detail TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            FOREIGN KEY(experiment_id) REFERENCES experiments(id)
        );
        CREATE INDEX IF NOT EXISTS experiment_progress_by_run
            ON experiment_progress_events(experiment_id,event_id);
        CREATE TABLE IF NOT EXISTS experiment_run_controls (
            experiment_id TEXT PRIMARY KEY,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            deadline_at TEXT,
            FOREIGN KEY(experiment_id) REFERENCES experiments(id)
        );
        CREATE TABLE IF NOT EXISTS target_business_context (
            project_id TEXT NOT NULL,
            quality_version INTEGER NOT NULL,
            target_column TEXT NOT NULL,
            outcome_definition TEXT NOT NULL,
            decision_action TEXT NOT NULL,
            prediction_moment TEXT NOT NULL,
            label_source TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (project_id, quality_version, target_column),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        """)


def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex


# These are factual checkpoints, not duration estimates or percentages.
STAGE_LABELS = {
    "queued": "Waiting to start",
    "loading_data": "Loading saved dataset version",
    "training_models": "Cross-validation and model fitting",
    "saving_artifacts": "Saving fitted models",
    "completed": "Completed",
    "failed": "Failed",
    "cancelled": "Cancelled",
    "timed_out": "Timed out",
    "running_legacy": "Running — individual stages not recorded",
}
ACTIVE_STAGE_ORDER = ("loading_data", "training_models", "saving_artifacts")


def _append_progress(con, eid, stage, detail):
    if stage not in STAGE_LABELS or stage == "running_legacy":
        raise ValueError("Invalid persisted training stage")
    con.execute(
        "INSERT INTO experiment_progress_events "
        "(experiment_id,stage,detail,occurred_at) VALUES (?,?,?,?)",
        (eid, stage, detail, now()),
    )


def _progress_for(con, eid, status):
    rows = con.execute(
        "SELECT stage,detail,occurred_at FROM experiment_progress_events "
        "WHERE experiment_id=? ORDER BY event_id ASC", (eid,),
    ).fetchall()
    if not rows:
        # Existing experiments are NOT retroactively assigned fictional stages.
        stage = status if status in ("queued", "completed", "failed", "cancelled", "timed_out") else "running_legacy"
        return {
            "stage": stage, "label": STAGE_LABELS[stage],
            "detail": "Historical experiment; intermediate milestones were not recorded.",
            "updated_at": None, "history": [], "history_available": False,
        }
    history = [
        {"stage": r["stage"], "label": STAGE_LABELS[r["stage"]],
         "detail": r["detail"], "at": r["occurred_at"]}
        for r in rows
    ]
    current = history[-1]
    return {
        "stage": current["stage"], "label": current["label"],
        "detail": current["detail"], "updated_at": current["at"],
        "history": history, "history_available": True,
    }


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



# Explicit USER-PROVIDED descriptions; storing them does not validate truth.
def target_contexts(project_id: str, quality_version: int) -> dict[str, dict]:
    with connect() as con:
        rows=con.execute(
            "SELECT target_column,outcome_definition,decision_action,"
            "prediction_moment,label_source,updated_at FROM target_business_context "
            "WHERE project_id=? AND quality_version=? ORDER BY target_column",
            (project_id,quality_version),
        ).fetchall()
    return {row["target_column"]: dict(row) for row in rows}


def save_target_context(project_id: str, quality_version: int, target_column: str,
                        outcome_definition: str, decision_action: str,
                        prediction_moment: str, label_source: str) -> dict:
    timestamp=now()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            "INSERT INTO target_business_context "
            "(project_id,quality_version,target_column,outcome_definition,decision_action,"
            "prediction_moment,label_source,updated_at) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(project_id,quality_version,target_column) DO UPDATE SET "
            "outcome_definition=excluded.outcome_definition,"
            "decision_action=excluded.decision_action,"
            "prediction_moment=excluded.prediction_moment,"
            "label_source=excluded.label_source,"
            "updated_at=excluded.updated_at",
            (project_id,quality_version,target_column,outcome_definition,decision_action,
             prediction_moment,label_source,timestamp),
        )
    return {
        "target_column":target_column,"outcome_definition":outcome_definition,
        "decision_action":decision_action,"prediction_moment":prediction_moment,
        "label_source":label_source,"updated_at":timestamp,
        "verification_state":"user_described_not_independently_verified",
    }


def new_experiment(pid, config):
    eid=uid()
    with connect() as con:
        con.execute("INSERT INTO experiments (id,project_id,status,config,created_at) VALUES (?,?,?,?,?)",
                    (eid,pid,"queued",json.dumps(config),now()))
        _append_progress(con,eid,"queued","Experiment accepted and waiting for a worker.")
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
        _append_progress(con,eid,"queued","Experiment accepted and waiting for a worker.")
    return eid


def claim_queued_experiment(eid):
    """Only a genuinely queued worker can become running (compare-and-set)."""
    with connect() as con:
        changed=con.execute(
            "UPDATE experiments SET status='running' WHERE id=? AND status='queued'",
            (eid,),
        )
        if changed.rowcount == 1:
            # The deadline starts when real work begins, not when queued.
            config_row = con.execute(
                "SELECT config FROM experiments WHERE id=?", (eid,)
            ).fetchone()
            seconds = json.loads(config_row["config"]).get("max_duration_seconds")
            deadline = (
                (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
                if seconds is not None else None
            )
            con.execute(
                "INSERT INTO experiment_run_controls (experiment_id,deadline_at) VALUES (?,?) "
                "ON CONFLICT(experiment_id) DO UPDATE SET deadline_at=excluded.deadline_at",
                (eid,deadline),
            )
            _append_progress(con,eid,"loading_data","Worker started; loading the saved dataset version.")
        return changed.rowcount == 1


class TrainingInterrupted(InterruptedError):
    """Cooperative checkpoint request; never implies preemptive model termination."""

    def __init__(self, status):
        if status not in ("cancelled", "timed_out"):
            raise ValueError("Unknown cooperative interruption")
        self.status = status
        super().__init__(
            "Training cancelled at a safe checkpoint." if status == "cancelled"
            else "Training exceeded its requested limit; stopped at a safe checkpoint."
        )


def _requested_interruption(con, eid):
    row = con.execute(
        "SELECT cancel_requested,deadline_at FROM experiment_run_controls "
        "WHERE experiment_id=?", (eid,),
    ).fetchone()
    if row:
        if row["cancel_requested"]:
            return "cancelled"
        if row["deadline_at"] and datetime.now(timezone.utc) >= datetime.fromisoformat(row["deadline_at"]):
            return "timed_out"
    return None


def check_training_interruption(eid):
    """Check before/after work boundaries; never forcibly interrupt an estimator."""
    with connect() as con:
        row = con.execute("SELECT status FROM experiments WHERE id=?", (eid,)).fetchone()
        if row is None or row["status"] not in ("queued", "running"):
            raise TrainingInterrupted("cancelled")
        reason = _requested_interruption(con, eid)
    if reason:
        raise TrainingInterrupted(reason)


def request_training_cancel(eid):
    """Queue cancellation is immediate; running cancellation is only REQUESTED.

    Both operations are transactionally serialized with terminal completion.
    """
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT status FROM experiments WHERE id=?", (eid,)).fetchone()
        if row is None:
            return None
        if row["status"] == "queued":
            con.execute(
                "UPDATE experiments SET status='cancelled',error=? "
                "WHERE id=? AND status='queued'",
                ("Cancelled before training started.",eid),
            )
            _append_progress(con,eid,"cancelled","Queued training cancelled before execution.")
            return "cancelled"
        if row["status"] == "running":
            con.execute(
                "INSERT INTO experiment_run_controls (experiment_id,cancel_requested) VALUES (?,1) "
                "ON CONFLICT(experiment_id) DO UPDATE SET cancel_requested=1",
                (eid,),
            )
            return "cancellation_requested"
        return "already_finished"


def finish_interrupted_experiment(eid, reason):
    """Record a confirmed cancellation/timeout only once a worker has stopped."""
    if reason not in ("cancelled", "timed_out"):
        raise ValueError("Invalid interruption terminal state")
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        changed = con.execute(
            "UPDATE experiments SET status=?,results=NULL,error=? "
            "WHERE id=? AND status='running'",
            (reason,
             "Cancelled by user at a cooperative checkpoint." if reason=="cancelled"
             else "Training time limit exceeded at a cooperative checkpoint.",
             eid),
        )
        if changed.rowcount == 1:
            _append_progress(
                con,eid,reason,
                "Running training stopped at a safe checkpoint."
                if reason=="cancelled" else "Time limit reached; work ended at a safe checkpoint.",
            )
        return changed.rowcount == 1


def training_control(eid):
    with connect() as con:
        row = con.execute(
            "SELECT cancel_requested,deadline_at FROM experiment_run_controls "
            "WHERE experiment_id=?", (eid,),
        ).fetchone()
        return {
            "cancel_requested": bool(row["cancel_requested"]) if row else False,
            "deadline_at": row["deadline_at"] if row else None,
            "interruption_is_cooperative": True,
        }


def advance_running_experiment(eid, stage, detail):
    """Record only forward, observed work milestones while a run is active.

    Compare and append in one SQLite write transaction. A stale worker cannot
    add events after interruption or move from saving backwards to training.
    """
    if stage not in ACTIVE_STAGE_ORDER:
        raise ValueError("Unknown active training stage")
    if not isinstance(detail, str) or not detail.strip() or len(detail) > 240:
        raise ValueError("Training milestone detail must be 1–240 characters")
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT status FROM experiments WHERE id=?", (eid,),
        ).fetchone()
        if row is None or row["status"] != "running":
            return False
        reason = _requested_interruption(con, eid)
        if reason:
            raise TrainingInterrupted(reason)
        last = con.execute(
            "SELECT stage FROM experiment_progress_events WHERE experiment_id=? "
            "ORDER BY event_id DESC LIMIT 1", (eid,),
        ).fetchone()
        if last is None or last["stage"] not in ACTIVE_STAGE_ORDER:
            return False
        if ACTIVE_STAGE_ORDER.index(stage) <= ACTIVE_STAGE_ORDER.index(last["stage"]):
            return False
        _append_progress(con, eid, stage, detail)
        return True


def finish_running_experiment(eid, status, *, results=None, error=None):
    """Never overwrite a completed, interrupted or otherwise terminal run."""
    if status not in ("completed", "failed"):
        raise ValueError("Only terminal ML statuses are accepted")
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        if status == "completed":
            reason = _requested_interruption(con,eid)
            if reason:
                raise TrainingInterrupted(reason)
        changed=con.execute(
            "UPDATE experiments SET status=?, results=?, error=? "
            "WHERE id=? AND status='running'",
            (status,json.dumps(results) if results is not None else None,error,eid),
        )
        if changed.rowcount == 1:
            _append_progress(
                con,eid,status,
                "Training and model artifacts saved." if status == "completed"
                else "Training stopped with an error; review experiment details.",
            )
        return changed.rowcount == 1


def recover_interrupted_experiments():
    """At a fresh backend startup, abandoned queued/running work cannot resume.

    No unfinished run is reported as complete. New experiments require a
    user action and fresh validation; no model artifact is automatically used.
    This is a single-process lifecycle recovery step, not a distributed lock.
    """
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        abandoned = con.execute(
            "SELECT id FROM experiments WHERE status IN ('queued','running')"
        ).fetchall()
        for row in abandoned:
            con.execute(
                "UPDATE experiments SET status='failed', results=NULL, "
                "error='Training interrupted by application restart. Review and start a new experiment.' "
                "WHERE id=? AND status IN ('queued','running')", (row["id"],),
            )
            _append_progress(
                con,row["id"],"failed",
                "Backend restarted while training was unfinished; no automatic retry.",
            )
        return len(abandoned)


def get_experiment(eid):
    with connect() as con:
        r=con.execute("SELECT * FROM experiments WHERE id=?",(eid,)).fetchone()
        if r is None:
            return None
        progress=_progress_for(con,eid,r["status"])
    controls = training_control(eid)
    return {**dict(r),"config":json.loads(r["config"]),
            "results":json.loads(r["results"]) if r["results"] else None,
            "final_results":json.loads(r["final_results"]) if r["final_results"] else None,
            "progress":progress,"control":controls}


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
