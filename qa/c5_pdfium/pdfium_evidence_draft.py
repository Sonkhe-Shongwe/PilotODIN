"""Disarmed two-wheel evidence draft. No HTTP transport, installation or wheel execution."""
from __future__ import annotations
import base64
import csv
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "0458d55ca84dac4473f0a40a698992424993f288"
INSPECTOR = "qa/c5_wheel_metadata/wheel_archive_inspector_v2.py"
INSPECTOR_PIN = "9bf91fb983bd354f0b6db20dbb4eec32c447f369"
VERSION_URL = "https://pypi.org/pypi/pypdfium2/5.15.2/json"
VERSION = "5.15.2"
MAX_REQUESTS = 5
MAX_BODY = 8_994_854
MAX_META = 262_144
MAX_ENTRIES = 2048
MAX_MEMBER = 64 * 1024**2
MAX_EXPANDED = 64 * 1024**2
MAX_BATCH_EXPANDED = 128 * 1024**2
MAX_NOTICE = 1 * 1024**2
MAX_BATCH_NOTICES = 8 * 1024**2
MAX_CONTROL = 1 * 1024**2
MAX_PATH_BYTES = 1 * 1024**2
MAX_SECONDS_PER_REQUEST = 30
MAX_JOB_SECONDS = 300
MIN_FREE_SCRATCH = 256 * 1024**2
PINS = {
    "pypdfium2-5.15.2-py3-none-win_amd64.whl":
        (4187589, "74d1bace34fb01c660d0b64344d5a4b7d276942b7c6623c88ab59ea21c5acfbd"),
    "pypdfium2-5.15.2-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl":
        (4020833, "dc31aea5b0fb9fefc9b537a65f4113980b2c40798445736a7e6565bc85161e37"),
}
HEX = re.compile(r"[0-9a-f]{64}")
URL = re.compile(r"https://files\.pythonhosted\.org/packages/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/[A-Za-z0-9_.-]+\.whl")
LIVE_ENABLED = False

class Refused(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise Refused(reason)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT,
                                   stderr=subprocess.DEVNULL, timeout=30)

def strict_json(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_META, "METADATA_SIZE")
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, "DUPLICATE_JSON_KEY")
            result[k] = v
        return result
    return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "JSON_CONSTANT"))

def select(raw):
    doc = strict_json(raw)
    need(type(doc) is dict, "PUBLISHER_OBJECT")
    info = doc.get("info")
    need(type(info) is dict and type(info.get("name")) is str
         and info["name"].lower() == "pypdfium2"
         and info.get("version") == VERSION and type(doc.get("urls")) is list,
         "PUBLISHER_IDENTITY")
    selected = []
    for fn, (size, digest) in PINS.items():
        rows = [x for x in doc["urls"] if type(x) is dict and x.get("filename") == fn]
        need(len(rows) == 1, "WHEEL_SELECTION")
        row = rows[0]
        url = row.get("url")
        need(row.get("packagetype") == "bdist_wheel" and row.get("yanked") is False
             and type(row.get("size")) is int and row["size"] == size
             and type(row.get("digests")) is dict and row["digests"].get("sha256") == digest
             and type(url) is str and URL.fullmatch(url) and url.rsplit("/", 1)[1] == fn,
             "WHEEL_PIN")
        advertisements = []
        for key in ("core-metadata", "dist-info-metadata", "core_metadata", "dist_info_metadata"):
            if key not in row:
                continue
            value = row[key]
            if type(value) is dict and type(value.get("sha256")) is str:
                need(HEX.fullmatch(value["sha256"]), "SIDECAR_DIGEST")
                advertisements.append(value["sha256"])
            else:
                need(value is True or value is False or value is None, "SIDECAR_DECLARATION")
        need(len(set(advertisements)) <= 1, "SIDECAR_AMBIGUITY")
        selected.append({"filename":fn, "bytes":size, "sha256":digest, "url":url,
                         "sidecar_sha256":advertisements[0] if advertisements else None})
    need(len({x["url"] for x in selected}) == 2, "DUPLICATE_URL")
    return selected

