"""Offline receipt and graph review; no collection, installer or lock interface."""
import base64
import email.policy
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import sys
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


PARTIAL_PREFIX = "qa/c5_wheel_metadata/v2_receipt_45700172241"
PARTIAL_MANIFEST_BLOB = "4f70c27c472fc993e6f2ce31e4334f05ee70810b"
PARTIAL_DIGEST = "bc229d6dcd0b9f9147275563e5d802aef44683f1639a1e7188c76184b7ea5bc9"


def canonical(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":")).encode("ascii") + b"\n"


def missing_inventory():
    # Derive a disjoint exact scope from both original pins and the persisted
    # manifest/shards; any drift blocks before a transport can be constructed.
    full = inventory()
    expected = {w["filename"]: w for rows in full.values() for w in rows}
    raw = read_pin(PARTIAL_PREFIX + "/manifest.json")
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    require(blob == PARTIAL_MANIFEST_BLOB, "PARTIAL_MANIFEST_PIN")
    manifest = parse(raw)
    require(manifest["run_id"] == "45700172241"
            and manifest["source_sha"] == "e0787864f6d95a8e20dd79c811a3000f82ad0e89"
            and manifest["receipt_sha256"] == PARTIAL_DIGEST
            and len(manifest["parts"]) == 6 and manifest["records"] == 239, "PARTIAL_MANIFEST")
    records = []
    for i, part in enumerate(manifest["parts"], 1):
        path = f"{PARTIAL_PREFIX}/part-{i:02d}.jsonl"
        require(part["path"] == path, "PARTIAL_SHARD_PATH")
        raw = read_pin(path)
        require(len(raw) == part["bytes"] and sha(raw) == part["sha256"], "PARTIAL_SHARD_PIN")
        records.extend(parse(line) for line in raw.splitlines())
    return reconcile(full, records)


