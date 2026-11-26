"""Marker-absent staged two-wheel evidence adapter; exact one-use gate required."""
from __future__ import annotations
import base64
from contextlib import contextmanager
import csv
import hashlib
import http.client
import io
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import ssl
import subprocess
import sys
import time
from urllib.parse import urlsplit
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
LIVE_ENABLED = True

# Exact upstream source tree notice identities, not a bundled licence clearance.
NOTICE_SOURCE = "a618c900bc03ab071e5ee8aea3c196a935cfa8a7"
NOTICE_PINS = {
    "BUILD_LICENSES/abseil.txt": "fb1517cba75ad9cde517848cb967eb04198c90ca",
    "BUILD_LICENSES/agg23.txt": "3040a2b5347e2a37545ed281bed18d5a289dec42",
    "BUILD_LICENSES/all_except_musl/llvm-libc.txt": "416a2ffdd948024a9a3422cd8a680753581af972",
    "BUILD_LICENSES/dragonbox-Apache2-LLVM.txt": "7f5c70ff8abe141beae536154d67e8b70b140d7a",
    "BUILD_LICENSES/dragonbox-Boost.txt": "36b7cd93cdfbac762f5be4c6ce276df2ea6305c2",
    "BUILD_LICENSES/fast_float.txt": "2fb2a37ad7fda521092c8b7b16911176c3f8a81b",
    "BUILD_LICENSES/freetype.txt": "bbaba33f47d92ee4ed527582d96aeebf54cdcbb0",
    "BUILD_LICENSES/harfbuzz.txt": "1dd917e9f2e72167de69e3b5dadbc4e7db417da1",
    "BUILD_LICENSES/highway.txt": "c49c9784a90ad0e1107ddf29c5537d85dbb2c704",
    "BUILD_LICENSES/icu.txt": "9f54372febca06e134bbc9d4700a1ebfeda13843",
    "BUILD_LICENSES/lcms.txt": "25276b28f686cc0b3332a4ae04cdb9409baa25b1",
    "BUILD_LICENSES/libjpeg_turbo.ijg": "dbf8070cac812bcfd7eb4d407062919f69c777c8",
    "BUILD_LICENSES/libjpeg_turbo.md": "a785258bcdaeb20de639c6a060a7e3d5df17ae8f",
    "BUILD_LICENSES/libopenjpeg.txt": "89df544ff5597e1a5e560f33ca0653d54884b2dc",
    "BUILD_LICENSES/libpng.txt": "e0c5b531cf548d608e911c43c577cd4ba9a1526e",
    "BUILD_LICENSES/libtiff.txt": "dc255dec69163021fec18c9d44a9946aa257d8b4",
    "BUILD_LICENSES/pbin_and_sbuild/brotli.txt": "33b7cdd2dbaeddce1e35aa1a13f63d71154dc42f",
    "BUILD_LICENSES/pbin_and_sbuild/libyuv.txt": "c911747a6b53f063503992c3903d932f54cf6c57",
    "BUILD_LICENSES/pdfium-binaries.txt": "f0c5a25c8c215e647b776e8fb4498a36da326493",
    "BUILD_LICENSES/pdfium.txt": "8b86eb001336e2a3731218c7c1314ab091b5c910",
    "BUILD_LICENSES/SHARED/Apache-2.0.txt": "62589edd12a37dd28b6b6fed1e2d728ac9f05c8d",
    "BUILD_LICENSES/simdutf.txt": "74c8302ba92830e170dfae35957468edd2e25271",
    "BUILD_LICENSES/zlib.txt": "67bbd81f0b20647f257e074bf7054637cbdfccd1",
    "LICENSES/Apache-2.0.txt": "d645695673349e3947e8e5ae42332d0ac3164cd7",
    "LICENSES/BSD-3-Clause.txt": "7baa27a311ec3d9924a4e2e50451b64d97947656",
    "LICENSES/CC-BY-4.0.txt": "49ce653bfc366fab544037dd1db759c9bb4c502b",
}
MAX_RECEIPT = 262144
_GATE_PASSED = False


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


