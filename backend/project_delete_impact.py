"""P1 read-only project deletion impact inventory. NO deletion capability.

This is deliberately an inventory, not a clearance certificate or full file
manifest. It never deletes, renames, unlinks, moves, writes to SQLite or reads
dataset contents. Unknown schema families and unmanaged paths are exposed as
review blockers rather than being silently skipped.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import re

from . import storage
from .project_lifecycle import ProjectLifecycleError

# Known actual PilotODIN SQL families. Indirect rows are counted through their
# owning parent. All queries are fixed literals; no user SQL or table identifiers.
COUNTS: tuple[tuple[str, str, str, str], ...] = (
    ("projects", "Project", "projects",
     "SELECT COUNT(*) FROM projects WHERE id=?"),
    ("project_lifecycle", "Lifecycle metadata", "project_lifecycle",
     "SELECT COUNT(*) FROM project_lifecycle WHERE project_id=?"),
    ("quality_state", "Quality state", "quality_state",
     "SELECT COUNT(*) FROM quality_state WHERE project_id=?"),
    ("quality_versions", "Quality versions", "quality_versions",
     "SELECT COUNT(*) FROM quality_versions WHERE project_id=?"),
    ("quality_actions", "Quality actions", "quality_actions",
     "SELECT COUNT(*) FROM quality_actions WHERE project_id=?"),
    ("quality_decisions", "Quality decisions", "quality_decisions",
     "SELECT COUNT(*) FROM quality_decisions WHERE project_id=?"),
    ("quality_approval_receipts", "Quality approval receipts", "quality_approval_receipts",
     "SELECT COUNT(*) FROM quality_approval_receipts WHERE project_id=?"),
    ("semantic_business_context", "User-described semantic context", "semantic_business_context",
     "SELECT COUNT(*) FROM semantic_business_context WHERE project_id=?"),
    ("target_business_context", "Target business context", "target_business_context",
     "SELECT COUNT(*) FROM target_business_context WHERE project_id=?"),
    ("experiments", "Model experiments", "experiments",
     "SELECT COUNT(*) FROM experiments WHERE project_id=?"),
    ("experiment_progress_events", "Training progress events", "experiment_progress_events",
     "SELECT COUNT(*) FROM experiment_progress_events e JOIN experiments x ON x.id=e.experiment_id WHERE x.project_id=?"),
    ("experiment_run_controls", "Training run controls", "experiment_run_controls",
     "SELECT COUNT(*) FROM experiment_run_controls e JOIN experiments x ON x.id=e.experiment_id WHERE x.project_id=?"),
    ("investigations_v1", "Investigations", "investigations_v1",
     "SELECT COUNT(*) FROM investigations_v1 WHERE project_id=?"),
    ("evidence_v1", "Investigation evidence", "evidence_v1",
     "SELECT COUNT(*) FROM evidence_v1 e JOIN investigations_v1 i ON i.id=e.investigation_id WHERE i.project_id=?"),
    ("odin_runs", "ODIN runs", "odin_runs",
     "SELECT COUNT(*) FROM odin_runs WHERE project_id=?"),
    ("odin_run_steps", "ODIN run steps", "odin_run_steps",
     "SELECT COUNT(*) FROM odin_run_steps s JOIN odin_runs r ON r.id=s.run_id WHERE r.project_id=?"),
    ("explore_snapshots_v1", "Saved Explore analyses", "explore_snapshots_v1",
     "SELECT COUNT(*) FROM explore_snapshots_v1 WHERE project_id=?"),
    ("reports_v1", "Reports", "reports_v1",
     "SELECT COUNT(*) FROM reports_v1 WHERE project_id=?"),
    ("report_revisions_v1", "Report revisions", "report_revisions_v1",
     "SELECT COUNT(*) FROM report_revisions_v1 r JOIN reports_v1 p ON p.id=r.report_id WHERE p.project_id=?"),
    ("report_quality_audits_v1", "Report quality evidence", "report_quality_audits_v1",
     "SELECT COUNT(*) FROM report_quality_audits_v1 WHERE project_id=?"),
)
KNOWN_TABLES = frozenset(item[0] for item in COUNTS)


def impact(project_id: str, expected_revision: int) -> dict:
    """Return a revision-pinned audit without ever authorizing deletion."""
    if not isinstance(expected_revision, int) or expected_revision < 0:
        raise ProjectLifecycleError("Invalid expected project revision.", 422)
    with closing(storage.connect()) as con:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        row = con.execute(
            "SELECT p.id,p.name,p.filename,p.dataset_path, "
            "COALESCE(l.revision,0) AS revision,l.archived_at "
            "FROM projects p LEFT JOIN project_lifecycle l ON l.project_id=p.id "
            "WHERE p.id=?", (project_id,)
        ).fetchone()
        if row is None:
            raise ProjectLifecycleError("Project not found.", 404)
        if row["revision"] != expected_revision:
            raise ProjectLifecycleError(
                "Project changed in another window. Refresh its details before reviewing deletion.",409
            )
        existing_tables = {record["name"] for record in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        counts = [
            {"key": table,"label": label,
             "count": int(con.execute(query,(project_id,)).fetchone()[0]) if table in existing_tables else 0,
             "schema_present": table in existing_tables}
            for table,label,query in ((item[0],item[1],item[3]) for item in COUNTS)
        ]
        # The project belongs to one local SQLite file. New/unknown tables must
        # be reviewed before any future destructive implementation.
        unknown = sorted(existing_tables - KNOWN_TABLES)
        pending_training = int(con.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id=? "
            "AND status IN ('queued','running')",(project_id,)
        ).fetchone()[0])
        running_odin = int(con.execute(
            "SELECT COUNT(*) FROM odin_runs WHERE project_id=? "
            "AND status IN ('running','waiting_for_resources')",(project_id,)
        ).fetchone()[0]) if "odin_runs" in existing_tables else 0
        experiment_ids = [
            record["id"] for record in con.execute(
                "SELECT id FROM experiments WHERE project_id=?",(project_id,)
            ).fetchall()
        ]

    home = storage.HOME.resolve(strict=False)
    datasets = storage.HOME / "datasets"
    model_root = storage.HOME / "models"
    source = Path(row["dataset_path"])
    # Classify, do not open or clean any path. Symlinks and legacy/external
    # sources must not be treated as safe managed deletion candidates.
    managed_source = (
        not datasets.is_symlink() and not source.is_symlink()
        and datasets.resolve(strict=False) == home / "datasets"
        and source.resolve(strict=False).parent == home / "datasets"
    )
    model_candidates = 0
    suspicious_artifacts = 0
    for experiment_id in experiment_ids:
        if not isinstance(experiment_id,str) or not re.fullmatch(r"[a-f0-9]{32}",experiment_id):
            suspicious_artifacts += 1
            continue
        item = model_root / experiment_id
        if item.is_symlink() or model_root.is_symlink():
            suspicious_artifacts += 1
        elif item.is_dir():
            model_candidates += 1

    blockers = ["Permanent deletion is not implemented or authorised."]
    if pending_training:
        blockers.append("Model training is queued or running.")
    if running_odin:
        blockers.append("An ODIN investigation is still active.")
    if not managed_source:
        blockers.append("Original source is not a verified directly managed dataset file.")
    if suspicious_artifacts:
        blockers.append("One or more model artifact locations require manual review.")
    if unknown:
        blockers.append("Unclassified SQLite tables require a retention and dependency review.")

    return {
        "project_id": row["id"],
        "name": row["name"],
        "revision": row["revision"],
        "archived": row["archived_at"] is not None,
        "preview_only": True,
        "deletion_available": False,
        "records": counts,
        "linked_sqlite_rows": sum(item["count"] for item in counts),
        "unclassified_tables": unknown,
        "artifacts": {
            "original_source_present": source.is_file(),
            "original_source_managed": managed_source,
            "linked_model_directories_present": model_candidates,
            "model_locations_requiring_review": suspicious_artifacts,
            "external_exports_and_backups": "Outside project deletion scope",
        },
        "active_work": {"model_training": pending_training,"odin_runs": running_odin},
        "blockers": blockers,
        "limitations": (
            "Read-only inventory of known SQLite dependencies and linked file locations. "
            "No contents were opened. This is not a complete filesystem manifest. "
            "User exports, external backups, shared settings and unknown assets are not covered."
        ),
    }
