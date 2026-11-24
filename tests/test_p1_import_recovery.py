"""P1 import recoverability: never leave ghost projects or orphaned sources.

Every case redirects the database and datasets into its own Pytest tmp_path,
so it neither reads nor modifies the owner's existing PilotODIN workspace.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

import pytest

from backend import artifact_publication, model_artifacts, model_publication, quality, storage
from backend.main import app


def _temporary_store(monkeypatch, tmp_path):
    home = tmp_path / "isolated-import"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    storage.init()
    return home


def _check_no_orphans(home: Path):
    assert storage.list_projects() == []
    with storage.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 0
    assert list((home / "datasets").iterdir()) == []


def _csv():
    return pd.DataFrame({
        "CustomerID": ["0001", "0002", "0003"],
        "Revenue": [100, 240, 360],
    }).to_csv(index=False).encode("utf-8")


def test_import_rollback_works_when_quality_schema_is_missing(monkeypatch, tmp_path):
    """Missing Quality tables cannot mask original initialization failure."""
    home = _temporary_store(monkeypatch, tmp_path)
    with storage.connect() as con:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "quality_versions" not in tables
    response = TestClient(app).post(
        "/api/projects",
        files={"file": ("source.csv", _csv(), "text/csv")},
    )
    assert response.status_code == 422, response.text
    assert "Could not process dataset" in response.json()["detail"]
    _check_no_orphans(home)


def test_partial_quality_registration_is_rolled_back_atomically(monkeypatch, tmp_path):
    """Failure of the final insert rolls back the entire import transaction."""
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    with storage.connect() as con:
        con.execute("""
            CREATE TRIGGER interrupt_registration BEFORE INSERT ON quality_versions
            BEGIN SELECT RAISE(ABORT, 'Synthetic interrupted registration'); END
        """)
    response = TestClient(app).post(
        "/api/projects",
        files={"file": ("source.csv", _csv(), "text/csv")},
    )
    assert response.status_code == 422, response.text
    assert "Synthetic interrupted registration" in response.json()["detail"]
    _check_no_orphans(home)
    with storage.connect() as con:
        for table in ("quality_state", "quality_versions"):
            assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_rejected_invalid_dataset_removes_staged_bytes(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    response = TestClient(app).post(
        "/api/projects",
        files={"file": ("invalid.csv", b"single_column\nvalue\n", "text/csv")},
    )
    assert response.status_code == 422, response.text
    _check_no_orphans(home)


def test_identifier_csv_import_quality_and_ml_preparation_agree(monkeypatch, tmp_path):
    """A real upload must not numerically coerce codes before Quality reload."""
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    lines = ["OrderNumber,SKU,CustomerID,PostalCode,Quantity,Revenue"]
    lines.extend(
        f"{i:06d},{i:05d},{i:05d},{i:04d},{i % 5 + 1},{100 + i * 12}"
        for i in range(1, 13)
    )
    source = ("\n".join(lines) + "\n").encode("utf-8")
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/projects", files={"file": ("leading_zeros.csv", source, "text/csv")},
        )
        assert uploaded.status_code == 201, uploaded.text
        payload = uploaded.json()
        pid, profile = payload["id"], payload["profile"]
        columns = {col["name"]: col for col in profile["columns"]}
        for col, expected in (
            ("OrderNumber", "000001"), ("SKU", "00001"),
            ("CustomerID", "00001"), ("PostalCode", "0001"),
        ):
            assert columns[col]["kind"] == "categorical"
            assert profile["preview"][0][col] == expected
        assert columns["Quantity"]["kind"] == "numeric"
        assert columns["Revenue"]["kind"] == "numeric"
        project = storage.get_project(pid)
        assert Path(project["dataset_path"]).read_bytes() == source

        current, version = quality.current_data(pid)
        assert version == 0
        for col in ("OrderNumber", "SKU", "CustomerID", "PostalCode"):
            assert current[col].iloc[0] == profile["preview"][0][col]
            assert pd.api.types.is_string_dtype(current[col])
        assert pd.api.types.is_numeric_dtype(current["Quantity"])
        assert pd.api.types.is_numeric_dtype(current["Revenue"])

        prepared = client.get(
            f"/api/projects/{pid}/preparation",
            params={"target": "Revenue", "expected_version": 0},
        )
        assert prepared.status_code == 200, prepared.text
        features = {row["column"]: row for row in prepared.json()["feature_audit"]}
        assert features["SKU"]["kind"] == "categorical"
        assert features["OrderNumber"]["kind"] == "categorical"
        assert features["Quantity"]["kind"] == "numeric"
        assert list((home / "models").iterdir()) == []


def test_unknown_commit_state_keeps_source_for_recovery(monkeypatch, tmp_path):
    """Retain published bytes when the database becomes unavailable."""
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()

    original_commit = storage.commit_dataset_publication
    def fail_and_disable(*args, **kwargs):
        monkeypatch.setattr(storage, "connect", lambda: (_ for _ in ()).throw(OSError("Synthetic storage failure")))
        raise OSError("Synthetic commit failure")
    connect = storage.connect
    monkeypatch.setattr(storage, "commit_dataset_publication", fail_and_disable)
    try:
        response = TestClient(app).post(
            "/api/projects", files={"file": ("recoverable.csv", _csv(), "text/csv")},
        )
    finally:
        monkeypatch.setattr(storage, "connect", connect)
        monkeypatch.setattr(storage, "commit_dataset_publication", original_commit)
    assert response.status_code == 500, response.text
    retained = list((home / "datasets").iterdir())
    assert len(retained) == 2
    assert {p.read_bytes() for p in retained} == {_csv()}
    assert storage.list_projects() == []


def test_error_after_commit_preserves_catalogue_and_source(monkeypatch, tmp_path):
    _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    save = storage.commit_dataset_publication

    def save_then_fail(*args, **kwargs):
        save(*args, **kwargs)
        raise OSError("Synthetic acknowledgement failure")

    monkeypatch.setattr(storage, "commit_dataset_publication", save_then_fail)
    client = TestClient(app)
    response = client.post("/api/projects", files={"file": ("generated.csv", _csv(), "text/csv")})
    assert response.status_code == 201, response.text
    row, = client.get("/api/projects").json()
    assert response.json()["id"] == row["id"]
    assert Path(storage.get_project(row["id"])["dataset_path"]).read_bytes() == _csv()
    assert client.get(f"/api/projects/{row['id']}/live-profile").json()["version"] == 0


class ImportRestartTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(self.enterContext(TemporaryDirectory(prefix="pilotodin-import-restart-")))
        self.datasets = self.home / "datasets"
        self.datasets.mkdir()
        (self.home / "models").mkdir()
        self.enterContext(patch.object(storage, "HOME", self.home))
        self.enterContext(patch.object(storage, "DB_PATH", self.home / "pilotodin.sqlite3"))
        self.enterContext(patch.dict(os.environ))
        os.environ.pop("PILOTODIN_DESKTOP_SESSION", None)
        self.enterContext(patch("backend.main.ai_provider.config_status", return_value={"cloud_enabled": False}))
        storage.init()
        quality._init_tables()

    def interrupt_child(self, boundary):
        child = r'''
import os
import sys
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main, storage, dataset_publication

boundary, raw = sys.argv[1:]
original_connect = storage.connect
original_save = storage.commit_dataset_publication
original_write = dataset_publication._write_exclusive

def connect():
    con = original_connect()
    def stop_before_original_version(sql):
        if sql.lstrip().upper().startswith("INSERT INTO QUALITY_VERSIONS"):
            os._exit(73)
    con.set_trace_callback(stop_before_original_version)
    return con

def save_and_stop(*args, **kwargs):
    original_save(*args, **kwargs)
    os._exit(73)

def stop_before_final(path, *args):
    if not path.name.endswith(".uploading"):
        os._exit(73)
    return original_write(path, *args)

def stop_after_intent(*args, **kwargs):
    original_intent(*args, **kwargs)
    os._exit(73)

def stop_after_staged(receipt, state, **kwargs):
    result = original_advance(receipt, state, **kwargs)
    if state == "staged":
        os._exit(73)
    return result

original_intent = storage.begin_dataset_publication
original_advance = storage.advance_dataset_publication

if boundary == 'intent':
    interruption = patch.object(storage, 'begin_dataset_publication', stop_after_intent)
elif boundary == 'staged':
    interruption = patch.object(storage, 'advance_dataset_publication', stop_after_staged)
elif boundary == 'before-commit':
    interruption = patch.object(storage, 'commit_dataset_publication', side_effect=lambda *a, **kw: os._exit(73))
elif boundary == 'replace':
    interruption = patch.object(dataset_publication, '_write_exclusive', stop_before_final)
elif boundary == 'version':
    interruption = patch.object(storage, 'connect', connect)
else:
    interruption = patch.object(storage, 'commit_dataset_publication', save_and_stop)

with interruption:
    response = TestClient(main.app).post('/api/projects', files={'file': ('generated.csv', raw, 'text/csv')})
    raise AssertionError(response.text)
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", child, boundary, _csv().decode("utf-8")],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PILOTODIN_HOME": str(self.home)},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 73, result.stderr)

    def assert_precommit_restart(self, suffix):
        retained = list(self.datasets.iterdir())
        self.assertEqual(len(retained), 1 if suffix == ".csv.uploading" else 2)
        self.assertTrue(any(p.name.endswith(suffix) for p in retained))
        self.assertTrue(all(p.read_bytes() == _csv() for p in retained))
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/projects").json(), [])
            self.assertEqual(client.get("/api/projects/manage").json(), [])
            with storage.connect() as con:
                self.assertEqual(con.execute("SELECT state FROM artifact_publications_v1").fetchone()[0], "interrupted")
                for table in ("projects", "quality_state", "quality_versions"):
                    self.assertEqual(con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], 0)
            uploaded = client.post("/api/projects", files={"file": ("generated.csv", _csv(), "text/csv")})
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            self.assertEqual(len(client.get("/api/projects").json()), 1)
        self.assertTrue(all(p.read_bytes() == _csv() for p in retained))

    def test_restart_after_intent_before_payload_creation(self):
        self.interrupt_child("intent")
        self.assertEqual(list(self.datasets.iterdir()), [])
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/projects").json(), [])
            with storage.connect() as con:
                self.assertEqual(con.execute("SELECT state FROM artifact_publications_v1").fetchone()[0], "interrupted")
        self.assertEqual(list(self.datasets.iterdir()), [])

    def test_restart_after_staged_receipt(self):
        self.interrupt_child("staged")
        self.assert_precommit_restart(".csv.uploading")

    def test_restart_after_final_fsync_before_business_commit(self):
        self.interrupt_child("before-commit")
        self.assert_precommit_restart(".csv")

    def test_restart_before_final_creation_keeps_staging_bytes_out_of_catalogue(self):
        self.interrupt_child("replace")
        self.assert_precommit_restart(".csv.uploading")

    def test_restart_during_original_version_insert_rolls_back_entire_catalogue(self):
        self.interrupt_child("version")
        self.assert_precommit_restart(".csv")

    def test_restart_after_catalogue_commit_loads_original_version(self):
        self.interrupt_child("committed")
        with TestClient(app) as client:
            project, = client.get("/api/projects").json()
            pid = project["id"]
            with storage.connect() as con:
                state = con.execute(
                    "SELECT original_sha256, current_version FROM quality_state WHERE project_id=?", (pid,),
                ).fetchone()
                version = con.execute(
                    "SELECT version, event FROM quality_versions WHERE project_id=?", (pid,),
                ).fetchone()
            self.assertIsNotNone(state)
            self.assertEqual(tuple(state), (hashlib.sha256(_csv()).hexdigest(), 0))
            self.assertEqual(tuple(version), (0, "original"))
            with storage.connect() as con:
                self.assertEqual(con.execute("SELECT state FROM artifact_publications_v1 WHERE subject_id=?", (pid,)).fetchone()[0], "committed")
            response = client.get(f"/api/projects/{pid}/live-profile")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["version"], 0)

    def test_restart_refuses_to_seal_legacy_unverified_bytes(self):
        source = self.datasets / "legacy.csv"
        source.write_bytes(_csv())
        pid = storage.save_project("Legacy", "legacy.csv", ".csv", source, {"rows": 3})
        changed = _csv() + b"0004,480\n"
        source.write_bytes(changed)
        with TestClient(app) as client:
            self.assertEqual([row["id"] for row in client.get("/api/projects/manage").json()], [pid])
            response = client.get(f"/api/projects/{pid}/live-profile")
            self.assertEqual(response.status_code, 409, response.text)
            self.assertIn("checksum", response.json()["detail"])
            with storage.connect() as con:
                for table in ("quality_state", "quality_versions"):
                    self.assertEqual(con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], 0)
        self.assertEqual(source.read_bytes(), changed)


def _ledger_intent():
    source = _csv()
    return storage.begin_dataset_publication(
        ".csv", len(source), hashlib.sha256(source).hexdigest())


def _ledger_publishing():
    intent = _ledger_intent()
    staged = storage.advance_dataset_publication(intent, "staged")
    return storage.advance_dataset_publication(staged, "publishing")


def test_publication_ledger_persists_intent_and_fences_transitions(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    intent = _ledger_intent()
    with storage.connect() as con:
        assert artifact_publication.read(con, intent.operation_id) == intent
        assert artifact_publication.pending_page(con) == [intent]
    assert intent.final_name == intent.operation_id + ".csv"
    assert intent.staging_name == intent.final_name + ".uploading"
    assert not list((home / "datasets").iterdir())
    with pytest.raises(artifact_publication.PublicationError):
        storage.advance_dataset_publication(intent, "publishing")
    staged = storage.advance_dataset_publication(intent, "staged")
    with pytest.raises(artifact_publication.PublicationError):
        storage.advance_dataset_publication(intent, "staged")
    with pytest.raises(artifact_publication.PublicationError):
        storage.advance_dataset_publication(staged, "committed")
    publishing = storage.advance_dataset_publication(staged, "publishing")
    interrupted = storage.advance_dataset_publication(
        publishing, "interrupted", reason="interrupted_before_commit")
    with pytest.raises(artifact_publication.PublicationError):
        storage.advance_dataset_publication(interrupted, "staged")
    with storage.connect() as con:
        assert artifact_publication.read(con, intent.operation_id) == interrupted
        assert artifact_publication.pending_page(con) == []
    _check_no_orphans(home)


def test_publication_schema_idempotent_refuses_incompatible_table(monkeypatch, tmp_path):
    _temporary_store(monkeypatch, tmp_path)
    intent = _ledger_intent()
    storage.init()
    with storage.connect() as con:
        assert artifact_publication.read(con, intent.operation_id) == intent
        con.execute("DROP TABLE artifact_publications_v1")
        con.execute("CREATE TABLE artifact_publications_v1 (operation_id TEXT)")
    with pytest.raises(artifact_publication.PublicationError, match="schema"):
        storage.init()
    with storage.connect() as con:
        assert [r[1] for r in con.execute(
            "PRAGMA table_info(artifact_publications_v1)")] == ["operation_id"]


def test_publication_receipt_validates_names_sizes_digests_and_reason(monkeypatch, tmp_path):
    _temporary_store(monkeypatch, tmp_path)
    digest = hashlib.sha256(_csv()).hexdigest()
    for suffix, size, sha in [
        ("../source.csv", 3, digest), (".csv", 0, digest),
        (".csv", 40 * 1024 * 1024 + 1, digest), (".xlsx", 3, "invalid"),
    ]:
        with pytest.raises(artifact_publication.PublicationError):
            storage.begin_dataset_publication(suffix, size, sha)
    intent = _ledger_intent()
    with pytest.raises(artifact_publication.PublicationError):
        storage.advance_dataset_publication(intent, "blocked", reason="private/path")
    with storage.connect() as con:
        assert artifact_publication.pending_page(con, limit=1) == [intent]
        assert artifact_publication.pending_page(con, after=intent.operation_id) == []
        with pytest.raises(artifact_publication.PublicationError):
            artifact_publication.pending_page(con, limit=129)


def test_publication_metadata_commit_is_atomic_and_terminal(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    receipt = _ledger_publishing()
    path = home / "datasets" / receipt.final_name
    path.write_bytes(_csv())
    checks = []
    committed = storage.commit_dataset_publication(
        receipt, "generated.csv", {"rows": 3},
        verify_final=lambda: checks.append(path.stat().st_size))
    assert checks == [len(_csv()), len(_csv())]
    assert committed.state == "committed"
    with storage.connect() as con:
        assert artifact_publication.read(con, receipt.operation_id) == committed
        assert artifact_publication.pending_page(con) == []
        assert tuple(con.execute(
            "SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",
            (receipt.subject_id,)).fetchone()) == (receipt.sha256, 0)
        assert tuple(con.execute(
            "SELECT version,event FROM quality_versions WHERE project_id=?",
            (receipt.subject_id,)).fetchone()) == (0, "original")
    assert Path(storage.get_project(receipt.subject_id)["dataset_path"]) == path
    assert path.read_bytes() == _csv()
    from backend import project_delete_impact
    inventory = project_delete_impact.impact(receipt.subject_id, 0)
    counts = {row["key"]: row["count"] for row in inventory["records"]}
    assert counts["artifact_publications_v1"] == 1
    assert "artifact_publications_v1" not in inventory["unclassified_tables"]
    assert inventory["deletion_available"] is False
    legacy = storage.save_project("Legacy", "legacy.csv", ".csv", path, {})
    inventory = project_delete_impact.impact(legacy, 0)
    assert {row["key"]: row["count"] for row in inventory["records"]}["artifact_publications_v1"] == 0

    with pytest.raises(artifact_publication.PublicationError):
        storage.advance_dataset_publication(committed, "interrupted",
                                            reason="unknown_commit")
    with pytest.raises(artifact_publication.PublicationError):
        storage.commit_dataset_publication(receipt, "generated.csv", {}, verify_final=lambda: None)


def test_publication_commit_rolls_back_on_version_or_final_identity_failure(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    receipt = _ledger_publishing()
    path = home / "datasets" / receipt.final_name
    path.write_bytes(_csv())
    with storage.connect() as con:
        con.execute("""CREATE TRIGGER publication_abort BEFORE INSERT ON quality_versions
                    BEGIN SELECT RAISE(ABORT, 'Synthetic version failure'); END""")
    with pytest.raises(Exception, match="Synthetic version failure"):
        storage.commit_dataset_publication(receipt, "generated.csv", {}, verify_final=lambda: None)
    with storage.connect() as con:
        con.execute("DROP TRIGGER publication_abort")
    checks = []
    def verify():
        checks.append(True)
        if len(checks) == 2:
            raise OSError("Synthetic identity change")
    with pytest.raises(OSError, match="identity change"):
        storage.commit_dataset_publication(receipt, "generated.csv", {}, verify_final=verify)
    with storage.connect() as con:
        assert artifact_publication.read(con, receipt.operation_id) == receipt
        for table in ("projects", "quality_state", "quality_versions"):
            assert con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    assert path.read_bytes() == _csv()


def test_publication_commit_refuses_archived_reference(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    receipt = _ledger_publishing()
    path = home / "datasets" / receipt.final_name
    path.write_bytes(_csv())
    other = storage.save_project("Legacy", "legacy.csv", ".csv", path, {})
    with storage.connect() as con:
        con.execute("INSERT INTO project_lifecycle VALUES (?,?,?)",
                    (other, 1, storage.now()))
    with pytest.raises(artifact_publication.PublicationError, match="reference conflict"):
        storage.commit_dataset_publication(receipt, "generated.csv", {}, verify_final=lambda: None)
    with storage.connect() as con:
        assert artifact_publication.read(con, receipt.operation_id) == receipt
        assert con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
    assert path.read_bytes() == _csv()


def test_publication_commit_requires_existing_expected_size_payload(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    receipt = _ledger_publishing()
    path = home / "datasets" / receipt.final_name
    with pytest.raises(FileNotFoundError):
        storage.commit_dataset_publication(receipt, "generated.csv", {}, verify_final=lambda: None)
    path.write_bytes(b"x")
    with pytest.raises(artifact_publication.PublicationError, match="size mismatch"):
        storage.commit_dataset_publication(receipt, "generated.csv", {}, verify_final=lambda: None)
    assert path.read_bytes() == b"x"
    assert storage.list_projects() == []
    with storage.connect() as con:
        assert artifact_publication.read(con, receipt.operation_id) == receipt


# B2 metadata-only regressions: no fitting or Joblib loading, inert byte digests.
def _model_receipt_fixture(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    source = home / "datasets" / "source.csv"
    source.write_bytes(_csv())
    digest = hashlib.sha256(_csv()).hexdigest()
    pid = storage.save_project("Source", "source.csv", ".csv", source, {}, original_sha256=digest)
    config = {"task": "regression", "models": ["ridge", "linear_regression"], "quality_version": 0}
    results = {"task": "regression", "models": [
        {"key": "ridge", "status": "ready"},
        {"key": "linear_regression", "status": "failed"},
    ]}
    eid = storage.new_experiment(pid, config, expected_quality_version=0)
    assert storage.claim_queued_experiment(eid)
    files = {name: {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
             for name, raw in {"ridge.joblib": b"inert-pipeline", "test_set.joblib": b"inert-holdout"}.items()}
    intent = storage.begin_model_publication(eid, config=config, source_sha256=digest)
    return home, pid, eid, config, results, files, intent


def test_model_receipt_binds_provenance_ready_keys_and_runtime(monkeypatch, tmp_path):
    home, pid, eid, config, results, files, intent = _model_receipt_fixture(monkeypatch, tmp_path)
    assert intent.project_id == pid
    assert intent.state == "intent"
    assert intent.runtime == model_publication.runtime_versions()
    assert not list((home / "models").iterdir())
    with storage.connect() as con:
        assert model_publication.read(con, eid) == intent
    with pytest.raises(artifact_publication.PublicationError):
        storage.stage_model_publication(intent, results, {"ridge.joblib": files["ridge.joblib"]})
    with pytest.raises(artifact_publication.PublicationError):
        storage.stage_model_publication(intent, results, {**files, "linear_regression.joblib": files["ridge.joblib"]})
    with pytest.raises(artifact_publication.PublicationError):
        storage.stage_model_publication(intent, results, {**files, "../escape.joblib": files["ridge.joblib"]})
    with pytest.raises(artifact_publication.PublicationError):
        storage.stage_model_publication(intent, results, {**files, "ridge.joblib": {"size": model_publication.MAX_FILE_BYTES+1, "sha256": "a"*64}})
    staged = storage.stage_model_publication(intent, results, files)
    assert staged.files == files
    with pytest.raises(artifact_publication.PublicationError):
        storage.stage_model_publication(intent, results, files)
    with pytest.raises(artifact_publication.PublicationError):
        staged.verify_binding(pid, {**config, "quality_version": 1}, intent.source_sha256, results)
    with pytest.raises(artifact_publication.PublicationError):
        staged.verify_binding(pid, config, "0"*64, results)
    with pytest.raises(artifact_publication.PublicationError):
        staged.verify_binding(pid, config, intent.source_sha256, results, runtime={**intent.runtime, "joblib": "0.0"})
    assert not list((home / "models").iterdir())


def test_model_manifest_commit_and_experiment_terminal_are_atomic(monkeypatch, tmp_path):
    home, pid, eid, config, results, files, intent = _model_receipt_fixture(monkeypatch, tmp_path)
    staged = storage.stage_model_publication(intent, results, files)
    publishing = storage.advance_model_publication(staged, "publishing")
    seen = []
    def fail_final():
        seen.append(True)
        if len(seen) == 2:
            raise OSError("Synthetic final verification failure")
    with pytest.raises(OSError, match="Synthetic final verification failure"):
        storage.commit_model_publication(publishing, results, verify_final=fail_final)
    assert storage.get_experiment(eid)["status"] == "running"
    with storage.connect() as con:
        assert model_publication.read(con, eid) == publishing
    committed = storage.commit_model_publication(publishing, results, verify_final=lambda: None)
    assert committed.state == "committed"
    assert storage.get_experiment(eid)["status"] == "completed"
    with storage.connect() as con:
        assert model_publication.read(con, eid) == committed
    with pytest.raises(artifact_publication.PublicationError):
        storage.advance_model_publication(committed, "interrupted", reason="unknown_commit")
    from backend import project_delete_impact
    inventory = project_delete_impact.impact(pid, 0)
    assert {row["key"]: row["count"] for row in inventory["records"]}["model_publications_v1"] == 1
    assert inventory["deletion_available"] is False


@pytest.mark.parametrize("boundary", ["cancel", "version", "archive"])
def test_model_completion_refuses_cancelled_stale_or_archived_run(monkeypatch, tmp_path, boundary):
    home, pid, eid, config, results, files, intent = _model_receipt_fixture(monkeypatch, tmp_path)
    staged = storage.stage_model_publication(intent, results, files)
    publishing = storage.advance_model_publication(staged, "publishing")
    if boundary == "cancel":
        storage.request_training_cancel(eid)
        error = storage.TrainingInterrupted
    elif boundary == "version":
        with storage.connect() as con:
            con.execute("UPDATE quality_state SET current_version=1 WHERE project_id=?", (pid,))
        error = storage.TrainingVersionConflict
    else:
        from backend.project_lifecycle import ProjectLifecycleError
        with storage.connect() as con:
            con.execute("INSERT INTO project_lifecycle VALUES (?,?,?)", (pid, 1, storage.now()))
        error = ProjectLifecycleError
    with pytest.raises(error):
        storage.commit_model_publication(publishing, results, verify_final=lambda: pytest.fail("Unexpected final verification"))
    assert storage.get_experiment(eid)["status"] == "running"
    with storage.connect() as con:
        assert model_publication.read(con, eid) == publishing


def test_legacy_model_metadata_is_not_retroactively_certified(monkeypatch, tmp_path):
    home, pid, eid, config, results, files, intent = _model_receipt_fixture(monkeypatch, tmp_path)
    legacy = storage.new_experiment(pid, config, expected_quality_version=0)
    assert storage.claim_queued_experiment(legacy)
    assert storage.finish_running_experiment(legacy, "completed", results=results)
    storage.init()
    assert storage.get_experiment(legacy)["results"] == results
    with storage.connect() as con:
        assert model_publication.read(con, legacy) is None
        assert model_publication.read(con, eid) == intent


def _fresh_model_worker(monkeypatch,tmp_path):
    home,pid,_,config,results,_,intent=_model_receipt_fixture(monkeypatch,tmp_path)
    eid=storage.new_experiment(pid,config,expected_quality_version=0)
    assert storage.claim_queued_experiment(eid)
    def dump(value,target):
        target.write(value)
    monkeypatch.setattr(model_artifacts.joblib,"dump",dump)
    return home,eid,config,results,intent.source_sha256


@pytest.mark.parametrize("lost_ack",[False,True])
def test_model_artifact_publication_verifies_and_commits_exact_bytes(monkeypatch,tmp_path,lost_ack):
    home,eid,config,results,digest=_fresh_model_worker(monkeypatch,tmp_path)
    if lost_ack:
        original=storage.commit_model_publication
        def commit(*args,**kwargs):
            original(*args,**kwargs)
            raise OSError("Synthetic lost completion acknowledgement")
        monkeypatch.setattr(storage,"commit_model_publication",commit)
    receipt=model_artifacts.publish(eid,config,digest,results,{"ridge":b"inert model"},b"inert holdout")
    assert receipt.state=="committed"
    assert storage.get_experiment(eid)["status"]=="completed"
    final=home/"models"/eid
    assert not final.with_name(eid+".publishing").exists()
    assert {p.name:p.read_bytes() for p in final.iterdir()}=={
        "ridge.joblib":b"inert model","test_set.joblib":b"inert holdout"}
    assert receipt.files["ridge.joblib"]["sha256"]==hashlib.sha256(b"inert model").hexdigest()


def test_model_artifact_collision_preserves_foreign_directory(monkeypatch,tmp_path):
    home,eid,config,results,digest=_fresh_model_worker(monkeypatch,tmp_path)
    final=home/"models"/eid
    final.mkdir()
    (final/"foreign").write_bytes(b"preserve")
    with pytest.raises((OSError,storage.WorkspaceBoundaryError)):
        model_artifacts.publish(eid,config,digest,results,{"ridge":b"inert model"},b"inert holdout")
    assert (final/"foreign").read_bytes()==b"preserve"
    assert storage.get_experiment(eid)["status"]=="running"
    assert not final.with_name(eid+".publishing").exists()


def test_model_artifact_budget_fails_without_completion(monkeypatch,tmp_path):
    home,eid,config,results,digest=_fresh_model_worker(monkeypatch,tmp_path)
    monkeypatch.setattr(model_publication,"MAX_FILE_BYTES",4)
    with pytest.raises(artifact_publication.PublicationError,match="budget"):
        model_artifacts.publish(eid,config,digest,results,{"ridge":b"too big"},b"test")
    assert storage.get_experiment(eid)["status"]=="running"
    assert not (home/"models"/eid).exists()
    assert not (home/"models"/(eid+".publishing")).exists()
    with storage.connect() as con:
        assert model_publication.read(con,eid).state=="interrupted"


def test_model_recovery_preserves_partial_artifacts_without_promoting(monkeypatch,tmp_path):
    home,pid,eid,config,results,files,intent=_model_receipt_fixture(monkeypatch,tmp_path)
    staged=storage.stage_model_publication(intent,results,files)
    publishing=storage.advance_model_publication(staged,"publishing")
    final=home/"models"/eid
    final.mkdir()
    (final/"ridge.joblib").write_bytes(b"partial")
    assert storage.recover_model_publications()==1
    assert storage.recover_model_publications()==0
    assert storage.recover_interrupted_experiments()==1
    assert storage.get_experiment(eid)["status"]=="failed"
    assert (final/"ridge.joblib").read_bytes()==b"partial"
    with storage.connect() as con:
        assert model_publication.read(con,eid).state=="interrupted"