def notice_matches(contents):
    results=[]
    prefix="pypdfium2-"+VERSION+".dist-info/licenses/"
    for path,raw in sorted(contents.items()):
        rel=path[len(prefix):] if path.startswith(prefix) else None
        expected=NOTICE_PINS.get(rel)
        measured=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
        results.append({"path":path,"upstream_path":rel if expected else None,
                        "upstream_git_blob":expected,"observed_git_blob":measured,
                        "status":"EXACT_TAGGED_SOURCE_MATCH" if expected==measured else
                        "TAGGED_SOURCE_MISMATCH" if expected else "UNMAPPED_REVIEW_REQUIRED"})
    return results


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
    receipt, notice_contents = budget.inspect(raw, expected, capture_notices=True)
    receipt["notice_source_commit"] = NOTICE_SOURCE
    receipt["notice_comparison"] = notice_matches(notice_contents)
    del notice_contents
    receipt.pop("license_expression",None)
    receipt["metadata_identity"] = "SIDECAR_MATCH" if expected_sidecar else "ARCHIVE_HASH_BOUND"
    receipt["requires_dist_count"] = 0
    receipt["requires_python_sha256"] = sha((expected["requires_python"] or "").encode())
    receipt["license_expression_sha256"] = sha((expected["license_expression"] or "").encode())
    receipt["requires_python"] = expected["requires_python"] if expected["requires_python"] in (">=3.6",">=3.7",">=3.8",">=3.9",">=3.10",">=3.11") else "REVIEW_REQUIRED"
    receipt["license_declaration"] = expected["license_expression"] if expected["license_expression"] in ("Apache-2.0 OR BSD-3-Clause","BSD-3-Clause OR Apache-2.0") else "REVIEW_REQUIRED"
    receipt["license_reviewed"] = False
    need(len(json.dumps(receipt,sort_keys=True,ensure_ascii=True).encode()) <= MAX_RECEIPT,"RECEIPT_CAP")
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


# Adapted fixed-origin/deadline pattern from remaining_dev_input_once.py
# blob 23433611fa42031c66b17379fe7e5baef8db7ff5; no redirect path.
DRIVER = "qa/c5_pdfium/pdfium_evidence_draft.py"
WORKFLOW = ".github/workflows/c5-pdfium-evidence-draft.yml"
MARKER = "qa/c5_pdfium/APPROVAL_PDFIUM_TWO_WHEEL_ONCE_20261126.json"
OP = "C5-PDFIUM-TWO-WHEEL-EVIDENCE-ONCE-20261126"
MESSAGE = OP + " owner approved exact acquisition only"
CAPABILITY = object()

def gate_snapshot(enabled, env, head, parents, subject, changed, dirty, marker, pins):
    need(enabled and env.get("GITHUB_ACTIONS") == "true"
         and env.get("GITHUB_EVENT_NAME") == "push"
         and env.get("GITHUB_REF") == "refs/heads/feature/live-dev-workspace-20261023"
         and env.get("GITHUB_WORKFLOW") == "C5 PDFium evidence draft"
         and env.get("GITHUB_RUN_ATTEMPT") == "1"
         and re.fullmatch(r"[0-9]{1,20}",env.get("GITHUB_RUN_ID","")), "FRESH_APPROVAL_REQUIRED")
    need(re.fullmatch(r"[0-9a-f]{40}",head) and head == env.get("GITHUB_SHA")
         and len(parents)==1 and re.fullmatch(r"[0-9a-f]{40}",parents[0])
         and subject == MESSAGE, "ACTIVATION_IDENTITY")
    need(changed == ["A\t"+MARKER] and not dirty, "ACTIVATION_SCOPE")
    need(set(pins)=={"driver","workflow","inspector"}
         and all(re.fullmatch(r"[0-9a-f]{40}",v) for v in pins.values())
         and pins["inspector"]==INSPECTOR_PIN, "ACTIVATION_PINS")
    need(marker == {"operation":OP,"parent":parents[0],**pins}, "APPROVAL_PIN")

