"""C5 acquisition-only identity verification; no downloaded code is used.

Reuses the previous checksum collector's HTTPResponse fixtures, fixed-origin
GET/deadline pattern and the source-test one-use marker gate. Disarmed by default.
"""
import base64
from contextlib import contextmanager
from dataclasses import dataclass, replace
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DRIVER = "qa/c5_wheel_metadata/remaining_dev_input_once.py"
WORKFLOW = ".github/workflows/c5-remaining-dev-input-once.yml"
MARKER = "qa/c5_wheel_metadata/APPROVAL_REMAINING_DEV_INPUT_ONCE_20261126.json"
OP = "C5-REMAINING-DEV-INPUT-ONCE-20261126"
MESSAGE = OP + " owner approved acquisition only"
LIVE_ENABLED = False
CAPABILITY = object()
SPEC = "docs/PILOTODIN_C5_REPRODUCIBLE_BUILD_INPUTS_IMPLEMENTATION_SPEC_2026-11-25.md"
SPEC_PIN = "8ca2c68b4de683d1162dd3efdbe5a7d971e4009b"
LOCK_PIN = "845bc92192a1b77432f4d472c7a056f47ca3a3a7"
MANIFEST_PIN = "fbb17a9f2e53eecb812498f02196fa7638f85299"
MAX_REQUESTS = 48
MAX_TOTAL = 928307900
MAX_NPM = 201326592
MAX_META = 262144
SCRATCH = 2 * 1024**3
HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
         "nodejs.org", "static.rust-lang.org", "pypi.org", "files.pythonhosted.org", "registry.npmjs.org"}
PYTHON_ASSETS = {
    "python-3.11.9-win32-x64.zip": ("3.11.9-9947079978", 179768229, 25934523),
    "python-3.11.18-linux-24.04-x64.tar.gz": ("3.11.18-40260280589", 676813336, 92610561),
}
PIP_NAME = "pip-26.3-py3-none-any.whl"
PIP_META_URL = "https://pypi.org/pypi/pip/26.3/json"
PIP_URL = re.compile(r"https://files\.pythonhosted\.org/packages/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/pip-26\.3-py3-none-any\.whl")

class Refused(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise Refused(reason)

def pinned(path, expected):
    p = ROOT / path
    need(p.is_file() and not p.is_symlink() and p.stat().st_size < 2**20, "PIN_PATH")
    raw = p.read_bytes()
    need(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == expected, "PIN_MISMATCH")
    return raw

def strict_json(raw):
    def unique(pairs):
        out = {}
        for key, val in pairs:
            need(key not in out, "JSON_DUPLICATE")
            out[key] = val
        return out
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: need(False, "JSON_CONSTANT"))

@dataclass(frozen=True)
class Row:
    id: str
    url: str
    alg: str
    digest: str | None
    cap: int
    exact: int | None = None
    npm: bool = False
    asset: int | None = None

def parts(url):
    need(type(url) is str and 0 < len(url) <= 8192 and all(33 <= ord(c) <= 126 for c in url), "URL_SYNTAX")
    u = urlsplit(url)
    need(u.scheme == "https" and u.netloc in HOSTS and not u.fragment and u.path.startswith("/"), "URL_ORIGIN")
    return u

def plan():
    doc = pinned(SPEC, SPEC_PIN).decode("utf-8").split("**Input set A: 11 toolchain archives.**", 1)[1].split("**Input set B:", 1)[0]
    rows = []
    for filename, digest, number, kind in re.findall(r"^\| ([A-Za-z0-9_.-]+) \| ([0-9a-f]{64}) \| ([0-9]+) (exact|cap) \|$", doc, re.M):
        cap = int(number)
        asset = None
        if filename in PYTHON_ASSETS:
            tag, asset, size = PYTHON_ASSETS[filename]
            need(kind == "exact" and cap == size, "PYTHON_ASSET_PIN")
            url = "https://github.com/actions/python-versions/releases/download/" + tag + "/" + filename
        elif filename == PIP_NAME:
            url = ""  # selected only from exact bounded publisher metadata
        elif re.fullmatch(r"node-v22\.23\.5-(win-x64\.zip|linux-x64\.tar\.xz)", filename):
            url = "https://nodejs.org/dist/v22.23.5/" + filename
        elif re.fullmatch(r"(rustc|cargo|rust-std)-1\.100\.0-x86_64-(pc-windows-msvc|unknown-linux-gnu)\.tar\.xz", filename):
            url = "https://static.rust-lang.org/dist/2026-11-12/" + filename
        else:
            raise Refused("TOOLCHAIN_ID")
        rows.append(Row(filename, url, "sha256", digest, cap, cap if kind == "exact" else None, asset=asset))
    need(len(rows) == 11 and len({r.id for r in rows}) == 11 and sum(r.cap for r in rows) + MAX_META + MAX_NPM == MAX_TOTAL, "TOOLCHAIN_SCOPE")
    pinned("frontend/package.json", MANIFEST_PIN)
    lock = strict_json(pinned("frontend/package-lock.json", LOCK_PIN))
    need(lock["lockfileVersion"] == 3 and len(lock["packages"]) == 91, "LOCK_SCOPE")
    def admits(v, osname):
        return (not v.get("os") or osname in v["os"]) and (not v.get("cpu") or "x64" in v["cpu"]) and (not v.get("libc") or (osname == "linux" and "glibc" in v["libc"]))
    win, linux = set(), set()
    for key, val in lock["packages"].items():
        if not key:
            continue
        if admits(val, "win32"): win.add(key)
        if admits(val, "linux"): linux.add(key)
    need(len(win) == len(linux) == 30 and len(win & linux) == 26 and len(win | linux) == 34, "NPM_TARGET_SCOPE")
    for key in sorted(win | linux):
        val = lock["packages"][key]
        u = parts(val["resolved"])
        need(u.netloc == "registry.npmjs.org" and not u.query and u.path.endswith(".tgz"), "NPM_URL")
        sri = val["integrity"]
        need(re.fullmatch(r"sha512-[A-Za-z0-9+/]{86}==", sri), "NPM_SRI")
        digest = base64.b64decode(sri[7:], validate=True).hex()
        rows.append(Row(key, val["resolved"], "sha512", digest, 33554432, npm=True))
    need(len(rows) == len({r.id for r in rows}) == len({r.url for r in rows}) == len({(r.alg,r.digest) for r in rows}) == 45, "ARTIFACT_SCOPE")
    return rows

