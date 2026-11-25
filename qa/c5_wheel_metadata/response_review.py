"""Offline-only candidate response contract. No live collector or approval interface."""
import base64
import email.policy
from email.parser import BytesParser
import hashlib
import http.client
import json
import io
from pathlib import Path
import re
import ssl
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
LIMITS = {"index": (50, 8 * MIB), "metadata": (62, MIB)}


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


def inventory():
    raw = read_pin(RECEIPT)
    require(sha(raw) == RECEIPT_SHA, "RECEIPT_PIN")
    rows = {}
    for line in raw.splitlines():
        r = parse(line)
        k = (r["name"], r["version"])
        require(k not in rows and r["status"] == "RELEASE_JSON_OBSERVED", "RELEASE_IDENTITY")
        rows[k] = r
    require(len(rows) == 50 and len({k[0] for k in rows}) == 50, "RELEASE_COUNT")
    raw = read_pin(OBSERVED)
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    require(blob == OBSERVED_BLOB, "OBSERVED_PIN")
    groups = {}
    total = 0
    profiles = parse(raw)["profiles"]
    require(len(profiles) == 2 and {p["profile"] for p in profiles} ==
            {"windows-x64-cp311-source-test", "linux-x64-cp311-source-test"}, "PROFILE_SET")
    for p in profiles:
        require(p["status"] == "OBSERVED_ONLY_BLOCKED" and len(p["selected_wheels"]) == 49,
                "PROFILE_SCOPE")
        seen = set()
        for w in p["selected_wheels"]:
            name, version, filename = w["name"], w["version"], w["filename"]
            require(NAME.fullmatch(name) and FILENAME.fullmatch(filename)
                    and name not in seen, "SELECTED_IDENTITY")
            seen.add(name)
            candidates = [x for x in rows[(name, version)]["selected_wheels"] if x["filename"] == filename]
            require(len(candidates) == 1, "RECEIPT_MATCH")
            item = candidates[0]
            u = urlsplit(item["url"])
            require(u.scheme == "https" and u.netloc == "files.pythonhosted.org"
                    and not u.query and not u.fragment and re.fullmatch(
                        r"/packages/[a-f0-9]{2}/[a-f0-9]{2}/[a-f0-9]{60}/" + re.escape(filename), u.path)
                    and HEX.fullmatch(item["sha256"]) and item["yanked"] is False
                    and type(item["bytes"]) is int and item["bytes"] > 0, "RECEIPT_WHEEL_INVALID")
            row = {"name": name, "version": version, "filename": filename, "url": item["url"],
                   "wheel_sha256": item["sha256"], "wheel_bytes": item["bytes"]}
            bucket = groups.setdefault(name, {})
            require(filename not in bucket or bucket[filename] == row, "DUPLICATE_IDENTITY_CONFLICT")
            bucket[filename] = row
            total += 1
    require(total == 98 and len(groups) == 50
            and sum(len(x) for x in groups.values()) == 62, "ALLOWLIST_COUNT")
    return {name: list(sorted(bucket.values(), key=lambda w: w["filename"]))
            for name, bucket in sorted(groups.items())}


def selected_index(raw, name, expected):
    doc = parse(raw)
    require(normalized(doc["name"]) == name and type(doc["files"]) is list, "INDEX_IDENTITY")
    selected = []
    for w in expected:
        found = [x for x in doc["files"] if x.get("filename") == w["filename"]]
        require(len(found) == 1, "INDEX_MISSING_OR_DUPLICATE")
        x = found[0]
        require(x["url"] == w["url"] and x["hashes"]["sha256"] == w["wheel_sha256"]
                and x.get("yanked") is False
                and ("size" not in x or (type(x["size"]) is int and x["size"] == w["wheel_bytes"])),
                "INDEX_WHEEL_MISMATCH")
        values = [x[k] for k in ("core-metadata", "dist-info-metadata") if k in x]
        require(values and all(type(v) is dict and type(v.get("sha256")) is str
                               and HEX.fullmatch(v["sha256"]) for v in values),
                "SIDECAR_HASH_UNAVAILABLE")
        require(all(v["sha256"] == values[0]["sha256"] for v in values), "SIDECAR_HASH_CONFLICT")
        selected.append({**w, "metadata_url": w["url"] + ".metadata",
                         "metadata_sha256": values[0]["sha256"],
                         "index_requires_python": x.get("requires-python")})
    return selected


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