def live_gate():
    global _GATE_PASSED
    need(LIVE_ENABLED and not _GATE_PASSED, "DISARMED_OR_CONSUMED")
    head = git("rev-parse","HEAD").decode().strip()
    parents = git("show","-s","--format=%P","HEAD").decode().split()
    need(len(parents)==1,"ACTIVATION_PARENT")
    marker_path=ROOT/MARKER
    need(marker_path.is_file() and not marker_path.is_symlink()
         and marker_path.stat().st_size<=4096,"MARKER")
    pins={k:git("rev-parse","HEAD:"+p).decode().strip()
          for k,p in (("driver",DRIVER),("workflow",WORKFLOW),("inspector",INSPECTOR))}
    gate_snapshot(LIVE_ENABLED,os.environ,head,parents,
                  git("log","-1","--format=%s").decode().strip(),
                  git("diff","--name-status",parents[0],head).decode().splitlines(),
                  git("status","--porcelain","--untracked-files=all"),
                  strict_json(marker_path.read_bytes()),pins)
    _GATE_PASSED = True
    return CAPABILITY

@contextmanager
def deadline(seconds):
    need(seconds>0 and hasattr(signal,"setitimer")
         and signal.getitimer(signal.ITIMER_REAL)==(0.,0.),"TIMER")
    def expired(*_):
        raise Refused("DEADLINE")
    prior=signal.signal(signal.SIGALRM,expired)
    try:
        signal.setitimer(signal.ITIMER_REAL,seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,prior)

def header(response,key):
    values=[v for k,v in response.getheaders() if k.lower()==key.lower()]
    need(len(values)<=1,"DUPLICATE_HEADER")
    if not values:
        return None
    need(len(values[0])<=256 and all(32<=ord(c)<=126 for c in values[0]),"HEADER_SYNTAX")
    return values[0]

class MemorySocket:
    def __init__(self,raw): self.raw=raw
    def makefile(self,*_): return io.BytesIO(self.raw)

class Replay:
    responses={}
    calls=[]
    def __init__(self,host,port,**_):
        need(host in ("pypi.org","files.pythonhosted.org") and port==443,"FIXTURE_HOST")
        self.host=host
    def request(self,method,path,headers):
        url="https://"+self.host+path
        need(method=="GET" and headers["Accept-Encoding"]=="identity"
             and url in self.responses,"FIXTURE_REQUEST")
        self.calls.append(url)
        self.raw=self.responses[url]
    def getresponse(self):
        resp=http.client.HTTPResponse(MemorySocket(self.raw))
        resp.begin()
        return resp
    def close(self): pass

