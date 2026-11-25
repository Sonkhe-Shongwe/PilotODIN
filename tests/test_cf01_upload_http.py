"""CF-01 real FastAPI import-contract tests for the full PilotODIN checkout.

All files, SQLite metadata, and project state belong to disposable tmp_path.
Never point this module at a real owner workspace. These tests require the
complete backend source and are not covered by the isolated preflight fixture.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from tests.fixture_http import fixture_client
from openpyxl import Workbook

from backend import quality, storage
from backend.main import app


def _isolated(monkeypatch, tmp_path):
    home = tmp_path / "cf01-isolated-http"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    monkeypatch.delenv("PILOTODIN_DESKTOP_SESSION", raising=False)
    storage.init()
    quality._init_tables()
    return home


def _xlsx_bytes(columns):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Data")
    sheet.append([f"column{i}" for i in range(columns)])
    sheet.append([1] * columns)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _assert_no_projects_or_uploads(home):
    assert storage.list_projects() == []
    assert list((home / "datasets").iterdir()) == []
    with storage.connect() as con:
        for table in ("projects", "quality_state", "quality_versions"):
            assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_oversize_csv_http_rejected_without_any_published_file(monkeypatch, tmp_path):
    home = _isolated(monkeypatch, tmp_path)
    source = ("OrderNumber,Revenue\n" + "0007,1\n" * 100_001).encode("utf-8")
    with fixture_client(app) as client:
        result = client.post("/api/projects", files={"file": ("oversize.csv", source, "text/csv")})
        assert result.status_code == 422, result.text
        assert "100,000 rows" in result.json()["detail"]
        assert client.get("/api/projects").json() == []
    _assert_no_projects_or_uploads(home)


def test_oversize_xlsx_http_rejected_without_any_published_file(monkeypatch, tmp_path):
    home = _isolated(monkeypatch, tmp_path)
    source = _xlsx_bytes(101)
    with fixture_client(app) as client:
        result = client.post("/api/projects", files={"file": ("wide.xlsx", source, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert result.status_code == 422, result.text
        assert "100 columns" in result.json()["detail"]
        assert client.get("/api/projects").json() == []
    _assert_no_projects_or_uploads(home)


def test_rejected_xlsx_does_not_modify_an_existing_project(monkeypatch, tmp_path):
    home = _isolated(monkeypatch, tmp_path)
    original = b"SKU,Revenue\n0007,12\n0008,13\n"
    with fixture_client(app) as client:
        initial = client.post("/api/projects", files={"file": ("good.csv", original, "text/csv")})
        assert initial.status_code == 201, initial.text
        pid = initial.json()["id"]
        source_path = Path(storage.get_project(pid)["dataset_path"])
        assert source_path.read_bytes() == original
        rejected = client.post("/api/projects", files={"file": ("wide.xlsx", _xlsx_bytes(101), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert rejected.status_code == 422, rejected.text
        listed = client.get("/api/projects").json()
        assert len(listed) == 1 and listed[0]["id"] == pid
        assert source_path.read_bytes() == original
        assert list((home / "datasets").iterdir()) == [source_path]
        frame, version = quality.current_data(pid)
        assert version == 0
        assert frame.iloc[0]["SKU"] == "0007"


def test_valid_long_text_and_identifier_http_import_survive(monkeypatch, tmp_path):
    home = _isolated(monkeypatch, tmp_path)
    long_note = "A" * 160_000
    original = ('SKU,Notes,Revenue\n0007,"' + long_note + '\",12\n').encode("utf-8")
    with fixture_client(app) as client:
        uploaded = client.post("/api/projects", files={"file": ("long-text.csv", original, "text/csv")})
        assert uploaded.status_code == 201, uploaded.text
        pid = uploaded.json()["id"]
        preview = uploaded.json()["profile"]["preview"][0]
        assert preview["SKU"] == "0007"
        assert preview["Notes"] == long_note
        assert Path(storage.get_project(pid)["dataset_path"]).read_bytes() == original
        assert len(list((home / "datasets").iterdir())) == 1
