"""Read-only, metadata-only inventory of SQLite relationship enforcement.

Stage A of CF-03. This does NOT enable PRAGMA foreign_keys, change schema,
repair orphan records, or migrate an owner's database. Run on an isolated
consistent backup before any enforcement decision.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
from typing import Any


def _quoted(name: str) -> str:
    """Quote a SQLite identifier obtained from sqlite_master or PRAGMA."""
    return '"' + name.replace('"', '""') + '"'


def audit_database(database: str | Path) -> dict[str, Any]:
    """Return counts and schema names only, never record values or row IDs.

    A read-only SQLite URI and query_only prevent modifications to database
    content. Use a disposable, consistent backup of a live WAL database; a
    read-only SQLite connection can still interact with sidecar lock files.
    """
    db = Path(database)
    if db.is_symlink() or not db.is_file():
        raise ValueError("Supply a regular, existing SQLite backup file")

    # as_uri percent-encodes URL-sensitive path characters. Do not use
    # immutable=1 on a live database, because it can ignore WAL changes.
    uri = db.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        con.execute("PRAGMA query_only = ON")
        con.execute("BEGIN")  # One stable read snapshot for the inventory.
        tables = sorted(str(row[0]) for row in con.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ))
        table_names = set(tables)
        declarations: list[dict[str, str]] = []
        unprotected: list[dict[str, Any]] = []
        for table in tables:
            table_sql = _quoted(table)
            constraints = list(con.execute(f"PRAGMA foreign_key_list({table_sql})"))
            for row in constraints:
                # SQLite FK list: id, seq, parent, from, to, on_update, on_delete, match.
                declarations.append({
                    "child_table": table,
                    "from_column": str(row[3]),
                    "parent_table": str(row[2]),
                    "to_column": str(row[4]),
                })
            columns = {str(row[1]) for row in con.execute(f"PRAGMA table_info({table_sql})")}
            if table == "projects" or "project_id" not in columns:
                continue
            protected = any(
                str(row[2]).lower() == "projects"
                and str(row[3]).lower() == "project_id"
                and str(row[4]).lower() == "id"
                for row in constraints
            )
            if not protected:
                orphans: int | None = None
                if "projects" in table_names:
                    orphans = int(con.execute(
                        f"SELECT COUNT(*) FROM {table_sql} AS child "
                        "LEFT JOIN projects AS parent ON child.project_id = parent.id "
                        "WHERE child.project_id IS NOT NULL AND parent.id IS NULL"
                    ).fetchone()[0])
                unprotected.append({"table": table, "orphan_count": orphans})

        counts: Counter[tuple[str, str]] = Counter()
        check_error: str | None = None
        try:
            # PRAGMA foreign_key_check detects orphans even if enforcement is
            # disabled on the current connection. Never emit rowid values.
            for table, _row_id, parent, _fkid in con.execute("PRAGMA foreign_key_check"):
                counts[(str(table), str(parent))] += 1
        except sqlite3.DatabaseError as exc:
            check_error = type(exc).__name__

        con.execute("ROLLBACK")
        violations = [
            {"child_table": child, "parent_table": parent, "count": count}
            for (child, parent), count in sorted(counts.items())
        ]
        missing_parent = "projects" not in table_names
        unprotected_orphans = sum(int(x["orphan_count"] or 0) for x in unprotected)
        detected = sum(counts.values()) + unprotected_orphans
        return {
            "audit_complete": check_error is None and not missing_parent,
            "project_table_present": not missing_parent,
            "table_count": len(tables),
            "declared_foreign_key_count": len(declarations),
            "declared_constraints": declarations,
            "declared_fk_violations": violations,
            "undeclared_project_links": unprotected,
            "unprotected_project_orphans": unprotected_orphans,
            "detected_orphan_links": detected,
            "foreign_key_check_error": check_error,
            "full_project_fk_coverage": not unprotected and not missing_parent,
            "enforcement_authorized": False,  # Read-only report is never consent.
        }
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only PilotODIN SQLite FK audit")
    parser.add_argument("database", type=Path, help="Path to a DISPOSABLE consistent database backup")
    args = parser.parse_args()
    try:
        report = audit_database(args.database)
    except (ValueError, OSError, sqlite3.DatabaseError) as exc:
        # Do not print paths or SQLite record content from exception strings.
        print(json.dumps({"audit_complete": False, "error_type": type(exc).__name__,
                          "enforcement_authorized": False}))
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["audit_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
