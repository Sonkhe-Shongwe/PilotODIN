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
from tests.fixture_http import fixture_client

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
    response = fixture_client(app).post(
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
    response = fixture_client(app).post(
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
    response = fixture_client(app).post(
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
    with fixture_client(app) as client:
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
        response = fixture_client(app).post(
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
    client = fixture_client(app)
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
from tests.fixture_http import fixture_client
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
    response = fixture_client(main.app).post('/api/projects', files={'file': ('generated.csv', raw, 'text/csv')})
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
        with fixture_client(app) as client:
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
        with fixture_client(app) as client:
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
        with fixture_client(app) as client:
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
        with fixture_client(app) as client:
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


def _verified_load_fixture(monkeypatch,tmp_path):
    home,eid,config,results,digest=_fresh_model_worker(monkeypatch,tmp_path)
    receipt=model_artifacts.publish(eid,config,digest,results,{"ridge":b"inert model"},b"inert holdout")
    return home,storage.get_experiment(eid),receipt


def test_verified_load_rewinds_same_private_handle_after_original_changes(monkeypatch,tmp_path):
    home,experiment,receipt=_verified_load_fixture(monkeypatch,tmp_path)
    final=home/"models"/experiment["id"]
    loaded=[]
    def load(stream,mmap_mode=None):
        assert mmap_mode is None
        assert stream.tell()==0
        if not loaded:
            (final/"ridge.joblib").write_bytes(b"unverified replacement")
            (final/"test_set.joblib").write_bytes(b"unverified holdout")
        value=stream.read()
        loaded.append(value)
        return value
    monkeypatch.setattr(model_artifacts.joblib,"load",load)
    assert model_artifacts.load_verified(experiment,"ridge",holdout=True)==(b"inert model",b"inert holdout")
    assert loaded==[b"inert model",b"inert holdout"]
    assert not list((home/"backend-temp").iterdir())


@pytest.mark.parametrize("failure",["legacy","missing","digest","holdout","extra","runtime","config","disk","memory","link"])
def test_unverified_artifact_never_reaches_deserializer(monkeypatch,tmp_path,failure):
    home,experiment,receipt=_verified_load_fixture(monkeypatch,tmp_path)
    eid=experiment["id"]
    directory=home/"models"/eid
    source=directory/"ridge.joblib"
    if failure=="legacy":
        with storage.connect() as con:
            con.execute("DELETE FROM model_publications_v1 WHERE experiment_id=?",(eid,))
    elif failure=="missing":
        source.unlink()
    elif failure=="digest":
        source.write_bytes(b"X"*len(b"inert model"))
    elif failure=="holdout":
        (directory/"test_set.joblib").write_bytes(b"X"*len(b"inert holdout"))
    elif failure=="extra":
        (directory/"unexpected.joblib").write_bytes(b"unknown")
    elif failure=="runtime":
        monkeypatch.setattr(model_publication,"runtime_versions",lambda:{**receipt.runtime,"joblib":"0.0"})
    elif failure=="config":
        with storage.connect() as con:
            con.execute("UPDATE model_publications_v1 SET config_sha256=? WHERE experiment_id=?",("0"*64,eid))
    elif failure=="disk":
        from types import SimpleNamespace
        monkeypatch.setattr(model_artifacts.shutil,"disk_usage",lambda _:SimpleNamespace(free=0))
    elif failure=="memory":
        monkeypatch.setattr(model_artifacts.resource_policy,"admit_new_work",lambda _:{"decision":"defer"})
    elif failure=="link":
        foreign=tmp_path/"foreign-model"
        source.rename(foreign)
        os.link(foreign,source)
    monkeypatch.setattr(model_artifacts.joblib,"load",lambda *a,**kw:pytest.fail("Unverified deserialization"))
    expected=model_artifacts.LoadDeferred if failure in ("disk","memory") else model_artifacts.LoadRefused
    with pytest.raises(expected):
        model_artifacts.load_verified(experiment,"ridge",holdout=True)
    assert storage.get_experiment(eid)["status"]=="completed"
    scratch=home/"backend-temp"
    assert not scratch.exists() or not list(scratch.iterdir())
    if failure=="link":
        assert foreign.read_bytes()==b"inert model"


def test_verified_prediction_requires_selected_model(monkeypatch,tmp_path):
    home,experiment,receipt=_verified_load_fixture(monkeypatch,tmp_path)
    monkeypatch.setattr(model_artifacts.joblib,"load",lambda *a,**kw:pytest.fail("Unexpected load"))
    with pytest.raises(model_artifacts.LoadRefused,match="selected"):
        model_artifacts.load_verified(experiment,"ridge")
    with storage.connect() as con:
        con.execute("UPDATE experiments SET selected_model='ridge' WHERE id=?",(experiment["id"],))
    experiment=storage.get_experiment(experiment["id"])
    monkeypatch.setattr(model_artifacts.joblib,"load",lambda stream,**kw:stream.read())
    assert model_artifacts.load_verified(experiment,"ridge")==b"inert model"

@pytest.mark.parametrize("failure", ["disk_full", "permission"])
def test_model_publication_final_copy_failure_preserves_foreign_bytes(monkeypatch, tmp_path, failure):
    import errno
    home, eid, config, results, digest = _fresh_model_worker(monkeypatch, tmp_path)
    foreign = home / "models" / "unrelated"
    foreign.mkdir()
    (foreign / "keep").write_bytes(b"preserve")
    original = model_artifacts._stream_verified
    def interrupted_copy(path, expected, verify, **kwargs):
        output = kwargs.get("output")
        if output is not None:
            output.write(b"partial")
            code = errno.ENOSPC if failure == "disk_full" else errno.EACCES
            raise OSError(code, "Injected final copy failure")
        return original(path, expected, verify, **kwargs)
    monkeypatch.setattr(model_artifacts, "_stream_verified", interrupted_copy)
    with pytest.raises(OSError):
        model_artifacts.publish(eid, config, digest, results, {"ridge": b"inert model"}, b"inert holdout")
    assert storage.get_experiment(eid)["status"] == "running"
    with storage.connect() as con:
        receipt = model_publication.read(con, eid)
        assert receipt.state == "interrupted"
        assert receipt.reason_code == "storage_unavailable"
    assert not (home / "models" / eid).exists()
    assert not (home / "models" / (eid + ".publishing")).exists()
    assert (foreign / "keep").read_bytes() == b"preserve"


def test_verified_load_disk_fills_after_admission_defers_without_deserializing(monkeypatch, tmp_path):
    import errno
    from types import SimpleNamespace
    home, experiment, receipt = _verified_load_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(model_artifacts.shutil, "disk_usage", lambda _: SimpleNamespace(free=2**30))
    monkeypatch.setattr(model_artifacts.resource_policy, "admit_new_work", lambda _: {"decision": "allow"})
    def interrupted_copy(path, expected, verify, **kwargs):
        kwargs["output"].write(b"partial")
        raise OSError(errno.ENOSPC, "Injected scratch capacity failure")
    monkeypatch.setattr(model_artifacts, "_stream_verified", interrupted_copy)
    monkeypatch.setattr(model_artifacts.joblib, "load", lambda *a, **kw: pytest.fail("Unexpected deserialization"))
    with pytest.raises(model_artifacts.LoadDeferred, match="disk space"):
        model_artifacts.load_verified(experiment, "ridge", holdout=True)
    assert storage.get_experiment(experiment["id"])["status"] == "completed"
    assert not list((home / "backend-temp").iterdir())
    assert (home / "models" / experiment["id"] / "ridge.joblib").read_bytes() == b"inert model"

@pytest.mark.parametrize("overflow", [False, True])
def test_model_publication_aggregate_byte_boundary(monkeypatch, tmp_path, overflow):
    home, eid, config, results, digest = _fresh_model_worker(monkeypatch, tmp_path)
    monkeypatch.setattr(model_publication, "MAX_FILE_BYTES", 8)
    monkeypatch.setattr(model_publication, "MAX_TOTAL_BYTES", 12)
    model, holdout = b"12345678", b"12345" if overflow else b"1234"
    if overflow:
        with pytest.raises(model_artifacts.ArtifactBudgetExceeded, match="Choose fewer model candidates"):
            model_artifacts.publish(eid, config, digest, results, {"ridge": model}, holdout)
        with storage.connect() as con:
            receipt = model_publication.read(con, eid)
            assert receipt.state == "interrupted"
            assert receipt.reason_code == "storage_unavailable"
        assert storage.get_experiment(eid)["status"] == "running"
        assert not (home / "models" / eid).exists()
        assert not (home / "models" / (eid + ".publishing")).exists()
    else:
        receipt = model_artifacts.publish(eid, config, digest, results, {"ridge": model}, holdout)
        assert receipt.state == "committed"
        assert sum(item["size"] for item in receipt.files.values()) == 12
        assert storage.get_experiment(eid)["status"] == "completed"

@pytest.mark.parametrize("journal_mode", ["delete", "wal"])
def test_b3_stage_database_snapshot_is_standalone_and_preserves_source(tmp_path, journal_mode):
    import sqlite3
    from backend import maintenance_backup
    home = tmp_path / "source"
    home.mkdir()
    db = home / "pilotodin.sqlite3"
    target = tmp_path / "stage"
    con = sqlite3.connect(db)
    try:
        assert con.execute("PRAGMA journal_mode=" + journal_mode).fetchone()[0] == journal_mode
        con.execute("CREATE TABLE records(id INTEGER PRIMARY KEY, label TEXT)")
        con.execute("INSERT INTO records VALUES(1, '0001')")
        con.commit()
        if journal_mode == "wal":
            assert (home / "pilotodin.sqlite3-wal").stat().st_size > 0
        original = db.read_bytes()
        wal = home / "pilotodin.sqlite3-wal"
        wal_before = wal.read_bytes() if wal.exists() else None
        receipt = maintenance_backup.stage_database_snapshot(home, target, confirmed=True)
        copied = target / "pilotodin.sqlite3"
        assert receipt.size == copied.stat().st_size
        assert receipt.sha256 == hashlib.sha256(copied.read_bytes()).hexdigest()
        from backend.workspace_boundary import LOCK_NAME, BACKUP_STAGE_NAME
        assert {p.name for p in target.iterdir()} == {"pilotodin.sqlite3", LOCK_NAME, BACKUP_STAGE_NAME}
        with sqlite3.connect(copied.as_uri() + "?mode=ro", uri=True) as restored:
            assert restored.execute("SELECT * FROM records").fetchall() == [(1, "0001")]
            assert restored.execute("PRAGMA journal_mode").fetchone() == ("delete",)
            assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.read_bytes() == original
        if wal_before is not None:
            assert wal.read_bytes() == wal_before
    finally:
        con.close()


def test_b3_snapshot_refuses_missing_confirmation_collision_and_active_lease(tmp_path):
    import sqlite3
    from backend import maintenance_backup
    from backend.workspace_boundary import existing_maintenance_workspace
    home = tmp_path / "source"
    home.mkdir()
    db = home / "pilotodin.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE records(id INTEGER PRIMARY KEY)")
    con.close()
    target = tmp_path / "stage"
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="confirmation"):
        maintenance_backup.stage_database_snapshot(home, target)
    assert not target.exists()
    with existing_maintenance_workspace(str(home)):
        with pytest.raises(maintenance_backup.SnapshotBlocked):
            maintenance_backup.stage_database_snapshot(home, target, confirmed=True)
    assert not target.exists()
    target.mkdir()
    (target / "foreign").write_bytes(b"preserve")
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="already exists"):
        maintenance_backup.stage_database_snapshot(home, target, confirmed=True)
    assert (target / "foreign").read_bytes() == b"preserve"
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="outside"):
        maintenance_backup.stage_database_snapshot(home, home / "stage", confirmed=True)


