"""Disarmed freezer candidate metadata collector; no automatic resolver or installation."""
import base64
import email.policy
from email.parser import BytesParser
import hashlib
import http.client
import json
import io
import os
from pathlib import Path
import re
import ssl
import signal
from contextlib import contextmanager
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = "qa/c5_metadata/release_metadata_receipt_20261125.jsonl"
RECEIPT_SHA = "2c9329e146f75fe3ba8c832f165660fd1e01027447c5adff28984093472e866b"
OBSERVED = "contracts/c5_observed_python_wheels_2026-11-25.json"
OBSERVED_BLOB = "6ccd3d47efe363ecf87fd13ce7d867cba4bef020"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
HEX = re.compile(r"[a-f0-9]{64}")
FILENAME = re.compile(r"[A-Za-z0-9_.+!-]{1,235}\.whl")
MIB = 1024 * 1024
TOTAL = 128 * MIB
LIMITS = {"index": (6, 32 * MIB), "metadata": (6, MIB)}
LIVE_ENABLED = False  # Approval consumed by exact run 45704870236; no replay.
OPERATION = "C5-FREEZER-METADATA-ONCE-20261125"
MARKER = ROOT / "qa/c5_wheel_metadata/APPROVAL_FREEZER_20261125.txt"
MARKER_BYTES = (OPERATION + "\nOne hosted attempt; 6 indexes and 6 selected hash-advertised sidecars maximum; 32 MiB/index, 1 MiB/sidecar, 128 MiB aggregate.\n").encode("ascii")
WORKFLOW = "C5 freezer metadata offline review"
_LIVE_CAPABILITY = object()


class Blocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Blocked(reason)


def unique(pairs):
    obj = {}
    for k, v in pairs:
        require(k not in obj, "DUPLICATE_JSON_KEY")
        obj[k] = v
    return obj


def parse(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(Blocked("NONFINITE_JSON")))


def normalized(value):
    require(type(value) is str, "INVALID_NAME")
    return re.sub(r"[-_.]+", "-", value).lower()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_pin(path):
    p = ROOT / path
    require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 2 * MIB, "SOURCE_PIN_SIZE")
    return p.read_bytes()