def select_pip(row, raw):
    d = strict_json(raw)
    need(d["info"]["name"].lower() == "pip" and d["info"]["version"] == "26.3", "PIP_PROJECT")
    matches = [v for v in d["urls"] if v.get("filename") == PIP_NAME]
    need(len(matches) == 1, "PIP_AMBIGUOUS")
    v = matches[0]
    need(v.get("packagetype") == "bdist_wheel" and v.get("yanked") is False and v["digests"]["sha256"] == row.digest
         and type(v["size"]) is int and 0 < v["size"] <= row.cap and PIP_URL.fullmatch(v["url"]), "PIP_IDENTITY")
    return replace(row, url=v["url"], exact=v["size"])

def filename_projection(expected, q):
    """Pure diagnostic categories only. Never grants redirect permission.

    Call only with the bounded, validated query map from an original response.
    Do not return any input values, raw header, path, signed query or parser error.
    """
    from email import policy
    from email.message import EmailMessage

    def classify(value):
        if value in ("attachment; filename=" + expected, 'attachment; filename="' + expected + '"'):
            return "LITERAL_MATCH"
        if type(value) is not str or not 0 < len(value) <= 4096 or any(not 32 <= ord(c) <= 126 for c in value):
            return "INVALID"
        try:
            msg = EmailMessage(policy=policy.default)
            msg["Content-Disposition"] = value
            h = msg["Content-Disposition"]
            if h.defects:
                return "INVALID"
            params = dict(h.params)
            if h.content_disposition != "attachment":
                return "NOT_ATTACHMENT"
            if "filename" not in params:
                return "NO_FILENAME"
            if params["filename"] != expected:
                return "FILENAME_MISMATCH"
            if set(params) != {"filename"}:
                return "MATCH_EXTRA_PARAMETERS"
            return "PARSED_MATCH"
        except Exception:
            return "INVALID"

    return {
        key: classify(q[key]) if key in q else "ABSENT"
        for key in ("rscd", "response-content-disposition")
    }


