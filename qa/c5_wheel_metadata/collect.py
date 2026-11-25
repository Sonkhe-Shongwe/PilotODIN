"""C5 one-use wheel CORE metadata only. No wheel/archive requests, resolver or installs."""
import base64
import email.policy
from email.parser import BytesParser
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
MARKER = ROOT / "qa/c5_wheel_metadata/APPROVAL_20261125.txt"
MARKER_BYTES = b"C5-SELECTED-WHEEL-METADATA-ONCE-20261125\nOne hosted attempt; 50 index and 62 hash-advertised sidecars maximum.\n"
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
    def singleton(key, required=False):
        values = msg.get_all(key, [])
        require(len(values) <= 1 and (not required or len(values) == 1), "DUPLICATE_OR_MISSING_SINGLETON")
        return str(values[0]) if values else None
    name, version = singleton("Name", True), singleton("Version", True)
    require(normalized(name) == row["name"] and version == row["version"], "METADATA_IDENTITY")
    return {"metadata_version": singleton("Metadata-Version", True),
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


class Client:
    def __init__(self, groups, connection=http.client.HTTPSConnection):
        self.allowed = {"index": {"https://pypi.org/simple/" + n + "/" for n in groups},
                        "metadata": {w["url"] + ".metadata" for g in groups.values() for w in g}}
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
        deadline = time.monotonic() + 15
        success = False
        try:
            conn = self.connection(u.hostname, 443, timeout=15, context=ssl.create_default_context())
            accept = "application/vnd.pypi.simple.v1+json" if kind == "index" else "text/plain"
            conn.request("GET", u.path, headers={"Accept": accept, "Accept-Encoding": "identity",
                                                "User-Agent": "PilotODIN-C5-wheel-metadata-only/1"})
            response = conn.getresponse()
            status = response.status
            require(status == 200, "HTTP_STATUS_REFUSED")
            require(response.getheader("Content-Encoding", "identity").lower() == "identity",
                    "CONTENT_ENCODING_REFUSED")
            content_type = response.getheader("Content-Type", "").split(";")[0].strip().lower()
            require(content_type in ({"application/vnd.pypi.simple.v1+json"} if kind == "index"
                                    else {"text/plain", "application/octet-stream"}), "CONTENT_TYPE_REFUSED")
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
                             "response_sha256": digest.hexdigest(), "complete": success})