def test_b3_snapshot_legacy_fk_violation_does_not_repair_or_certify(tmp_path):
    import sqlite3
    from backend import maintenance_backup
    home = tmp_path / "source"
    home.mkdir()
    db = home / "pilotodin.sqlite3"
    with sqlite3.connect(db) as con:
        con.executescript("CREATE TABLE parent(id INTEGER PRIMARY KEY);"
                          "CREATE TABLE child(pid REFERENCES parent(id));"
                          "INSERT INTO child VALUES(42);")
    con.close()
    before = db.read_bytes()
    stage = tmp_path / "stage"
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="foreign-key violations"):
        maintenance_backup.stage_database_snapshot(home, stage, confirmed=True)
    assert db.read_bytes() == before
    assert (stage / "pilotodin.sqlite3").is_file()
    assert not (stage / "manifest.json").exists()


def test_b3_snapshot_refuses_missing_source_without_creating_database(tmp_path):
    from backend import maintenance_backup
    home = tmp_path / "source"
    home.mkdir()
    with pytest.raises(maintenance_backup.SnapshotBlocked):
        maintenance_backup.stage_database_snapshot(home, tmp_path / "stage", confirmed=True)
    assert not list(home.iterdir())
    assert not (tmp_path / "stage").exists()

def _backup_model_fixture(monkeypatch, tmp_path):
    home, experiment, receipt = _verified_load_fixture(monkeypatch, tmp_path)
    # The helper creates an earlier running experiment, so settle it using
    # existing startup recovery before the offline maintenance fixture.
    storage.recover_model_publications()
    storage.recover_interrupted_experiments()
    with storage.connect() as con:
        con.execute("INSERT INTO project_lifecycle VALUES (?,?,?)",
                    (experiment["project_id"], 1, storage.now()))
    return home, experiment, receipt


