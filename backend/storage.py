"""Single-user local project store (metadata in SQLite; local artifacts by generated IDs)."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from . import artifact_publication, model_publication, sqlite_fk_gate
    from .workspace_boundary import (WorkspaceBoundaryError, storage_home,
                                     validate_process_database, validate_process_write,
                                     configure_process_scratch, validate_process_scratch,
                                     pin_process_model_directory)
except ImportError:
    import artifact_publication, model_publication, sqlite_fk_gate
    from workspace_boundary import (WorkspaceBoundaryError, storage_home,
                                    validate_process_database, validate_process_write,
                                    configure_process_scratch, validate_process_scratch,
                                     pin_process_model_directory)

# No implicit checkout data root. Product entrypoints establish ownership
# before import; isolated in-process tests must supply an explicit home.
HOME = storage_home(os.environ.get("PILOTODIN_HOME"))
DB_PATH = HOME / "pilotodin.sqlite3"
validate_process_database(HOME, DB_PATH)
configure_process_scratch(HOME)
HOME.mkdir(parents=True,exist_ok=True)


def check_scratch():
    validate_process_scratch(HOME)


def check_write_path(path, **options):
    return validate_process_write(HOME, path, **options)


def pin_model_directory(path, *, expected=None):
    return pin_process_model_directory(HOME, path, expected=expected)


def guarded_unlink(path, *, expected=None):
    check_write_path(path, missing=True, expected=expected)
    path.unlink(missing_ok=True)


for _directory_name in ("datasets", "models"):
    _path = HOME / _directory_name
    check_write_path(_path, directory=True, missing=True)
    _path.mkdir(exist_ok=True)
    check_write_path(_path, directory=True)


class _ClosingSQLiteConnection(sqlite3.Connection):
    """Keep SQLite transaction semantics and always close managed handles."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect():
    validate_process_database(HOME, DB_PATH)
    con = sqlite3.connect(DB_PATH, timeout=30, factory=_ClosingSQLiteConnection)
    con.row_factory = sqlite3.Row
    try:
        validate_process_database(HOME, DB_PATH)
        sqlite_fk_gate.configure_connection(con)
    except Exception:
        con.close()
        raise
    return con


