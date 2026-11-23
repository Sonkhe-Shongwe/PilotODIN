"""CF-03: connection-level foreign key gate for verified PilotODIN schemas.

New databases are certified after the core schema has been created. Historical
SQLite files are never auto-certified or migrated by the connection factory.
A separately authorized disposable migration must be audited and certified
before a legacy database can be moved to an enforced deployment.
"""
from __future__ import annotations

import sqlite3

GATE_TABLE = "pilotodin_fk_gate_v1"
GATE_VERSION = 1
REQUIRED_CORE_TABLES = frozenset({
    "projects", "project_lifecycle", "experiments",
    "experiment_progress_events", "experiment_run_controls",
    "semantic_business_context", "semantic_human_reviews",
    "semantic_human_review_events", "target_business_context",
})


class ForeignKeyGateError(RuntimeError):
    """A verified schema or connection enforcement precondition has failed."""


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _gate_present(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (GATE_TABLE,),
    ).fetchone() is not None


def gate_version(conn: sqlite3.Connection) -> int | None:
    """Return the certificate version, or None for an unverified legacy DB."""
    if not _gate_present(conn):
        return None
    try:
        rows = conn.execute(
            f"SELECT id,version FROM {_quote(GATE_TABLE)}"
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ForeignKeyGateError("Invalid SQLite foreign-key gate table") from exc
    if len(rows) != 1 or tuple(rows[0]) != (1, GATE_VERSION):
        raise ForeignKeyGateError("Unrecognized SQLite foreign-key certificate")
    return GATE_VERSION


def configure_connection(conn: sqlite3.Connection) -> bool:
    """Enable FKs for certified DBs and assert SQLite honored the setting.

    Existing unverified files remain in the original OFF mode to avoid an
    unreviewed compatibility change. This is not a security bypass or a claim
    that pre-existing orphan rows are safe. Audit and migration are separate.
    """
    certified = gate_version(conn) == GATE_VERSION
    if certified:
        if conn.in_transaction:
            raise ForeignKeyGateError("Cannot enable SQLite foreign keys during a transaction")
        conn.execute("PRAGMA foreign_keys=ON")
        value = conn.execute("PRAGMA foreign_keys").fetchone()
        if value is None or int(value[0]) != 1:
            raise ForeignKeyGateError("SQLite foreign-key enforcement could not be enabled")
    return certified


def validate_schema(conn: sqlite3.Connection) -> None:
    """Strictly validate the core and every currently created project link."""
    names = {str(row[0]) for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}
    if not REQUIRED_CORE_TABLES.issubset(names):
        raise ForeignKeyGateError("SQLite core schema incomplete; certification refused")
    for table in names:
        if table == GATE_TABLE or table == "projects":
            continue
        cols = {str(row[1]) for row in conn.execute(
            f"PRAGMA table_info({_quote(table)})"
        )}
        if "project_id" not in cols:
            continue
        refs = list(conn.execute(f"PRAGMA foreign_key_list({_quote(table)})"))
        if not any(
            str(ref[2]).lower() == "projects" and
            str(ref[3]).lower() == "project_id" and
            str(ref[4]).lower() == "id"
            for ref in refs
        ):
            raise ForeignKeyGateError("SQLite project foreign-key coverage incomplete")
    # PRAGMA foreign_key_check works even when FK enforcement is OFF.
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ForeignKeyGateError("SQLite foreign-key violations block certification")
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        raise ForeignKeyGateError("SQLite integrity check blocks certification")


def certify_new_schema(conn: sqlite3.Connection) -> None:
    """Seal a fresh, initialized DB or an explicitly disposable migrated copy.

    The production runtime invokes this only if its database did not exist
    before core initialization. A legacy DB is NEVER silently certified.
    """
    if conn.in_transaction:
        raise ForeignKeyGateError("Schema certification requires no active transaction")
    if _gate_present(conn):
        raise ForeignKeyGateError("SQLite schema is already certified")
    conn.execute("BEGIN IMMEDIATE")
    try:
        validate_schema(conn)
        conn.execute(f"""CREATE TABLE {_quote(GATE_TABLE)} (
            id INTEGER PRIMARY KEY CHECK(id=1),
            version INTEGER NOT NULL CHECK(version={GATE_VERSION})
        )""")
        conn.execute(
            f"INSERT INTO {_quote(GATE_TABLE)} (id,version) VALUES (1,?)",
            (GATE_VERSION,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
