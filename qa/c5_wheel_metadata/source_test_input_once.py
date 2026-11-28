"""Exact source-test wheel identity and standard offline dry-run; no install."""
from email.parser import BytesParser
import email.policy
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, unquote
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DRIVER = "qa/c5_wheel_metadata/source_test_input_once.py"
WORKFLOW = ".github/workflows/c5-source-test-input-once.yml"
MARKER = "qa/c5_wheel_metadata/APPROVAL_SOURCE_TEST_INPUT_ONCE_20261126.txt"
MESSAGE = "C5-SOURCE-TEST-INPUT-ONCE-20261126 owner approved exact source-test dry-run only"
PLAN = "qa/c5_wheel_metadata/wheel_acquisition_plan_20261125.json"
PLAN_PIN = "1aa96a7172508f94b2cdc4b7aabd65e3b8f21f89"
TARGETS = {
    "win32": ("windows-x64-cp311-source-test", "3.11.9", "AMD64", 107014797,
              "6dba467333bd1111d4375aa10f268c0cb360cb2f"),
    "linux": ("linux-x64-cp311-source-test", "3.11.18", "x86_64", 123505565,
              "2d4601fc3103afc34df25a2b4f24646a959c1f6e"),
}
HEX = re.compile(r"[0-9a-f]{64}")
URL = re.compile(r"https://files\.pythonhosted\.org/packages/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/[A-Za-z0-9_.+-]+\.whl")
MAX_META = 2 * 1024 * 1024


class Refused(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Refused(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned(path, expected):
    raw = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    need(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == expected,
         "PIN_MISMATCH")
    return raw


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                   stderr=subprocess.DEVNULL, timeout=10).strip()


def live_gate():
    need(os.environ.get("GITHUB_ACTIONS") == "true"
         and os.environ.get("GITHUB_EVENT_NAME") == "push"
         and os.environ.get("GITHUB_REF") == "refs/heads/feature/live-dev-workspace-20261023"
         and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
         and (ROOT / MARKER).is_file(), "FRESH_APPROVAL_REQUIRED")
    head = git("rev-parse", "HEAD")
    need(head == os.environ.get("GITHUB_SHA") and git("log", "-1", "--format=%s") == MESSAGE,
         "ACTIVATION_IDENTITY")
    parent = git("rev-parse", "HEAD^")
    marker = json.loads((ROOT / MARKER).read_text(encoding="ascii"))
    need(marker == {"parent": parent, "driver": git("rev-parse", "HEAD:" + DRIVER),
                    "workflow": git("rev-parse", "HEAD:" + WORKFLOW),
                    "plan": PLAN_PIN}, "APPROVAL_PIN")
    need(git("diff", "--name-status", parent, head).splitlines() == ["A\t" + MARKER],
         "ACTIVATION_SCOPE")


def clean_env(scratch):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PIP_")
           and k.upper() not in ("PYTHONPATH", "PYTHONHOME", "HTTP_PROXY", "HTTPS_PROXY",
                                 "ALL_PROXY", "NO_PROXY", "CURL_HOME", "CURL_CA_BUNDLE",
                                 "SSL_CERT_FILE", "SSL_CERT_DIR")}
    env.update(PIP_CONFIG_FILE=os.devnull, TMP=str(scratch), TEMP=str(scratch),
               TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE="1")
    return env


def target():
    from pip._vendor.packaging.tags import sys_tags
    from pip._vendor.packaging.utils import parse_wheel_filename
    from pip._vendor.packaging.version import Version
    need(sys.platform in TARGETS, "TARGET")
    pid, py, machine, size, pin = TARGETS[sys.platform]
    need(sys.implementation.name == "cpython" and platform.python_version() == py
         and platform.machine() == machine and sys.maxsize > 2**32
         and metadata.version("pip") == "26.3", "EXISTING_TOOLCHAIN_MISMATCH")
    plan = json.loads(pinned(PLAN, PLAN_PIN))
    need(plan["status"] == "PROPOSAL_ONLY_DISABLED" and len(plan["wheels"]) == 68, "PLAN")
    rows = sorted((r for r in plan["wheels"] if pid in r["profiles"]), key=lambda r: r["name"])
    need(len(rows) == len({r["name"] for r in rows}) == 49
         and sum(r["bytes"] for r in rows) == size, "SCOPE")
    tags = set(sys_tags())
    for r in rows:
        name, version, _, wheel_tags = parse_wheel_filename(r["filename"])
        need(name == r["name"] and version == Version(r["version"]) and bool(wheel_tags & tags)
             and URL.fullmatch(r["url"]) and r["url"].endswith("/" + r["filename"])
             and HEX.fullmatch(r["sha256"]) and HEX.fullmatch(r["metadata_sha256"])
             and type(r["bytes"]) is int and 0 < r["bytes"] <= 36607512, "WHEEL_IDENTITY")
    lock = ROOT / "backend" / "locks" / (pid + ".txt")
    raw = pinned(lock.relative_to(ROOT).as_posix(), pin)
    lines = [line for line in raw.decode("ascii").splitlines() if line and not line.startswith("#")]
    expected = ["--no-index", "--only-binary=:all:", "--require-hashes"] + [
        r["name"] + ("[standard]" if r["name"] == "uvicorn" else "") +
        "==" + r["version"] + " --hash=sha256:" + r["sha256"] for r in rows]
    need(lines == expected, "LOCK_GRAPH_MISMATCH")
    return pid, rows, size, lock