def redirect(row, original, location):
    # Numeric asset IDs are independently confirmed in publisher metadata, not
    # inferred from the opaque UUID. Bind the redirect to the response to the
    # exact original TLS-authenticated endpoint, publisher repository and filename.
    need(row.id in PYTHON_ASSETS and original == row.url, "REDIRECT_SCOPE")
    tag, asset, size = PYTHON_ASSETS[row.id]
    need(row.asset == asset and row.exact == size and original == "https://github.com/actions/python-versions/releases/download/" + tag + "/" + row.id, "REDIRECT_ASSET")
    u = parts(location)
    need(u.netloc in {"release-assets.githubusercontent.com", "objects.githubusercontent.com"}
         and re.fullmatch(r"/github-production-release-asset(?:-2e65be)?/250077933/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", u.path), "REDIRECT_PATH")
    need(0 < len(u.query) <= 7000, "REDIRECT_QUERY")
    pairs = parse_qsl(u.query, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
    q = {k.lower(): v for k, v in pairs}
    need(len(q) == len(pairs) and all(k and 0 < len(v) <= 4096 and all(32 <= ord(c) <= 126 for c in v) for k, v in pairs), "REDIRECT_QUERY")
    dispositions = [q[k] for k in ("rscd", "response-content-disposition") if k in q]
    need(len(dispositions) == 1 and dispositions[0] in ("attachment; filename=" + row.id, 'attachment; filename="' + row.id + '"'), "REDIRECT_FILENAME")
    need(("sig" in q and "se" in q) or all(k in q for k in ("x-amz-signature", "x-amz-credential", "x-amz-expires")), "REDIRECT_SIGNATURE")
    return location

def header(resp, name, maximum=256):
    values = [v for k, v in resp.getheaders() if k.lower() == name.lower()]
    need(len(values) <= 1, "DUPLICATE_HEADER")
    if not values:
        return None
    v = values[0]
    need(len(v) <= maximum and all(32 <= ord(c) <= 126 for c in v), "HEADER_SYNTAX")
    return v

@contextmanager
def deadline(seconds):
    need(hasattr(signal, "setitimer") and signal.getitimer(signal.ITIMER_REAL) == (0., 0.), "TIMER")
    def alarm(*_):
        raise Refused("REQUEST_DEADLINE")
    prior = signal.signal(signal.SIGALRM, alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prior)

class MemorySocket:
    def __init__(self, raw): self.raw = raw
    def makefile(self, *_): return io.BytesIO(self.raw)

class Replay:
    responses = {}
    calls = []
    def __init__(self, host, port, **kwargs):
        need(host in HOSTS and port == 443, "FIXTURE_HOST")
        self.host = host
    def request(self, method, path, headers):
        url = "https://" + self.host + path
        need(method == "GET" and headers["Accept-Encoding"] == "identity" and url in self.responses, "FIXTURE_REQUEST")
        self.calls.append(url)
        self.raw = self.responses[url]
    def getresponse(self):
        resp = http.client.HTTPResponse(MemorySocket(self.raw))
        resp.begin()
        return resp
    def close(self): pass

class Transport:
    def __init__(self, scratch, connection, record, capability=None):
        need(connection is Replay or (LIVE_ENABLED and capability is CAPABILITY and connection is http.client.HTTPSConnection), "OFFLINE_FIXTURE_ONLY")
        self.scratch, self.connection, self.record = scratch, connection, record
        self.requests = self.body = self.npm_body = 0
        self.seen = set()
        self.end = time.monotonic() + 30 * 60

    def get(self, row):
        need(row.id not in self.seen and row.url and not parts(row.url).query, "REQUEST_SCOPE")
        self.seen.add(row.id)
        url = row.url
        for hop in (0, 1):
            cap = min(row.cap, MAX_TOTAL-self.body, MAX_NPM-self.npm_body if row.npm else MAX_TOTAL)
            need(self.requests < MAX_REQUESTS and cap > 0 and (row.exact is None or row.exact <= cap), "BUDGET")
            u = parts(url)
            self.requests += 1
            path = self.scratch / ("body-%02d" % self.requests)
            received, status, declared, complete = 0, None, None, False
            h = hashlib.new(row.alg)
            conn = None
            try:
                remaining = self.end - time.monotonic()
                need(remaining > 0, "JOB_DEADLINE")
                with deadline(min(120, remaining)):
                    conn = self.connection(u.netloc, 443, timeout=120, context=ssl.create_default_context())
                    conn.request("GET", u.path + ("?" + u.query if u.query else ""), headers={
                        "Accept-Encoding": "identity", "Connection": "close", "User-Agent": "PilotODIN-C5-acquisition/1"})
                    resp = conn.getresponse()
                    status = resp.status
                    enc = header(resp, "Content-Encoding")
                    need(enc is None or enc.lower() == "identity", "CONTENT_ENCODING")
                    length, te = header(resp, "Content-Length"), header(resp, "Transfer-Encoding")
                    need(te is None or (te.lower() == "chunked" and length is None), "FRAMING")
                    if length is not None:
                        need(re.fullmatch(r"[0-9]{1,10}", length), "BODY_LENGTH")
                        declared = int(length)
                    if status in (301,302,303,307,308):
                        need(hop == 0 and declared == 0 and te is None, "REDIRECT_FRAMING")
                        url = redirect(row, url, header(resp, "Location", 8192))
                        complete = True
                        continue
                    need(status == 200, "HTTP_STATUS")
                    need((declared is None and row.exact is None) or (declared is not None and 0 < declared <= cap and (row.exact is None or declared == row.exact)), "BODY_LENGTH")
                    with path.open("xb") as f:
                        while declared is None or received < declared:
                            room = cap - received
                            if room == 0:
                                need(resp.isclosed(), "BODY_BUDGET")
                                break
                            amount = min(65536, room, declared-received if declared is not None else room)
                            interrupted = False
                            try:
                                chunk = resp.read1(amount)
                            except http.client.IncompleteRead as exc:
                                chunk = exc.partial
                                interrupted = True
                            need(isinstance(chunk, bytes) and len(chunk) <= amount, "BODY_BUDGET")
                            if chunk:
                                received += len(chunk)
                                self.body += len(chunk)
                                if row.npm: self.npm_body += len(chunk)
                                h.update(chunk)
                                f.write(chunk)
                            need(not interrupted, "INCOMPLETE_BODY")
                            if not chunk: break
                    need(received > 0 and (declared is None or declared == received) and (row.exact is None or row.exact == received)
                         and path.stat().st_size == received, "INCOMPLETE_BODY")
                    complete = True
                    need(row.digest is None or h.hexdigest() == row.digest, "HASH_MISMATCH")
                    return path, received, h.hexdigest()
            finally:
                if conn is not None: conn.close()
                self.record("REQUEST", {"id": row.id, "hop": hop, "host": u.netloc, "status": status, "declared": declared,
                             "bytes": received, "algorithm": row.alg, "digest": h.hexdigest(), "complete": complete})
        raise Refused("REDIRECT_LIMIT")

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL, timeout=10).strip()

def live_gate():
    need(LIVE_ENABLED and os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_EVENT_NAME") == "push"
         and os.environ.get("GITHUB_REF") == "refs/heads/feature/live-dev-workspace-20261023"
         and os.environ.get("GITHUB_WORKFLOW") == "C5 remaining development input one-use"
         and os.environ.get("GITHUB_RUN_ATTEMPT") == "1" and re.fullmatch(r"[0-9]{1,20}", os.environ.get("GITHUB_RUN_ID","")), "FRESH_APPROVAL_REQUIRED")
    head = git("rev-parse", "HEAD")
    need(head == os.environ.get("GITHUB_SHA") and git("log","-1","--format=%s") == MESSAGE, "ACTIVATION_IDENTITY")
    parent = git("rev-parse","HEAD^")
    p = ROOT / MARKER
    need(p.is_file() and not p.is_symlink() and p.stat().st_size <= 4096, "MARKER")
    marker = strict_json(p.read_bytes())
    need(marker == {"operation": OP, "parent": parent, "driver": git("rev-parse","HEAD:"+DRIVER),
                    "workflow": git("rev-parse","HEAD:"+WORKFLOW), "spec": SPEC_PIN, "lock": LOCK_PIN,
                    "manifest": MANIFEST_PIN}, "APPROVAL_PIN")
    need(git("diff","--name-status",parent,head).splitlines() == ["A\t"+MARKER], "ACTIVATION_SCOPE")
    need(not git("status","--porcelain","--untracked-files=all"), "CHECKOUT_DIRTY")
    return CAPABILITY