def test_b3_stage_referenced_archived_payloads_and_exclude_unknown_files(monkeypatch, tmp_path):
    from backend import maintenance_backup
    import json
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    (home / "ai_secrets.dpapi").write_bytes(b"synthetic-secret")
    (home / "datasets" / "unreferenced.csv").write_bytes(b"unknown")
    (home / "models" / "unreferenced").mkdir()
    before = (home / "pilotodin.sqlite3").read_bytes()
    target = tmp_path / "backup"
    manifest = maintenance_backup.stage_workspace_backup(home, target, confirmed=True)
    expected = {"pilotodin.sqlite3", "datasets/source.csv",
                f"models/{experiment['id']}/ridge.joblib",
                f"models/{experiment['id']}/test_set.joblib"}
    assert set(manifest["files"]) == expected
    assert json.loads((target / "manifest.json").read_text()) == manifest
    for name, item in manifest["files"].items():
        raw = (target / name).read_bytes()
        assert item == {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    assert (target / "datasets" / "source.csv").read_bytes() == _csv()
    assert (target / "models" / experiment["id"] / "ridge.joblib").read_bytes() == b"inert model"
    assert not (target / "ai_secrets.dpapi").exists()
    assert not (target / "datasets" / "unreferenced.csv").exists()
    assert (home / "pilotodin.sqlite3").read_bytes() == before
    assert (home / "ai_secrets.dpapi").read_bytes() == b"synthetic-secret"


@pytest.mark.parametrize("failure", ["missing", "digest", "external", "legacy_model", "model_digest", "extra_model", "hardlink"])
def test_b3_invalid_references_do_not_publish_manifest(monkeypatch, tmp_path, failure):
    from backend import maintenance_backup
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    source = home / "datasets" / "source.csv"
    foreign = tmp_path / "foreign.csv"
    foreign.write_bytes(_csv())
    model = home / "models" / experiment["id"] / "ridge.joblib"
    if failure == "missing":
        source.unlink()
    elif failure == "digest":
        source.write_bytes(b"x" * len(_csv()))
    elif failure == "external":
        with storage.connect() as con:
            con.execute("UPDATE projects SET dataset_path=? WHERE id=?",
                        (str(foreign), experiment["project_id"]))
    elif failure == "legacy_model":
        with storage.connect() as con:
            con.execute("DELETE FROM model_publications_v1 WHERE experiment_id=?", (experiment["id"],))
    elif failure == "model_digest":
        model.write_bytes(b"x" * len(b"inert model"))
    elif failure == "extra_model":
        (model.parent / "unexpected.joblib").write_bytes(b"unknown")
    elif failure == "hardlink":
        source.unlink()
        os.link(foreign, source)
    target = tmp_path / "backup"
    before = (home / "pilotodin.sqlite3").read_bytes()
    expected_message = {
        "missing": "unavailable or unsafe",
        "digest": "Referenced payload digest mismatch",
        "external": "outside the admitted source layout",
        "legacy_model": "Legacy or unverified completed model",
        "model_digest": "Referenced payload digest mismatch",
        "extra_model": "Unexpected model directory entry",
        "hardlink": "unavailable or unsafe",
    }[failure]
    with pytest.raises(maintenance_backup.SnapshotBlocked, match=expected_message):
        maintenance_backup.stage_workspace_backup(home, target, confirmed=True)
    assert not (target / "manifest.json").exists()
    assert (home / "pilotodin.sqlite3").read_bytes() == before
    assert foreign.read_bytes() == _csv()
    if failure in ("digest", "model_digest"):
        # A prior, unrelated refusal must not count as digest coverage.
        copied = target / ("datasets/source.csv" if failure == "digest"
                           else f"models/{experiment['id']}/ridge.joblib")
        assert copied.is_file()
        assert copied.read_bytes() == (source if failure == "digest" else model).read_bytes()

def test_b3_replaced_stage_parent_blocks_nested_creation(monkeypatch, tmp_path):
    from backend import maintenance_backup
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    stage = tmp_path / "backup"
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    original = maintenance_backup.pinned_existing_directory
    from contextlib import contextmanager

    @contextmanager
    def replaced(value, **kwargs):
        path = Path(value)
        if path == stage / "models" and kwargs.get("expected") is not None:
            # Replace the parent between the initial mkdir and its admission.
            # The retained expected identity must prevent nested writes.
            if not (stage / "displaced-models").exists():
                path.rename(stage / "displaced-models")
                path.mkdir()
        with original(value, **kwargs) as verify:
            yield verify

    monkeypatch.setattr(maintenance_backup, "pinned_existing_directory", replaced)
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="unavailable or unsafe"):
        maintenance_backup.stage_workspace_backup(home, stage, confirmed=True)
    assert (stage / "displaced-models").is_dir(), "Replacement must actually have been injected"
    assert not (stage / "manifest.json").exists()
    assert not (stage / "models" / experiment["id"]).exists()
    assert not list(unrelated.iterdir())