def metadata(raw, row):
    require(sha(raw) == row["metadata_sha256"], "SIDECAR_DIGEST_MISMATCH")
    raw.decode("utf-8", errors="strict")
    msg = BytesParser(policy=email.policy.default).parsebytes(raw, headersonly=True)
    require(not msg.defects, "MALFORMED_METADATA")
    require(all(not getattr(v, "defects", ()) for _, v in msg.items()), "MALFORMED_METADATA_HEADER")
    def singleton(key, required=False):
        values = msg.get_all(key, [])
        require(len(values) <= 1 and (not required or len(values) == 1), "DUPLICATE_OR_MISSING_SINGLETON")
        return str(values[0]) if values else None
    mv = singleton("Metadata-Version", True)
    require(mv in {"1.0", "1.1", "1.2", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6"}, "METADATA_VERSION_UNSUPPORTED")
    name, version = singleton("Name", True), singleton("Version", True)
    require(normalized(name) == row["name"] and version == row["version"], "METADATA_IDENTITY")
    return {"metadata_version": mv,
            "name": name, "version": version, "requires_python": singleton("Requires-Python"),
            "requires_dist": [str(x) for x in msg.get_all("Requires-Dist", [])],
            "provides_extra": [str(x) for x in msg.get_all("Provides-Extra", [])],
            "license": singleton("License"), "license_expression": singleton("License-Expression"),
            "license_files": [str(x) for x in msg.get_all("License-File", [])],
            "license_classifiers": [str(x) for x in msg.get_all("Classifier", [])
                                    if str(x).startswith("License ::")]}


def emit(kind, value):
    print("C5_WHEEL_" + kind + " " + json.dumps(value, ensure_ascii=True, sort_keys=True,
                                                separators=(",", ":")), flush=True)


MEDIA = re.compile(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+")
INDEX_TYPE = "application/vnd.pypi.simple.v1+json"


def media_type(value):
    # Log only the normalized, bounded type token, never raw arbitrary headers.
    if value is None:
        return "ABSENT"
    if type(value) is not str or not 0 < len(value) <= 256:
        return "INVALID"
    if any(ord(c) < 32 or ord(c) > 126 for c in value):
        return "INVALID"
    token = value.split(";", 1)[0].strip().lower()
    return token if MEDIA.fullmatch(token) else "INVALID"


def media_allowed(kind, token):
    if kind == "index":
        return token == INDEX_TYPE
    # PEP 658 binds the metadata to the distribution and advertised digest,
    # not a required HTTP MIME. Generic/absent types are admissible only
    # to bounded reading and mandatory hash/identity parsing, never to trust.
    return token == "ABSENT" or token in {
        "text/plain", "application/octet-stream", "binary/octet-stream",
        "application/x-octet-stream",
    }


@contextmanager
def request_deadline():
    """Hosted Linux only: bound DNS, handshake, headers and body together."""
    require(hasattr(signal, "setitimer") and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0),
            "DEADLINE_TIMER_UNAVAILABLE")
    def expired(signum, frame):
        raise Blocked("REQUEST_DEADLINE")
    previous = signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, 15)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def singleton_header(response, key):
    values = [v for k, v in response.getheaders() if k.lower() == key.lower()]
    require(len(values) <= 1, "DUPLICATE_HTTP_HEADER")
    if not values:
        return None
    require(type(values[0]) is str and len(values[0]) <= 256 and
            all(32 <= ord(c) <= 126 for c in values[0]), "INVALID_HTTP_HEADER")
    return values[0]


class Client:
    def __init__(self, groups, connection, capability=None):
        self.allowed = {"index": {"https://pypi.org/simple/" + n + "/" for n in groups},
                        "metadata": set()}
        require(connection in (FixtureConnection, ReplayConnection, Never) or
                (LIVE_ENABLED and capability is _LIVE_CAPABILITY and
                 connection is http.client.HTTPSConnection), "OFFLINE_FIXTURE_ONLY")
        self.connection = connection
        self.fixture = connection is not http.client.HTTPSConnection
        self.counts = {"index": 0, "metadata": 0}
        self.total = 0
        self.seen = set()
        self.enabled = set()
        self.selected_names = set()
        self.groups = groups

    def authorize_sidecar(self, raw, name):
        require(name in self.groups and name not in self.selected_names
                and "https://pypi.org/simple/"+name+"/" in self.seen, "SIDECAR_NOT_ALLOWLISTED")
        w = choose(raw,name,self.groups[name])
        self.selected_names.add(name)
        self.allowed["metadata"].add(w["metadata_url"])
        self.enabled.add(w["metadata_url"])
        return w

    def get(self, kind, url):
        with request_deadline():
            return self._get(kind, url)

    def _get(self, kind, url):
        maximum, cap = LIMITS[kind]
        require(url in self.allowed[kind] and url not in self.seen
                and (kind == "index" or url in self.enabled)
                and self.counts[kind] < maximum and self.total < TOTAL, "REQUEST_SCOPE_OR_BUDGET")
        self.seen.add(url)
        self.counts[kind] += 1
        u = urlsplit(url)
        conn = None
        received = 0
        digest = hashlib.sha256()
        status = None
        content_type = "UNOBSERVED"
        declared_length = "UNOBSERVED"
        deadline = time.monotonic() + 15
        success = False
        try:
            conn = self.connection(u.hostname, 443, timeout=15, context=ssl.create_default_context())
            accept = "application/vnd.pypi.simple.v1+json" if kind == "index" else "text/plain, application/octet-stream, */*;q=0.1"
            conn.request("GET", u.path, headers={"Accept": accept, "Accept-Encoding": "identity",
                                                "User-Agent": "PilotODIN-C5-wheel-metadata-only/1"})
            response = conn.getresponse()
            status = response.status
            # Keep normalized diagnostic even on rejection; reject duplicate framing.
            content_type = media_type(response.getheader("Content-Type"))
            require(status == 200, "HTTP_STATUS_REFUSED")
            require(singleton_header(response, "Content-Type") == response.getheader("Content-Type"),
                    "DUPLICATE_HTTP_HEADER")
            encoding = singleton_header(response, "Content-Encoding")
            require(encoding is None or encoding.lower() == "identity", "CONTENT_ENCODING_REFUSED")
            require(media_allowed(kind, content_type), "CONTENT_TYPE_REFUSED")
            length = singleton_header(response, "Content-Length")
            declared_length = (int(length) if length is not None and re.fullmatch(r"[0-9]{1,10}", length)
                               else "ABSENT" if length is None else "INVALID")
            transfer = singleton_header(response, "Transfer-Encoding")
            require(transfer is None or (transfer.lower() == "chunked" and length is None),
                    "AMBIGUOUS_HTTP_FRAMING")
            remaining = min(cap, TOTAL - self.total)
            if length is not None:
                require(re.fullmatch(r"[0-9]{1,10}", length) and 0 < int(length) <= remaining,
                        "RESPONSE_LENGTH_REFUSED")
            chunks = []
            while True:
                require(time.monotonic() < deadline, "REQUEST_DEADLINE")
                if length is not None and received == int(length):
                    break
                room = min(cap - received, TOTAL - self.total)
                require(room > 0, "RESPONSE_BUDGET_REACHED")
                if conn.sock is not None:
                    conn.sock.settimeout(max(0.001, deadline - time.monotonic()))
                chunk = response.read1(min(65536, room))
                if not chunk:
                    break
                require(len(chunk) <= room, "RESPONSE_BUDGET_REACHED")
                received += len(chunk)
                self.total += len(chunk)
                digest.update(chunk)
                chunks.append(chunk)
            require(received > 0 and (length is None or received == int(length)), "INCOMPLETE_BODY")
            require(time.monotonic() < deadline, "REQUEST_DEADLINE")
            success = True
            return b"".join(chunks)
        finally:
            if conn is not None:
                conn.close()
            emit("REQUEST", {"kind": kind, "url": url, "http_status": status, "bytes": received,
                             "response_sha256": digest.hexdigest(), "complete": success,
                             "content_type": content_type, "declared_length": declared_length,
                             "response_cap_bytes": cap, "fixture": self.fixture})


class Never:
    def __init__(self, *a, **kw):
        raise Blocked("UNEXPECTED_NETWORK")


class FixtureResponse:
    def __init__(self, status, headers, raw):
        self.status = status
        self.headers = headers
        self.body = io.BytesIO(raw)

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def getheaders(self):
        return list(self.headers.items())

    def read1(self, size):
        return self.body.read(size)


class FixtureConnection:
    sock = None
    fixture = None
    expected = None

    def __init__(self, host, port, **kwargs):
        require(port == 443 and host in {"pypi.org", "files.pythonhosted.org"}, "FIXTURE_HOST")
        self.host = host

    def request(self, method, path, headers):
        require(method == "GET" and (self.host, path) == self.expected
                and headers["Accept-Encoding"] == "identity", "FIXTURE_REQUEST")

    def getresponse(self):
        return self.fixture

    def close(self):
        pass


class MemorySocket:
    def __init__(self, wire):
        self.wire = wire
    def makefile(self, mode):
        return io.BytesIO(self.wire)


class ReplayConnection:
    """Real stdlib HTTPResponse parser over in-memory wire bytes; no socket."""
    sock = None
    responses = {}
    requests = []
    def __init__(self, host, port, **kwargs):
        require(port == 443 and host in {"pypi.org", "files.pythonhosted.org"}, "FIXTURE_HOST")
        self.host = host
    def request(self, method, path, headers):
        url = "https://" + self.host + path
        require(method == "GET" and headers["Accept-Encoding"] == "identity" and
                url in self.responses, "FIXTURE_REQUEST")
        self.requests.append(url)
        self.wire = self.responses[url]
    def getresponse(self):
        response = http.client.HTTPResponse(MemorySocket(self.wire))
        response.begin()
        return response
    def close(self):
        pass


def authorize_live():
    require(LIVE_ENABLED, "FRESH_APPROVAL_REQUIRED")
    require(os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_EVENT_NAME") == "push"
            and os.environ.get("GITHUB_REF") == "refs/heads/feature/live-dev-workspace-20261023"
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
            and os.environ.get("GITHUB_WORKFLOW") == WORKFLOW
            and os.environ.get("C5_APPROVED_ONCE") == OPERATION
            and re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", ""))
            and os.environ.get("GITHUB_SHA") == os.environ.get("C5_EXPECTED_SOURCE_SHA")
            and re.fullmatch(r"[0-9]{1,20}", os.environ.get("GITHUB_RUN_ID", "")),
            "ONE_USE_CONTEXT_REQUIRED")
    require(MARKER.is_file() and not MARKER.is_symlink() and
            MARKER.stat().st_size == len(MARKER_BYTES) and MARKER.read_bytes() == MARKER_BYTES,
            "APPROVAL_MARKER_MISMATCH")
    return _LIVE_CAPABILITY


def wire(body, headers=(), status="200 OK", length=True):
    fields = list(headers)
    if length:
        fields.append(("Content-Length", str(len(body))))
    return ("HTTP/1.1 " + status + "\r\n" +
            "".join(k + ": " + v + "\r\n" for k, v in fields) +
            "\r\n").encode("ascii") + body



from packaging import __version__ as packaging_version
from packaging.specifiers import SpecifierSet
from packaging.tags import cpython_tags, compatible_tags
from packaging.utils import parse_wheel_filename, InvalidWheelFilename
from packaging.version import Version

INTENT = "qa/c5_wheel_metadata/freezer_source_intent_20261125.json"
INTENT_BLOB = "71293a827b880f3c48b858a52ad783f6cd5411be"
RULES = {"altgraph":"", "pefile":">=2022.5.30", "pyinstaller":"==6.22.3",
         "pyinstaller-hooks-contrib":"==2026.9", "pywin32-ctypes":">=0.2.1",
         "setuptools":">=42.0.0"}
PYTHON = Version("3.11.9")
TAGS = list(cpython_tags((3,11),abis=["cp311"],platforms=["win_amd64"])) + list(
    compatible_tags((3,11),interpreter="cp311",platforms=["win_amd64"]))
RANK = {t:i for i,t in reversed(list(enumerate(TAGS)))}


def source_scope():
    raw = read_pin(INTENT)
    require(hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()==INTENT_BLOB,
            "FREEZER_INTENT_PIN")
    require(packaging_version == "24.0","REVIEWER_VERSION")
    return dict(RULES)


def choose(raw,name,constraint):
    require(name in RULES and constraint==RULES[name],"PROJECT_SCOPE")
    doc=parse(raw)
    require(type(doc) is dict and normalized(doc["name"])==name and type(doc["files"]) is list,
            "INDEX_IDENTITY")
    candidates=[]
    names=set()
    for item in doc["files"]:
        require(type(item) is dict and type(item.get("filename")) is str,"INDEX_ROW")
        filename=item["filename"]
        if not filename.endswith(".whl"):
            continue
        require(FILENAME.fullmatch(filename) and filename not in names,"INDEX_FILENAME")
        names.add(filename)
        try:
            pname,version,build,tags=parse_wheel_filename(filename)
        except InvalidWheelFilename:
            raise Blocked("INVALID_WHEEL_FILENAME")
        require(pname==name,"INDEX_WHEEL_PROJECT")
        ranks=[RANK[t] for t in tags if t in RANK]
        if not ranks or version.is_prerelease or version.is_devrelease or version.local is not None:
            continue
        if not SpecifierSet(constraint).contains(version,prereleases=False):
            continue
        if item.get("yanked") is not False:
            continue
        rp=item.get("requires-python")
        if rp is not None:
            require(type(rp) is str and bool(rp.strip()),"INDEX_PYTHON_INVALID")
            if not SpecifierSet(rp).contains(PYTHON):
                continue
        candidates.append((version,min(ranks),build,item))
    require(candidates,"NO_COMPATIBLE_CANDIDATE")
    # No resolver, backtracking or cross-project search.
    v=max(x[0] for x in candidates)
    rank=min(x[1] for x in candidates if x[0]==v)
    best=[x for x in candidates if x[0]==v and x[1]==rank]
    require(len(best)==1,"AMBIGUOUS_BEST_WHEEL")
    _,_,_,item=best[0]
    filename=item["filename"]
    url=item["url"]
    u=urlsplit(url)
    require(u.scheme=="https" and u.netloc=="files.pythonhosted.org" and not u.query and not u.fragment
            and re.fullmatch(r"/packages/[a-f0-9]{2}/[a-f0-9]{2}/[a-f0-9]{60}/"+re.escape(filename),u.path),
            "WHEEL_URL_REFUSED")
    require(type(item.get("hashes")) is dict and HEX.fullmatch(item["hashes"].get("sha256","")),
            "WHEEL_HASH_UNAVAILABLE")
    size=item.get("size")
    require(type(size) is int and size>0,"WHEEL_SIZE_UNAVAILABLE")
    values=[item[k] for k in ("core-metadata","dist-info-metadata") if k in item]
    require(values and all(type(x) is dict and type(x.get("sha256")) is str and HEX.fullmatch(x["sha256"])
                           for x in values),"SIDECAR_HASH_UNAVAILABLE")
    require(all(x["sha256"]==values[0]["sha256"] for x in values),"SIDECAR_HASH_CONFLICT")
    return {"name":name,"version":str(v),"filename":filename,"url":url,
            "wheel_sha256":item["hashes"]["sha256"],"wheel_bytes":size,
            "metadata_url":url+".metadata","metadata_sha256":values[0]["sha256"],
            "index_requires_python":item.get("requires-python"),"constraint":constraint,
            "selection":"HISTORICAL_EXACT" if constraint.startswith("==") else "HIGHEST_STABLE_ELIGIBLE",
            "candidate_only":True}


def collect(groups,client,record=emit):
    verified=[]
    failure=None
    digest=hashlib.sha256()
    def write(kind,row):
        digest.update(json.dumps({"kind":kind,"record":row},sort_keys=True,ensure_ascii=True,
                                 separators=(",",":")).encode("ascii")+b"\n")
        record(kind,row)
    current=None
    try:
        for name in sorted(groups):
            current=name
            raw=client.get("index","https://pypi.org/simple/"+name+"/")
            w=client.authorize_sidecar(raw,name)
            write("INDEX",{"name":name,"response_sha256":sha(raw),"selected":[w]})
            sidecar=client.get("metadata",w["metadata_url"])
            d=metadata(sidecar,w)
            if d["requires_python"] is not None:
                require(SpecifierSet(d["requires_python"]).contains(PYTHON),"METADATA_PYTHON_CONFLICT")
            b64=base64.b64encode(sidecar).decode("ascii")
            for offset in range(0,len(b64),8192):
                write("BYTES",{"filename":w["filename"],"offset":offset,"base64":b64[offset:offset+8192]})
            write("VERIFIED",{"filename":w["filename"],"metadata_sha256":sha(sidecar),
                              "bytes":len(sidecar),"declarations":d})
            verified.append(name)
    except (Blocked,OSError,ValueError,KeyError,TypeError,AttributeError,http.client.HTTPException) as exc:
        failure=str(exc) if type(exc) is Blocked else type(exc).__name__
    result={"requests":dict(client.counts),"response_bytes":client.total,"verified":len(verified),
            "missing":sorted(set(groups)-set(verified)),"failure":failure,"last_identity":current,
            "artifact_requests":0,"fixture":client.fixture,"receipt_sha256":digest.hexdigest(),
            "status":"METADATA_ONLY_COMPLETE" if len(verified)==6 and failure is None else "BLOCKED"}
    record("RESULT",result)
    return result


def live_collect():
    capability=authorize_live()
    groups=source_scope()
    client=Client(groups,http.client.HTTPSConnection,capability=capability)
    def record(kind,row):
        if kind=="RESULT":
            row={**row,"source_sha":os.environ["GITHUB_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],
                 "run_attempt":1,"operation":OPERATION}
        emit(kind,row)
    return 0 if collect(groups,client,record)["status"]=="METADATA_ONLY_COMPLETE" else 2


def fixture_item(name,version,tag="py3-none-any",rp=">=3.8",yanked=False):
    filename=name.replace("-","_")+"-"+version+"-"+tag+".whl"
    raw=("Metadata-Version: 2.4\nName: "+name+"\nVersion: "+version+"\nRequires-Python: >=3.8\n\nfixture").encode()
    item={"filename":filename,"url":"https://files.pythonhosted.org/packages/ab/cd/"+"0"*60+"/"+filename,
          "hashes":{"sha256":"1"*64},"size":10,"yanked":yanked,"requires-python":rp,
          "core-metadata":{"sha256":sha(raw)}}
    return item,raw


def self_test():
    groups=source_scope()
    count=0
    def check(ok,reason):
        nonlocal count
        require(ok,"TEST_"+reason)
        count+=1
    def refuse(fn,reason):
        try:
            fn()
        except Blocked as exc:
            check(str(exc)==reason,"REFUSAL_"+reason)
        else:
            raise Blocked("TEST_ACCEPTED_"+reason)
    def index(name,items):
        return json.dumps({"name":name,"files":items}).encode()
    versions={"altgraph":"1.0","pefile":"2025.1","pyinstaller":"6.22.3",
              "pyinstaller-hooks-contrib":"2026.9","pywin32-ctypes":"0.2.3","setuptools":"80.0"}
    replies={}
    for name,version in versions.items():
        item,raw=fixture_item(name,version)
        replies["https://pypi.org/simple/"+name+"/"]=wire(index(name,[item]),(("Content-Type",INDEX_TYPE),))
        replies[item["url"]+".metadata"]=wire(raw,(("Content-Type","binary/octet-stream"),))
    def run(replies):
        ReplayConnection.responses=replies
        ReplayConnection.requests=[]
        records=[]
        result=collect(groups,Client(groups,ReplayConnection),lambda k,r:records.append((k,r)))
        return result,records,list(ReplayConnection.requests)
    r,records,requests=run(replies)
    check(r["status"]=="METADATA_ONLY_COMPLETE" and r["verified"]==6 and r["requests"]=={"index":6,"metadata":6},"FULL")
    check(len(requests)==len(set(requests))==12 and set(requests)==set(replies) and r["fixture"],"EXACT_SCOPE")
    check(sum(k=="VERIFIED" for k,_ in records)==6 and sum(k=="BYTES" for k,_ in records)==6,"RECEIPT")
    name="altgraph"
    low,_=fixture_item(name,"1.0")
    high,_=fixture_item(name,"2.0")
    bad,_=fixture_item(name,"3.0",rp=">=3.12")
    yanked,_=fixture_item(name,"4.0",yanked=True)
    pre,_=fixture_item(name,"5.0rc1")
    linux,_=fixture_item(name,"6.0",tag="cp311-cp311-manylinux_2_28_x86_64")
    check(choose(index(name,[low,high,bad,yanked,pre,linux]),name,"")["version"]=="2.0","STABLE_COMPATIBLE")
    native,_=fixture_item(name,"2.0",tag="cp311-cp311-win_amd64")
    check(choose(index(name,[high,native]),name,"")["filename"]==native["filename"],"TAG_RANK")
    fix,_=fixture_item("pyinstaller","6.22.3")
    other,_=fixture_item("pyinstaller","6.23.0")
    check(choose(index("pyinstaller",[fix,other]),"pyinstaller","==6.22.3")["version"]=="6.22.3","HISTORICAL_PIN")
    refuse(lambda:choose(index(name,[{**high,"core-metadata":True},low]),name,""),"SIDECAR_HASH_UNAVAILABLE")
    refuse(lambda:choose(index(name,[{**high,"dist-info-metadata":{"sha256":"2"*64}}]),name,""),"SIDECAR_HASH_CONFLICT")
    refuse(lambda:choose(index(name,[{**high,"url":"https://evil.invalid/"+high["filename"]}]),name,""),"WHEEL_URL_REFUSED")
    refuse(lambda:choose(index(name,[{**high,"size":None}]),name,""),"WHEEL_SIZE_UNAVAILABLE")
    refuse(lambda:choose(index(name,[high,high]),name,""),"INDEX_FILENAME")
    refuse(lambda:choose(index(name,[linux]),name,""),"NO_COMPATIBLE_CANDIDATE")
    refuse(lambda:choose(index("other",[high]),"other",""),"PROJECT_SCOPE")
    c=Client(groups,ReplayConnection)
    refuse(lambda:c.get("index","https://pypi.org/simple/pandas/"),"REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda:c.get("metadata",high["url"]),"REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda:c.get("metadata",high["url"]+".metadata"),"REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda:Client(groups,http.client.HTTPSConnection),"OFFLINE_FIXTURE_ONLY")
    idx="https://pypi.org/simple/altgraph/"
    meta=low["url"]+".metadata"
    for response,reason in [(wire(b"x",(("Content-Type","text/html"),)),"CONTENT_TYPE_REFUSED"),
                            (wire(b"",(("Content-Length",str(MIB+1)),),length=False),"RESPONSE_LENGTH_REFUSED"),
                            (wire(b"wrong"),"SIDECAR_DIGEST_MISMATCH"),
                            (wire(b"x",status="302 Found"),"HTTP_STATUS_REFUSED"),
                            (wire(b"x",(("Content-Encoding","gzip"),)),"CONTENT_ENCODING_REFUSED")]:
        r,_,reqs=run({**replies,meta:response})
        check(r["failure"]==reason and len(reqs)==2 and r["verified"]==0,"TRANSPORT_"+reason)
    r,_,reqs=run({**replies,idx:wire(b"",(("Content-Type",INDEX_TYPE),("Content-Length",str(32*MIB+1))),length=False)})
    check(r["failure"]=="RESPONSE_LENGTH_REFUSED" and len(reqs)==1 and r["response_bytes"]==0,"INDEX_CAP")
    prior=os.environ.pop("C5_APPROVED_ONCE",None)
    try:
        refuse(authorize_live,"ONE_USE_CONTEXT_REQUIRED" if LIVE_ENABLED else "FRESH_APPROVAL_REQUIRED")
    finally:
        if prior is not None:
            os.environ["C5_APPROVED_ONCE"]=prior
    emit("FREEZER_REVIEW",{"status":"PASS","checks":count,"projects":6,"synthetic_requests":12,
                           "live_requests":0,"live_enabled":LIVE_ENABLED,"packaging":packaging_version})


if __name__=="__main__":
    if sys.argv[1:]==["--self-test"]:
        self_test()
    elif sys.argv[1:]==["--collect"]:
        try:
            raise SystemExit(live_collect())
        except Blocked as exc:
            emit("REFUSAL",{"reason":str(exc)})
            raise SystemExit(2)
    else:
        raise SystemExit(2)
