"""B5 bounded serializer tests on generated data and owned disposable files."""
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile

import openpyxl
import pandas as pd
import pytest
from backend import data_exports as exports, quality, storage


@pytest.fixture
def project(tmp_path,monkeypatch):
    home=tmp_path/"workspace"
    (home/"datasets").mkdir(parents=True)
    (home/"models").mkdir()
    monkeypatch.setattr(storage,"HOME",home)
    monkeypatch.setattr(storage,"DB_PATH",home/"pilotodin.sqlite3")
    storage.init()
    quality._init_tables()
    raw=b"OrderID,Note,Amount\n0001,=SUM(1),12\n0002,Normal,3\n"
    path=home/"datasets"/"source.csv"
    path.write_bytes(raw)
    pid=storage.save_project("Generated",path.name,".csv",path,{},
                             original_sha256=hashlib.sha256(raw).hexdigest())
    return pid,home,path,raw


def test_seekable_cap_checks_extent_not_cumulative_writes():
    raw=io.BytesIO()
    writer=exports._BoundedOutput(raw,8)
    assert writer.write(b"12345678")==8
    writer.seek(0)
    writer.write(b"abcd")
    assert raw.getvalue()==b"abcd5678" and writer.extent==8
    writer.seek(0,os.SEEK_END)
    with pytest.raises(quality.QualityError) as exc:
        writer.write(b"x")
    assert exc.value.status==413 and len(raw.getvalue())==8
    writer.seek(0)
    with pytest.raises(quality.QualityError):
        writer.write(b"x")


@pytest.mark.parametrize("fmt",["csv","xlsx"])
def test_actual_writer_exact_cap_and_overflow(fmt):
    frame=pd.DataFrame({"Key":["001","002"],"Text":["é","normal"]})
    serialize=exports._write_csv if fmt=="csv" else exports._write_xlsx
    raw=io.BytesIO()
    serialize(frame,exports._BoundedOutput(raw,1024*1024))
    size=len(raw.getvalue())
    # XLSX ZIP timestamps can change metadata but not output extent here.
    exact=io.BytesIO()
    serialize(frame,exports._BoundedOutput(exact,size))
    assert len(exact.getvalue())==size
    if fmt=="csv":
        assert exact.getvalue().startswith(b"\xef\xbb\xbf")
        assert exact.getvalue().decode("utf-8-sig")=="Key,Text\r\n001,é\r\n002,normal\r\n"
    else:
        with ZipFile(exact) as archive:
            assert archive.testzip() is None
        exact.seek(0)
        book=openpyxl.load_workbook(exact,read_only=True)
        try:
            assert list(book.active.values)==[("Key","Text"),("001","é"),("002","normal")]
        finally:
            book.close()
    small=io.BytesIO()
    with pytest.raises(quality.QualityError) as exc:
        serialize(frame,exports._BoundedOutput(small,size-1))
    assert exc.value.status==413 and len(small.getvalue())<=size-1


@pytest.mark.parametrize("fmt",["csv","xlsx"])
def test_prepare_overflow_releases_owned_file_and_preserves_original(project,monkeypatch,fmt):
    pid,home,path,raw=project
    from openpyxl.worksheet import _writer
    before=list(_writer.ALL_TEMP_FILES)
    monkeypatch.setattr(exports,"MAX_EXPORT_BYTES",16)
    with pytest.raises(quality.QualityError) as exc:
        exports.prepare(pid,exports.ExportRequest(version=0,format=fmt))
    assert exc.value.status==413
    assert list((home/"export_tmp").iterdir())==[]
    assert list(_writer.ALL_TEMP_FILES)==before
    assert path.read_bytes()==raw


def test_formula_escape_boundary_is_checked_after_prefix():
    text="="+"x"*32766
    assert len(exports._safe_excel_string(text,xlsx=False))==32768
    with pytest.raises(quality.QualityError,match="32,767"):
        exports._safe_excel_string(text,xlsx=True)
    assert len(exports._safe_excel_string(text[:-1],xlsx=True))==32767
    assert exports._safe_excel_string("  =1")=="'  =1"


def test_xlsx_concurrent_writes_never_create_default_xml_scratch(project,monkeypatch):
    pid,home,path,raw=project
    from openpyxl.worksheet import _writer
    def refuse(*args,**kwargs):
        pytest.fail("Default worksheet scratch creation entered")
    monkeypatch.setattr(_writer,"create_temporary_file",refuse)
    before=list(_writer.ALL_TEMP_FILES)
    def one(_):
        result=exports.prepare(pid,exports.ExportRequest(version=0,format="xlsx"))
        output=result[0]
        book=openpyxl.load_workbook(output,read_only=True)
        try:
            rows=list(book.active.values)
            assert rows[1][0]=="0001" and rows[1][1]=="'=SUM(1)"
        finally:
            book.close()
        return output
    with ThreadPoolExecutor(max_workers=2) as pool:
        files=list(pool.map(one,range(2)))
    assert len(set(files))==2
    assert list(_writer.ALL_TEMP_FILES)==before
    assert set((home/"export_tmp").iterdir())==set(files)
    assert path.read_bytes()==raw


def test_replaced_scratch_path_is_not_deleted(project,monkeypatch):
    pid,home,path,raw=project
    real=exports._write_csv
    def replace(frame,output):
        real(frame,output)
        target=next((home/"export_tmp").iterdir())
        target.rename(target.with_suffix(".retained"))
        target.write_bytes(b"foreign replacement")
    monkeypatch.setattr(exports,"_write_csv",replace)
    with pytest.raises(quality.QualityError,match="identity changed"):
        exports.prepare(pid,exports.ExportRequest(version=0))
    assert sorted(p.read_bytes() for p in (home/"export_tmp").glob("*.csv"))==[b"foreign replacement"]
    assert path.read_bytes()==raw


def test_disk_write_failure_removes_only_own_file(project,monkeypatch):
    pid,home,path,raw=project
    scratch=home/"export_tmp"
    scratch.mkdir()
    other=scratch/"foreign.csv"
    other.write_bytes(b"untouched")
    def fail(frame,output):
        output.write(b"partial")
        raise OSError("synthetic disk full")
    monkeypatch.setattr(exports,"_write_csv",fail)
    with pytest.raises(OSError,match="disk full"):
        exports.prepare(pid,exports.ExportRequest(version=0))
    assert list(scratch.iterdir())==[other]
    assert other.read_bytes()==b"untouched" and path.read_bytes()==raw