def collect(rows, scratch, connection, record, capability=None):
    if connection is not Replay:
        need(rows == plan(), "LIVE_PLAN_MISMATCH")
    t = Transport(scratch, connection, record, capability)
    verified = []
    failure = None
    try:
        for row in rows:
            if row.id == PIP_NAME:
                meta = Row("pip-26.3-metadata", PIP_META_URL, "sha256", None, MAX_META)
                p, size, digest = t.get(meta)
                row = select_pip(row, p.read_bytes())
                record("PIP_SELECTED", {"id": row.id, "metadata_bytes": size, "metadata_sha256": digest,
                                       "url": row.url, "bytes": row.exact, "sha256": row.digest})
            _, size, digest = t.get(row)
            verified.append(row.id)
            record("VERIFIED", {"id":row.id, "url":row.url, "algorithm":row.alg, "bytes":size, "digest":digest})
    except Exception as exc:
        failure = str(exc) if isinstance(exc, Refused) else "TRANSPORT_OR_IO_REFUSED"
    return {"status":"IDENTITY_PASS" if failure is None and len(verified)==len(rows) else "REFUSED",
            "requests":t.requests, "response_bytes":t.body, "npm_bytes":t.npm_body,
            "verified":verified, "remaining":[r.id for r in rows if r.id not in verified],
            "failure":failure, "installed":False, "extracted":False, "licence_cleared":False}

def wire(body=b"", status="200 OK", headers=(), length=True):
    return ("HTTP/1.1 "+status+"\r\n"+"".join(k+": "+v+"\r\n" for k,v in headers)
            +("Content-Length: "+str(len(body))+"\r\n" if length else "")+"\r\n").encode()+body

HEADER_ENABLED = True
HEADER_CAPABILITY = object()
HEADER_OP = "C5-PYTHON-REDIRECT-HEADER-ONLY-20261126"
HEADER_MARKER = "qa/c5_wheel_metadata/APPROVAL_PYTHON_REDIRECT_HEADER_ONLY_20261126.json"
HEADER_MESSAGE = HEADER_OP + " owner approved headers only"


def header_gate():
    need(HEADER_ENABLED and not LIVE_ENABLED and os.environ.get("GITHUB_ACTIONS") == "true"
         and os.environ.get("GITHUB_EVENT_NAME") == "push"
         and os.environ.get("GITHUB_REF") == "refs/heads/feature/live-dev-workspace-20261023"
         and os.environ.get("GITHUB_WORKFLOW") == "C5 remaining development input one-use"
         and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
         and re.fullmatch(r"[0-9]{1,20}", os.environ.get("GITHUB_RUN_ID","")), "HEADER_APPROVAL_REQUIRED")
    head = git("rev-parse","HEAD")
    need(head == os.environ.get("GITHUB_SHA") and git("log","-1","--format=%s") == HEADER_MESSAGE, "HEADER_ACTIVATION")
    parent = git("rev-parse","HEAD^")
    p = ROOT / HEADER_MARKER
    need(p.is_file() and not p.is_symlink() and p.stat().st_size <= 4096 and not (ROOT / MARKER).exists(), "HEADER_MARKER")
    need(strict_json(p.read_bytes()) == {
        "operation": HEADER_OP, "parent": parent, "driver": git("rev-parse","HEAD:"+DRIVER),
        "workflow": git("rev-parse","HEAD:"+WORKFLOW), "spec": SPEC_PIN, "lock": LOCK_PIN, "manifest": MANIFEST_PIN
    }, "HEADER_PIN")
    need(git("diff","--name-status",parent,head).splitlines() == ["A\t"+HEADER_MARKER], "HEADER_SCOPE")
    need(not git("status","--porcelain","--untracked-files=all"), "CHECKOUT_DIRTY")
    return HEADER_CAPABILITY


def header_projection(row, location):
    # Original gate remains authoritative; only its final two predicate failures
    # allow a categorical diagnostic. Nothing here authorizes a redirected GET.
    gate = "PASS"
    try:
        redirect(row, row.url, location)
    except Refused as exc:
        gate = str(exc)
        if gate not in ("REDIRECT_FILENAME", "REDIRECT_SIGNATURE"):
            raise
    u = parts(location)
    q = {k.lower():v for k,v in parse_qsl(u.query,keep_blank_values=True,strict_parsing=True,max_num_fields=32)}
    shape = ("sig" in q and "se" in q) or all(k in q for k in ("x-amz-signature","x-amz-credential","x-amz-expires"))
    # Additional finite structural categories, never the raw value.
    aliases = ("rscd","response-content-disposition")
    def form(key):
        if key not in q:
            return "ABSENT"
        v = q[key]
        if v in ("attachment; filename="+row.id,'attachment; filename="'+row.id+'"'):
            return "LITERAL"
        if re.fullmatch(r"(?i:attachment;[ \t]*filename[ \t]*=[ \t]*)" + re.escape(row.id),v):
            return "ASCII_CASE_OR_SPACING"
        if re.fullmatch(r"(?i:attachment;[ \t]*filename[ \t]*=[ \t]*)\"" + re.escape(row.id) + '"',v):
            return "ASCII_CASE_OR_SPACING_QUOTED"
        if re.fullmatch(r"(?i:attachment;[ \t]*filename\*[ \t]*=[ \t]*UTF-8'')" + re.escape(row.id),v):
            return "EXTENDED_UTF8_ASCII"
        if re.fullmatch(r"(?i:attachment;[ \t]*filename[ \t]*=[ \t]*)" + re.escape(row.id) +
                        r";[ \t]*(?i:filename\*[ \t]*=[ \t]*UTF-8'')" + re.escape(row.id),v):
            return "DUAL_MATCHING_ASCII_EXTENDED"
        if re.fullmatch(r"(?i:attachment;[ \t]*filename[ \t]*=[ \t]*)\"" + re.escape(row.id) +
                        r"\";[ \t]*(?i:filename\*[ \t]*=[ \t]*UTF-8'')" + re.escape(row.id),v):
            return "DUAL_MATCHING_QUOTED_EXTENDED"
        return "OTHER"
    return {"gate":gate, "destination_host":u.netloc, "query_fields":len(q),
            "filename_categories":filename_projection(row.id,q),
            "filename_forms":{k:form(k) for k in aliases}, "signature_shape":shape}


