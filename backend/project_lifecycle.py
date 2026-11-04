"""P1 project management metadata: reversible rename and archive; NO permanent delete.

The new lifecycle table is an additive migration. Original uploads, Quality
histories, investigations, experiments, model artifacts and reports remain intact.
Archive hides a project from the active selector and from normal project loads.
"""

from __future__ import annotations

import re
from . import storage

# Only known project-scoped HTTP mutations are covered by the request gate.
# This is not an atomic lock against archive concurrent with an in-flight
# operation. A later P1 increment must pair it with commit-time write checks.
_PROJECT_ROUTE = re.compile(r"^/api/projects/([a-f0-9]{32})(?:/.*)?$")
_EXPERIMENT_ROUTE = re.compile(r"^/api/experiments/([a-f0-9]{32})/(?:cancel|select|predict)$")
_INVESTIGATION_ROUTE = re.compile(r"^/api/investigations/([a-f0-9]{32})/(?:runs|autonomy/(?:start|resume|cancel))$")
_REPORT_ROUTE = re.compile(r"^/api/reports/([a-f0-9]{32})/revisions$")


def archived_mutation_project(method: str, path: str) -> str | None:
    """Find an archived owning project for a mutating HTTP request.

    A 409 is deliberate for an archived owner. Missing projects/records fall
    through to existing API 404/validation behaviour. Read-only GET/HEAD,
    project import and lifecycle rename/restore are not blocked.
    No SQL writes, project file reads or user-controlled query fragments.
    """
    if method.upper() not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    direct = _PROJECT_ROUTE.fullmatch(path)
    if direct:
        pid = direct.group(1)
        if path in (f"/api/projects/{pid}/lifecycle",
                    f"/api/projects/{pid}/deletion-impact"):
            return None
        sql = ("SELECT p.id FROM projects p JOIN project_lifecycle l "
               "ON l.project_id=p.id WHERE p.id=? AND l.archived_at IS NOT NULL")
    else:
        experiment = _EXPERIMENT_ROUTE.fullmatch(path)
        investigation = _INVESTIGATION_ROUTE.fullmatch(path)
        report = _REPORT_ROUTE.fullmatch(path)
        if experiment:
            pid = experiment.group(1)
            sql = ("SELECT p.id FROM experiments e JOIN projects p ON p.id=e.project_id "
                   "JOIN project_lifecycle l ON l.project_id=p.id "
                   "WHERE e.id=? AND l.archived_at IS NOT NULL")
        elif investigation:
            pid = investigation.group(1)
            sql = ("SELECT p.id FROM investigations_v1 i JOIN projects p ON p.id=i.project_id "
                   "JOIN project_lifecycle l ON l.project_id=p.id "
                   "WHERE i.id=? AND l.archived_at IS NOT NULL")
        elif report:
            pid = report.group(1)
            sql = ("SELECT p.id FROM reports_v1 r JOIN projects p ON p.id=r.project_id "
                   "JOIN project_lifecycle l ON l.project_id=p.id "
                   "WHERE r.id=? AND l.archived_at IS NOT NULL")
        else:
            return None
    with storage.connect() as con:
        found = con.execute(sql, (pid,)).fetchone()
    return found["id"] if found else None



class ProjectLifecycleError(ValueError):
    def __init__(self, detail: str, status: int):
        self.status = status
        super().__init__(detail)


def listing() -> list[dict]:
    """Read-only catalogue of active and archived records, including CAS revision."""
    with storage.connect() as con:
        rows = con.execute(
            "SELECT p.id,p.name,p.filename,p.created_at, "
            "COALESCE(l.revision,0) AS revision,l.archived_at "
            "FROM projects p LEFT JOIN project_lifecycle l ON p.id=l.project_id "
            "ORDER BY p.created_at DESC,p.id"
        ).fetchall()
    return [dict(row) for row in rows]


def change(project_id: str, action: str, expected_revision: int, name: str | None = None) -> dict:
    """One revision-bound metadata transaction; never changes data/artifact files."""
    if action not in ('rename','archive','restore'):
        raise ProjectLifecycleError('Unsupported project management action.', 422)
    if not isinstance(expected_revision,int) or expected_revision < 0:
        raise ProjectLifecycleError('Invalid expected project revision.', 422)
    cleaned = None
    if action == 'rename':
        if not isinstance(name,str):
            raise ProjectLifecycleError('Enter a project name.', 422)
        cleaned = name.strip()
        if not cleaned or len(cleaned) > 80 or any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
            raise ProjectLifecycleError('Project name must be 1–80 characters, without control characters.', 422)

    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute(
            "SELECT p.id,p.name,p.filename,p.created_at, "
            "COALESCE(l.revision,0) AS revision,l.archived_at "
            "FROM projects p LEFT JOIN project_lifecycle l ON p.id=l.project_id "
            "WHERE p.id=?", (project_id,)
        ).fetchone()
        if row is None:
            raise ProjectLifecycleError('Project not found.', 404)
        if row['revision'] != expected_revision:
            raise ProjectLifecycleError('Project changed in another window. Refresh and review before retrying.', 409)
        archived_at = row['archived_at']
        if action == 'rename':
            if cleaned == row['name']:
                return dict(row)
            duplicate = con.execute(
                "SELECT id FROM projects WHERE name=? COLLATE NOCASE AND id<>? LIMIT 1",
                (cleaned,project_id)
            ).fetchone()
            if duplicate:
                raise ProjectLifecycleError('Another project already uses that name.', 409)
            con.execute("UPDATE projects SET name=? WHERE id=?", (cleaned,project_id))
        elif action == 'archive':
            if archived_at is not None:
                raise ProjectLifecycleError('Project is already archived.', 409)
            active = con.execute(
                "SELECT id FROM experiments WHERE project_id=? AND status IN ('queued','running') LIMIT 1",
                (project_id,)
            ).fetchone()
            if active:
                raise ProjectLifecycleError('Finish or cancel active model training before archiving.', 409)
            has_odin = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='odin_runs'"
            ).fetchone()
            if has_odin and con.execute(
                "SELECT id FROM odin_runs WHERE project_id=? "
                "AND status IN ('running','waiting_for_resources') LIMIT 1",(project_id,)
            ).fetchone():
                raise ProjectLifecycleError('An ODIN investigation is still running. Stop it before archiving.',409)
            archived_at = storage.now()
        else:
            if archived_at is None:
                raise ProjectLifecycleError('Project is not archived.',409)
            archived_at = None

        revision = expected_revision + 1
        con.execute(
            "INSERT INTO project_lifecycle(project_id,revision,archived_at) VALUES (?,?,?) "
            "ON CONFLICT(project_id) DO UPDATE SET "
            "revision=excluded.revision,archived_at=excluded.archived_at",
            (project_id,revision,archived_at),
        )
        updated = con.execute(
            "SELECT p.id,p.name,p.filename,p.created_at,l.revision,l.archived_at "
            "FROM projects p JOIN project_lifecycle l ON p.id=l.project_id WHERE p.id=?",
            (project_id,),
        ).fetchone()
        return dict(updated)