def request_plan(rows):
    need(len(rows) == 2 and {x["filename"] for x in rows} == set(PINS), "PLAN")
    plan = [(VERSION_URL, MAX_META, None, None)]
    for row in rows:
        fn = row["filename"]
        size, digest = PINS[fn]
        need(row["bytes"] == size and row["sha256"] == digest
             and URL.fullmatch(row["url"]) and row["url"].endswith("/"+fn), "PLAN_PIN")
        sidecar = row["sidecar_sha256"]
        if sidecar is not None:
            need(HEX.fullmatch(sidecar), "SIDECAR_DIGEST")
            plan.append((row["url"]+".metadata", MAX_META, None, sidecar))
        plan.append((row["url"], size, size, digest))
    need(len(plan) <= MAX_REQUESTS and sum(p[1] for p in plan) <= MAX_BODY
         and len({p[0] for p in plan}) == len(plan), "PLAN_BUDGET")
    return plan

def inspector():
    p = ROOT / INSPECTOR
    need(p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_META, "INSPECTOR_PATH")
    raw = p.read_bytes()
    need(hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest() == INSPECTOR_PIN,
         "INSPECTOR_PIN")
    spec = importlib.util.spec_from_file_location("_c5_pdfium_pinned_inspector", p)
    need(spec is not None and spec.loader is not None, "INSPECTOR_IMPORT")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MAX_MEMBERS = MAX_ENTRIES
    module.MAX_DIRECTORIES = MAX_ENTRIES
    module.MAX_MEMBER = MAX_MEMBER
    module.MAX_WHEEL = MAX_EXPANDED
    module.MAX_TOTAL = MAX_BATCH_EXPANDED
    module.MAX_NOTICE = MAX_NOTICE
    module.MAX_NOTICES = MAX_BATCH_NOTICES
    module.MAX_CONTROL = MAX_CONTROL
    module.MAX_PATH_BYTES = MAX_PATH_BYTES
    return module

def inspect_archive(raw, row, module, budget, sidecar=None):
    """Independent outer archive pin first, then strict member/RECORD inspection.
    No extraction, and no independently advertised sidecar claim if absent.
    """
    fn = row["filename"]
    size, digest = PINS[fn]
    need(type(raw) is bytes and len(raw) == size and sha(raw) == digest,
         "ARCHIVE_PIN")
    need(row["bytes"] == size and row["sha256"] == digest, "ROW_PIN")
    cd, rows, _ = module.central(raw)
    path = "pypdfium2-"+VERSION+".dist-info/METADATA"
    matches = [x for x in rows if x[0] == path]
    need(len(matches) == 1, "METADATA_MEMBER")
    _, needed, flags, method, tm, date, crc, packed, expanded, local = matches[0]
    need(0 < expanded <= MAX_META, "METADATA_MEMBER_SIZE")
    sig,n,f,m,t,d,c,p,e,nl,el = module.header(module.LOCAL,raw,local,cd)
    start = local + module.LOCAL.size
    data_start = start + nl
    need(sig == b"PK\x03\x04" and (n,f,m,t,d,c,p,e)==(needed,flags,method,tm,date,crc,packed,expanded)
         and el == 0 and 0 < nl <= 1024 and data_start + packed <= cd
         and raw[start:data_start] == path.encode("ascii"), "METADATA_LOCAL")
    _, _, metadata = module.member(raw,data_start,packed,method,expanded,crc,True)
    measured = sha(metadata)
    expected_sidecar = row["sidecar_sha256"]
    if expected_sidecar is not None:
        need(type(sidecar) is bytes and len(sidecar) <= MAX_META and sha(sidecar) == expected_sidecar
             and sidecar == metadata, "SIDECAR_MISMATCH")
    else:
        need(sidecar is None, "UNAPPROVED_SIDECAR")
    msg = module.message(metadata)
    need(module.norm(module.single(msg,"Name")) == "pypdfium2"
         and module.single(msg,"Version") == VERSION, "METADATA_IDENTITY")
    need(not msg.get_all("Requires-Dist", []), "DEPENDENCY_REVIEW_REQUIRED")
    declared = [str(v) for v in msg.get_all("License-File",[])]
    expected = {"filename":fn,"bytes":size,"sha256":digest,"name":"pypdfium2",
                "version":VERSION,"metadata_sha256":measured,"license_files":declared,
                "license_expression":module.single(msg,"License-Expression",False),
                "requires_python":module.single(msg,"Requires-Python",False)}
    receipt = budget.inspect(raw, expected)
    receipt.pop("license_expression",None)
    receipt["metadata_identity"] = "SIDECAR_MATCH" if expected_sidecar else "ARCHIVE_HASH_BOUND"
    receipt["requires_dist_count"] = 0
    receipt["requires_python_sha256"] = sha((expected["requires_python"] or "").encode())
    receipt["license_expression_sha256"] = sha((expected["license_expression"] or "").encode())
    receipt["requires_python"] = expected["requires_python"] if expected["requires_python"] in (">=3.6",">=3.7",">=3.8",">=3.9",">=3.10",">=3.11") else "REVIEW_REQUIRED"
    receipt["license_declaration"] = expected["license_expression"] if expected["license_expression"] in ("Apache-2.0 OR BSD-3-Clause","BSD-3-Clause OR Apache-2.0") else "REVIEW_REQUIRED"
    receipt["license_reviewed"] = False
    return receipt

