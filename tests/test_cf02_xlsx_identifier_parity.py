"""CF-02 XLSX text identifier parity using generated, disposable workbooks.

This is a product source test and never accesses the owner's project data.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib

import pandas as pd
from tests.fixture_http import fixture_client
from openpyxl import Workbook

from backend import engine, main, quality, storage


def _workbook():
    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    sheet.append(["SKU", "OrderNumber", "CustomerID", "PostalCode", "Quantity", "Revenue"])
    sheet.append(["0007", "000012", "0009", "0018", 2, 120.50])
    sheet.append(["0008", "000013", "0010", "0019", 3, 140.00])
    # A second sheet must not be silently chosen.
    other = book.create_sheet("Other")
    other.append(["SKU", "Revenue"])
    other.append(["9999", 1])
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def _store(monkeypatch, tmp_path):
    home = tmp_path / "xlsx-parity"
    (home / "datasets").mkdir(parents=True)
    (home / "models").mkdir()
    monkeypatch.setattr(storage, "HOME", home)
    monkeypatch.setattr(storage, "DB_PATH", home / "pilotodin.sqlite3")
    monkeypatch.delenv("PILOTODIN_DESKTOP_SESSION", raising=False)
    storage.init()
    quality._init_tables()
    return home


def _assert_values(df):
    for col, want in [("SKU", "0007"), ("OrderNumber", "000012"),
                      ("CustomerID", "0009"), ("PostalCode", "0018")]:
        assert df.iloc[0][col] == want
        assert pd.api.types.is_string_dtype(df[col])
    assert df.iloc[0]["Revenue"] == 120.5
    assert df.iloc[0]["Quantity"] == 2
    assert pd.api.types.is_numeric_dtype(df["Revenue"])
    assert len(df) == 2


def test_reader_and_quality_preserve_xlsx_text_ids(tmp_path):
    path = tmp_path / "source.xlsx"
    raw = _workbook()
    path.write_bytes(raw)
    imported = engine.read_data(str(path), ".xlsx")
    working = quality._source_df({"dataset_path": str(path), "file_ext": ".xlsx"})
    _assert_values(imported)
    _assert_values(working)
    assert imported.to_dict("records") == working.to_dict("records")
    assert path.read_bytes() == raw


def test_xlsx_http_import_quality_and_original_sha(monkeypatch, tmp_path):
    home = _store(monkeypatch, tmp_path)
    raw = _workbook()
    with fixture_client(main.app) as client:
        result = client.post(
            "/api/projects",
            files={"file": ("ids.xlsx", raw,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert result.status_code == 201, result.text
        pid = result.json()["id"]
        prof = result.json()["profile"]
        for col, expected in (("SKU", "0007"), ("OrderNumber", "000012"),
                              ("CustomerID", "0009"), ("PostalCode", "0018")):
            assert prof["preview"][0][col] == expected
            item = next(c for c in prof["columns"] if c["name"] == col)
            assert item["kind"] == "categorical"
        source_path = Path(storage.get_project(pid)["dataset_path"])
        assert source_path.read_bytes() == raw
        frame, version = quality.current_data(pid)
        assert version == 0
        _assert_values(frame)
        assert frame.iloc[0]["SKU"] == prof["preview"][0]["SKU"]
        with storage.connect() as con:
            original = con.execute("SELECT original_sha256 FROM quality_state WHERE project_id=?",(pid,)).fetchone()
            if original is not None:
                assert original[0] == hashlib.sha256(raw).hexdigest()
        assert list((home / "models").iterdir()) == []