MEDIA = re.compile(r"[a-z0-9!#class Client:
    def __init__(self, groups, connection=http.client.HTTPSConnection):^_.+-]+/[a-z0-9!#class Client:
    def __init__(self, groups, connection=http.client.HTTPSConnection):^_.+-]+")
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


class Client:
    def __init__(self, groups, connection):
        self.allowed = {"index": {"https://pypi.org/simple/" + n + "/" for n in groups},
                        "metadata": {w["url"] + ".metadata" for g in groups.values() for w in g}}
        require(connection is FixtureConnection or connection is Never, "OFFLINE_FIXTURE_ONLY")
        self.connection = connection
        self.counts = {"index": 0, "metadata": 0}
        self.total = 0
        self.seen = set()
        self.enabled = set()

    def authorize_sidecars(self, selected):
        for w in selected:
            require(w["metadata_url"] in self.allowed["metadata"] and HEX.fullmatch(w["metadata_sha256"]),
                    "SIDECAR_NOT_ALLOWLISTED")
            self.enabled.add(w["metadata_url"])

    def get(self, kind, url):
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
        deadline = time.monotonic() + 15
        success = False
        try:
            conn = self.connection(u.hostname, 443, timeout=15, context=ssl.create_default_context())
            accept = "application/vnd.pypi.simple.v1+json" if kind == "index" else "text/plain, application/octet-stream, */*;q=0.1"
            conn.request("GET", u.path, headers={"Accept": accept, "Accept-Encoding": "identity",
                                                "User-Agent": "PilotODIN-C5-wheel-metadata-only/1"})
            response = conn.getresponse()
            status = response.status
            content_type = media_type(response.getheader("Content-Type"))
            require(status == 200, "HTTP_STATUS_REFUSED")
            require(response.getheader("Content-Encoding", "identity").lower() == "identity",
                    "CONTENT_ENCODING_REFUSED")
            require(media_allowed(kind, content_type), "CONTENT_TYPE_REFUSED")
            length = response.getheader("Content-Length")
            remaining = min(cap, TOTAL - self.total)
            if length is not None:
                require(length.isdigit() and 0 < int(length) <= remaining, "RESPONSE_LENGTH_REFUSED")
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
                             "content_type": content_type, "fixture": True})


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


