"""One-use C5 public release JSON collection. No artifact downloads or installs."""
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "contracts/c5_observed_python_wheels_2026-11-25.json"
EXPECTED_BLOB = "6ccd3d47efe363ecf87fd13ce7d867cba4bef020"
MARKER = ROOT / "qa/c5_metadata/APPROVAL_20261125.txt"
MARKER_BYTES = b"C5-PYPI-METADATA-ONCE-20261125\nApproved: one exact hosted release JSON metadata collection; no artifact bytes.\n"
MAX_RESPONSE = 2 * 1024 * 1024
MAX_PAIRS = 50
HEX64 = re.compile(r"[0-9a-f]{64}")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VERSION = re.compile(r"[0-9][A-Za-z0-9_.+!]{0,127}")
FILENAME = re.compile(r"[A-Za-z0-9_.+!-]{1,235}\.whl")


class Refusal(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def normalized_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal("NONFINITE_JSON")))


def exact_inventory():
    raw = INVENTORY.read_bytes()
    digest = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    require(digest == EXPECTED_BLOB, "INVENTORY_PIN_MISMATCH")
    doc = parse(raw)
    require(len(doc["profiles"]) == 2, "PROFILE_COUNT")
    pairs = {}
    total = 0
    for profile in doc["profiles"]:
        require(profile["status"] == "OBSERVED_ONLY_BLOCKED"
                and len(profile["selected_wheels"]) == 49, "PROFILE_SCOPE")
        for row in profile["selected_wheels"]:
            name, version, filename = row["name"], row["version"], row["filename"]
            require(NAME.fullmatch(name) and VERSION.fullmatch(version)
                    and FILENAME.fullmatch(filename), "UNSAFE_INVENTORY_ROW")
            pairs.setdefault((name, version), set()).add(filename)
            total += 1
    require(total == 98 and len(pairs) == MAX_PAIRS, "PAIR_COUNT")
    return pairs


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refusal("REDIRECT_REFUSED")


def build_opener():
    # Explicitly disable ambient proxy configuration; standard TLS verification.
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def fetch_release(opener, name, version):
    require(NAME.fullmatch(name) and VERSION.fullmatch(version), "REQUEST_SCOPE")
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    request = urllib.request.Request(url, method="GET", headers={
        "Accept": "application/json", "Accept-Encoding": "identity",
        "User-Agent": "PilotODIN-C5-metadata-only/1",
    })
    with opener.open(request, timeout=10) as response:
        require(response.status == 200 and response.geturl() == url,
                "UNEXPECTED_RESPONSE")
        require(response.headers.get_content_type() == "application/json"
                and response.headers.get("Content-Encoding", "identity").lower() == "identity",
                "NON_JSON_RESPONSE")
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            require(content_length.isdigit() and int(content_length) <= MAX_RESPONSE,
                    "RESPONSE_TOO_LARGE")
        raw = response.read(MAX_RESPONSE + 1)
        require(0 < len(raw) <= MAX_RESPONSE, "RESPONSE_SIZE")
    return parse(raw), len(raw), hashlib.sha256(raw).hexdigest()


def short(value, maximum=4096):
    require(value is None or (type(value) is str and len(value) <= maximum),
            "METADATA_FIELD_INVALID")
    return value


def string_list(value, count=512, width=2048):
    if value is None:
        return None
    require(type(value) is list and len(value) <= count
            and all(type(x) is str and len(x) <= width for x in value),
            "METADATA_LIST_INVALID")
    return value