def curl_tool(env):
    exe = shutil.which("curl.exe" if sys.platform == "win32" else "curl")
    need(bool(exe), "CURL_MISSING")
    result = subprocess.run([exe, "-q", "--version"], env=env, capture_output=True,
                            text=True, timeout=10)
    m = re.match(r"curl (\d+)\.(\d+)\.(\d+)", result.stdout)
    need(result.returncode == 0 and m and tuple(map(int, m.groups())) >= (8, 4, 0),
         "CURL_STREAM_CAP_UNAVAILABLE")
    return exe


def curl_command(exe, row, path):
    return [exe, "-q", "--silent", "--show-error", "--fail", "--noproxy", "*",
            "--http1.1", "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "0",
            "--retry", "0", "--connect-timeout", "10", "--max-time", "30",
            "--max-filesize", str(row["bytes"]), "--header", "Accept-Encoding: identity",
            "--output", str(path), "--write-out", "%{http_code} %{size_download}", row["url"]]


def transfer(exe, row, path, env):
    need(not path.exists(), "DESTINATION_EXISTS")
    result = subprocess.run(curl_command(exe, row, path), env=env, capture_output=True,
                            text=True, timeout=31)
    need(result.returncode == 0 and result.stdout.strip() == "200 " + str(row["bytes"]),
         "TRANSFER_REFUSED")
    need(path.is_file() and path.stat().st_size == row["bytes"], "BODY_SIZE")


def inspect_metadata(path, row):
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.specifiers import SpecifierSet
    from pip._vendor.packaging.utils import canonicalize_name
    from pip._vendor.packaging.version import Version
    need(path.stat().st_size == row["bytes"] and sha(path.read_bytes()) == row["sha256"],
         "WHEEL_HASH")
    member = "-".join(row["filename"].split("-")[:2]) + ".dist-info/METADATA"
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        need(0 < len(entries) <= 50000, "MEMBER_COUNT")
        matches = [x for x in entries if x.filename.casefold().endswith(".dist-info/metadata")]
        need(len(matches) == 1 and matches[0].filename == member, "METADATA_PATH")
        entry = matches[0]
        need(stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG)
             and not entry.external_attr & 0x458 and not entry.is_dir()
             and not entry.flag_bits & 1 and 0 < entry.file_size <= MAX_META, "METADATA_MODE")
        with z.open(entry) as f:
            raw = f.read(MAX_META + 1)
    need(len(raw) == entry.file_size and sha(raw) == row["metadata_sha256"], "METADATA_HASH")
    msg = BytesParser(policy=email.policy.compat32).parsebytes(raw)
    need(not msg.defects, "METADATA_PARSE")
    def one(key):
        vals = msg.get_all(key, [])
        need(len(vals) <= 1, "METADATA_DUPLICATE")
        return vals[0] if vals else None
    need(canonicalize_name(one("Name")) == row["name"]
         and Version(one("Version")) == Version(row["version"])
         and one("Requires-Python") == row["requires_python"]
         and one("License-Expression") == row["license_expression"]
         and sorted(msg.get_all("License-File", [])) == sorted(row["license_files"]),
         "METADATA_DECLARATION")
    if row["requires_python"] is not None:
        need(SpecifierSet(row["requires_python"]).contains(platform.python_version()), "PYTHON_RANGE")
    for declaration in msg.get_all("Requires-Dist", []):
        need(Requirement(declaration).url is None, "DIRECT_URL_REQUIREMENT")


def dry_run(rows, lock, house, scratch, env):
    from pip._vendor.packaging.utils import canonicalize_name
    expected = {r["name"]: r for r in rows}
    need({p.name for p in house.iterdir()} == {r["filename"] for r in rows}, "WHEELHOUSE_INVENTORY")
    report = scratch / "report.json"
    need(not report.exists(), "REPORT_EXISTS")
    cmd = [sys.executable, "-I", "-B", "-m", "pip", "--isolated",
           "--disable-pip-version-check", "--no-input", "--no-cache-dir",
           "--keyring-provider", "disabled", "install", "--dry-run", "--ignore-installed",
           "--no-index", "--only-binary=:all:", "--require-hashes",
           "--find-links", str(house), "--report", str(report), "-r", str(lock)]
    result = subprocess.run(cmd, env=env, cwd=scratch, capture_output=True, timeout=120)
    need(result.returncode == 0 and report.is_file() and report.stat().st_size <= 4 * 1024 * 1024,
         "PIP_DRY_RUN_REFUSED")
    items = json.loads(report.read_bytes())["install"]
    seen = set()
    for item in items:
        m = item["metadata"]
        name = canonicalize_name(m["name"])
        need(name in expected and name not in seen, "RESOLVED_GRAPH")
        row = expected[name]
        info = item["download_info"]
        url = urlsplit(info["url"])
        need(m["version"] == row["version"] and url.scheme == "file"
             and not url.netloc and not url.query and not url.fragment
             and unquote(url.path.rsplit("/", 1)[-1]) == row["filename"]
             and info["archive_info"]["hashes"]["sha256"] == row["sha256"]
             and not item.get("is_direct"), "RESOLVED_IDENTITY")
        seen.add(name)
    need(seen == set(expected), "RESOLVED_GRAPH")


