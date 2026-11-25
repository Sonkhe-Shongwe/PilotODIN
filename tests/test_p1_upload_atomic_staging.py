"""P1 import byte staging: recoverable I/O failures leave no partial project source.

All tests use a temporary project database; never access a user's workspace.
"""
from __future__ import annotations

import hashlib
import errno
import os
import pytest
from codecs import BOM_UTF8
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.fixture_http import fixture_client

from backend import artifact_publication, dataset_publication, engine, main, quality, storage


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
    return fixture_client(main.app).post(
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


def test_final_creation_failure_cleans_temporary_upload(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    write=dataset_publication._write_exclusive
    def interrupted(path,*args):
        if not path.name.endswith(".uploading"):
            raise OSError("Synthetic final creation failure")
        return write(path,*args)
    monkeypatch.setattr(dataset_publication,"_write_exclusive",interrupted)
    response=_upload()
    assert response.status_code==422,response.text
    assert "Synthetic final creation failure" in response.json()["detail"]
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
    response=fixture_client(main.app).post(
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
        self.client = fixture_client(main.app)
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


def test_final_collision_does_not_overwrite_or_remove_foreign_bytes(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    original=dataset_publication._write_exclusive
    collision=b"existing immutable bytes"
    def create_collision(path,raw,owned,verify):
        if not path.name.endswith(".uploading"):
            path.write_bytes(collision)
        return original(path,raw,owned,verify)
    monkeypatch.setattr(dataset_publication,"_write_exclusive",create_collision)
    response=_upload()
    assert response.status_code==422,response.text
    assert storage.list_projects()==[]
    retained,=list((home/"datasets").iterdir())
    assert retained.read_bytes()==collision
    with storage.connect() as con:
        assert con.execute("SELECT state FROM artifact_publications_v1").fetchone()[0]=="interrupted"


def test_parser_uses_verified_immutable_bytes_and_final_digest(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    original=engine.read_data
    def parse(raw,ext):
        assert isinstance(raw,bytes)
        assert raw==_data()
        return original(raw,ext)
    monkeypatch.setattr(engine,"read_data",parse)
    response=_upload()
    assert response.status_code==201,response.text
    pid=response.json()["id"]
    with storage.connect() as con:
        row=con.execute("SELECT state,sha256,expected_bytes FROM artifact_publications_v1 WHERE subject_id=?",(pid,)).fetchone()
        assert tuple(row)==("committed",hashlib.sha256(_data()).hexdigest(),len(_data()))
    source,=list((home/"datasets").iterdir())
    assert source.read_bytes()==_data()


def test_recovery_preserves_unreferenced_and_unknown_bytes_twice(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    raw=_data()
    receipt=storage.begin_dataset_publication(".csv",len(raw),hashlib.sha256(raw).hexdigest())
    partial=home/"datasets"/receipt.staging_name
    partial.write_bytes(raw[:8])
    unknown=home/"datasets"/"legacy.csv"
    unknown.write_bytes(b"unknown original")
    assert dataset_publication.recover_pending()==1
    assert dataset_publication.recover_pending()==0
    assert partial.read_bytes()==raw[:8]
    assert unknown.read_bytes()==b"unknown original"
    assert storage.list_projects()==[]
    with storage.connect() as con:
        assert con.execute("SELECT state FROM artifact_publications_v1").fetchone()[0]=="interrupted"


def test_collision_after_absence_check_is_never_overwritten(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    original=Path.open
    foreign=b"foreign immutable original"
    def race(path,mode="r",*args,**kwargs):
        if mode=="xb" and path.parent==home/"datasets" and path.suffix==".csv":
            with original(path,"xb") as f:
                f.write(foreign)
        return original(path,mode,*args,**kwargs)
    monkeypatch.setattr(Path,"open",race)
    response=_upload()
    assert response.status_code==422,response.text
    retained,=list((home/"datasets").iterdir())
    assert retained.read_bytes()==foreign
    assert storage.list_projects()==[]
    with storage.connect() as con:
        assert tuple(con.execute("SELECT state,reason_code FROM artifact_publications_v1").fetchone())==("interrupted","collision")


def test_missing_referenced_original_is_not_filled_by_new_upload(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    operation="b"*32
    final=home/"datasets"/(operation+".csv")
    legacy=storage.save_project("Missing","missing.csv",".csv",final,{},original_sha256="0"*64)
    with storage.connect() as con:
        con.execute("INSERT INTO project_lifecycle VALUES (?,?,?)",(legacy,1,storage.now()))
    ids=iter((operation,"c"*32))
    monkeypatch.setattr(storage,"uid",lambda: next(ids))
    response=_upload()
    assert response.status_code==422,response.text
    assert not final.exists()
    assert not list((home/"datasets").iterdir())
    with storage.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM projects").fetchone()[0]==1
        assert tuple(con.execute("SELECT state,reason_code FROM artifact_publications_v1").fetchone())==("blocked","reference_conflict")


@pytest.mark.parametrize("failure",[errno.ENOSPC,errno.EACCES])
def test_failed_final_creation_does_not_register_project(monkeypatch,tmp_path,failure):
    home=_isolated(monkeypatch,tmp_path)
    original=Path.open
    def fail(path,mode="r",*args,**kwargs):
        if mode=="xb" and path.parent==home/"datasets" and path.suffix==".csv":
            raise OSError(failure,"Synthetic final write failure")
        return original(path,mode,*args,**kwargs)
    monkeypatch.setattr(Path,"open",fail)
    response=_upload()
    assert response.status_code==422,response.text
    _empty(home)
    with storage.connect() as con:
        assert tuple(con.execute("SELECT state,reason_code FROM artifact_publications_v1").fetchone())==("interrupted","storage_unavailable")


def test_recovery_blocks_hardlinked_payload_and_preserves_both_names(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    raw=_data()
    receipt=storage.begin_dataset_publication(".csv",len(raw),hashlib.sha256(raw).hexdigest())
    original=home/"datasets"/"legacy.csv"
    original.write_bytes(raw)
    staged=home/"datasets"/receipt.staging_name
    os.link(original,staged)
    assert dataset_publication.recover_pending()==1
    assert dataset_publication.recover_pending()==0
    assert original.read_bytes()==staged.read_bytes()==raw
    with storage.connect() as con:
        assert tuple(con.execute("SELECT state,reason_code FROM artifact_publications_v1").fetchone())==("blocked","unsafe_identity")


def test_receipt_disagreement_blocks_quality_without_rewriting_history(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    response=_upload()
    assert response.status_code==201,response.text
    pid=response.json()["id"]
    path=Path(storage.get_project(pid)["dataset_path"])
    with storage.connect() as con:
        con.execute("UPDATE artifact_publications_v1 SET sha256=? WHERE subject_id=?",("0"*64,pid))
    response=fixture_client(main.app).get(f"/api/projects/{pid}/live-profile")
    assert response.status_code==409,response.text
    assert path.read_bytes()==_data()
    with storage.connect() as con:
        assert tuple(con.execute("SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",(pid,)).fetchone())==(hashlib.sha256(_data()).hexdigest(),0)
        assert con.execute("SELECT COUNT(*) FROM quality_versions WHERE project_id=?",(pid,)).fetchone()[0]==1


def test_recovery_refuses_malformed_receipt_without_touching_bytes(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    raw=_data()
    receipt=storage.begin_dataset_publication(".csv",len(raw),hashlib.sha256(raw).hexdigest())
    staging=home/"datasets"/receipt.staging_name
    staging.write_bytes(raw[:8])
    with storage.connect() as con:
        con.execute("UPDATE artifact_publications_v1 SET created_at=? WHERE operation_id=?",
                    ("invalid timestamp",receipt.operation_id))
    with pytest.raises(artifact_publication.PublicationError):
        dataset_publication.recover_pending()
    assert staging.read_bytes()==raw[:8]
    assert storage.list_projects()==[]
    with storage.connect() as con:
        assert con.execute("SELECT state FROM artifact_publications_v1").fetchone()[0]=="intent"


def test_recovery_blocks_redirected_payload_without_touching_target(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    raw=_data()
    receipt=storage.begin_dataset_publication(".csv",len(raw),hashlib.sha256(raw).hexdigest())
    foreign=tmp_path/"foreign.csv"
    foreign.write_bytes(raw)
    staged=home/"datasets"/receipt.staging_name
    try:
        staged.symlink_to(foreign)
    except OSError as exc:
        pytest.skip("Symbolic links unavailable in disposable fixture: "+str(exc))
    assert dataset_publication.recover_pending()==1
    assert dataset_publication.recover_pending()==0
    assert staged.is_symlink()
    assert foreign.read_bytes()==raw
    with storage.connect() as con:
        assert tuple(con.execute("SELECT state,reason_code FROM artifact_publications_v1").fetchone())==("blocked","unsafe_identity")


def test_committed_receipt_survives_exact_digest_relink(monkeypatch,tmp_path):
    home=_isolated(monkeypatch,tmp_path)
    response=_upload()
    assert response.status_code==201,response.text
    pid=response.json()["id"]
    original=Path(storage.get_project(pid)["dataset_path"])
    relocated=home/"datasets"/"relocated-original.csv"
    original.rename(relocated)
    # Simulate the metadata-only result of an approved exact-digest relink.
    # The real maintenance command has its own P1 backup/lease regressions.
    with storage.connect() as con:
        before=tuple(con.execute("SELECT * FROM artifact_publications_v1 WHERE subject_id=?",(pid,)).fetchone())
        con.execute("UPDATE projects SET dataset_path=? WHERE id=?",(str(relocated),pid))
    assert dataset_publication.recover_pending()==0
    response=fixture_client(main.app).get(f"/api/projects/{pid}/live-profile")
    assert response.status_code==200,response.text
    assert response.json()["version"]==0
    assert relocated.read_bytes()==_data()
    assert not original.exists()
    with storage.connect() as con:
        assert tuple(con.execute("SELECT * FROM artifact_publications_v1 WHERE subject_id=?",(pid,)).fetchone())==before
        assert tuple(con.execute("SELECT original_sha256,current_version FROM quality_state WHERE project_id=?",(pid,)).fetchone())==(hashlib.sha256(_data()).hexdigest(),0)