def init():
    # Do not automatically certify or rewrite databases already on disk.
    # Legacy FK enforcement requires a separate audited migration.
    fresh_database = not DB_PATH.exists()
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, filename TEXT NOT NULL,
            file_ext TEXT NOT NULL, dataset_path TEXT NOT NULL,
            profile TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS project_lifecycle (
            project_id TEXT PRIMARY KEY,
            revision INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
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
        CREATE TABLE IF NOT EXISTS semantic_business_context (
            project_id TEXT NOT NULL,
            quality_version INTEGER NOT NULL,
            domain_description TEXT NOT NULL,
            record_grain_description TEXT NOT NULL,
            field_definitions_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (project_id,quality_version),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS semantic_human_reviews (
            project_id TEXT NOT NULL,
            quality_version INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            hypothesis_role TEXT NOT NULL,
            hypothesis_hash TEXT NOT NULL,
            decision TEXT NOT NULL,
            explanation TEXT NOT NULL,
            revision INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (project_id, quality_version, column_name, hypothesis_role),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS semantic_human_review_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            quality_version INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            hypothesis_role TEXT NOT NULL,
            hypothesis_hash TEXT NOT NULL,
            revision INTEGER NOT NULL,
            previous_decision TEXT,
            decision TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE INDEX IF NOT EXISTS semantic_review_event_lookup
            ON semantic_human_review_events(project_id,quality_version,column_name,hypothesis_role,event_id);
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
        artifact_publication.ensure_schema(conn)
        model_publication.ensure_schema(conn)
        if fresh_database:
            sqlite_fk_gate.certify_new_schema(conn)


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


def save_project(name, filename, ext, path, profile, *, original_sha256: str | None = None):
    """Publish the catalogue and original Quality version in one transaction.

    Metadata-only records without a digest cannot be opened as working data.
    """
    ident=uid()
    created=now()
    with connect() as con:
        con.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?)",
                    (ident,name,filename,ext,str(path),json.dumps(profile),created))
        if original_sha256 is not None:
            con.execute("INSERT INTO quality_state VALUES (?,?,0)", (ident, original_sha256))
            con.execute("INSERT INTO quality_versions VALUES (?,?,?,?,?,?)",
                        (ident, 0, "[]", "original", "{}", created))
    return ident


def begin_dataset_publication(suffix, expected_bytes, sha256):
    """Persist intent before the import coordinator touches payload files."""
    with connect() as con:
        artifact_publication.begin_durable(con)
        return artifact_publication.insert_intent(
            con, uid(), uid(), suffix, expected_bytes, sha256)


def advance_dataset_publication(receipt, state, *, reason=None):
    with connect() as con:
        artifact_publication.begin_durable(con)
        return artifact_publication.advance(con, receipt, state, reason=reason)


def publication_reference_conflict(con, receipt, paths, *, allow_subject=False):
    """Conservative, bounded catalogue reference admission, archives included.

    Never open dataset contents here. Resolve path aliases and compare physical
    identity where available. Unreadable or ambiguous references block cleanup.
    """
    candidates = [Path(p) for p in paths]
    names = {os.path.normcase(os.path.abspath(p)).casefold() for p in candidates}
    resolved = {os.path.normcase(str(p.resolve(strict=False))).casefold() for p in candidates}
    identities = []
    for path in candidates:
        try:
            identities.append(path.stat())
        except FileNotFoundError:
            pass
    rows = con.execute("SELECT id,dataset_path FROM projects LIMIT 10001").fetchall()
    if len(rows) > 10000:
        raise artifact_publication.PublicationError("Publication reference inventory limit")
    for row in rows:
        if row["id"] == receipt.subject_id and not allow_subject:
            return True
        source = Path(row["dataset_path"])
        if not source.is_absolute():
            raise artifact_publication.PublicationError("Ambiguous catalogue source location")
        if (os.path.normcase(os.path.abspath(source)).casefold() in names
                or os.path.normcase(str(source.resolve(strict=False))).casefold() in resolved):
            return True
        try:
            info = source.stat()
        except FileNotFoundError:
            continue
        if any(os.path.samestat(info, expected) for expected in identities):
            return True
    return False


def commit_dataset_publication(receipt, filename, profile, *, verify_final):
    """Atomic catalogue, original Quality version and publication receipt.

    The coordinator verifies actual payload bytes outside the transaction.
    verify_final is a short identity check on its already verified file,
    not another parse or a long-running hash under the SQLite write lock.
    """
    receipt.validate()
    if receipt.state != "publishing":
        raise artifact_publication.PublicationError("Dataset is not publishing")
    path = HOME / "datasets" / receipt.final_name
    # Metadata commitment must not rely solely on a caller-supplied callback.
    # Require an existing regular single-link payload of the recorded size,
    # including in the explicitly unleased disposable fixture seam.
    def checked_identity(expected=None):
        check_write_path(path, expected=expected)
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_ino
                or getattr(info, "st_file_attributes", 0) & 0x400
                or info.st_size != receipt.expected_bytes
                or (expected is not None and not os.path.samestat(expected, info))):
            raise artifact_publication.PublicationError("Publication payload identity or size mismatch")
        return info

    identity = checked_identity()
    created = now()
    with connect() as con:
        artifact_publication.begin_durable(con)
        if artifact_publication.read(con, receipt.operation_id) != receipt:
            raise artifact_publication.PublicationError("Publication receipt changed")
        if publication_reference_conflict(con, receipt, (path,)):
            raise artifact_publication.PublicationError("Publication reference conflict")
        checked_identity(identity)
        verify_final()
        con.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?)",
                    (receipt.subject_id, Path(filename).stem, filename, receipt.suffix,
                     str(path), json.dumps(profile), created))
        con.execute("INSERT INTO quality_state VALUES (?,?,0)",
                    (receipt.subject_id, receipt.sha256))
        con.execute("INSERT INTO quality_versions VALUES (?,?,?,?,?,?)",
                    (receipt.subject_id, 0, "[]", "original", "{}", created))
        committed = artifact_publication.commit_dataset_receipt(con, receipt)
        verify_final()
        checked_identity(identity)
        return committed


def get_project(pid):
    with connect() as con:
        # Archived records stay durable but cannot be mounted as working projects.
        row=con.execute(
            "SELECT p.* FROM projects p LEFT JOIN project_lifecycle l ON p.id=l.project_id "
            "WHERE p.id=? AND l.archived_at IS NULL", (pid,),
        ).fetchone()
    if not row: return None
    return {**dict(row),"profile":json.loads(row["profile"])}


def list_projects():
    with connect() as con:
        rows=con.execute(
            "SELECT p.id,p.name,p.filename,p.created_at FROM projects p "
            "LEFT JOIN project_lifecycle l ON p.id=l.project_id "
            "WHERE l.archived_at IS NULL ORDER BY p.created_at DESC",
        ).fetchall()
    return [dict(x) for x in rows]



