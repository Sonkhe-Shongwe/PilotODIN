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

from backend import quality, storage
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

    with patch.object(storage, "connect", side_effect=OSError("Synthetic storage failure")):
        response = TestClient(app).post(
            "/api/projects", files={"file": ("recoverable.csv", _csv(), "text/csv")},
        )
    assert response.status_code == 500, response.text
    retained, = (home / "datasets").iterdir()
    assert retained.suffix == ".csv"
    assert retained.read_bytes() == _csv()
    assert storage.list_projects() == []


def test_error_after_commit_preserves_catalogue_and_source(monkeypatch, tmp_path):
    _temporary_store(monkeypatch, tmp_path)
    quality._init_tables()
    save = storage.save_project

    def save_then_fail(*args, **kwargs):
        save(*args, **kwargs)
        raise OSError("Synthetic acknowledgement failure")

    monkeypatch.setattr(storage, "save_project", save_then_fail)
    client = TestClient(app)
    response = client.post("/api/projects", files={"file": ("generated.csv", _csv(), "text/csv")})
    assert response.status_code == 500, response.text
    row, = client.get("/api/projects").json()
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
from backend import main, storage

boundary, raw = sys.argv[1:]
original_connect = storage.connect
original_save = storage.save_project

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

if boundary == 'replace':
    interruption = patch.object(main.os, 'replace', side_effect=lambda *_: os._exit(73))
elif boundary == 'version':
    interruption = patch.object(storage, 'connect', connect)
else:
    interruption = patch.object(storage, 'save_project', save_and_stop)

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
        retained, = self.datasets.iterdir()
        self.assertTrue(retained.name.endswith(suffix), retained.name)
        self.assertEqual(retained.read_bytes(), _csv())
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/projects").json(), [])
            self.assertEqual(client.get("/api/projects/manage").json(), [])
            with storage.connect() as con:
                for table in ("projects", "quality_state", "quality_versions"):
                    self.assertEqual(con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], 0)
            uploaded = client.post("/api/projects", files={"file": ("generated.csv", _csv(), "text/csv")})
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            self.assertEqual(len(client.get("/api/projects").json()), 1)
        self.assertEqual(retained.read_bytes(), _csv())

    def test_restart_before_rename_keeps_staging_bytes_out_of_catalogue(self):
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