def test_b3_independent_verification_without_original_workspace(monkeypatch, tmp_path):
    from backend import maintenance_backup
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    stage = tmp_path / "backup"
    manifest = maintenance_backup.stage_workspace_backup(home, stage, confirmed=True)
    # Verification must rely on the explicit recorded location, not on
    # opening the old location or matching arbitrary source basenames.
    moved = tmp_path / "moved-source"
    home.rename(moved)
    before = {p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}
    monkeypatch.setattr(model_artifacts.joblib, "load", lambda *a, **kw: pytest.fail("Unexpected deserialization"))
    assert maintenance_backup.verify_staged_backup(stage, recorded_source_home=home) == manifest
    assert not home.exists()
    assert before == {p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="outside the admitted source layout"):
        maintenance_backup.verify_staged_backup(stage, recorded_source_home=moved)


@pytest.mark.parametrize("failure,message", [
    ("duplicate", "Duplicate backup manifest key"),
    ("traversal", "Invalid relative backup payload name"),
    ("extra", "Unexpected backup tree entry"),
    ("missing", "Missing backup tree entry"),
    ("digest", "Backup payload digest mismatch"),
    ("forged_digest", "disagrees with database provenance"),
    ("foreign_key", "foreign-key violations"),
    ("hardlink", "unavailable or unsafe"),
    ("case_collision", "Case-colliding backup payload names"),
])
def test_b3_independent_verification_rejects_tampering(monkeypatch, tmp_path, failure, message):
    from backend import maintenance_backup
    import json
    import sqlite3
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    stage = tmp_path / "backup"
    manifest = maintenance_backup.stage_workspace_backup(home, stage, confirmed=True)
    path = stage / "manifest.json"
    source = stage / "datasets" / "source.csv"
    if failure == "duplicate":
        path.write_text('{"schema_version":1,' + path.read_text()[1:])
    elif failure == "traversal":
        manifest["files"]["../escape.csv"] = manifest["files"]["datasets/source.csv"]
        path.write_text(json.dumps(manifest))
    elif failure == "extra":
        (stage / "unknown").mkdir()
    elif failure == "missing":
        source.unlink()
    elif failure in ("digest", "forged_digest"):
        source.write_bytes(b"x" * len(_csv()))
        if failure == "forged_digest":
            manifest["files"]["datasets/source.csv"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            path.write_text(json.dumps(manifest))
    elif failure == "foreign_key":
        db = stage / "pilotodin.sqlite3"
        with sqlite3.connect(db) as con:
            con.execute("PRAGMA foreign_keys=OFF")
            con.execute("UPDATE project_lifecycle SET project_id=?", ("f"*32,))
        con.close()
        manifest["files"]["pilotodin.sqlite3"] = {"size": db.stat().st_size, "sha256": hashlib.sha256(db.read_bytes()).hexdigest()}
        path.write_text(json.dumps(manifest))
    elif failure == "hardlink":
        foreign = tmp_path / "foreign"
        source.rename(foreign)
        os.link(foreign, source)
    elif failure == "case_collision":
        manifest["files"]["datasets/SOURCE.csv"] = manifest["files"]["datasets/source.csv"]
        path.write_text(json.dumps(manifest))
    with pytest.raises(maintenance_backup.SnapshotBlocked, match=message):
        maintenance_backup.verify_staged_backup(stage, recorded_source_home=home)
    assert (home / "datasets" / "source.csv").read_bytes() == _csv()

def test_b3_restore_archived_workspace_preserves_all_rows_except_exact_paths(monkeypatch, tmp_path):
    from backend import maintenance_backup
    import json
    import sqlite3
    from contextlib import closing
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    stage = tmp_path / "backup"
    maintenance_backup.stage_workspace_backup(home, stage, confirmed=True)
    before = {p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}
    original = (home / "pilotodin.sqlite3").read_bytes()
    target = tmp_path / "restored"
    monkeypatch.setattr(model_artifacts.joblib, "load", lambda *a, **kw: pytest.fail("Unexpected deserialization"))
    outcome = maintenance_backup.restore_staged_backup(stage, target, recorded_source_home=home, confirmed=True)
    assert outcome["status"] == "staged_not_activated"
    assert outcome["mappings"] == [{"project_id": experiment["project_id"], "relative_path": "datasets/source.csv"}]
    assert json.loads((target / "restore_receipt.json").read_text()) == outcome
    assert outcome["source_manifest_sha256"] == hashlib.sha256((stage / "manifest.json").read_bytes()).hexdigest()
    db = target / "pilotodin.sqlite3"
    assert outcome["database"]["sha256"] == hashlib.sha256(db.read_bytes()).hexdigest()
    assert (target / "datasets" / "source.csv").read_bytes() == _csv()
    assert (target / "models" / experiment["id"] / "ridge.joblib").read_bytes() == b"inert model"
    with closing(sqlite3.connect((stage / "pilotodin.sqlite3").as_uri() + "?mode=ro", uri=True)) as old:
        with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as new:
            assert new.execute("PRAGMA foreign_key_check").fetchall() == []
            tables = old.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            for (table,) in tables:
                quoted = '"' + table.replace('"', '""') + '"'
                previous = old.execute("SELECT * FROM " + quoted).fetchall()
                current = new.execute("SELECT * FROM " + quoted).fetchall()
                if table == "projects":
                    assert len(previous) == len(current) == 1
                    row = list(previous[0])
                    row[4] = str(target / "datasets" / "source.csv")
                    assert current == [tuple(row)]
                else:
                    assert previous == current, table
    assert before == {p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}
    assert (home / "pilotodin.sqlite3").read_bytes() == original


@pytest.mark.parametrize("failure,message", [
    ("unconfirmed", "confirmation required"),
    ("collision", "already exists"),
    ("inside_backup", "outside backup and historical source"),
    ("inside_source", "outside backup and historical source"),
    ("tamper", "Backup payload digest mismatch"),
])
def test_b3_restore_refuses_before_destination_creation(monkeypatch, tmp_path, failure, message):
    from backend import maintenance_backup
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    stage = tmp_path / "backup"
    maintenance_backup.stage_workspace_backup(home, stage, confirmed=True)
    target = tmp_path / "restored"
    if failure == "collision":
        target.mkdir()
        (target / "keep").write_bytes(b"preserve")
    elif failure == "inside_backup":
        target = stage / "restore"
    elif failure == "inside_source":
        target = home / "restore"
    elif failure == "tamper":
        (stage / "datasets" / "source.csv").write_bytes(b"x" * len(_csv()))
    with pytest.raises(maintenance_backup.SnapshotBlocked, match=message):
        maintenance_backup.restore_staged_backup(stage, target, recorded_source_home=home,
                                                 confirmed=failure != "unconfirmed")
    if failure == "collision":
        assert (target / "keep").read_bytes() == b"preserve"
    else:
        assert not target.exists()


def test_b3_interrupted_restore_retains_uncompleted_stage(monkeypatch, tmp_path):
    from backend import maintenance_backup
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    stage = tmp_path / "backup"
    maintenance_backup.stage_workspace_backup(home, stage, confirmed=True)
    target = tmp_path / "restored"
    before = (stage / "pilotodin.sqlite3").read_bytes()
    def interrupted(*args, **kwargs):
        raise OSError("Injected interruption before reference mapping")
    monkeypatch.setattr(maintenance_backup, "_restore_references", interrupted)
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="Restore unavailable"):
        maintenance_backup.restore_staged_backup(stage, target, recorded_source_home=home, confirmed=True)
    assert (target / "pilotodin.sqlite3").read_bytes() == before
    assert not (target / "restore_receipt.json").exists()
    assert (stage / "pilotodin.sqlite3").read_bytes() == before