# P3 bounded human-authored metadata; not independently verified business truth.
def semantic_context(project_id: str, quality_version: int) -> dict | None:
    with connect() as con:
        row = con.execute(
            "SELECT domain_description,record_grain_description,field_definitions_json,"
            "updated_at FROM semantic_business_context WHERE project_id=? AND quality_version=?",
            (project_id, quality_version),
        ).fetchone()
    if row is None:
        return None
    return {
        "domain_description": row["domain_description"],
        "record_grain_description": row["record_grain_description"],
        "field_definitions": json.loads(row["field_definitions_json"]),
        "updated_at": row["updated_at"],
        "verification_state": "user_described_not_independently_verified",
    }


def save_semantic_context(project_id: str, quality_version: int,
                          domain: str, grain: str, fields: list[dict]) -> dict:
    timestamp = now()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            "INSERT INTO semantic_business_context VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(project_id,quality_version) DO UPDATE SET "
            "domain_description=excluded.domain_description,"
            "record_grain_description=excluded.record_grain_description,"
            "field_definitions_json=excluded.field_definitions_json,"
            "updated_at=excluded.updated_at",
            (project_id,quality_version,domain,grain,json.dumps(fields,ensure_ascii=False),timestamp),
        )
    return semantic_context(project_id, quality_version)


class HumanReviewConflict(ValueError):
    """A stale version or concurrently modified human review was rejected."""


def human_reviews(project_id: str, quality_version: int) -> dict[tuple[str, str], dict]:
    """Only read records for the exact project and Quality version requested."""
    with connect() as con:
        rows=con.execute(
            "SELECT column_name,hypothesis_role,hypothesis_hash,decision,explanation,"
            "revision,updated_at FROM semantic_human_reviews "
            "WHERE project_id=? AND quality_version=? ORDER BY column_name,hypothesis_role",
            (project_id,quality_version),
        ).fetchall()
    return {(row["column_name"],row["hypothesis_role"]):dict(row) for row in rows}


def save_human_review(project_id: str, quality_version: int, column: str,
                      role: str, hypothesis_hash: str, decision: str,
                      explanation: str, expected_revision: int) -> dict:
    """Single immediate SQLite transaction, optimistic revision and immutable audit.

    Quality version must still be current at the transaction boundary.
    This protects against a version change between the API's displayed
    candidate check and persistence, not just stale client payloads.
    """
    timestamp=now()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        # Match project archive's SQLite writer lock before this consented write.
        from .project_lifecycle import require_active_for_write
        require_active_for_write(con,project_id)
        state=con.execute(
            "SELECT current_version FROM quality_state WHERE project_id=?",
            (project_id,),
        ).fetchone()
        if state is None or int(state["current_version"]) != quality_version:
            raise HumanReviewConflict("Working dataset version changed; refresh Your data before reviewing.")
        prior=con.execute(
            "SELECT revision,decision FROM semantic_human_reviews "
            "WHERE project_id=? AND quality_version=? AND column_name=? AND hypothesis_role=?",
            (project_id,quality_version,column,role),
        ).fetchone()
        current_revision=0 if prior is None else int(prior["revision"])
        if current_revision != expected_revision:
            raise HumanReviewConflict("This review changed in another window; refresh before saving.")
        new_revision=current_revision+1
        con.execute(
            "INSERT INTO semantic_human_reviews "
            "(project_id,quality_version,column_name,hypothesis_role,hypothesis_hash,"
            "decision,explanation,revision,updated_at) VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(project_id,quality_version,column_name,hypothesis_role) DO UPDATE SET "
            "hypothesis_hash=excluded.hypothesis_hash,decision=excluded.decision,"
            "explanation=excluded.explanation,revision=excluded.revision,"
            "updated_at=excluded.updated_at",
            (project_id,quality_version,column,role,hypothesis_hash,
             decision,explanation,new_revision,timestamp),
        )
        con.execute(
            "INSERT INTO semantic_human_review_events "
            "(project_id,quality_version,column_name,hypothesis_role,hypothesis_hash,"
            "revision,previous_decision,decision,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (project_id,quality_version,column,role,hypothesis_hash,new_revision,
             None if prior is None else prior["decision"],decision,timestamp),
        )
    return {
        "column":column,"role":role,"hypothesis_hash":hypothesis_hash,
        "decision":decision,"explanation":explanation,"revision":new_revision,
        "updated_at":timestamp,
        "review_state":"owner_attestation_not_independently_verified",
    }


