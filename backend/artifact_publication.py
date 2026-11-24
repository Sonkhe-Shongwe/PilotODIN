"""B1 dataset publication ledger: SQLite intent and business-commit authority.

This module does not create, delete, or publish payload files. The owned
import coordinator must verify physical identity and bytes before using it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import sqlite3

TABLE = "artifact_publications_v1"
INDEX = "artifact_publications_v1_state_operation"
MAX_DATASET_BYTES = 40 * 1024 * 1024
NONTERMINAL = frozenset({"intent", "staged", "publishing"})
TERMINAL = frozenset({"committed", "interrupted", "blocked"})
REASONS = frozenset({
    "validation_failed", "interrupted_before_commit", "collision",
    "unsafe_identity", "reference_conflict", "integrity_mismatch",
    "storage_unavailable", "unknown_commit",
})
_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")

_TABLE_SQL = """CREATE TABLE artifact_publications_v1 (
    operation_id TEXT NOT NULL PRIMARY KEY
        CHECK(length(operation_id)=32 AND operation_id NOT GLOB '*[^0-9a-f]*'),
    kind TEXT NOT NULL CHECK(kind='dataset'),
    subject_id TEXT NOT NULL
        CHECK(length(subject_id)=32 AND subject_id NOT GLOB '*[^0-9a-f]*'),
    schema_version INTEGER NOT NULL CHECK(schema_version=1),
    suffix TEXT NOT NULL CHECK(suffix IN ('.csv','.xlsx')),
    expected_bytes INTEGER NOT NULL
        CHECK(typeof(expected_bytes)='integer' AND expected_bytes BETWEEN 1 AND 41943040),
    sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    state TEXT NOT NULL CHECK(state IN ('intent','staged','publishing','committed','interrupted','blocked')),
    reason_code TEXT CHECK(reason_code IN ('validation_failed','interrupted_before_commit',
        'collision','unsafe_identity','reference_conflict','integrity_mismatch','storage_unavailable','unknown_commit')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(kind,subject_id),
    CHECK((state IN ('interrupted','blocked') AND reason_code IS NOT NULL)
       OR (state NOT IN ('interrupted','blocked') AND reason_code IS NULL))
)"""
_INDEX_SQL = """CREATE INDEX artifact_publications_v1_state_operation
    ON artifact_publications_v1(state,operation_id)"""


class PublicationError(RuntimeError):
    """Receipt or transition is not safe to use."""


def _sql_shape(sql):
    # The ledger has a version-specific, application-owned schema. Do not
    # silently accept a same-named table with weaker constraints.
    return re.sub(r"\s+", "", sql or "").lower()


def ensure_schema(con: sqlite3.Connection) -> None:
    """Add only the v1 schema; refuse a conflicting existing schema."""
    for name, kind, ddl in ((TABLE, "table", _TABLE_SQL), (INDEX, "index", _INDEX_SQL)):
        row = con.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
        if row is None:
            con.execute(ddl)
        elif row[0] != kind or _sql_shape(row[1]) != _sql_shape(ddl):
            raise PublicationError("Incompatible publication ledger schema")


def begin_durable(con: sqlite3.Connection) -> None:
    """Start a short receipt write transaction without changing journal mode."""
    if con.in_transaction:
        raise PublicationError("Publication requires a fresh transaction")
    mode = con.execute("PRAGMA journal_mode").fetchone()[0].lower()
    if mode not in {"delete", "truncate", "persist", "wal"}:
        raise PublicationError("Unsupported publication journal mode")
    if con.execute("PRAGMA synchronous").fetchone()[0] < 2:
        con.execute("PRAGMA synchronous=FULL")
    if con.execute("PRAGMA synchronous").fetchone()[0] < 2:
        raise PublicationError("Publication durability unavailable")
    con.execute("BEGIN IMMEDIATE")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Receipt:
    operation_id: str
    kind: str
    subject_id: str
    schema_version: int
    suffix: str
    expected_bytes: int
    sha256: str
    state: str
    reason_code: str | None
    created_at: str
    updated_at: str

    def validate(self) -> None:
        if (not isinstance(self.operation_id, str) or not _ID.fullmatch(self.operation_id)
                or not isinstance(self.subject_id, str) or not _ID.fullmatch(self.subject_id)
                or self.kind != "dataset" or type(self.schema_version) is not int
                or self.schema_version != 1 or self.suffix not in (".csv", ".xlsx")
                or type(self.expected_bytes) is not int
                or not 1 <= self.expected_bytes <= MAX_DATASET_BYTES
                or not isinstance(self.sha256, str) or not _SHA.fullmatch(self.sha256)
                or self.state not in NONTERMINAL | TERMINAL):
            raise PublicationError("Invalid publication receipt")
        if self.state in {"interrupted", "blocked"}:
            if self.reason_code not in REASONS:
                raise PublicationError("Invalid publication reason")
        elif self.reason_code is not None:
            raise PublicationError("Unexpected publication reason")
        for value in (self.created_at, self.updated_at):
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.utcoffset() != timezone.utc.utcoffset(None):
                    raise ValueError
            except (TypeError, ValueError):
                raise PublicationError("Invalid publication timestamp") from None

    @property
    def final_name(self) -> str:
        self.validate()
        return self.operation_id + self.suffix

    @property
    def staging_name(self) -> str:
        return self.final_name + ".uploading"


_COLUMNS = ("operation_id,kind,subject_id,schema_version,suffix,expected_bytes,"
            "sha256,state,reason_code,created_at,updated_at")


def read(con: sqlite3.Connection, operation_id: str) -> Receipt | None:
    if not isinstance(operation_id, str) or not _ID.fullmatch(operation_id):
        raise PublicationError("Invalid publication operation ID")
    row = con.execute(f"SELECT {_COLUMNS} FROM {TABLE} WHERE operation_id=?",
                      (operation_id,)).fetchone()
    if row is None:
        return None
    receipt = Receipt(*row)
    receipt.validate()
    return receipt


def _require_write(con):
    if not con.in_transaction:
        raise PublicationError("Publication requires an active transaction")


def insert_intent(con, operation_id, subject_id, suffix, expected_bytes, sha256) -> Receipt:
    """Caller commits intent before creating any payload file."""
    _require_write(con)
    stamp = _now()
    receipt = Receipt(operation_id, "dataset", subject_id, 1, suffix, expected_bytes,
                      sha256, "intent", None, stamp, stamp)
    receipt.validate()
    con.execute(f"INSERT INTO {TABLE} ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (receipt.operation_id, receipt.kind, receipt.subject_id,
                 receipt.schema_version, receipt.suffix, receipt.expected_bytes,
                 receipt.sha256, receipt.state, receipt.reason_code,
                 receipt.created_at, receipt.updated_at))
    return receipt


def _cas(con, expected: Receipt, state: str, reason: str | None = None) -> Receipt:
    _require_write(con)
    expected.validate()
    if read(con, expected.operation_id) != expected:
        raise PublicationError("Publication receipt changed")
    stamp = _now()
    changed = con.execute(
        f"UPDATE {TABLE} SET state=?,reason_code=?,updated_at=? WHERE operation_id=? AND state=?",
        (state, reason, stamp, expected.operation_id, expected.state),
    )
    if changed.rowcount != 1:
        raise PublicationError("Publication transition conflict")
    result = read(con, expected.operation_id)
    if result is None:
        raise PublicationError("Publication receipt disappeared")
    return result


def advance(con, expected: Receipt, state: str, *, reason: str | None = None) -> Receipt:
    """Only nonterminal transitions; commitment belongs to business transaction."""
    if expected.state not in NONTERMINAL:
        raise PublicationError("Terminal publication cannot transition")
    if state in {"interrupted", "blocked"}:
        if reason not in REASONS:
            raise PublicationError("Invalid publication reason")
    elif (expected.state, state) not in {("intent", "staged"), ("staged", "publishing")} or reason is not None:
        raise PublicationError("Illegal publication transition")
    return _cas(con, expected, state, reason)


def commit_dataset_receipt(con, expected: Receipt) -> Receipt:
    """Commit only when the catalogue and original Quality record agree.

    The caller must insert these records and commit this same transaction.
    This is metadata consistency, not a physical payload verification.
    """
    _require_write(con)
    if expected.state != "publishing":
        raise PublicationError("Dataset is not publishing")
    project = con.execute(
        "SELECT file_ext FROM projects WHERE id=?", (expected.subject_id,)
    ).fetchone()
    quality = con.execute(
        "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",
        (expected.subject_id,),
    ).fetchone()
    original = con.execute(
        "SELECT operations_json,event FROM quality_versions WHERE project_id=? AND version=0",
        (expected.subject_id,),
    ).fetchone()
    if (project is None or tuple(project) != (expected.suffix,)
            or quality is None or tuple(quality) != (expected.sha256, 0)
            or original is None or tuple(original) != ("[]", "original")):
        raise PublicationError("Dataset metadata does not match publication receipt")
    return _cas(con, expected, "committed")


def pending_page(con, *, after: str = "", limit: int = 128) -> list[Receipt]:
    """Bounded keyset read for startup reconciliation; never scans payloads."""
    if type(limit) is not int or not 1 <= limit <= 128:
        raise PublicationError("Invalid publication page limit")
    if after and not _ID.fullmatch(after):
        raise PublicationError("Invalid publication page cursor")
    rows = con.execute(
        f"SELECT {_COLUMNS} FROM {TABLE} WHERE state IN ('intent','staged','publishing') "
        "AND operation_id>? ORDER BY operation_id LIMIT ?", (after, limit),
    ).fetchall()
    receipts = [Receipt(*row) for row in rows]
    for receipt in receipts:
        receipt.validate()
    return receipts