def header_collect(connection, record, capability=None):
    need(connection is Replay or (HEADER_ENABLED and not LIVE_ENABLED and capability is HEADER_CAPABILITY
         and connection is http.client.HTTPSConnection), "HEADER_OFFLINE_ONLY")
    rows = [r for r in plan() if r.asset is not None]
    need(len(rows)==2 and [r.asset for r in rows]==[179768229,676813336], "HEADER_PLAN")
    requests = 0
    diagnosed = []
    failure = None
    end = time.monotonic()+270
    for row in rows:
        conn = resp = None
        item = {"id":row.id,"asset":row.asset,"origin":"github.com","status":None,"declared":None,
                "body_bytes":0,"redirects_followed":0}
        try:
            u = parts(row.url)
            need(requests<2 and u.netloc=="github.com" and not u.query, "HEADER_BUDGET")
            remaining = end-time.monotonic()
            need(remaining>0, "JOB_DEADLINE")
            with deadline(min(120,remaining)):
                conn = connection("github.com",443,timeout=120,context=ssl.create_default_context())
                requests += 1
                conn.request("GET",u.path,headers={"Accept-Encoding":"identity","Connection":"close",
                            "User-Agent":"PilotODIN-C5-acquisition/1"})
                resp = conn.getresponse()
                item["status"] = resp.status
                need(resp.status in (301,302,303,307,308),"HEADER_STATUS")
                enc = header(resp,"Content-Encoding")
                need(enc is None or enc.lower()=="identity","CONTENT_ENCODING")
                length = header(resp,"Content-Length")
                if length is not None and re.fullmatch(r"[0-9]{1,10}",length):
                    item["declared"]=int(length)
                need(item["declared"]==0 and header(resp,"Transfer-Encoding") is None,"REDIRECT_FRAMING")
                item.update(header_projection(row,header(resp,"Location",8192)))
                need(item["signature_shape"],"REDIRECT_SIGNATURE")
                need(item["gate"] in ("PASS","REDIRECT_FILENAME"),"HEADER_GATE")
                diagnosed.append(row.id)
        except Refused as exc:
            # Only fixed source refusal codes, never third-party exception text.
            failure = str(exc)
        except Exception:
            failure = "HEADER_TRANSPORT_REFUSED"
        finally:
            try:
                if resp is not None: resp.close()
                if conn is not None: conn.close()
            except Exception:
                failure = "HEADER_CLOSE_REFUSED"
            item["failure"] = failure
            record("ROW",item)
        if failure is not None:
            break
    return {"status":"DIAGNOSTIC_COMPLETE" if len(diagnosed)==2 and failure is None else "REFUSED",
            "requests":requests,"diagnosed":diagnosed,"body_bytes":0,"redirects_followed":0,
            "archive_acquisition":False,"failure":failure}


def header_live():
    cap = header_gate()
    def record(kind,data):
        print("C5_HEADER_"+kind,json.dumps(data,sort_keys=True,ensure_ascii=True),flush=True)
    result = header_collect(http.client.HTTPSConnection,record,cap)
    record("RESULT",result)
    return 0 if result["status"]=="DIAGNOSTIC_COMPLETE" else 2