def inventory():
    """Inspect tracked content with Git only; output matching paths/blob IDs, not text."""
    need(git("rev-parse", BASE).decode().strip() == BASE, "BASE")
    files = {}
    for item in git("ls-tree","-r","-z",BASE).split(b"\0"):
        if not item:
            continue
        fields, path = item.split(b"\t",1)
        mode, kind, oid = fields.split()
        if kind == b"blob":
            files[path.decode("utf-8","strict")] = oid.decode("ascii")
    pattern = r"fitz|pymupdf|pypdfium2|p2_pdf_font_coverage_probe|p2_pdf_font_local_review|p2_pdf_visual_devqa|p2_actual_unicode_report_devqa|p2_pdf_unicode_context_devqa|p2_pdf_cmap_scoped_devqa|p2_pdf_tounicode_research|p2_mixed_report_devqa|Run_P2_Legacy_PDF_Visual_Local|requirements-test[.]txt"
    completed = subprocess.run(["git","grep","-I","-i","-l","-z","-E",pattern,BASE,"--",
                                "*.py","*.ps1","*.bat","*.yml","*.yaml","*.toml","*.json","*.txt","*.spec","*.rs","*.mjs"],
                               cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60)
    need(completed.returncode in (0,1), "GREP_FAILED")
    matched = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        prefix,name = raw.decode("utf-8","strict").split(":",1)
        need(prefix == BASE and name in files, "GREP_IDENTITY")
        matched.append({"path":name,"blob":files[name]})
    need(len(matched)==len({x["path"] for x in matched}), "GREP_DUPLICATE")
    print(json.dumps({"source":BASE,"tracked_blobs":len(files),"matches":sorted(matched,key=lambda x:x["path"]),
                      "classification":"UNREVIEWED_MATCHES_NOT_CALLER_CLOSURE"}, sort_keys=True))