@pytest.mark.parametrize("fault", ["disk_full", "permission", "interrupted"])
def test_b3_restore_fault_retains_nonactivatable_stage(monkeypatch, tmp_path, fault):
    import errno
    from backend import maintenance_backup, workspace_boundary
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    stage = tmp_path / "backup"
    maintenance_backup.stage_workspace_backup(home, stage, confirmed=True)
    before = {p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}
    target = tmp_path / "restored"
    original = maintenance_backup._fingerprint
    injected = []

    def fail_copy(path, verify, checkpoint, **kwargs):
        if path == stage / "datasets" / "source.csv" and kwargs.get("output") is not None:
            assert (target / workspace_boundary.RESTORE_STAGE_NAME).is_file()
            with pytest.raises(workspace_boundary.WorkspaceBoundaryError, match="activation approval"):
                with workspace_boundary.engine_workspace(str(target)):
                    pytest.fail("Restore stage admitted")
            injected.append(fault)
            kwargs["output"].write(b"partial")
            code = {"disk_full": errno.ENOSPC, "permission": errno.EACCES,
                    "interrupted": errno.EIO}[fault]
            raise OSError(code, "Injected restore write failure")
        return original(path, verify, checkpoint, **kwargs)

    monkeypatch.setattr(maintenance_backup, "_fingerprint", fail_copy)
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="Restore unavailable"):
        maintenance_backup.restore_staged_backup(stage, target, recorded_source_home=home, confirmed=True)
    assert injected == [fault]
    assert (target / "datasets" / "source.csv").read_bytes() == b"partial"
    assert not (target / "restore_receipt.json").exists()
    with pytest.raises(workspace_boundary.WorkspaceBoundaryError, match="activation approval"):
        with workspace_boundary.engine_workspace(str(target)):
            pytest.fail("Interrupted restore stage admitted")
    assert before == {p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}


def test_b3_completed_restore_still_requires_separate_activation(monkeypatch, tmp_path):
    from backend import maintenance_backup, workspace_boundary
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    stage, target = tmp_path / "backup", tmp_path / "restored"
    maintenance_backup.stage_workspace_backup(home, stage, confirmed=True)
    outcome = maintenance_backup.restore_staged_backup(stage, target, recorded_source_home=home, confirmed=True)
    assert outcome["status"] == "staged_not_activated"
    assert (target / workspace_boundary.RESTORE_STAGE_NAME).is_file()
    before = (target / "pilotodin.sqlite3").read_bytes()
    with pytest.raises(workspace_boundary.WorkspaceBoundaryError, match="activation approval"):
        with workspace_boundary.engine_workspace(str(target)):
            pytest.fail("Completed restore stage admitted")
    assert (target / "pilotodin.sqlite3").read_bytes() == before


def test_b3_backup_directory_refuses_runtime_and_excludes_coordination_from_manifest(monkeypatch, tmp_path):
    from backend import maintenance_backup, workspace_boundary
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    target = tmp_path / "backup"
    manifest = maintenance_backup.stage_workspace_backup(home, target, confirmed=True)
    assert workspace_boundary.LOCK_NAME not in manifest["files"]
    assert workspace_boundary.BACKUP_STAGE_NAME not in manifest["files"]
    assert (target / workspace_boundary.BACKUP_STAGE_NAME).read_bytes() == b""
    with pytest.raises(workspace_boundary.WorkspaceBoundaryError, match="not an active workspace"):
        with workspace_boundary.engine_workspace(str(target)):
            pytest.fail("Backup directory admitted")
    assert maintenance_backup.verify_staged_backup(target, recorded_source_home=home) == manifest