def self_test():
    import unittest
    rows = plan()
    class Tests(unittest.TestCase):
        def setUp(self):
            self.tmp = tempfile.TemporaryDirectory()
            self.addCleanup(self.tmp.cleanup)
            self.records = []
            Replay.responses = {}; Replay.calls = []
            self.t = Transport(Path(self.tmp.name), Replay, lambda k,v:self.records.append((k,v)))
            self.row = Row("fixture", "https://nodejs.org/fixture", "sha256", hashlib.sha256(b"abc").hexdigest(), 3, 3)
        def reply(self, raw, row=None):
            row = row or self.row
            Replay.responses[row.url] = raw
            return self.t.get(row)
        def test_plan(self):
            self.assertEqual(len(rows),45)
            self.assertEqual(sum(r.npm for r in rows),34)
            self.assertEqual(sum(r.asset is not None for r in rows),2)
        def test_sha256(self):
            self.assertEqual(self.reply(wire(b"abc"))[1:], (3,self.row.digest))
        def test_sha512(self):
            row=replace(self.row,alg="sha512",digest=hashlib.sha512(b"abc").hexdigest(),npm=True)
            self.assertEqual(self.reply(wire(b"abc"),row)[2],row.digest)
            self.assertEqual(self.t.npm_body,3)
        def test_hash(self):
            with self.assertRaisesRegex(Refused,"HASH_MISMATCH"): self.reply(wire(b"xyz"))
            self.assertEqual(self.t.body,3)
        def test_large(self):
            with self.assertRaisesRegex(Refused,"BODY_LENGTH"): self.reply(wire(b"abcd"))
            self.assertEqual(self.t.body,0)
        def test_short(self):
            with self.assertRaisesRegex(Refused,"INCOMPLETE_BODY"): self.reply(wire(b"a",headers=(("Content-Length","3"),),length=False))
            self.assertEqual(self.t.body,1)
        def test_missing_length(self):
            with self.assertRaisesRegex(Refused,"BODY_LENGTH"): self.reply(wire(b"abc",length=False))
        def test_duplicate_header(self):
            with self.assertRaisesRegex(Refused,"DUPLICATE_HEADER"): self.reply(wire(b"abc",headers=(("Content-Length","3"),)))
        def test_encoding(self):
            with self.assertRaisesRegex(Refused,"CONTENT_ENCODING"): self.reply(wire(b"abc",headers=(("Content-Encoding","gzip"),)))
        def test_http_failure(self):
            with self.assertRaisesRegex(Refused,"HTTP_STATUS"): self.reply(wire(status="503 Unavailable"))
            self.assertEqual(self.t.requests,1)
        def test_no_retry(self):
            self.reply(wire(b"abc"))
            with self.assertRaisesRegex(Refused,"REQUEST_SCOPE"): self.t.get(self.row)
            self.assertEqual(len(Replay.calls),1)
        def test_request_cap(self):
            self.t.requests=MAX_REQUESTS
            with self.assertRaisesRegex(Refused,"BUDGET"): self.reply(wire(b"abc"))
        def test_total_cap(self):
            self.t.body=MAX_TOTAL-2
            with self.assertRaisesRegex(Refused,"BUDGET"): self.reply(wire(b"abc"))
        def test_npm_cap(self):
            self.t.npm_body=MAX_NPM-2
            with self.assertRaisesRegex(Refused,"BUDGET"): self.reply(wire(b"abc"),replace(self.row,npm=True))
        def test_unknown_origin(self):
            with self.assertRaisesRegex(Refused,"URL_ORIGIN"): self.reply(wire(b"abc"),replace(self.row,url="https://example.invalid/fixture"))
        def test_non_python_redirect(self):
            with self.assertRaisesRegex(Refused,"REDIRECT_SCOPE"): self.reply(wire(status="302 Found",headers=(("Location","https://github.com/foo"),)))
        def test_redirect_binding(self):
            row=next(r for r in rows if r.asset)
            url="https://release-assets.githubusercontent.com/github-production-release-asset/250077933/00000000-0000-0000-0000-000000000001?sig=fixture&se=fixture&rscd=attachment%3B%20filename%3D"+row.id
            self.assertEqual(redirect(row,row.url,url),url)
            for bad, reason in [(url.replace("250077933","999"),"REDIRECT_PATH"),(url.replace(row.id,"wrong.zip"),"REDIRECT_FILENAME"),(url+"&sig=duplicate","REDIRECT_QUERY"),(url.replace("sig=fixture&",""),"REDIRECT_SIGNATURE"),(url.replace("https:","http:"),"URL_ORIGIN")]:
                with self.subTest(reason=reason),self.assertRaisesRegex(Refused,reason): redirect(row,row.url,bad)
            with self.assertRaisesRegex(Refused,"REDIRECT_ASSET"): redirect(replace(row,asset=1),row.url,url)
            with self.assertRaisesRegex(Refused,"REDIRECT_SCOPE"): redirect(row,row.url+"x",url)
            Replay.responses[row.url]=wire(status="302 Found",headers=(("Location",url),))
            Replay.responses[url]=wire(status="302 Found",headers=(("Location",url),))
            with self.assertRaisesRegex(Refused,"REDIRECT_FRAMING"): self.t.get(row)
            self.assertEqual(len(Replay.calls),2)
            self.assertNotIn("sig=fixture",str(self.records))
        def test_redirect_nonzero(self):
            row=next(r for r in rows if r.asset)
            with self.assertRaisesRegex(Refused,"REDIRECT_FRAMING"): self.reply(wire(b"x",status="302 Found"),row)
            self.assertEqual(len(Replay.calls),1)
        def test_pip_metadata(self):
            row=next(r for r in rows if r.id==PIP_NAME)
            entry={"filename":PIP_NAME,"packagetype":"bdist_wheel","yanked":False,"digests":{"sha256":row.digest},"size":100,
                   "url":"https://files.pythonhosted.org/packages/aa/bb/"+"c"*60+"/"+PIP_NAME}
            doc={"info":{"name":"pip","version":"26.3"},"urls":[entry]}
            self.assertEqual(select_pip(row,json.dumps(doc).encode()).exact,100)
            for bad in [dict(entry,yanked=True),dict(entry,size=row.cap+1),dict(entry,url="https://example.invalid/"+PIP_NAME),dict(entry,digests={"sha256":"0"*64})]:
                with self.assertRaisesRegex(Refused,"PIP_IDENTITY"): select_pip(row,json.dumps(dict(doc,urls=[bad])).encode())
            with self.assertRaisesRegex(Refused,"PIP_AMBIGUOUS"): select_pip(row,json.dumps(dict(doc,urls=[entry,entry])).encode())
            with self.assertRaisesRegex(Refused,"JSON_DUPLICATE"): strict_json(b'{"a":1,"a":2}')
        def test_stop_and_safe_receipt(self):
            r2=replace(self.row,id="second",url="https://nodejs.org/second")
            Replay.responses={self.row.url:wire(b"xyz"),r2.url:wire(b"abc")}
            result=collect([self.row,r2],Path(self.tmp.name),Replay,lambda k,v:self.records.append((k,v)))
            self.assertEqual((result["status"],result["requests"],result["response_bytes"],result["verified"]),("REFUSED",1,3,[]))
            self.assertNotIn("xyz",str(self.records))
        def test_all_45_success(self):
            payload=b"abc"
            fixture=[replace(r,cap=3,exact=3,digest=hashlib.new(r.alg,payload).hexdigest()) for r in rows]
            pip=next(r for r in fixture if r.id==PIP_NAME)
            url="https://files.pythonhosted.org/packages/aa/bb/"+"c"*60+"/"+PIP_NAME
            doc={"info":{"name":"pip","version":"26.3"},"urls":[{"filename":PIP_NAME,"packagetype":"bdist_wheel","yanked":False,"digests":{"sha256":pip.digest},"size":3,"url":url}]}
            meta=json.dumps(doc).encode()
            Replay.responses={r.url:wire(payload) for r in fixture if r.url}
            Replay.responses.update({PIP_META_URL:wire(meta),url:wire(payload)})
            result=collect(fixture,Path(self.tmp.name),Replay,lambda k,v:self.records.append((k,v)))
            self.assertEqual(result["status"],"IDENTITY_PASS")
            self.assertEqual(result["requests"],46)
            self.assertEqual(result["response_bytes"],135+len(meta))
            self.assertEqual(result["npm_bytes"],102)
            self.assertEqual(result["verified"],[r.id for r in fixture])
            self.assertEqual(sum(k=="VERIFIED" for k,v in self.records),45)
            self.assertEqual(sum(k=="REQUEST" for k,v in self.records),46)
            self.assertEqual(result["remaining"],[])
        def test_valid_redirect_and_hash(self):
            row=next(r for r in rows if r.asset)
            body=b"x"*row.exact
            row=replace(row,digest=hashlib.sha256(body).hexdigest())
            url="https://release-assets.githubusercontent.com/github-production-release-asset/250077933/00000000-0000-0000-0000-000000000001?sig=fixture&se=fixture&rscd=attachment%3B%20filename%3D"+row.id
            Replay.responses={row.url:wire(status="302 Found",headers=(("Location",url),)),url:wire(body)}
            self.assertEqual(self.t.get(row)[1:],(row.exact,row.digest))
            self.assertEqual(self.t.requests,2)
            self.assertEqual(self.t.body,row.exact)
            self.assertNotIn("sig=fixture",str(self.records))
        def test_chunked_cap(self):
            row=replace(self.row,exact=None,cap=2,digest=None)
            with self.assertRaisesRegex(Refused,"BODY_BUDGET"):
                self.reply(wire(b"3\r\nabc\r\n0\r\n\r\n",headers=(("Transfer-Encoding","chunked"),),length=False),row)
            self.assertEqual(self.t.body,2)
        def test_partial_exception_accounted(self):
            row=replace(self.row,exact=None,cap=4,digest=None)
            with self.assertRaises((Refused,http.client.IncompleteRead)):
                self.reply(wire(b"3\r\na",headers=(("Transfer-Encoding","chunked"),),length=False),row)
            self.assertLessEqual(self.t.body,4)
            self.assertEqual(self.t.body,sum(v["bytes"] for k,v in self.records if k=="REQUEST"))
        def test_filename_projection(self):
            expected=next(r.id for r in rows if r.asset)
            for value, category in [
                ("attachment; filename="+expected,"LITERAL_MATCH"),
                ('attachment; filename="'+expected+'"',"LITERAL_MATCH"),
                ("Attachment;Filename = "+expected,"PARSED_MATCH"),
                ("attachment; filename*=UTF-8''"+expected,"PARSED_MATCH"),
                ("attachment; filename="+expected+"; size=123","MATCH_EXTRA_PARAMETERS"),
                ("attachment; filename=untrusted.zip","FILENAME_MISMATCH"),
                ("attachment; filename="+expected+"; filename=untrusted.zip","INVALID"),
                ("attachment","NO_FILENAME"),
                ("inline; filename="+expected,"NOT_ATTACHMENT"),
                ("attachment;\r\nfilename="+expected,"INVALID"),
            ]:
                with self.subTest(category=category):
                    out=filename_projection(expected,{"rscd":value,"sig":"fixture-secret"})
                    self.assertEqual(out,{"rscd":category,"response-content-disposition":"ABSENT"})
                    self.assertNotIn(expected,str(out))
                    self.assertNotIn("fixture-secret",str(out))
                    self.assertNotIn("untrusted.zip",str(out))
            self.assertEqual(filename_projection(expected,{}),{"rscd":"ABSENT","response-content-disposition":"ABSENT"})
            self.assertEqual(filename_projection(expected,{"rscd":"attachment; filename="+expected,
              "response-content-disposition":"attachment; filename=untrusted.zip"}),
              {"rscd":"LITERAL_MATCH","response-content-disposition":"FILENAME_MISMATCH"})
        def test_diagnostic_does_not_relax_redirect(self):
            row=next(r for r in rows if r.asset)
            prefix="https://release-assets.githubusercontent.com/github-production-release-asset/250077933/00000000-0000-0000-0000-000000000001?sig=fixture&se=fixture"
            from urllib.parse import urlencode
            for q in [{},{"rscd":"Attachment;Filename = "+row.id},{"rscd":"attachment; filename*=UTF-8''"+row.id},
                      {"rscd":"attachment; filename="+row.id,"response-content-disposition":"attachment; filename="+row.id},
                      {"rscd":"attachment; filename=untrusted.zip"}]:
                with self.subTest(keys=sorted(q)),self.assertRaisesRegex(Refused,"REDIRECT_FILENAME"):
                    redirect(row,row.url,prefix+("&"+urlencode(q) if q else ""))
        def test_header_only_two_original_requests(self):
            from unittest.mock import patch
            from urllib.parse import urlencode
            python_rows=[r for r in rows if r.asset]
            for row in python_rows:
                location="https://release-assets.githubusercontent.com/github-production-release-asset/250077933/00000000-0000-0000-0000-000000000001?"+urlencode({"sig":"fixture-secret","se":"fixture","rscd":"attachment; filename="+row.id+"; filename*=UTF-8''"+row.id})
                Replay.responses[row.url]=wire(status="302 Found",headers=(("Location",location),))
            with patch.object(http.client.HTTPResponse,"read",side_effect=AssertionError("body read")),patch.object(http.client.HTTPResponse,"read1",side_effect=AssertionError("body read")):
                result=header_collect(Replay,lambda k,v:self.records.append((k,v)))
            self.assertEqual(result["status"],"DIAGNOSTIC_COMPLETE")
            self.assertEqual(Replay.calls,[r.url for r in python_rows])
            self.assertEqual(result["requests"],2)
            self.assertEqual(result["body_bytes"],0)
            self.assertEqual(result["redirects_followed"],0)
            self.assertTrue(all(v["gate"]=="REDIRECT_FILENAME" and v["signature_shape"] for _,v in self.records))
            self.assertTrue(all(v["filename_forms"]["rscd"]=="DUAL_MATCHING_ASCII_EXTENDED" for _,v in self.records))
            self.assertNotIn("fixture-secret",str(self.records))
            self.assertNotIn("00000000-",str(self.records))
        def test_header_only_stops_on_framing_or_origin(self):
            from unittest.mock import patch
            row=next(r for r in rows if r.asset)
            for raw, reason in [(wire(b"x",status="302 Found"),"REDIRECT_FRAMING"),
                                (wire(status="302 Found",headers=(("Location","https://example.invalid/fixture"),)),"URL_ORIGIN"),
                                (wire(b"x"),"HEADER_STATUS")]:
                Replay.responses={row.url:raw}; Replay.calls=[]
                with patch.object(http.client.HTTPResponse,"read",side_effect=AssertionError("body read")),patch.object(http.client.HTTPResponse,"read1",side_effect=AssertionError("body read")):
                    result=header_collect(Replay,lambda *_:None)
                self.assertEqual((result["status"],result["failure"],result["requests"]),("REFUSED",reason,1))
                self.assertEqual(Replay.calls,[row.url])
        def test_header_only_signature_refusal(self):
            row=next(r for r in rows if r.asset)
            location="https://release-assets.githubusercontent.com/github-production-release-asset/250077933/00000000-0000-0000-0000-000000000001?rscd=attachment%3B%20filename%3D"+row.id
            Replay.responses[row.url]=wire(status="302 Found",headers=(("Location",location),))
            result=header_collect(Replay,lambda k,v:self.records.append((k,v)))
            self.assertEqual((result["status"],result["failure"],result["requests"]),("REFUSED","REDIRECT_SIGNATURE",1))
            self.assertFalse(self.records[0][1]["signature_shape"])
        def test_header_gate_disarmed(self):
            with self.assertRaisesRegex(Refused,"HEADER_APPROVAL_REQUIRED"): header_gate()
            with self.assertRaisesRegex(Refused,"HEADER_OFFLINE_ONLY"): header_collect(http.client.HTTPSConnection,lambda *_:None)
        def test_disarmed(self):
            with self.assertRaisesRegex(Refused,"FRESH_APPROVAL_REQUIRED"): live_gate()
            with self.assertRaisesRegex(Refused,"OFFLINE_FIXTURE_ONLY"): Transport(Path(self.tmp.name),http.client.HTTPSConnection,lambda *_:None)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    need(result.wasSuccessful(),"SYNTHETIC_FAILURE")
    print("C5_REMAINING_INPUT_REHEARSAL_PASS",json.dumps({"checks":result.testsRun,"artifacts":len(rows),"live_requests":0,"live_enabled":LIVE_ENABLED}),flush=True)