def release_row(doc, name, version, filenames):
    info = doc["info"]
    require(normalized_name(info["name"]) == name and info["version"] == version,
            "RELEASE_IDENTITY_MISMATCH")
    rows = []
    urls = doc["urls"]
    require(type(urls) is list and len(urls) <= 4096, "RELEASE_FILES_INVALID")
    for filename in sorted(filenames):
        selected = [x for x in urls if x.get("filename") == filename]
        require(len(selected) == 1, "SELECTED_FILE_ABSENT_OR_DUPLICATE")
        item = selected[0]
        digest, size, url = item["digests"]["sha256"], item["size"], item["url"]
        u = urlsplit(url)
        require(item["packagetype"] == "bdist_wheel"
                and HEX64.fullmatch(digest) and type(size) is int and size > 0
                and u.scheme == "https" and u.netloc == "files.pythonhosted.org"
                and not u.query and not u.fragment
                and re.fullmatch(r"/packages/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/"
                                 + re.escape(filename), u.path)
                and type(item["yanked"]) is bool, "SELECTED_FILE_METADATA_INVALID")
        rows.append({
            "filename": filename, "sha256": digest, "bytes": size,
            "url": url, "requires_python": short(item.get("requires_python"), 256),
            "yanked": item["yanked"], "yanked_reason": short(item.get("yanked_reason")),
            "upload_time_iso_8601": short(item.get("upload_time_iso_8601"), 128),
        })
    # This is release-level Requires-Dist, not selected-wheel METADATA.
    license_text = info.get("license")
    require(license_text is None or type(license_text) is str, "LICENSE_FIELD_INVALID")
    return {
        "name": name, "version": version, "status": "RELEASE_JSON_OBSERVED",
        "metadata_url": f"https://pypi.org/pypi/{name}/{version}/json",
        "requires_python": short(info.get("requires_python"), 256),
        "requires_dist_release_level": string_list(info.get("requires_dist")),
        "license_expression": short(info.get("license_expression"), 1024),
        "license_declared_excerpt": license_text[:4096] if license_text else license_text,
        "license_declared_truncated": bool(license_text and len(license_text) > 4096),
        "license_classifiers": [x for x in (string_list(info.get("classifiers")) or [])
                                if x.startswith("License ::")],
        "selected_wheels": rows,
    }


def self_test():
    name, version, filename = "fixture", "1.2.3", "fixture-1.2.3-py3-none-any.whl"
    item = {"filename": filename, "digests": {"sha256": "0"*64}, "size": 5,
            "url": "https://files.pythonhosted.org/packages/ab/cd/"+"0"*60+"/"+filename,
            "packagetype": "bdist_wheel", "yanked": False}
    doc = {"info": {"name": "fixture", "version": version, "requires_dist": []},
           "urls": [item]}
    assert release_row(doc, name, version, {filename})["selected_wheels"][0]["bytes"] == 5
    try:
        release_row(doc, name, version, {"missing.whl"})
    except Refusal:
        pass
    else:
        raise Refusal("SELF_TEST_MISSING_FILE")
    try:
        NoRedirect().redirect_request(None, None, 302, "", {}, "https://foreign.invalid/")
    except Refusal:
        pass
    else:
        raise Refusal("SELF_TEST_REDIRECT")
    try:
        parse(b'{"a":1,"a":2}')
    except Refusal:
        pass
    else:
        raise Refusal("SELF_TEST_DUPLICATE")
    print("C5_METADATA_SELF_TEST PASS", flush=True)


def main():
    require(os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_EVENT_NAME") == "push"
            and os.environ.get("GITHUB_REF") == "refs/heads/feature/live-dev-workspace-20261023"
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
            and os.environ.get("GITHUB_WORKFLOW") == "C5 PyPI release metadata one use",
            "ONE_USE_CONTEXT_REQUIRED")
    require(MARKER.read_bytes() == MARKER_BYTES, "APPROVAL_MARKER_MISMATCH")
    pairs = exact_inventory()
    self_test()
    opener = build_opener()
    receipt = hashlib.sha256()
    completed = selected = response_bytes = attempts = 0
    for (name, version), filenames in sorted(pairs.items()):
        attempts += 1
        try:
            doc, count, response_digest = fetch_release(opener, name, version)
            response_bytes += count
            row = release_row(doc, name, version, filenames)
            row["response_sha256"] = response_digest
            row["response_bytes"] = count
            completed += 1
            selected += len(row["selected_wheels"])
        except (Refusal, urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as exc:
            # Never print arbitrary response contents, private paths or exception text.
            row = {"name": name, "version": version, "status": "BLOCKED",
                   "reason": str(exc) if type(exc) is Refusal else type(exc).__name__}
        line = json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        receipt.update((line + "\n").encode("ascii"))
        print("C5_METADATA_ROW " + line, flush=True)
    result = {"attempts": attempts, "completed_releases": completed,
              "distinct_selected_wheels": selected, "response_bytes": response_bytes,
              "receipt_sha256": receipt.hexdigest(), "source_sha": os.environ.get("GITHUB_SHA"),
              "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": 1,
              "artifact_requests": 0, "status": "METADATA_ONLY_COMPLETE" if completed == MAX_PAIRS else "BLOCKED"}
    print("C5_METADATA_RESULT " + json.dumps(result, sort_keys=True), flush=True)
    return 0 if completed == MAX_PAIRS else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Refusal, OSError, ValueError, KeyError, TypeError) as exc:
        print("C5_METADATA_BLOCKED " + (str(exc) if type(exc) is Refusal else type(exc).__name__),
              file=sys.stderr)
        raise SystemExit(2)