@pytest.mark.parametrize("fault", ["disk_full", "permission"])
def test_b3_backup_copy_failure_retains_blocked_stage(monkeypatch, tmp_path, fault):
    import errno
    from backend import maintenance_backup, workspace_boundary
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    target = tmp_path / "backup"
    before = (home / "pilotodin.sqlite3").read_bytes()
    original = maintenance_backup._fingerprint
    injected = []
    def fail(path, verify, checkpoint, **kwargs):
        if path == home / "datasets" / "source.csv" and kwargs.get("output") is not None:
            assert (target / workspace_boundary.BACKUP_STAGE_NAME).is_file()
            with pytest.raises(workspace_boundary.WorkspaceBoundaryError, match="not an active workspace"):
                with workspace_boundary.engine_workspace(str(target)):
                    pytest.fail("Backup directory admitted during copy")
            injected.append(fault)
            kwargs["output"].write(b"partial")
            raise OSError(errno.ENOSPC if fault == "disk_full" else errno.EACCES, "Injected backup write failure")
        return original(path, verify, checkpoint, **kwargs)
    monkeypatch.setattr(maintenance_backup, "_fingerprint", fail)
    with pytest.raises(maintenance_backup.SnapshotBlocked, match="snapshot unavailable"):
        maintenance_backup.stage_workspace_backup(home, target, confirmed=True)
    assert injected == [fault]
    assert (target / "datasets" / "source.csv").read_bytes() == b"partial"
    assert not (target / "manifest.json").exists()
    with pytest.raises(workspace_boundary.WorkspaceBoundaryError, match="not an active workspace"):
        with workspace_boundary.engine_workspace(str(target)):
            pytest.fail("Incomplete backup directory admitted")
    assert (home / "pilotodin.sqlite3").read_bytes() == before


@pytest.mark.parametrize("fault", ["missing_marker", "nonempty_marker", "original_history"])
def test_b3_backup_verifier_rejects_invalid_coordination_or_origin(monkeypatch, tmp_path, fault):
    import json
    import sqlite3
    from backend import maintenance_backup, workspace_boundary
    home, experiment, receipt = _backup_model_fixture(monkeypatch, tmp_path)
    target = tmp_path / "backup"
    manifest = maintenance_backup.stage_workspace_backup(home, target, confirmed=True)
    marker = target / workspace_boundary.BACKUP_STAGE_NAME
    if fault == "missing_marker":
        marker.unlink()
        message = "unavailable or unsafe"
    elif fault == "nonempty_marker":
        marker.write_bytes(b"invalid")
        message = "Invalid backup coordination marker"
    else:
        db = target / "pilotodin.sqlite3"
        with sqlite3.connect(db) as con:
            con.execute("UPDATE quality_versions SET event='tampered' WHERE version=0")
        con.close()
        manifest["files"]["pilotodin.sqlite3"] = {"size": db.stat().st_size,
                                                  "sha256": hashlib.sha256(db.read_bytes()).hexdigest()}
        (target / "manifest.json").write_text(json.dumps(manifest))
        message = "Invalid original Quality history"
    with pytest.raises(maintenance_backup.SnapshotBlocked, match=message):
        maintenance_backup.verify_staged_backup(target, recorded_source_home=home)


@pytest.mark.parametrize("ext", [".csv", ".xlsx"])
def test_b4_quality_parser_uses_identical_verified_bytes_after_source_replaced(monkeypatch, tmp_path, ext):
    import io
    from backend import dataset_publication
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    frame = pd.DataFrame({"CustomerID": ["0001", "0002"], "Revenue": [12, 34]})
    altered = pd.DataFrame({"CustomerID": ["9999", "8888"], "Revenue": [90, 80]})
    def encode(value):
        if ext == ".csv":
            return value.to_csv(index=False).encode()
        buffer = io.BytesIO()
        value.to_excel(buffer, index=False, engine="openpyxl")
        return buffer.getvalue()
    original = encode(frame)
    changed = encode(altered)
    path = home / "datasets" / ("source" + ext)
    path.write_bytes(original)
    pid = storage.save_project("Source", path.name, ext, path, {},
                               original_sha256=hashlib.sha256(original).hexdigest())
    real = dataset_publication.read_verified_source
    injected = []
    def replace_after_read(*args, **kwargs):
        raw = real(*args, **kwargs)
        if kwargs.get("capture"):
            injected.append(True)
            path.write_bytes(changed)
        return raw
    monkeypatch.setattr(dataset_publication, "read_verified_source", replace_after_read)
    actual, version = quality.current_data(pid)
    assert injected == [True]
    assert version == 0
    assert actual["CustomerID"].tolist() == ["0001", "0002"]
    assert actual["Revenue"].tolist() == [12, 34]
    with pytest.raises(quality.QualityError, match="changed outside PilotODIN"):
        quality.current_data(pid)