def live():
    capability=live_gate()
    rows=plan()
    def record(kind, data):
        print("C5_REMAINING_INPUT_"+kind,json.dumps(data,sort_keys=True,ensure_ascii=True),flush=True)
    with tempfile.TemporaryDirectory(prefix="c5-remaining-input-",dir=os.environ["RUNNER_TEMP"]) as directory:
        scratch=Path(directory)
        need(shutil.disk_usage(scratch).free >= SCRATCH,"FREE_SPACE")
        result=collect(rows,scratch,http.client.HTTPSConnection,record,capability)
    record("RESULT",result)
    return 0 if result["status"]=="IDENTITY_PASS" else 2

if __name__=="__main__":
    try:
        if sys.argv[1:]==["--rehearse"]: self_test()
        elif sys.argv[1:]==["--live"]: raise SystemExit(live())
        elif sys.argv[1:]==["--header-live"]: raise SystemExit(header_live())
        else: raise Refused("COMMAND_REFUSED")
    except Refused as exc:
        print("C5_REMAINING_INPUT_REFUSED",str(exc),flush=True)
        raise SystemExit(2)
    except Exception:
        print("C5_REMAINING_INPUT_REFUSED INTERNAL_OR_IO_REFUSED",flush=True)
        raise SystemExit(2)
