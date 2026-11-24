"""B5 typed export-transfer receipts. No filesystem operations or delivery claims.

A receipt records generated scratch ownership and transfer state, not a
committed dataset, delivery to a user's disk, or authorization to delete a path.
The coordinator must verify the exact opened file before stage/transfer/cleanup.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

try:
    from .artifact_publication import PublicationError, _sql_shape, begin_durable
except ImportError:
    from artifact_publication import PublicationError, _sql_shape, begin_durable

TABLE = "export_publications_v1"
INDEX = "export_publications_v1_state_operation"
MAX_EXPORT_BYTES = 75 * 1024 * 1024
MAX_PENDING = 4096
PAGE_SIZE = 128
_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
NEXT = {"intent":"staged", "staged":"ready", "ready":"transferring",
        "transferring":"released"}
NONTERMINAL = frozenset(NEXT)
TERMINAL = frozenset(("released", "interrupted", "blocked"))
REASONS = frozenset(("validation_failed", "interrupted_before_release",
                     "cancelled", "collision", "unsafe_identity",
                     "integrity_mismatch", "storage_unavailable", "unknown_commit"))
_COLUMNS = ("operation_id,subject_id,quality_version,format,schema_version,"
            "expected_bytes,sha256,state,reason_code,created_at,updated_at")
_DDL = """CREATE TABLE export_publications_v1 (
    operation_id TEXT NOT NULL PRIMARY KEY
        CHECK(length(operation_id)=32 AND operation_id NOT GLOB '*[^0-9a-f]*'),
    subject_id TEXT NOT NULL
        CHECK(length(subject_id)=32 AND subject_id NOT GLOB '*[^0-9a-f]*'),
    quality_version INTEGER NOT NULL
        CHECK(typeof(quality_version)='integer' AND quality_version>=0),
    format TEXT NOT NULL CHECK(format IN ('csv','xlsx')),
    schema_version INTEGER NOT NULL CHECK(schema_version=1),
    expected_bytes INTEGER CHECK(typeof(expected_bytes)='integer' AND expected_bytes BETWEEN 1 AND 78643200 OR expected_bytes IS NULL),
    sha256 TEXT CHECK(sha256 IS NULL OR (length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*')),
    state TEXT NOT NULL CHECK(state IN ('intent','staged','ready','transferring','released','interrupted','blocked')),
    reason_code TEXT CHECK(reason_code IN ('validation_failed','interrupted_before_release',
        'cancelled','collision','unsafe_identity','integrity_mismatch','storage_unavailable','unknown_commit')),
    created_at TEXT NOT NULL CHECK(length(created_at) BETWEEN 1 AND 64),
    updated_at TEXT NOT NULL CHECK(length(updated_at) BETWEEN 1 AND 64),
    CHECK((expected_bytes IS NULL)=(sha256 IS NULL)),
    CHECK(state!='intent' OR expected_bytes IS NULL),
    CHECK(state NOT IN ('staged','ready','transferring','released') OR expected_bytes IS NOT NULL),
    CHECK((state IN ('interrupted','blocked'))=(reason_code IS NOT NULL))
)"""
_INDEX_DDL = "CREATE INDEX export_publications_v1_state_operation ON export_publications_v1(state,operation_id)"


def ensure_schema(con):
    """Add only a distinct typed table; do not weaken dataset/model ledgers."""
    for name, kind, ddl in ((TABLE,"table",_DDL),(INDEX,"index",_INDEX_DDL)):
        row = con.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
        if row is None:
            con.execute(ddl)
        elif row[0] != kind or _sql_shape(row[1]) != _sql_shape(ddl):
            raise PublicationError("Incompatible export publication schema")


def validate_existing_schema(con):
    """Read-only backup compatibility; absent ledger is a valid old database."""
    table = con.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (TABLE,)).fetchone()
    index = con.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (INDEX,)).fetchone()
    if table is None and index is None:
        return False
    if (table is None or index is None or table[0] != "table" or index[0] != "index"
            or _sql_shape(table[1]) != _sql_shape(_DDL)
            or _sql_shape(index[1]) != _sql_shape(_INDEX_DDL)):
        raise PublicationError("Incompatible export publication schema")
    return True


@dataclass(frozen=True)
class Receipt:
    operation_id: str
    subject_id: str
    quality_version: int
    format: str
    schema_version: int
    expected_bytes: int | None
    sha256: str | None
    state: str
    reason_code: str | None
    created_at: str
    updated_at: str

    def validate(self):
        if (not isinstance(self.operation_id,str) or not _ID.fullmatch(self.operation_id)
                or not isinstance(self.subject_id,str) or not _ID.fullmatch(self.subject_id)
                or type(self.quality_version) is not int or self.quality_version < 0
                or self.format not in ("csv","xlsx") or type(self.schema_version) is not int
                or self.schema_version != 1 or self.state not in NONTERMINAL | TERMINAL
                or any(not isinstance(v,str) or not 1 <= len(v) <= 64
                       for v in (self.created_at,self.updated_at))):
            raise PublicationError("Invalid export receipt")
        if (self.expected_bytes is None) != (self.sha256 is None):
            raise PublicationError("Incomplete export payload metadata")
        if self.expected_bytes is not None and (
                type(self.expected_bytes) is not int or not 1 <= self.expected_bytes <= MAX_EXPORT_BYTES
                or not isinstance(self.sha256,str) or not _SHA.fullmatch(self.sha256)):
            raise PublicationError("Invalid export payload metadata")
        if ((self.state == "intent" and self.expected_bytes is not None)
                or (self.state in ("staged","ready","transferring","released") and self.expected_bytes is None)):
            raise PublicationError("Export state disagrees with payload")
        if self.state in ("interrupted","blocked"):
            if self.reason_code not in REASONS:
                raise PublicationError("Invalid export reason")
        elif self.reason_code is not None:
            raise PublicationError("Unexpected export reason")
        return self

    @property
    def project_id(self):
        """Historical subject, not a live project foreign key."""
        return self.subject_id

    @property
    def filename(self):
        self.validate()
        return "pilotodin-" + self.operation_id + "." + self.format


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _write_required(con):
    if not con.in_transaction:
        raise PublicationError("Export receipt requires a durable write transaction")


def read(con, operation_id):
    if not isinstance(operation_id,str) or not _ID.fullmatch(operation_id):
        raise PublicationError("Invalid export operation ID")
    # Fixed-size schema fields. Never treat arbitrary path text as authority.
    row = con.execute(f"SELECT {_COLUMNS} FROM {TABLE} WHERE operation_id=?", (operation_id,)).fetchone()
    return Receipt(*row).validate() if row is not None else None


def insert_intent(con, operation_id, project_id, quality_version, format):
    _write_required(con)
    now = _now()
    receipt = Receipt(operation_id, project_id, quality_version, format, 1,
                      None, None, "intent", None, now, now).validate()
    # No FK to projects: export receipts remain evidence after a separately
    # authorized project deletion. Admission still requires an existing version.
    row = con.execute("SELECT 1 FROM projects p JOIN quality_versions v ON p.id=v.project_id "
                      "LEFT JOIN project_lifecycle l ON p.id=l.project_id "
                      "WHERE p.id=? AND v.version=? AND l.archived_at IS NULL",
                      (project_id,quality_version)).fetchone()
    if row is None:
        raise PublicationError("Export version is unavailable")
    pending = con.execute(f"SELECT COUNT(*) FROM (SELECT operation_id FROM {TABLE} "
                          "WHERE state IN ('intent','staged','ready','transferring') LIMIT ?)",
                          (MAX_PENDING,)).fetchone()[0]
    if pending >= MAX_PENDING:
        raise PublicationError("Export pending receipt limit reached")
    con.execute(f"INSERT INTO {TABLE} ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                tuple(getattr(receipt,key) for key in _COLUMNS.split(",")))
    return receipt


def advance(con, expected, state, *, expected_bytes=None, sha256=None, reason=None):
    """CAS complete receipt, never revive terminal or invent a released transfer."""
    _write_required(con)
    expected.validate()
    if expected.state not in NONTERMINAL or (
            state != NEXT[expected.state] and state not in ("interrupted","blocked")):
        raise PublicationError("Illegal export receipt transition")
    if state == "staged":
        updated = replace(expected,state=state,expected_bytes=expected_bytes,
                          sha256=sha256,reason_code=reason,updated_at=_now())
    else:
        if expected_bytes is not None or sha256 is not None:
            raise PublicationError("Export payload metadata is immutable after stage")
        updated = replace(expected,state=state,reason_code=reason,updated_at=_now())
    updated.validate()
    if read(con,expected.operation_id) != expected:
        raise PublicationError("Export receipt changed")
    changed = con.execute(f"UPDATE {TABLE} SET expected_bytes=?,sha256=?,state=?,reason_code=?,updated_at=? "
                          "WHERE operation_id=? AND state=? AND updated_at=?",
                          (updated.expected_bytes,updated.sha256,updated.state,updated.reason_code,
                           updated.updated_at,expected.operation_id,expected.state,expected.updated_at))
    if changed.rowcount != 1:
        raise PublicationError("Export receipt transition conflict")
    return updated


def pending_page(con, *, after="", limit=PAGE_SIZE):
    if (after != "" and (not isinstance(after,str) or not _ID.fullmatch(after))
            or type(limit) is not int or not 1 <= limit <= PAGE_SIZE):
        raise PublicationError("Invalid export recovery page")
    rows = con.execute(f"SELECT {_COLUMNS} FROM {TABLE} WHERE operation_id>? "
                       "AND state IN ('intent','staged','ready','transferring') "
                       "ORDER BY operation_id LIMIT ?", (after,limit))
    return [Receipt(*row).validate() for row in rows]


def reconcile_pending(con):
    """Metadata-only startup recovery. Caller must own the process writer lease.

    No file enumeration, promotion, or cleanup: a digest/name is not proof of
    ownership after a crash. All potentially ambiguous bytes remain untouched.
    """
    _write_required(con)
    count = 0
    after = ""
    while True:
        page = pending_page(con,after=after)
        if not page:
            return count
        for receipt in page:
            if count >= MAX_PENDING:
                raise PublicationError("Export recovery limit reached")
            advance(con,receipt,"interrupted",reason="interrupted_before_release")
            count += 1
            after = receipt.operation_id