class TargetContextConflict(ValueError):
    """The chosen Quality version changed before target context could be saved."""


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
        # The API's earlier Quality-version and archive check can race with a
        # Quality revision or project archive. Recheck BOTH under the same
        # SQLite writer lock used by those mutations before any INSERT.
        from .project_lifecycle import require_active_for_write
        require_active_for_write(con, project_id)
        version_row = con.execute(
            "SELECT current_version FROM quality_state WHERE project_id=?",
            (project_id,),
        ).fetchone()
        if version_row is None or int(version_row["current_version"]) != quality_version:
            raise TargetContextConflict(
                "Working dataset version changed before target context was saved. "
                "Refresh the target review and retry."
            )
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


class TrainingSlotBusy(RuntimeError):
    """A queued or running experiment already owns the constrained ML slot."""


class TrainingVersionConflict(ValueError):
    """The working dataset changed after training admission inspected it."""


def _queue_experiment(pid, config, *, single_slot: bool, expected_quality_version: int | None):
    """Recheck admission under the same write lock as archive and Quality."""
    from .project_lifecycle import require_active_for_write

    eid = uid()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        require_active_for_write(con, pid)
        if expected_quality_version is not None:
            state = con.execute("SELECT current_version FROM quality_state WHERE project_id=?", (pid,)).fetchone()
            if state is None:
                raise TrainingVersionConflict("The working dataset version could not be verified. Refresh before training.")
            current = state["current_version"]
            if current != expected_quality_version:
                raise TrainingVersionConflict(
                    f"Dataset version changed from {expected_quality_version} to {current}. Refresh before training."
                )
        if single_slot and con.execute(
            "SELECT 1 FROM experiments WHERE status IN ('queued','running') LIMIT 1"
        ).fetchone() is not None:
            raise TrainingSlotBusy("Another ML training operation is queued or running.")
        con.execute(
            "INSERT INTO experiments (id,project_id,status,config,created_at) VALUES (?,?,?,?,?)",
            (eid,pid,"queued",json.dumps(config),now()),
        )
        _append_progress(con,eid,"queued","Experiment accepted and waiting for a worker.")
    return eid


def new_experiment(pid, config, *, expected_quality_version: int | None = None):
    return _queue_experiment(pid, config, single_slot=False, expected_quality_version=expected_quality_version)


def new_experiment_with_capacity(pid, config, *, expected_quality_version: int | None = None):
    """Atomically reserve the single workstation-wide Low-memory training slot."""
    return _queue_experiment(pid, config, single_slot=True, expected_quality_version=expected_quality_version)


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


def _model_publication_context(con, eid):
    """Fence model publication against cancellation, archive and version changes."""
    try:
        from .project_lifecycle import require_active_for_write
    except ImportError:
        from project_lifecycle import require_active_for_write
    row = con.execute(
        "SELECT project_id,status,config FROM experiments WHERE id=?", (eid,)
    ).fetchone()
    if row is None or row["status"] != "running":
        raise TrainingInterrupted("cancelled")
    reason = _requested_interruption(con, eid)
    if reason:
        raise TrainingInterrupted(reason)
    pid = row["project_id"]
    require_active_for_write(con, pid)
    config = json.loads(row["config"])
    state = con.execute(
        "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?", (pid,)
    ).fetchone()
    if state is None or state["current_version"] != config.get("quality_version"):
        raise TrainingVersionConflict("Dataset version changed before model publication")
    return pid, config, state["original_sha256"]


def model_training_source(eid, pid, config):
    """Capture recorded source provenance before loading training data."""
    with connect() as con:
        project_id, persisted, digest = _model_publication_context(con, eid)
        if project_id != pid or model_publication.config_digest(config) != model_publication.config_digest(persisted):
            raise artifact_publication.PublicationError("Model training provenance changed")
        return digest


def begin_model_publication(eid, *, config, source_sha256):
    """Create a receipt before writing any model artifacts."""
    runtime = model_publication.runtime_versions()
    with connect() as con:
        artifact_publication.begin_durable(con)
        pid, persisted, digest = _model_publication_context(con, eid)
        if model_publication.config_digest(persisted) != model_publication.config_digest(config) or digest != source_sha256:
            raise artifact_publication.PublicationError("Model training provenance changed")
        return model_publication.insert_intent(con, eid, pid, persisted, digest, runtime)


def stage_model_publication(receipt, results, files):
    """Persist the complete verified inventory before final-file publication."""
    with connect() as con:
        artifact_publication.begin_durable(con)
        pid, config, digest = _model_publication_context(con, receipt.experiment_id)
        receipt.verify_binding(pid, config, digest)
        return model_publication.stage(con, receipt, config, results, files)