def reconcile(full, records):
    expected = {w["filename"]: w for rows in full.values() for w in rows}
    require(len(records) == 239 and records[-1]["kind"] == "RESULT", "PARTIAL_RECORD_COUNT")
    requests = {}
    selected = {}
    completed_projects = set()
    chunks = {}
    verified = {}
    digest = hashlib.sha256()
    counts = {}
    for wrapper in records[:-1]:
        kind, row = wrapper["kind"], wrapper["record"]
        counts[kind] = counts.get(kind, 0) + 1
        require(kind in {"REQUEST", "INDEX", "BYTES", "VERIFIED"}, "PARTIAL_KIND")
        if kind != "REQUEST":
            digest.update(canonical(wrapper))
        if kind == "REQUEST":
            url = row["url"]
            require(row["fixture"] is False and url not in requests and row["http_status"] == 200
                    and type(row["bytes"]) is int and row["bytes"] >= 0
                    and HEX.fullmatch(row["response_sha256"]), "PARTIAL_REQUEST")
            requests[url] = row
        elif kind == "INDEX":
            name = row["name"]
            req = requests.get("https://pypi.org/simple/" + name + "/", {})
            require(name in full and name not in completed_projects and req.get("complete") is True
                    and req.get("kind") == "index" and req.get("response_sha256") == row["response_sha256"]
                    and {w["filename"] for w in row["selected"]} == {w["filename"] for w in full[name]}
                    and len(row["selected"]) == len(full[name]), "PARTIAL_INDEX")
            completed_projects.add(name)
            for w in row["selected"]:
                fname = w["filename"]
                require(fname in expected and fname not in selected
                        and all(w[k] == v for k, v in expected[fname].items())
                        and w["metadata_url"] == w["url"] + ".metadata"
                        and HEX.fullmatch(w["metadata_sha256"]), "PARTIAL_SELECTED_IDENTITY")
                selected[fname] = w
        elif kind == "BYTES":
            name = row["filename"]
            require(name in selected and name not in verified and type(row["base64"]) is str
                    and 0 < len(row["base64"]) <= 8192, "PARTIAL_CHUNK")
            prev = chunks.get(name, "")
            require(row["offset"] == len(prev), "PARTIAL_OFFSET")
            chunks[name] = prev + row["base64"]
            require(len(chunks[name]) <= 4 * ((MIB+2)//3), "PARTIAL_METADATA_CAP")
        elif kind == "VERIFIED":
            name = row["filename"]
            require(name in chunks and name not in verified, "PARTIAL_VERIFIED")
            w = selected[name]
            raw = base64.b64decode(chunks[name], validate=True)
            req = requests.get(w["metadata_url"], {})
            require(0 < len(raw) <= MIB and len(raw) == row["bytes"] == req.get("bytes")
                    and sha(raw) == w["metadata_sha256"] == row["metadata_sha256"] == req.get("response_sha256")
                    and req.get("complete") is True and req.get("kind") == "metadata"
                    and metadata(raw, w) == row["declarations"], "PARTIAL_METADATA_MISMATCH")
            verified[name] = row
    terminal = records[-1]["record"]
    require(counts == {"REQUEST":62,"INDEX":28,"BYTES":115,"VERIFIED":33}
            and set(selected) == set(chunks) == set(verified)
            and digest.hexdigest() == PARTIAL_DIGEST == terminal["receipt_sha256"]
            and terminal["run_id"] == "45700172241" and terminal["run_attempt"] == 1
            and terminal["source_sha"] == "e0787864f6d95a8e20dd79c811a3000f82ad0e89"
            and terminal["fixture"] is False and terminal["status"] == "BLOCKED"
            and terminal["failure"] == "RESPONSE_LENGTH_REFUSED"
            and terminal["artifact_requests"] == 0 and terminal["verified"] == 33
            and terminal["requests"] == {"index":29,"metadata":33}
            and terminal["response_bytes"] == 12867486 == sum(r["bytes"] for r in requests.values()),
            "PARTIAL_TERMINAL")
    failed = "https://pypi.org/simple/pydantic-core/"
    require(set(requests) == {"https://pypi.org/simple/" + n + "/" for n in completed_projects}
            | {w["metadata_url"] for w in selected.values()} | {failed}
            and requests[failed]["complete"] is False and requests[failed]["bytes"] == 0,
            "PARTIAL_REQUEST_SCOPE")
    missing = set(expected) - set(verified)
    groups = {n: [w for w in rows if w["filename"] in missing] for n, rows in full.items()}
    groups = {n: rows for n, rows in groups.items() if rows}
    require(len(groups) == 22 and len(missing) == 29
            and sorted(missing) == terminal["missing"]
            and not set(groups) & completed_projects, "MISSING_SCOPE")
    return groups, verified


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



from packaging import __version__ as packaging_version
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import cpython_tags, compatible_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

NEW_PREFIX = "qa/c5_wheel_metadata/missing_receipt_45701493997"
NEW_BLOB = "b83b914e806d34c40176a8788de20accf21f5b25"
NEW_DIGEST = "4f4781d266234e9aa83cca2a9597b915d6bfe2ddfc18a45229531742db474f22"
ROOT_PINS = {"backend/requirements.txt":"30d347462aa29b4db9c7308079f231185f4c1703",
             "backend/requirements-test.txt":"0ed0b88920a281167cf1dc8a3ca038096bf1e7b8"}
TARGETS = {"windows-x64-cp311-source-test":("3.11.9","win32"),
           "linux-x64-cp311-source-test":("3.11.18","linux")}


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def new_receipt(groups):
    raw = read_pin(NEW_PREFIX + "/manifest.json")
    require(git_blob(raw) == NEW_BLOB, "NEW_MANIFEST_PIN")
    m = parse(raw)
    require(m["run_id"] == "45701493997" and m["receipt_sha256"] == NEW_DIGEST
            and m["records"] == 181 and len(m["parts"]) == 5, "NEW_MANIFEST")
    records = []
    for i, part in enumerate(m["parts"], 1):
        path = f"{NEW_PREFIX}/part-{i:02d}.jsonl"
        require(part["path"] == path, "NEW_SHARD_PATH")
        raw = read_pin(path)
        require(len(raw) == part["bytes"] and sha(raw) == part["sha256"], "NEW_SHARD_PIN")
        records.extend(parse(line) for line in raw.splitlines())
    return verify_new(groups, records)


def verify_new(groups, records):
    expected = {w["filename"]: w for rows in groups.values() for w in rows}
    require(len(records) == 181 and records[-1]["kind"] == "RESULT", "NEW_RECORDS")
    reqs, selected, buffers, verified, seen_projects = {}, {}, {}, {}, set()
    digest = hashlib.sha256()
    for wrapper in records[:-1]:
        kind, row = wrapper["kind"], wrapper["record"]
        require(kind in {"REQUEST","INDEX","BYTES","VERIFIED"}, "NEW_RECORD_KIND")
        if kind != "REQUEST":
            digest.update(canonical(wrapper))
        if kind == "REQUEST":
            url = row["url"]
            cap = {"index":32*MIB,"metadata":MIB}[row["kind"]]
            require(url not in reqs and row["fixture"] is False and row["complete"] is True
                    and row["http_status"] == 200 and type(row["bytes"]) is int
                    and 0 < row["bytes"] <= cap == row["response_cap_bytes"]
                    and HEX.fullmatch(row["response_sha256"]), "NEW_REQUEST")
            reqs[url] = row
        elif kind == "INDEX":
            name = row["name"]
            req = reqs.get("https://pypi.org/simple/"+name+"/", {})
            require(name in groups and name not in seen_projects and req.get("kind") == "index"
                    and req.get("response_sha256") == row["response_sha256"]
                    and len(row["selected"]) == len(groups[name])
                    and {w["filename"] for w in row["selected"]} == {w["filename"] for w in groups[name]},
                    "NEW_INDEX")
            seen_projects.add(name)
            for w in row["selected"]:
                n = w["filename"]
                require(n not in selected and n in expected and
                        all(w[k] == v for k,v in expected[n].items()) and
                        w["metadata_url"] == w["url"]+".metadata" and HEX.fullmatch(w["metadata_sha256"]),
                        "NEW_IDENTITY")
                selected[n] = w
        elif kind == "BYTES":
            n = row["filename"]
            prior = buffers.get(n,"")
            require(n in selected and n not in verified and row["offset"] == len(prior)
                    and type(row["base64"]) is str and 0 < len(row["base64"]) <= 8192,
                    "NEW_CHUNK")
            buffers[n] = prior + row["base64"]
            require(len(buffers[n]) <= 4*((MIB+2)//3), "NEW_CHUNK_CAP")
        else:
            n = row["filename"]
            require(n not in verified and n in buffers, "NEW_VERIFIED")
            raw = base64.b64decode(buffers[n], validate=True)
            w = selected[n]
            req = reqs.get(w["metadata_url"],{})
            require(req.get("kind") == "metadata" and 0 < len(raw) <= MIB
                    and len(raw) == row["bytes"] == req.get("bytes")
                    and sha(raw) == w["metadata_sha256"] == row["metadata_sha256"] == req.get("response_sha256")
                    and metadata(raw,w) == row["declarations"], "NEW_METADATA")
            verified[n] = row
    terminal = records[-1]["record"]
    require(set(expected) == set(selected) == set(buffers) == set(verified)
            and seen_projects == set(groups) and len(groups) == 22 and len(verified) == 29
            and set(reqs) == {"https://pypi.org/simple/"+n+"/" for n in groups}
              | {w["metadata_url"] for w in selected.values()}
            and len(reqs) == 51 and digest.hexdigest() == NEW_DIGEST == terminal["receipt_sha256"]
            and terminal["run_id"] == "45701493997" and terminal["run_attempt"] == 1
            and terminal["source_sha"] == "cb71f2b3ac937eaa88677489e74dce6bfe775bb8"
            and terminal["fixture"] is False and terminal["status"] == "METADATA_ONLY_COMPLETE"
            and terminal["failure"] is None and terminal["missing"] == []
            and terminal["artifact_requests"] == 0 and terminal["verified"] == 29
            and terminal["prior_verified"] == 33 and terminal["combined_verified"] == 62
            and terminal["requests"] == {"index":22,"metadata":29}
            and terminal["response_bytes"] == 21089670 == sum(r["bytes"] for r in reqs.values()),
            "NEW_TERMINAL")
    return verified


def roots():
    result = []
    for path, pin in ROOT_PINS.items():
        raw = read_pin(path)
        require(git_blob(raw) == pin,"ROOT_PIN")
        group = []
        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or (path.endswith("-test.txt") and line == "-r requirements.txt"):
                continue
            r = Requirement(line)
            require(not r.url and r.marker is None, "ROOT_REQUIREMENT")
            group.append(r)
        result.append(group)
    require([len(x) for x in result] == [10,4],"ROOT_COUNT")
    return result[0], result[0]+result[1]


def environment(python, platform):
    return {"implementation_name":"cpython","implementation_version":python,
            "python_full_version":python,"python_version":"3.11",
            "platform_python_implementation":"CPython","sys_platform":platform,
            "os_name":"nt" if platform=="win32" else "posix",
            "platform_system":"Windows" if platform=="win32" else "Linux",
            "platform_machine":"AMD64" if platform=="win32" else "x86_64",
            "platform_release":"","platform_version":"","extra":""}


def candidate_tags(platform):
    platforms = ["win_amd64"] if platform == "win32" else (
        [f"manylinux_2_{n}_x86_64" for n in range(28,4,-1)]
        + ["manylinux2014_x86_64","manylinux2010_x86_64","manylinux1_x86_64"])
    return set(cpython_tags((3,11),abis=["cp311"],platforms=platforms)) | set(
        compatible_tags((3,11),interpreter="cp311",platforms=platforms))


def marker_active(req, env, extras):
    if req.marker is None:
        return True
    unquoted = re.sub(r'"[^"]*"|\'[^\']*\'',"",str(req.marker))
    require(not set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*",unquoted)) &
            {"platform_release","platform_version","extras","dependency_groups"},"UNKNOWN_MARKER")
    return any(req.marker.evaluate(environment={**env,"extra":x}) for x in sorted(set(extras)|{""}))


def graph(profile, verified, root_requirements, label):
    pid = profile["profile"]
    python, platform = TARGETS[pid]
    require(profile["observed_cpython"] == python and profile["platform"] == platform
            and profile["architecture"] == "x64" and len(profile["selected_wheels"]) == 49,"TARGET")
    env, tags = environment(python,platform), candidate_tags(platform)
    selected = {}
    issues = set()
    unknown_python = []
    for w in profile["selected_wheels"]:
        name, version, filename = w["name"], w["version"], w["filename"]
        d = verified[filename]["declarations"]
        require(name not in selected and canonicalize_name(d["name"]) == name and d["version"] == version,
                "PROFILE_IDENTITY")
        pn,pv,_,ptags = parse_wheel_filename(filename)
        require(pn == name and pv == Version(version),"WHEEL_IDENTITY")
        selected[name] = {"version":version,"filename":filename,"d":d,"tag_ok":bool(tags & ptags)}
    extras = {}
    def add(req, source):
        name = canonicalize_name(req.name)
        if req.url or name not in selected:
            issues.add((source,str(req),"DIRECT_URL" if req.url else "MISSING"))
            return False
        if not req.specifier.contains(Version(selected[name]["version"])):
            issues.add((source,str(req),"VERSION_CONFLICT"))
        wanted = {canonicalize_name(x) for x in req.extras}
        offered = {canonicalize_name(x) for x in selected[name]["d"]["provides_extra"]}
        if wanted - offered:
            issues.add((source,str(req),"EXTRA_NOT_PROVIDED"))
        changed = name not in extras or not wanted <= extras.get(name,set())
        extras.setdefault(name,set()).update(wanted)
        return changed
    for req in root_requirements:
        add(req,"ROOT")
    for _ in range(len(selected)*4):
        changed = False
        for name in sorted(extras):
            for declaration in selected[name]["d"]["requires_dist"]:
                req = Requirement(declaration)
                if marker_active(req,env,extras[name]):
                    changed = add(req,name) or changed
        if not changed:
            break
    else:
        raise Blocked("FIXED_POINT_LIMIT")
    edges, inactive = [], 0
    for name in sorted(extras):
        row = selected[name]
        declared = row["d"]["requires_python"]
        if declared is None:
            unknown_python.append(name)
        elif not SpecifierSet(declared).contains(Version(python)):
            issues.add((name,declared,"PYTHON_CONFLICT"))
        if not row["tag_ok"]:
            issues.add((name,row["filename"],"TAG_CONFLICT"))
        for declaration in row["d"]["requires_dist"]:
            req = Requirement(declaration)
            if marker_active(req,env,extras[name]):
                edges.append({"from":name,"to":canonicalize_name(req.name),"requirement":declaration})
            else:
                inactive += 1
    unused = sorted(set(selected)-set(extras))
    if label == "source-test" and unused:
        issues.add(("PROFILE",",".join(unused),"UNEXPLAINED_SELECTED"))
    return {"profile":pid,"scope":label,"python":python,"roots":len(root_requirements),
            "reachable":len(extras),"active_edges":len(edges),"inactive":inactive,
            "extras":{k:sorted(v) for k,v in sorted(extras.items()) if v},
            "unknown_python":sorted(unknown_python),"unused_selected":unused,
            "issues":[{"source":a,"requirement":b,"reason":c} for a,b,c in sorted(issues)],
            "graph_status":"DECLARED_GRAPH_COMPATIBLE" if not issues else "GRAPH_BLOCKED",
            "profile_status":"BLOCKED",
            "edges":edges,"nodes":[{"name":n,"filename":selected[n]["filename"],
                                  "version":selected[n]["version"]} for n in sorted(extras)]}


def controls():
    e = environment("3.11.9","win32")
    require(marker_active(Requirement('a; sys_platform == "win32"'),e,[]),"TEST_WINDOWS")
    require(not marker_active(Requirement('a; sys_platform == "linux"'),e,[]),"TEST_LINUX")
    require(marker_active(Requirement('a; extra == "standard"'),e,["standard"]),"TEST_EXTRA")
    require(not marker_active(Requirement('a; extra == "standard"'),e,[]),"TEST_NO_EXTRA")
    try:
        marker_active(Requirement('a; platform_release == "x"'),e,[])
    except Blocked:
        pass
    else:
        raise Blocked("TEST_UNKNOWN_MARKER")
    require(not SpecifierSet(">=3.12").contains(Version("3.11.9")),"TEST_VERSION")
    require(bool(candidate_tags("win32") & parse_wheel_filename("a-1-cp311-cp311-win_amd64.whl")[3]),
            "TEST_TAG")
    require(not candidate_tags("win32") & parse_wheel_filename("a-1-cp311-cp311-manylinux_2_28_x86_64.whl")[3],
            "TEST_WRONG_TAG")
    return 8


def main():
    require(sys.argv[1:] == ["--review"],"REVIEW_ONLY")
    groups, prior = missing_inventory()
    new = new_receipt(groups)
    all_rows = inventory()
    verified = {**prior,**new}
    require(not set(prior)&set(new) and len(verified)==62
            and set(verified)=={w["filename"] for g in all_rows.values() for w in g},"COMBINED_COVERAGE")
    runtime,test = roots()
    inv = parse(read_pin(OBSERVED))
    checks = controls()
    reports = [graph(p,verified,r,label) for p in inv["profiles"]
               for r,label in [(test,"source-test"),(runtime,"runtime-root-subset")]]
    for p in reports:
        print("C5_GRAPH_FULL "+json.dumps(p,sort_keys=True,ensure_ascii=True),flush=True)
        print("C5_GRAPH_SUMMARY "+json.dumps({k:v for k,v in p.items() if k not in {"edges","nodes"}},
                                             sort_keys=True),flush=True)
    print("C5_COMBINED_GRAPH "+json.dumps({"status":"REVIEW_COMPLETE","verified":len(verified),
          "prior":len(prior),"new":len(new),"controls":checks,"packaging":packaging_version,
          "live_requests":0,"profiles_blocked":4},sort_keys=True),flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("C5_COMBINED_REVIEW_BLOCKED: "+(str(exc) if type(exc) is Blocked else type(exc).__name__),
              file=sys.stderr)
        raise SystemExit(2)