def rehearsal():
    pid, rows, cap, _ = target()
    need(not (ROOT / MARKER).exists(), "APPROVAL_MARKER_PRESENT")
    try:
        live_gate()
    except Refused:
        pass
    else:
        raise Refused("LIVE_GATE_OPEN")
    with tempfile.TemporaryDirectory(prefix="c5-fixture-", dir=os.environ["RUNNER_TEMP"]) as directory:
        scratch = Path(directory)
        env = clean_env(scratch)
        exe = curl_tool(env)
        house = scratch / "wheels"
        house.mkdir()
        filename = "c5_inert_fixture-1.0-py3-none-any.whl"
        wheel = house / filename
        meta = b"Metadata-Version: 2.1\nName: c5-inert-fixture\nVersion: 1.0\n"
        dist = "c5_inert_fixture-1.0.dist-info/"
        with zipfile.ZipFile(wheel, "w") as z:
            z.writestr(dist + "METADATA", meta)
            z.writestr(dist + "WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            z.writestr(dist + "RECORD", dist + "METADATA,,\n" + dist + "WHEEL,,\n" + dist + "RECORD,,\n")
        row = dict(name="c5-inert-fixture", version="1.0", filename=filename,
                   bytes=wheel.stat().st_size, sha256=sha(wheel.read_bytes()), metadata_sha256=sha(meta),
                   requires_python=None, license_expression=None, license_files=[])
        inspect_metadata(wheel, row)
        for bad in (dict(row, sha256="0"*64), dict(row, metadata_sha256="0"*64)):
            try:
                inspect_metadata(wheel, bad)
            except Refused:
                pass
            else:
                raise Refused("BAD_HASH_ACCEPTED")
        lock = scratch / "fixture.txt"
        lock.write_text("c5-inert-fixture==1.0 --hash=sha256:" + row["sha256"] + "\n", encoding="ascii")
        dry_run([row], lock, house, scratch, env)
        command = curl_command(exe, rows[0], scratch / rows[0]["filename"])
        need("--location" not in command and "--http1.1" in command and command[1] == "-q"
             and command[command.index("--retry")+1] == "0"
             and command[command.index("--max-filesize")+1] == str(rows[0]["bytes"]),
             "TRANSPORT_COMMAND")
    print("C5_SOURCE_TEST_REHEARSAL_PASS", pid, len(rows), cap, flush=True)


def live():
    live_gate()
    pid, rows, cap, lock = target()
    requests = body = verified = 0
    status = "REFUSED"
    try:
        with tempfile.TemporaryDirectory(prefix="c5-source-test-", dir=os.environ["RUNNER_TEMP"]) as directory:
            scratch = Path(directory)
            need(shutil.disk_usage(scratch).free >= cap + 64 * 1024 * 1024, "FREE_SPACE")
            env = clean_env(scratch)
            exe = curl_tool(env)
            house = scratch / "wheels"
            house.mkdir()
            for row in rows:
                need(requests < 49 and body + row["bytes"] <= cap, "BUDGET")
                path = house / row["filename"]
                requests += 1
                try:
                    transfer(exe, row, path, env)
                finally:
                    if path.is_file():
                        body += path.stat().st_size
                need(body <= cap, "BODY_CAP")
                inspect_metadata(path, row)
                verified += 1
                print("C5_SOURCE_TEST_ROW", json.dumps({"filename": row["filename"], "bytes": row["bytes"],
                      "sha256": row["sha256"], "metadata_sha256": row["metadata_sha256"]},
                      sort_keys=True), flush=True)
            need(requests == verified == 49 and body == cap, "TERMINAL_SCOPE")
            dry_run(rows, lock, house, scratch, env)
            status = "DRY_RUN_PASS"
    finally:
        print("C5_SOURCE_TEST_RESULT", json.dumps({"profile": pid, "requests": requests,
              "retained_body_bytes": body, "verified": verified, "status": status,
              "installed": False, "licence_cleared": False}, sort_keys=True), flush=True)


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--rehearse"]:
            rehearsal()
        elif sys.argv[1:] == ["--live"]:
            live()
        else:
            raise Refused("FRESH_APPROVAL_REQUIRED")
    except Refused as exc:
        print("C5_SOURCE_TEST_REFUSED", str(exc), flush=True)
        sys.exit(2)
    except Exception as exc:
        print("C5_SOURCE_TEST_REFUSED", type(exc).__name__, flush=True)
        sys.exit(2)