def advance_model_publication(receipt, state, *, reason=None):
    with connect() as con:
        artifact_publication.begin_durable(con)
        if state == "publishing":
            pid, config, digest = _model_publication_context(con, receipt.experiment_id)
            receipt.verify_binding(pid, config, digest)
        return model_publication.advance(con, receipt, state, reason=reason)


def commit_model_publication(receipt, results, *, verify_final):
    """Atomically commit an experiment's completion and its typed manifest.

    The caller must already have verified all files and supply a bounded final
    identity recheck. This function does not serialize or deserialize models.
    """
    with connect() as con:
        artifact_publication.begin_durable(con)
        pid, config, digest = _model_publication_context(con, receipt.experiment_id)
        receipt.verify_binding(pid, config, digest, results)
        if receipt.state != "publishing" or model_publication.read(con, receipt.experiment_id) != receipt:
            raise artifact_publication.PublicationError("Model publication receipt changed")
        verify_final()
        changed = con.execute(
            "UPDATE experiments SET status='completed',results=?,error=NULL WHERE id=? AND status='running'",
            (json.dumps(results), receipt.experiment_id))
        if changed.rowcount != 1:
            raise artifact_publication.PublicationError("Model completion transition conflict")
        _append_progress(con, receipt.experiment_id, "completed", "Training and model artifacts saved.")
        committed = model_publication.commit(con, receipt, results, config, digest)
        verify_final()
        return committed


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


def recover_model_publications():
    """Startup-only receipt classification; never inspect or delete artifact files."""
    cursor = ""
    count = 0
    while True:
        with connect() as con:
            artifact_publication.begin_durable(con)
            rows = con.execute(
                "SELECT experiment_id FROM model_publications_v1 "
                "WHERE state IN ('intent','staged','publishing') AND experiment_id>? "
                "ORDER BY experiment_id LIMIT 128", (cursor,)).fetchall()
            if not rows:
                return count
            if count + len(rows) > 4096:
                raise artifact_publication.PublicationError("Model publication recovery limit reached")
            for row in rows:
                cursor = row[0]
                receipt = model_publication.read(con, cursor)
                experiment = con.execute("SELECT status,project_id FROM experiments WHERE id=?", (cursor,)).fetchone()
                if experiment is None or experiment["project_id"] != receipt.project_id or experiment["status"] == "completed":
                    model_publication.advance(con, receipt, "blocked", reason="reference_conflict")
                else:
                    model_publication.advance(con, receipt, "interrupted", reason="interrupted_before_commit")
                count += 1


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


def latest_version_training(pid, version):
    """Read the latest experiment with recorded execution on this dataset version."""
    with connect() as con:
        row = con.execute(
            "SELECT status, selected_model, results FROM experiments AS e "
            "WHERE project_id=? AND COALESCE(json_extract(config, '$.quality_version'), 0)=? "
            "AND (status IN ('running', 'completed') OR EXISTS ("
            "SELECT 1 FROM experiment_progress_events WHERE experiment_id=e.id "
            "AND stage IN ('loading_data','training_models','saving_artifacts'))) "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (pid, version),
        ).fetchone()
    if row is None:
        return None
    return {**dict(row), 'results': json.loads(row['results']) if row['results'] else None}


def mark(eid, status, results=None, error=None):
    with connect() as con:
        con.execute("UPDATE experiments SET status=?, results=?, error=? WHERE id=?",
                    (status,json.dumps(results) if results is not None else None,error,eid))


class ModelSelectionVersionConflict(ValueError):
    """The evaluated experiment no longer matches the working dataset."""


def select_model(eid,model,final_results):
    """Commit one evaluation under the same write lock as archive and Quality."""
    from .project_lifecycle import require_active_for_write

    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        candidate = con.execute(
            "SELECT e.project_id,e.config,q.current_version FROM experiments e "
            "LEFT JOIN quality_state q ON q.project_id=e.project_id "
            "WHERE e.id=? AND e.status='completed' AND e.selected_model IS NULL", (eid,),
        ).fetchone()
        if candidate is None:
            return False
        require_active_for_write(con, candidate["project_id"])
        trained_version = json.loads(candidate["config"]).get("quality_version", 0)
        current_version = candidate["current_version"]
        if current_version is None or current_version != trained_version:
            raise ModelSelectionVersionConflict("Dataset changed since training. Start a new experiment on the current version.")
        updated = con.execute(
            "UPDATE experiments SET selected_model=?,final_results=? WHERE id=? AND selected_model IS NULL",
            (model,json.dumps(final_results),eid),
        )
        return updated.rowcount == 1

init()