def self_test():
    groups = inventory()
    w = {"name": "fixture", "version": "1.2", "filename": "fixture-1.2-py3-none-any.whl",
         "url": "https://files.pythonhosted.org/packages/ab/cd/" + "0"*60 + "/fixture-1.2-py3-none-any.whl",
         "wheel_sha256": "1"*64, "wheel_bytes": 10}
    raw = b"Metadata-Version: 2.4\nName: fixture\nVersion: 1.2\nRequires-Dist: foo\nRequires-Dist: bar\n\nDescription\n"
    item = {"filename": w["filename"], "url": w["url"], "hashes": {"sha256": w["wheel_sha256"]},
            "yanked": False, "core-metadata": {"sha256": sha(raw)}}
    def idx(x):
        return selected_index(json.dumps({"name": "fixture", "files": [x]}).encode(), "fixture", [w])
    def refuse(fn, reason):
        try:
            fn()
        except Blocked as exc:
            require(str(exc) == reason, "SELF_TEST_WRONG_REFUSAL")
        else:
            raise Blocked("SELF_TEST_MISSING_REFUSAL")
    selected = idx(item)[0]
    require(metadata(raw, selected)["requires_dist"] == ["foo", "bar"], "SELF_TEST_PARSE")
    refuse(lambda: idx({**item, "core-metadata": True}), "SIDECAR_HASH_UNAVAILABLE")
    refuse(lambda: idx({**item, "dist-info-metadata": {"sha256": "2"*64}}), "SIDECAR_HASH_CONFLICT")
    refuse(lambda: idx({**item, "url": "https://foreign.invalid/a.whl"}), "INDEX_WHEEL_MISMATCH")
    refuse(lambda: idx({**item, "yanked": True}), "INDEX_WHEEL_MISMATCH")
    refuse(lambda: metadata(raw+b"x", selected), "SIDECAR_DIGEST_MISMATCH")
    duplicate = raw.replace(b"Name: fixture\n", b"Name: fixture\nName: fixture\n")
    refuse(lambda: metadata(duplicate, {**selected, "metadata_sha256": sha(duplicate)}),
           "DUPLICATE_OR_MISSING_SINGLETON")
    wrong = raw.replace(b"Version: 1.2", b"Version: 1.3")
    refuse(lambda: metadata(wrong, {**selected, "metadata_sha256": sha(wrong)}), "METADATA_IDENTITY")
    refuse(lambda: parse(b'{"x":1,"x":2}'), "DUPLICATE_JSON_KEY")
    class Never:
        def __init__(self, *a, **kw):
            raise Blocked("UNEXPECTED_NETWORK")
    client = Client({"fixture": [w]}, Never)
    refuse(lambda: client.get("metadata", w["url"]), "REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda: client.get("metadata", w["url"]+".metadata"), "REQUEST_SCOPE_OR_BUDGET")
    refuse(lambda: client.get("index", "https://foreign.invalid/"), "REQUEST_SCOPE_OR_BUDGET")
    client.total = TOTAL
    refuse(lambda: client.get("index", "https://pypi.org/simple/fixture/"), "REQUEST_SCOPE_OR_BUDGET")
    class Fake:
        sock = None
        def __init__(self, host, port, **kw):
            require(host == "pypi.org" and port == 443, "SELF_TEST_HOST")
        def request(self, method, path, headers):
            require(method == "GET" and path == "/simple/fixture/" and
                    headers["Accept-Encoding"] == "identity", "SELF_TEST_REQUEST")
        def getresponse(self):
            return type("Response", (), {"status": 302})()
        def close(self):
            pass
    refuse(lambda: Client({"fixture": [w]}, Fake).get("index", "https://pypi.org/simple/fixture/"),
           "HTTP_STATUS_REFUSED")
    emit("SELF_TEST", {"status": "PASS", "refusal_checks": 13, "projects": len(groups),
                       "wheels": sum(len(g) for g in groups.values()), "network_requests": 0})


def collect():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_EVENT_NAME") == "push"
            and os.environ.get("GITHUB_REF") == "refs/heads/feature/live-dev-workspace-20261023"
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
            and os.environ.get("GITHUB_WORKFLOW") == "C5 selected-wheel metadata one use"
            and os.environ.get("C5_APPROVED_ONCE") == "C5-SELECTED-WHEEL-METADATA-ONCE-20261125",
            "ONE_USE_CONTEXT_REQUIRED")
    require(MARKER.read_bytes() == MARKER_BYTES, "APPROVAL_MARKER_MISMATCH")
    groups = inventory()
    client = Client(groups)
    completed = []
    failure = None
    current = None
    try:
        for name, expected in groups.items():
            current = name
            index_raw = client.get("index", "https://pypi.org/simple/" + name + "/")
            selected = selected_index(index_raw, name, expected)
            emit("INDEX", {"name": name, "response_sha256": sha(index_raw), "selected": selected})
            client.authorize_sidecars(selected)
            for row in selected:
                current = row["filename"]
                raw = client.get("metadata", row["metadata_url"])
                parsed = metadata(raw, row)
                # Preserve exact verified bytes in bounded log chunks; no index body or unrelated artifact.
                encoded = base64.b64encode(raw).decode("ascii")
                for offset in range(0, len(encoded), 8192):
                    emit("BYTES", {"filename": current, "offset": offset, "base64": encoded[offset:offset+8192]})
                emit("VERIFIED", {"filename": current, "metadata_sha256": sha(raw), "bytes": len(raw),
                                  "declarations": parsed})
                completed.append(current)
    except (Blocked, OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as exc:
        failure = str(exc) if type(exc) is Blocked else type(exc).__name__
    missing = sorted(w["filename"] for g in groups.values() for w in g if w["filename"] not in completed)
    result = {"source_sha": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID"),
              "run_attempt": 1, "requests": client.counts, "response_bytes": client.total,
              "verified": len(completed), "missing": missing, "failure": failure,
              "last_identity": current, "artifact_requests": 0,
              "status": "METADATA_ONLY_COMPLETE" if not missing and failure is None else "BLOCKED"}
    emit("RESULT", result)
    return 0 if result["status"] == "METADATA_ONLY_COMPLETE" else 2


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--self-test"]:
            self_test()
            raise SystemExit(0)
        require(sys.argv[1:] == ["--collect"], "EXPLICIT_MODE_REQUIRED")
        raise SystemExit(collect())
    except (Blocked, OSError, ValueError, KeyError, TypeError) as exc:
        emit("REFUSAL", {"reason": str(exc) if type(exc) is Blocked else type(exc).__name__})
        raise SystemExit(2)