class Transport:
    """Sequential, fixed plan, in-memory body caps; never retries after refusal."""
    def __init__(self,connection,record,capability=None):
        need(connection is Replay or (LIVE_ENABLED and _GATE_PASSED and capability is CAPABILITY
             and connection is http.client.HTTPSConnection),"OFFLINE_FIXTURE_ONLY")
        self.connection,self.record=connection,record
        self.requests=self.body=0
        self.failed=False
        self.end=time.monotonic()+MAX_JOB_SECONDS
        self.plan=[(VERSION_URL,MAX_META,None,None)]
        self.meta_digest=None
        self.bound=False

    def remaining(self):
        remaining=self.end-time.monotonic()
        need(remaining>0,"JOB_DEADLINE")
        return remaining

    def bind(self,metadata):
        need(not self.failed and not self.bound and self.requests==1
             and self.meta_digest==sha(metadata),"PLAN_BINDING")
        try:
            rows=select(metadata)
            self.plan=request_plan(rows)
            self.bound=True
            return rows
        except Exception:
            self.failed=True
            raise

    def get(self):
        need(not self.failed and self.requests<len(self.plan)
             and self.requests<MAX_REQUESTS,"REQUEST_SCOPE")
        url,cap,exact,digest=self.plan[self.requests]
        u=urlsplit(url)
        need(url==VERSION_URL or (u.netloc=="files.pythonhosted.org"
             and URL.fullmatch(url.removesuffix(".metadata"))),"REQUEST_ORIGIN")
        need(u.scheme=="https" and not u.query and not u.fragment
             and cap<=MAX_BODY-self.body,"BODY_BUDGET")
        self.requests+=1
        self.failed=True
        raw=bytearray()
        status=None
        complete=False
        conn=None
        try:
            duration=min(MAX_SECONDS_PER_REQUEST,self.remaining())
            with deadline(duration):
                conn=self.connection(u.netloc,443,timeout=duration,
                                     context=ssl.create_default_context())
                conn.request("GET",u.path,headers={"Accept-Encoding":"identity",
                             "Connection":"close","User-Agent":"PilotODIN-C5-PDFium/1"})
                response=conn.getresponse()
                status=response.status
                need(status==200,"HTTP_STATUS")
                enc=header(response,"Content-Encoding")
                need(enc is None or enc.lower()=="identity","CONTENT_ENCODING")
                length,te=header(response,"Content-Length"),header(response,"Transfer-Encoding")
                need(te is None or (te.lower()=="chunked" and length is None),"FRAMING")
                need(length is not None or (exact is None and te=="chunked"),"BODY_FRAMING")
                declared=None
                if length is not None:
                    need(re.fullmatch(r"[0-9]{1,10}",length),"BODY_LENGTH")
                    declared=int(length)
                    need(0<declared<=cap and (exact is None or declared==exact),"BODY_LENGTH")
                while declared is None or len(raw)<declared:
                    room=cap-len(raw)
                    if room==0:
                        need(response.isclosed(),"BODY_BUDGET")
                        break
                    amount=min(65536,room,declared-len(raw) if declared is not None else room)
                    interrupted=False
                    try:
                        chunk=response.read1(amount)
                    except http.client.IncompleteRead as exc:
                        chunk=exc.partial
                        interrupted=True
                    need(type(chunk) is bytes and len(chunk)<=amount,"BODY_BUDGET")
                    raw.extend(chunk)
                    self.body+=len(chunk)
                    need(not interrupted,"INCOMPLETE_BODY")
                    if not chunk:
                        break
                need(len(raw)>0 and (declared is None or len(raw)==declared)
                     and (exact is None or len(raw)==exact) and response.isclosed(),"INCOMPLETE_BODY")
                measured=sha(raw)
                need(digest is None or measured==digest,"HASH_MISMATCH")
                if self.requests==1:
                    self.meta_digest=measured
                complete=True
                self.failed=False
                return bytes(raw)
        finally:
            if conn is not None:
                conn.close()
            self.record("REQUEST",{"ordinal":self.requests,"host":u.netloc,
                        "status":status,"bytes":len(raw),"sha256":sha(raw),"complete":complete})

def collect(connection,record,capability=None):
    transport=Transport(connection,record,capability)
    verified=0
    settled=False
    try:
        with deadline(transport.remaining()):
            module=inspector()
            budget=module.InspectionBudget()
        metadata=transport.get()
        rows=transport.bind(metadata)
        for row in rows:
            sidecar=transport.get() if row["sidecar_sha256"] else None
            raw=transport.get()
            with deadline(transport.remaining()):
                receipt=inspect_archive(raw,row,module,budget,sidecar)
            record("WHEEL",{"url":row["url"],**receipt})
            verified+=1
            del raw,sidecar
        need(transport.bound and transport.requests==len(transport.plan)
             and verified==2 and transport.body<=MAX_BODY,"TERMINAL_SCOPE")
        transport.remaining()
        settled=True
        return 0
    finally:
        record("RESULT",{"requests":transport.requests,"response_bytes":transport.body,
                        "verified":verified,"status":"INTEGRITY_PASS" if settled else "REFUSED",
                        "installed":False,"extracted":False,"license_reviewed":False})

def live():
    capability=live_gate()
    def record(kind,value):
        encoded=json.dumps(value,sort_keys=True,ensure_ascii=True)
        need(len(encoded.encode())<=MAX_RECEIPT,"RECEIPT_CAP")
        print("C5_PDFIUM_"+kind,encoded,flush=True)
    return collect(http.client.HTTPSConnection,record,capability)