class Synthetic(unittest.TestCase):
    def fixture(self):
        return {"info":{"name":"pypdfium2","version":VERSION},"urls":[
            {"filename":fn,"size":sz,"digests":{"sha256":dg},"packagetype":"bdist_wheel",
             "yanked":False,"url":"https://files.pythonhosted.org/packages/aa/bb/"+"c"*60+"/"+fn}
            for fn,(sz,dg) in PINS.items()]}
    def encode(self,obj):
        return json.dumps(obj).encode()
    def test_exact_plan(self):
        rows=select(self.encode(self.fixture()))
        self.assertEqual(len(request_plan(rows)),3)
        self.assertEqual(sum(p[1] for p in request_plan(rows)),8470566)
    def test_optional_sidecar_budget(self):
        d=self.fixture()
        for x in d["urls"]: x["core-metadata"]={"sha256":"a"*64}
        p=request_plan(select(self.encode(d)))
        self.assertEqual(len(p),5)
        self.assertEqual(sum(x[1] for x in p),MAX_BODY)
    def test_selection_refusals(self):
        for key,val in (("yanked",True),("size",1),("url","https://example.com/x.whl"),
                        ("digests",{"sha256":"f"*64}),("packagetype","sdist")):
            d=self.fixture();d["urls"][0][key]=val
            with self.subTest(key=key),self.assertRaises(Refused):
                select(self.encode(d))
        d=self.fixture();d["urls"].append(d["urls"][0])
        with self.assertRaises(Refused): select(self.encode(d))
    def test_duplicate_json(self):
        with self.assertRaises(Refused): strict_json(b'{"a":1,"a":2}')
    def test_archive_wrong_hash_refused_before_inspector(self):
        row=select(self.encode(self.fixture()))[0]
        with self.assertRaises(Refused): inspect_archive(b"not a wheel",row,None,None)
    def test_pinned_inspector_and_narrowed_limits(self):
        m=inspector()
        self.assertEqual(m.MAX_MEMBERS,2048)
        self.assertEqual(m.MAX_TOTAL,128*1024**2)
    def test_disarmed(self):
        self.assertFalse(LIVE_ENABLED)

    def make_wheel(self, *, linux=False, dependency=False, wrong_record=False,
                   missing_notice=False, bad_tag=False, unsafe=False, duplicate=False):
        fn = list(PINS)[int(linux)]
        dist = "pypdfium2-"+VERSION+".dist-info/"
        tag = fn[:-4].split("-",2)[2]
        tags = ["py3-none-"+x for x in tag.split("py3-none-",1)[1].split(".")]
        if bad_tag:
            tags = ["py3-none-any"]
        meta = ("Metadata-Version: 2.4\nName: pypdfium2\nVersion: "+VERSION+
                "\nRequires-Python: >=3.6\nLicense-Expression: Apache-2.0 OR BSD-3-Clause\n"
                "License-File: LICENSE\n"+
                ("Requires-Dist: unexpected\n" if dependency else "")+"\n").encode()
        entries = {
            dist+"METADATA":meta,
            dist+"WHEEL":("Wheel-Version: 1.0\nRoot-Is-Purelib: false\n"+
                          "".join("Tag: "+x+"\n" for x in tags)+"\n").encode(),
            "pypdfium2_raw/pdfium."+("so" if linux else "dll"):b"INERT SYNTHETIC BYTES",
        }
        if not missing_notice:
            entries[dist+"licenses/LICENSE"] = b"Synthetic notice, not publisher terms."
        if unsafe:
            entries["../escape.txt"] = b"inert"
        record = io.StringIO(newline="")
        writer = csv.writer(record,lineterminator="\n")
        for name, data in entries.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
            if wrong_record and name.endswith("/METADATA"):
                digest = "A"*43
            writer.writerow((name,"sha256="+digest,len(data)))
        writer.writerow((dist+"RECORD","",""))
        entries[dist+"RECORD"] = record.getvalue().encode()
        raw = io.BytesIO()
        with zipfile.ZipFile(raw,"w",compression=zipfile.ZIP_DEFLATED) as z:
            for name,data in entries.items():
                info=zipfile.ZipInfo(name)
                info.create_system=3
                info.external_attr=0o100644 << 16
                z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED)
            if duplicate:
                info=zipfile.ZipInfo("PYPDFIUM2_RAW/PDFIUM."+("so" if linux else "dll"))
                info.create_system=3
                info.external_attr=0o100644 << 16
                z.writestr(info,b"case collision")
        raw=raw.getvalue()
        row={"filename":fn,"bytes":len(raw),"sha256":sha(raw),"sidecar_sha256":None}
        return raw,row,meta

    def inspect_fixture(self, raw, row, sidecar=None, module=None, budget=None):
        m=module if module is not None else inspector()
        b=budget if budget is not None else m.InspectionBudget()
        # Only test-local pins are replaced; no live transport or CLI supports this.
        with mock.patch.dict(PINS,{row["filename"]:(row["bytes"],row["sha256"])}):
            return inspect_archive(raw,row,m,b,sidecar)

    def test_archive_positive_both_platforms(self):
        m=inspector()
        budget=m.InspectionBudget()
        for linux in (False,True):
            with self.subTest(linux=linux):
                raw,row,meta=self.make_wheel(linux=linux)
                result=self.inspect_fixture(raw,row,module=m,budget=budget)
                self.assertEqual(result["metadata_identity"],"ARCHIVE_HASH_BOUND")
                self.assertEqual(result["metadata_sha256"],sha(meta))
                self.assertEqual(result["members"],5)
                self.assertEqual(len(result["native_candidates"]),1)
                self.assertEqual(len(result["notices"]),1)
                self.assertEqual(result["requires_python"],">=3.6")
                self.assertFalse(result["license_reviewed"])

    def test_archive_positive_sidecar(self):
        raw,row,meta=self.make_wheel()
        row["sidecar_sha256"]=sha(meta)
        result=self.inspect_fixture(raw,row,meta)
        self.assertEqual(result["metadata_identity"],"SIDECAR_MATCH")

    def test_sidecar_mismatch_and_unadvertised(self):
        raw,row,meta=self.make_wheel()
        with self.assertRaisesRegex(Refused,"UNAPPROVED_SIDECAR"):
            self.inspect_fixture(raw,row,meta)
        row["sidecar_sha256"]=sha(b"different")
        with self.assertRaisesRegex(Refused,"SIDECAR_MISMATCH"):
            self.inspect_fixture(raw,row,b"different")
        with self.assertRaisesRegex(Refused,"SIDECAR_MISMATCH"):
            self.inspect_fixture(raw,row,None)

    def test_dependency_graph_refusal(self):
        raw,row,_=self.make_wheel(dependency=True)
        with self.assertRaisesRegex(Refused,"DEPENDENCY_REVIEW_REQUIRED"):
            self.inspect_fixture(raw,row)

    def test_wrong_record_refused(self):
        raw,row,_=self.make_wheel(wrong_record=True)
        m=inspector()
        with self.assertRaisesRegex(m.Blocked,"RECORD_DIGEST_SIZE"):
            self.inspect_fixture(raw,row,module=m)

    def test_notice_missing_refused(self):
        raw,row,_=self.make_wheel(missing_notice=True)
        m=inspector()
        with self.assertRaisesRegex(m.Blocked,"DECLARED_NOTICE_MISSING_OR_AMBIGUOUS"):
            self.inspect_fixture(raw,row,module=m)

    def test_tag_mismatch_refused(self):
        raw,row,_=self.make_wheel(bad_tag=True)
        m=inspector()
        with self.assertRaisesRegex(m.Blocked,"WHEEL_TAG_MISMATCH"):
            self.inspect_fixture(raw,row,module=m)

    def test_unsafe_paths_and_case_collision_refused(self):
        for arg,reason in (("unsafe","UNSAFE_PATH"),("duplicate","ZIP_DUPLICATE")):
            raw,row,_=self.make_wheel(**{arg:True})
            m=inspector()
            with self.subTest(arg=arg),self.assertRaisesRegex(m.Blocked,reason):
                self.inspect_fixture(raw,row,module=m)

    def test_batch_duplicate_and_expansion_limits(self):
        raw,row,_=self.make_wheel()
        m=inspector()
        b=m.InspectionBudget()
        self.inspect_fixture(raw,row,module=m,budget=b)
        with self.assertRaisesRegex(m.Blocked,"BATCH_DUPLICATE"):
            self.inspect_fixture(raw,row,module=m,budget=b)
        m=inspector()
        m.MAX_WHEEL=1
        with self.assertRaisesRegex(m.Blocked,"ZIP_WHEEL_EXPANSION|ZIP_BOUNDS"):
            self.inspect_fixture(raw,row,module=m)

if __name__ == "__main__":
    if sys.argv[1:] == ["--rehearse"]:
        unittest.main(argv=[sys.argv[0]],verbosity=2)
    elif sys.argv[1:] == ["--inventory"]:
        inventory()
    else:
        print("C5_PDFIUM_LIVE_REFUSED: DISARMED_DRAFT",flush=True)
        raise SystemExit(2)