def self_test():
    groups = inventory()
    w = {"name": "fixture", "version": "1.2", "filename": "fixture-1.2-py3-none-any.whl",
         "url": "https://files.pythonhosted.org/packages/ab/cd/" + "0"*60 + "/fixture-1.2-py3-none-any.whl",
         "wheel_sha256": "1"*64, "wheel_bytes": 10}
    raw = b"Metadata-Version: 2.4\nName: fixture\nVersion: 1.2\nRequires-Dist: foo\nRequires-Dist: bar\n\nDescription\n"
    item = {"filename": w["filename"], "url": w["url"], "hashes": {"sha256": w["wheel_sha256"]},
            "yanked": False, "core-metadata": {"sha256": sha(raw)}}
    index_url = "https://pypi.org/simple/fixture/"
    meta_url = w["url"] + ".metadata"
    index_raw = json.dumps({"name": "fixture", "files": [item]}).encode()
    selected = selected_index(index_raw, "fixture", [w])[0]
    passed = {"positive": 0, "negative": 0}
    def positive(ok):
        require(ok, "SELF_TEST_POSITIVE")
        passed["positive"] += 1
    def refuse(fn, reason):
        try:
            fn()
        except Blocked as exc:
            require(str(exc) == reason, "SELF_TEST_WRONG_REFUSAL")
        else:
            raise Blocked("SELF_TEST_MISSING_REFUSAL")
        passed["negative"] += 1
    def client():
        return Client({"fixture": [w]}, FixtureConnection)
    def setup(url, headers, data, status=200):
        u = urlsplit(url)
        FixtureConnection.expected = (u.hostname, u.path)
        FixtureConnection.fixture = FixtureResponse(status, headers, data)
    def sidecar(headers, data=raw, status=200, total=0):
        c = client()
        c.authorize_sidecars([selected])
        c.total = total
        setup(meta_url, headers, data, status)
        return c.get("metadata", meta_url)
    c = client()
    setup(index_url, {"Content-Type": INDEX_TYPE, "Content-Length": str(len(index_raw))}, index_raw)
    positive(selected_index(c.get("index", index_url), "fixture", [w]) == [selected])
    for ct in ["text/plain; charset=UTF-8", "application/octet-stream", "binary/octet-stream",
               "application/x-octet-stream", None]:
        headers = {"Content-Length": str(len(raw))}
        if ct is not None:
            headers["Content-Type"] = ct
        positive(metadata(sidecar(headers), selected)["requires_dist"] == ["foo", "bar"])
    positive(metadata(sidecar({"Content-Type": "text/plain"}), selected)["name"] == "fixture")
    for ct in ["text/html", "application/json", "application/zip", "application/vnd.unknown",
               "text/plain\r\nInjected: secret", "", "a"*257, "text/plain, text/plain"]:
        refuse(lambda ct=ct: sidecar({"Content-Type": ct}), "CONTENT_TYPE_REFUSED")
    refuse(lambda: sidecar({"Content-Encoding": "gzip"}), "CONTENT_ENCODING_REFUSED")
    refuse(lambda: sidecar({"Content-Length": str(MIB+1)}), "RESPONSE_LENGTH_REFUSED")
    refuse(lambda: sidecar({"Content-Length": str(len(raw)+1)}), "INCOMPLETE_BODY")
    refuse(lambda: sidecar({}, b""), "INCOMPLETE_BODY")
    refuse(lambda: sidecar({}, b"x"*(MIB+1)), "RESPONSE_BUDGET_REACHED")
    refuse(lambda: sidecar({}, raw, total=TOTAL-1), "RESPONSE_BUDGET_REACHED")
    refuse(lambda: sidecar({}, status=302), "HTTP_STATUS_REFUSED")
    refuse(lambda: metadata(sidecar({}, raw+b"x"), selected), "SIDECAR_DIGEST_MISMATCH")
    duplicate = raw.replace(b"Name: fixture\n", b"Name: fixture\nName: fixture\n")
    refuse(lambda: metadata(duplicate, {**selected, "metadata_sha256": sha(duplicate)}),
           "DUPLICATE_OR_MISSING_SINGLETON")
    wrong = raw.replace(b"Version: 1.2", b"Version: 1.3")
    refuse(lambda: metadata(wrong, {**selected, "metadata_sha256": sha(wrong)}), "METADATA_IDENTITY")
    newer = raw.replace(b"Metadata-Version: 2.4", b"Metadata-Version: 3.0")
    refuse(lambda: metadata(newer, {**selected, "metadata_sha256": sha(newer)}),
           "METADATA_VERSION_UNSUPPORTED")
    c = client()
    refuse(lambda: c.get("metadata", meta_url), "REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda: c.get("metadata", w["url"]), "REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda: c.get("index", "https://foreign.invalid/"), "REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda: Client({"fixture": [w]}, http.client.HTTPSConnection), "OFFLINE_FIXTURE_ONLY")
    setup(index_url, {"Content-Type": "application/json"}, index_raw)
    refuse(lambda: client().get("index", index_url), "CONTENT_TYPE_REFUSED")
    setup(index_url, {}, index_raw)
    refuse(lambda: client().get("index", index_url), "CONTENT_TYPE_REFUSED")
    setup(index_url, {"Content-Type": INDEX_TYPE}, index_raw)
    c.get("index", index_url)
    refuse(lambda: c.get("index", index_url), "REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda: parse(b'{"x":1,"x":2}'), "DUPLICATE_JSON_KEY")
    emit("RESPONSE_REVIEW", {**passed, "projects": len(groups),
                             "wheels": sum(len(g) for g in groups.values()),
                             "live_requests": 0, "status": "PASS"})


if __name__ == "__main__":
    if sys.argv[1:] != ["--self-test"]:
        raise SystemExit(2)
    self_test()