def wire(body=b"",status="200 OK",headers=(),length=True):
    fields=list(headers)
    if length: fields.append(("Content-Length",str(len(body))))
    return ("HTTP/1.1 "+status+"\r\n"+"".join(k+": "+v+"\r\n" for k,v in fields)
            +"\r\n").encode()+body


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
        self.assertTrue(LIVE_ENABLED)
        self.assertFalse(_GATE_PASSED)
        self.assertFalse((ROOT/MARKER).exists())

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

    def test_gate_refuses_disarmed_and_wrong_context(self):
        env={"GITHUB_ACTIONS":"true","GITHUB_EVENT_NAME":"push",
             "GITHUB_REF":"refs/heads/feature/live-dev-workspace-20261023",
             "GITHUB_WORKFLOW":"C5 PDFium evidence draft","GITHUB_RUN_ATTEMPT":"1",
             "GITHUB_RUN_ID":"123","GITHUB_SHA":"a"*40}
        pins={"driver":"b"*40,"workflow":"c"*40,"inspector":INSPECTOR_PIN}
        marker={"operation":OP,"parent":"d"*40,**pins}
        args=[True,env,"a"*40,["d"*40],MESSAGE,["A\t"+MARKER],b"",marker,pins]
        gate_snapshot(*args)
        for index,value in ((0,False),(1,{**env,"GITHUB_RUN_ATTEMPT":"2"}),
              (1,{**env,"GITHUB_REF":"refs/heads/main"}),(2,"e"*40),
              (3,["d"*40,"e"*40]),(4,"wrong"),(5,["M\t"+DRIVER]),
              (6,b"dirty"),(7,{**marker,"parent":"e"*40}),(8,{**pins,"inspector":"e"*40})):
            mutated=args.copy();mutated[index]=value
            with self.subTest(index=index),self.assertRaises(Refused):
                gate_snapshot(*mutated)
        with self.assertRaisesRegex(Refused,"MARKER"): live_gate()

    def test_transport_refuses_real_connection(self):
        with self.assertRaisesRegex(Refused,"OFFLINE_FIXTURE_ONLY"):
            Transport(http.client.HTTPSConnection,lambda *_:None,CAPABILITY)

    def transport(self,response):
        Replay.responses={VERSION_URL:response}
        Replay.calls=[]
        logs=[]
        return Transport(Replay,lambda k,v:logs.append((k,v))),logs

    def test_transport_metadata_and_plan_binding(self):
        metadata=self.encode(self.fixture())
        t,logs=self.transport(wire(metadata))
        self.assertEqual(t.get(),metadata)
        rows=t.bind(metadata)
        self.assertEqual(len(rows),2)
        self.assertEqual(t.requests,1)
        self.assertEqual(t.body,len(metadata))
        self.assertTrue(logs[0][1]["complete"])
        with self.assertRaisesRegex(Refused,"PLAN_BINDING"): t.bind(metadata)

    def test_transport_redirect_status_and_headers_refused(self):
        for response,reason in (
            (wire(status="302 Found",headers=(("Location","https://example.com/x"),)),"HTTP_STATUS"),
            (wire(status="503 Unavailable"),"HTTP_STATUS"),
            (wire(b"x",headers=(("Content-Encoding","gzip"),)),"CONTENT_ENCODING"),
            (wire(b"x",headers=(("Content-Length","1"),)),"DUPLICATE_HEADER"),
            (wire(b"x",headers=(("Transfer-Encoding","chunked"),)),"FRAMING"),
            (wire(b"x",length=False),"BODY_FRAMING"),
            (wire(b"x",length=False,headers=(("Content-Length",str(MAX_META+1)),)),"BODY_LENGTH"),
            (wire(b"x",length=False,headers=(("Content-Length","2"),)),"INCOMPLETE_BODY")):
            t,logs=self.transport(response)
            with self.subTest(reason=reason),self.assertRaisesRegex(Refused,reason): t.get()
            self.assertEqual(t.requests,1)
            self.assertEqual(len(Replay.calls),1)
            self.assertFalse(logs[0][1]["complete"])
            with self.assertRaisesRegex(Refused,"REQUEST_SCOPE"): t.get()
            self.assertEqual(len(Replay.calls),1)

    def test_transport_chunked_metadata(self):
        t,_=self.transport(wire(b"3\r\nabc\r\n0\r\n\r\n",length=False,
                               headers=(("Transfer-Encoding","chunked"),)))
        self.assertEqual(t.get(),b"abc")

    def test_transport_budget_and_deadline(self):
        t,_=self.transport(wire(b"x"))
        t.body=MAX_BODY
        with self.assertRaisesRegex(Refused,"BODY_BUDGET"): t.get()
        self.assertEqual(Replay.calls,[])
        t,_=self.transport(wire(b"x"))
        t.end=time.monotonic()-1
        with self.assertRaisesRegex(Refused,"JOB_DEADLINE"): t.get()
        self.assertEqual(Replay.calls,[])
        with self.assertRaisesRegex(Refused,"DEADLINE"):
            with deadline(0.01): time.sleep(0.05)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.,0.))

    def test_collect_synthetic_complete_and_hash_refusal(self):
        raw1,row1,meta1=self.make_wheel()
        raw2,row2,_=self.make_wheel(linux=True)
        pins={row1["filename"]:(len(raw1),sha(raw1)),row2["filename"]:(len(raw2),sha(raw2))}
        with mock.patch.dict(PINS,pins,clear=True):
            doc=self.fixture()
            doc["urls"][0]["core-metadata"]={"sha256":sha(meta1)}
            metadata=self.encode(doc)
            u1,u2=[x["url"] for x in doc["urls"]]
            Replay.responses={VERSION_URL:wire(metadata),u1+".metadata":wire(meta1),
                              u1:wire(raw1),u2:wire(raw2)}
            Replay.calls=[]
            logs=[]
            self.assertEqual(collect(Replay,lambda k,v:logs.append((k,v))),0)
            self.assertEqual(Replay.calls,[VERSION_URL,u1+".metadata",u1,u2])
            self.assertEqual(logs[-1][1]["verified"],2)
            self.assertEqual(logs[-1][1]["status"],"INTEGRITY_PASS")
            self.assertEqual(logs[-1][1]["response_bytes"],len(metadata)+len(meta1)+len(raw1)+len(raw2))
            Replay.responses[u1]=wire(b"x"*len(raw1))
            Replay.calls=[];logs=[]
            with self.assertRaisesRegex(Refused,"HASH_MISMATCH"):
                collect(Replay,lambda k,v:logs.append((k,v)))
            self.assertEqual(Replay.calls,[VERSION_URL,u1+".metadata",u1])
            self.assertEqual(logs[-1][1]["status"],"REFUSED")

    def test_inspector_preflight_before_any_request(self):
        Replay.calls=[]
        logs=[]
        with mock.patch(__name__+".inspector",side_effect=Refused("INSPECTOR_PIN")):
            with self.assertRaisesRegex(Refused,"INSPECTOR_PIN"):
                collect(Replay,lambda k,v:logs.append((k,v)))
        self.assertEqual(Replay.calls,[])
        self.assertEqual(logs[-1][1]["status"],"REFUSED")
        self.assertEqual(logs[-1][1]["requests"],0)

    def test_notice_comparison_exact_mismatch_unmapped(self):
        raw=b"fixture notice"
        pin=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
        prefix="pypdfium2-"+VERSION+".dist-info/licenses/"
        with mock.patch.dict(NOTICE_PINS,{"LICENSES/test.txt":pin}):
            result=notice_matches({prefix+"LICENSES/test.txt":raw})
            self.assertEqual(result[0]["status"],"EXACT_TAGGED_SOURCE_MATCH")
            result=notice_matches({prefix+"LICENSES/test.txt":b"other"})
            self.assertEqual(result[0]["status"],"TAGGED_SOURCE_MISMATCH")
            result=notice_matches({prefix+"unknown.txt":raw})
            self.assertEqual(result[0]["status"],"UNMAPPED_REVIEW_REQUIRED")

if __name__ == "__main__":
    if sys.argv[1:] == ["--rehearse"]:
        unittest.main(argv=[sys.argv[0]],verbosity=2)
    elif sys.argv[1:] == ["--inventory"]:
        inventory()
    elif sys.argv[1:] == ["--live"]:
        try:
            raise SystemExit(live())
        except Refused as exc:
            print("C5_PDFIUM_LIVE_REFUSED:",str(exc),flush=True)
            raise SystemExit(2)
        except Exception:
            print("C5_PDFIUM_LIVE_REFUSED: INTERNAL_OR_INSPECTION_REFUSED",flush=True)
            raise SystemExit(2)
    else:
        raise SystemExit(2)
