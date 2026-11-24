"""Staged C1 durable training witnesses; no live route registration.

Use only for the exact experiment ID returned by the trusted queue transaction.
A terminal database row never proves worker exit on its own. The caller must
own the actual synchronous worker and establish its return before using that
witness. No schema change, global recovery, retry, or model work.
"""
try:
    from . import storage
except ImportError:
    import storage

_TERMINAL = frozenset(("completed", "failed", "cancelled", "timed_out"))


def _state(con, eid):
    return con.execute(
        "SELECT e.status, "
        "(SELECT stage FROM experiment_progress_events "
        " WHERE experiment_id=e.id ORDER BY event_id DESC LIMIT 1) AS latest_stage, "
        "EXISTS(SELECT 1 FROM experiment_progress_events WHERE experiment_id=e.id "
        " AND stage NOT IN ('queued','failed','cancelled')) AS worker_history, "
        "EXISTS(SELECT 1 FROM experiment_run_controls WHERE experiment_id=e.id) AS controls, "
        "(e.results IS NOT NULL OR e.final_results IS NOT NULL OR "
        " e.selected_model IS NOT NULL) AS artifacts "
        "FROM experiments e WHERE e.id=?", (eid,),
    ).fetchone()


def _unstarted(row):
    return (row is not None and row["status"] == row["latest_stage"]
            and not row["worker_history"] and not row["controls"]
            and not row["artifacts"])


def settle_unstarted(eid):
    """Settle one proven queued record; leave running/unknown records untouched.

    A cancelled or failed record with no recorded worker evidence may already
    be settled. Update status and append the matching event atomically. A
    database or acknowledgement failure propagates to the lease owner.
    """
    with storage.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = _state(con, eid)
        if not _unstarted(row):
            return False
        if row["status"] in ("failed", "cancelled"):
            return True
        if row["status"] != "queued":
            return False
        changed = con.execute(
            "UPDATE experiments SET status='failed',results=NULL,error=? "
            "WHERE id=? AND status='queued'",
            ("Training did not start. Review and start a new experiment.", eid),
        )
        if changed.rowcount != 1:
            return False
        storage._append_progress(
            con, eid, "failed",
            "Training request ended before the worker started; no automatic retry.",
        )
        row = _state(con, eid)
        if not _unstarted(row) or row["status"] != "failed":
            raise RuntimeError("Queued experiment settlement not confirmed")
        return True


def terminal(eid):
    """Bounded durable terminal-state witness, only after worker return."""
    with storage.connect() as con:
        row = _state(con, eid)
        return (row is not None and row["status"] in _TERMINAL
                and row["latest_stage"] == row["status"])