def test_b4_legacy_source_over_limit_refused_before_parser(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    raw = _csv()
    path = home / "datasets" / "source.csv"
    path.write_bytes(raw)
    pid = storage.save_project("Source", path.name, ".csv", path, {},
                               original_sha256=hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(artifact_publication, "MAX_DATASET_BYTES", len(raw) - 1)
    monkeypatch.setattr(quality, "_source_df", lambda *a, **kw: pytest.fail("Oversized source parsed"))
    with pytest.raises(quality.QualityError, match="40 MiB"):
        quality.current_data(pid)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("fault", ["none", "source", "revision", "decision", "archive"])
def test_b4_direct_imputation_stages_without_sqlite_write_lock(monkeypatch, tmp_path, fault):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    raw = b"CustomerID,Revenue\n0001,10\n0002,\n0003,30\n"
    path = home / "datasets" / "source.csv"
    path.write_bytes(raw)
    pid = storage.save_project("Source", path.name, ".csv", path, {},
                               original_sha256=hashlib.sha256(raw).hexdigest())
    issue = next(x for x in quality.snapshot(pid)["issues"]
                 if x["kind"] == "missing" and x["column"] == "Revenue")
    apply = quality._apply
    injected = []
    def stage(frame, proposal, **kwargs):
        result = apply(frame, proposal, **kwargs)
        if proposal["kind"] == "impute_numeric_median":
            with storage.connect() as con:
                con.execute("PRAGMA busy_timeout=200")
                con.execute("BEGIN IMMEDIATE")
                if fault in ("revision", "archive"):
                    con.execute("INSERT INTO project_lifecycle VALUES(?,?,?)",
                                (pid, 1, storage.now() if fault == "archive" else None))
                elif fault == "decision":
                    con.execute("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                                (pid, issue["id"], "rejected", storage.now()))
            if fault == "source":
                path.write_bytes(raw.replace(b",30", b",40"))
            injected.append(fault)
        return result
    monkeypatch.setattr(quality, "_apply", stage)
    if fault == "none":
        assert quality.approve_imputation(pid, "Revenue", issue["id"], 0)["version"] == 1
    else:
        with pytest.raises(quality.QualityError, match="changed|archived"):
            quality.approve_imputation(pid, "Revenue", issue["id"], 0)
    assert injected == [fault]
    with storage.connect() as con:
        assert con.execute("SELECT current_version FROM quality_state WHERE project_id=?", (pid,)).fetchone()[0] == (1 if fault == "none" else 0)
        assert con.execute("SELECT COUNT(*) FROM quality_actions WHERE project_id=?", (pid,)).fetchone()[0] == (1 if fault == "none" else 0)


def test_b4_read_snapshot_releases_metadata_transaction_before_parse(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    raw = _csv()
    path = home / "datasets" / "source.csv"
    path.write_bytes(raw)
    pid = storage.save_project("Source", path.name, ".csv", path, {},
                               original_sha256=hashlib.sha256(raw).hexdigest())
    original = quality._source_df
    called = []
    def parse(*args, **kwargs):
        with storage.connect() as con:
            con.execute("PRAGMA busy_timeout=200")
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                        (pid, "synthetic-later-decision", "rejected", storage.now()))
        called.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(quality, "_source_df", parse)
    frame, version = quality.current_data(pid)
    assert called == [True]
    assert version == 0
    assert frame["CustomerID"].tolist() == ["0001", "0002", "0003"]


def _b4_autopilot_fixture(monkeypatch, tmp_path):
    home = _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    raw = b"Region,Segment,Revenue\n North, Retail,10\nNorth,Retail,20\nNorth,Retail,30\nNorth,Retail,40\nNorth,Retail,50\nNorth,Retail,60\nNorth,Retail,70\nNorth,Retail,80\n"
    path = home / "datasets" / "source.csv"
    path.write_bytes(raw)
    pid = storage.save_project("Source", path.name, ".csv", path, {},
                               original_sha256=hashlib.sha256(raw).hexdigest())
    assert quality.snapshot(pid)["summary"]["automatic_available"] == 2
    return pid, path, raw


@pytest.mark.parametrize("fault", ["none", "source", "decision"])
def test_b4_autopilot_stages_entire_batch_before_write(monkeypatch, tmp_path, fault):
    pid, path, raw = _b4_autopilot_fixture(monkeypatch, tmp_path)
    apply = quality._apply
    calls = []
    def stage(frame, proposal, **kwargs):
        result = apply(frame, proposal, **kwargs)
        calls.append(proposal["column"])
        if len(calls) == 2:
            with storage.connect() as con:
                con.execute("PRAGMA busy_timeout=200")
                con.execute("BEGIN IMMEDIATE")
                if fault == "decision":
                    con.execute("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                                (pid, "later-review", "rejected", storage.now()))
            if fault == "source":
                path.write_bytes(raw.replace(b",80", b",81"))
        return result
    monkeypatch.setattr(quality, "_apply", stage)
    if fault == "none":
        result = quality.autopilot(pid, 0)
        assert result["version"] == result["count"] == 2
    else:
        with pytest.raises(quality.QualityError, match="changed"):
            quality.autopilot(pid, 0)
    assert len(calls) == 2
    with storage.connect() as con:
        expected = 2 if fault == "none" else 0
        assert con.execute("SELECT current_version FROM quality_state WHERE project_id=?", (pid,)).fetchone()[0] == expected
        assert con.execute("SELECT COUNT(*) FROM quality_actions WHERE project_id=?", (pid,)).fetchone()[0] == expected


@pytest.mark.parametrize("operation", ["undo", "restore"])
@pytest.mark.parametrize("fault", ["none", "audit", "target"])
def test_b4_history_transition_replays_outside_lock_and_fences_history(monkeypatch, tmp_path, operation, fault):
    pid, path, raw = _b4_autopilot_fixture(monkeypatch, tmp_path)
    batch = quality.autopilot(pid, 0)
    action = batch["applied"][-1]["id"]
    parse = quality._source_df
    injected = []
    def stage(*args, **kwargs):
        with storage.connect() as con:
            con.execute("PRAGMA busy_timeout=200")
            con.execute("BEGIN IMMEDIATE")
            if fault == "audit":
                con.execute("UPDATE quality_versions SET details_json='{}' WHERE project_id=? AND version=2", (pid,))
            elif fault == "target":
                con.execute("UPDATE quality_actions SET source='tampered' WHERE project_id=? AND id=?",
                            (pid, batch["applied"][0]["id"]))
        injected.append(True)
        return parse(*args, **kwargs)
    monkeypatch.setattr(quality, "_source_df", stage)
    call = (lambda: quality.undo(pid, action, 2)) if operation == "undo" else (lambda: quality.restore(pid, 1, 2))
    if fault == "none":
        outcome = call()
        assert outcome["version"] == 3 and outcome["active_actions"] == 1
    else:
        with pytest.raises(quality.QualityError, match="changed"):
            call()
    assert injected == [True]
    with storage.connect() as con:
        assert con.execute("SELECT current_version FROM quality_state WHERE project_id=?", (pid,)).fetchone()[0] == (3 if fault == "none" else 2)
        assert con.execute("SELECT COUNT(*) FROM quality_actions WHERE project_id=?", (pid,)).fetchone()[0] == 2
        assert con.execute("SELECT COUNT(*) FROM quality_decisions WHERE project_id=? AND status='undone'", (pid,)).fetchone()[0] == (1 if fault == "none" else 0)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("fault", ["none", "revision", "decision", "same_bytes_replacement", "legacy_receipt"])
def test_b4_explicit_receipt_binds_review_source_and_metadata(monkeypatch, tmp_path, fault):
    import json
    from backend import quality_approvals as approvals
    pid,path,raw=_b4_autopilot_fixture(monkeypatch,tmp_path)
    issue=next(x for x in quality.snapshot(pid)["issues"] if x["automatic"])
    response=approvals.prepare(pid,approvals.ProposalRequest(operation="approve",expected_version=0,issue_id=issue["id"]))
    if fault in ("revision","decision","legacy_receipt"):
        with storage.connect() as con:
            if fault=="revision":
                con.execute("INSERT INTO project_lifecycle VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET revision=1",(pid,1,None))
            elif fault=="decision":
                con.execute("INSERT INTO quality_decisions VALUES(?,?,?,?)",(pid,issue["id"],"rejected",storage.now()))
            else:
                row=con.execute("SELECT payload_json FROM quality_approval_receipts WHERE proposal_id=?",(response["proposal_id"],)).fetchone()
                payload=json.loads(row[0])
                payload.pop("review_binding")
                response["proposal_hash"]=approvals._hash(payload)
                con.execute("UPDATE quality_approval_receipts SET payload_json=?,proposal_hash=? WHERE proposal_id=?",
                            (quality._json(payload),response["proposal_hash"],response["proposal_id"]))
    elif fault=="same_bytes_replacement":
        replacement=path.with_name("replacement.csv")
        replacement.write_bytes(raw)
        replacement.replace(path)
    body=approvals.ApprovalCommit(proposal_id=response["proposal_id"],proposal_hash=response["proposal_hash"])
    if fault=="none":
        assert approvals.commit(pid,body)["version"]==1
    else:
        with pytest.raises(quality.QualityError,match="review state changed"):
            approvals.commit(pid,body)
    with storage.connect() as con:
        consumed=con.execute("SELECT consumed_at FROM quality_approval_receipts WHERE proposal_id=?",(body.proposal_id,)).fetchone()[0]
        assert (consumed is not None)==(fault=="none")
        assert con.execute("SELECT COUNT(*) FROM quality_actions WHERE project_id=?",(pid,)).fetchone()[0]==(1 if fault=="none" else 0)
    assert path.read_bytes()==raw


def test_b4_receipt_preview_refuses_source_change_before_publication(monkeypatch,tmp_path):
    from backend import quality_approvals as approvals
    pid,path,raw=_b4_autopilot_fixture(monkeypatch,tmp_path)
    issue=next(x for x in quality.snapshot(pid)["issues"] if x["automatic"])
    original=approvals._compare_rows
    injected=[]
    def mutate(*args,**kwargs):
        result=original(*args,**kwargs)
        path.write_bytes(raw.replace(b",80",b",81"))
        injected.append(True)
        return result
    monkeypatch.setattr(approvals,"_compare_rows",mutate)
    with pytest.raises(quality.QualityError,match="changed outside PilotODIN"):
        approvals.prepare(pid,approvals.ProposalRequest(operation="approve",expected_version=0,issue_id=issue["id"]))
    assert injected==[True]
    with storage.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM quality_approval_receipts WHERE project_id=?",(pid,)).fetchone()[0]==0
        assert con.execute("SELECT COUNT(*) FROM quality_actions WHERE project_id=?",(pid,)).fetchone()[0]==0


@pytest.mark.parametrize("fault", ["none", "source", "revision", "decision", "version", "archive", "action"])
def test_b4_quality_audit_stages_without_database_lock_and_fences_state(monkeypatch,tmp_path,fault):
    import json
    from backend import reports
    pid,path,raw=_b4_autopilot_fixture(monkeypatch,tmp_path)
    batch=quality.autopilot(pid,0)
    reports.init()
    original=quality._issues
    injected=[]
    def stage(frame):
        result=original(frame)
        with storage.connect() as con:
            con.execute("PRAGMA busy_timeout=200")
            con.execute("BEGIN IMMEDIATE")
            if fault in ("revision","archive"):
                con.execute("INSERT INTO project_lifecycle VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET revision=excluded.revision,archived_at=excluded.archived_at",
                            (pid,1,storage.now() if fault=="archive" else None))
            elif fault=="decision":
                con.execute("INSERT INTO quality_decisions VALUES(?,?,?,?)",
                            (pid,"later-decision","rejected",storage.now()))
            elif fault=="version":
                quality._add_version(con,pid,[],"restore",{"synthetic":True})
            elif fault=="action":
                con.execute("UPDATE quality_actions SET source='tampered' WHERE id=?",
                            (batch["applied"][0]["id"],))
        if fault=="source":
            path.write_bytes(raw.replace(b",80",b",81"))
        injected.append(fault)
        return result
    monkeypatch.setattr(quality,"_issues",stage)
    if fault=="none":
        result=reports.capture_quality(pid,2)
        assert result["dataset_version"]==2
        with storage.connect() as con:
            row=con.execute("SELECT * FROM report_quality_audits_v1 WHERE id=?",(result["id"],)).fetchone()
        audit=json.loads(row["snapshot_json"])
        assert row["sha256"]==hashlib.sha256(row["snapshot_json"].encode()).hexdigest()
        assert audit["summary"]["Approved working corrections active"]==2
        assert audit["source_original_sha256"]==hashlib.sha256(raw).hexdigest()
        assert '"preview"' not in row["snapshot_json"] and '"proposal"' not in row["snapshot_json"]
    else:
        with pytest.raises(reports.ReportError,match="changed|archived") as err:
            reports.capture_quality(pid,2)
        assert err.value.status==409
    assert injected==[fault]
    with storage.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM report_quality_audits_v1 WHERE project_id=?",(pid,)).fetchone()[0]==(1 if fault=="none" else 0)
        assert con.execute("SELECT COUNT(*) FROM quality_actions WHERE project_id=?",(pid,)).fetchone()[0]==2
    assert path.read_bytes()==(raw.replace(b",80",b",81") if fault=="source" else raw)
