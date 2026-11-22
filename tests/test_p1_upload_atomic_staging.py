"""P1 import byte staging: recoverable I/O failures leave no partial project source.

All tests use a temporary project database; never access a user's workspace.
"""
from __future__ import annotations

import hashlib
from codecs import BOM_UTF8
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import engine, main, quality, storage


def _isolated(monkeypatch, tmp_path):
    home=tmp_path/"isolated-upload"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    return home


def _data():
    return b"CustomerID,Revenue\n0001,100\n0002,200\n0003,300\n"


def _upload():
    return TestClient(main.app).post(
        "/api/projects",
        files={"file":("source.csv",_data(),"text/csv")},
    )


def _empty(home):
    assert storage.list_projects()==[]
    assert list((home/"datasets").iterdir())==[]
    with storage.connect() as con:
        for name in ("projects","quality_state","quality_versions"):
            assert con.execute("SELECT COUNT(*) FROM "+name).fetchone()[0]==0


def test_fsync_failure_cleans_partial_upload_before_metadata(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    def interrupted(_fd):
        raise OSError("Synthetic disk synchronization failure")
    monkeypatch.setattr(main.os,"fsync",interrupted)
    response=_upload()
    assert response.status_code==422,response.text
    assert "Synthetic disk synchronization failure" in response.json()["detail"]
    _empty(home)


def test_replace_failure_cleans_temporary_upload(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    def interrupted(_src,_dst):
        raise OSError("Synthetic atomic rename failure")
    monkeypatch.setattr(main.os,"replace",interrupted)
    response=_upload()
    assert response.status_code==422,response.text
    assert "Synthetic atomic rename failure" in response.json()["detail"]
    _empty(home)


def test_successful_import_pins_complete_original_sha_and_no_staging(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    response=_upload()
    assert response.status_code==201,response.text
    pid=response.json()["id"]
    project=storage.get_project(pid)
    source=Path(project["dataset_path"])
    assert source.parent==home/"datasets"
    assert source.read_bytes()==_data()
    assert sorted(p.name for p in (home/"datasets").iterdir())==[source.name]
    with storage.connect() as con:
        state=con.execute("SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",(pid,)).fetchone()
        assert state is not None
        assert state["original_sha256"]==hashlib.sha256(_data()).hexdigest()
        assert state["current_version"]==0


def test_bad_content_is_discarded_without_publication(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    response=TestClient(main.app).post(
        "/api/projects",files={"file":("invalid.csv",b"only_column\nhello\n","text/csv")}
    )
    assert response.status_code==422,response.text
    _empty(home)


def _late_windows_csv():
    return (b"CustomerID,City,Revenue\r\n" + b"0001,Plain town,100\r\n" * 18_000
            + "0099,Café €,300\r\n".encode("cp1252"))


class CsvEncodingTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(self.enterContext(TemporaryDirectory(prefix="pilotodin-csv-encoding-")))
        self.datasets = self.home / "datasets"
        self.datasets.mkdir()
        (self.home / "models").mkdir()
        self.enterContext(patch.object(storage, "HOME", self.home))
        self.enterContext(patch.object(storage, "DB_PATH", self.home / "pilotodin.sqlite3"))
        storage.init()
        quality._init_tables()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def _upload_bytes(self, raw):
        return self.client.post("/api/projects", files={"file": ("generated.csv", raw, "text/csv")})

    def _check_import_and_quality(self, raw, city, row_count):
        response = self._upload_bytes(raw)
        self.assertEqual(response.status_code, 201, response.text)
        pid = response.json()["id"]
        profile = response.json()["profile"]
        self.assertEqual(profile["rows"], row_count)
        self.assertIn(city, next(col for col in profile["columns"] if col["name"] == "City")["sample_values"])
        working, version = quality.current_data(pid)
        self.assertEqual(version, 0)
        self.assertEqual(len(working), row_count)
        self.assertEqual(working.iloc[-1].to_dict(), {"CustomerID": "0099", "City": city, "Revenue": 300})
        self.assertEqual(Path(storage.get_project(pid)["dataset_path"]).read_bytes(), raw)
        with storage.connect() as con:
            checksum = con.execute("SELECT original_sha256 FROM quality_state WHERE project_id=?", (pid,)).fetchone()[0]
        self.assertEqual(checksum, hashlib.sha256(raw).hexdigest())

    def test_import_retries_when_a_windows_character_appears_past_the_header_buffer(self):
        self._check_import_and_quality(_late_windows_csv(), "Café €", 18_001)

    def test_quality_reopens_an_existing_windows_csv_with_a_valid_original_checksum(self):
        raw = _late_windows_csv()
        source = self.datasets / "existing.csv"
        source.write_bytes(raw)
        pid = storage.save_project("Existing", "existing.csv", ".csv", source, {"rows": 18_001},
                                   original_sha256=hashlib.sha256(raw).hexdigest())
        frame, version = quality.current_data(pid)
        self.assertEqual(version, 0)
        self.assertEqual(frame.iloc[-1]["City"], "Café €")
        self.assertEqual(frame.iloc[-1]["CustomerID"], "0099")

    def test_utf8_and_utf8_bom_keep_unicode_and_identifier_rules(self):
        text = "CustomerID,SKU,City,Revenue\r\n0099,0007,Zoë 東京,300\r\n"
        for encoding in ("utf-8", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                source = self.home / "unicode.csv"
                source.write_bytes(text.encode(encoding))
                imported = engine.read_data(str(source), ".csv")
                self.assertEqual(imported.iloc[0].to_dict(),
                                 {"CustomerID": "0099", "SKU": "0007", "City": "Zoë 東京", "Revenue": 300})
                working = quality._source_df({"dataset_path": str(source), "file_ext": ".csv"})
                self.assertEqual(working.iloc[0].to_dict(), imported.iloc[0].to_dict())

    def test_invalid_utf8_marked_with_a_bom_is_not_reinterpreted_as_windows_csv(self):
        response = self._upload_bytes(BOM_UTF8 + _late_windows_csv())
        self.assertEqual(response.status_code, 422, response.text)
        _empty(self.home)
