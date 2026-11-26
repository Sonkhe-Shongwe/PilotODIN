"""Detached, disarmed C5 executor. Standard tools, owned disposable scratch only.

No source activation, workflow registration or live approval is supplied here.
The existing literal guard is unconditional. No unreviewed licence/linkage
disposition can be inferred from archive hashes or successful resolution.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile

from qa.c5_pdfium import staged_equivalence as stages
from qa.c5_wheel_metadata import source_test_input_once as old
from qa.c5_wheel_metadata import wheel_archive_inspector_v2 as wheelcheck

ROOT = stages.ROOT
LIVE_ENABLED = False
# No reviewed actual-use disposition exists yet. A future exact approval must
# supply this pin and reviewed activation; neither an environment variable nor
# a caller-provided digest can grant it.
DISPOSITION_PATH = "qa/c5_pdfium/approved_use_disposition.json"
DISPOSITION_PIN = None
MAX_STATUS = 4 * 1024**2
MAX_HEADERS = 128 * 1024
MAX_ARCHIVE_MEMBERS = 50_000
MAX_ARCHIVE_MEMBER = 512 * 1024**2
MAX_INTERPRETER_EXPANDED = 1024**3
MIN_FREE = 8 * 1024**3


def require_live():
    if LIVE_ENABLED is not True:
        raise RuntimeError("C5_PDFIUM_EXECUTOR_DISARMED")
    stages.require_live_authority()


def need(ok, reason):
    stages.need(ok, reason)


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def owned(path, root):
    path, root = Path(path), Path(root)
    need(path.is_absolute() and root.is_absolute() and
         path.resolve().is_relative_to(root.resolve()), "SCRATCH_SCOPE")
    for p in (path, *path.parents):
        if p.exists():
            attrs = getattr(p.lstat(), "st_file_attributes", 0)
            need(not p.is_symlink() and not attrs & 0x400, "SCRATCH_LINK")
    return path


def identity(row):
    if row["kind"] == "npm":
        return "sha512", row["sha512"]
    if row["kind"] in ("font", "font_notice"):
        return "git_blob_sha1", row["git_blob_sha1"]
    return "sha256", row["sha256"]


def exact_file(path, row):
    need(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1 and
         path.stat().st_size == row["bytes"], "ARTIFACT_IDENTITY")
    algorithm, expected = identity(row)
    if algorithm == "git_blob_sha1":
        raw = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    else:
        actual = digest(path, algorithm)
    need(actual == expected, "ARTIFACT_IDENTITY")


def clean_env(scratch):
    # Existing isolation policy plus stricter Python/pytest/loader scrubbing.
    env = old.clean_env(scratch)
    banned = ("PIP_", "PYTHON", "PYTEST_", "LD_", "DYLD_", "GIT_", "PILOTODIN_")
    keep = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL", "TZ",
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "TMP", "TEMP", "TMPDIR"}
    env = {k: v for k, v in env.items() if k.upper() in keep and
           not k.upper().startswith(banned)}
    # All executable entrypoints are absolute. Do not inherit arbitrary PATH.
    env["PATH"] = str(scratch)
    env.update(stages.REQUIRED_ENV, PIP_CONFIG_FILE=os.devnull,
               HOME=str(scratch), USERPROFILE=str(scratch), APPDATA=str(scratch),
               LOCALAPPDATA=str(scratch), XDG_CONFIG_HOME=str(scratch),
               XDG_CACHE_HOME=str(scratch), XDG_DATA_HOME=str(scratch))
    return env


def read_disposition(plan, profile):
    require_live()
    need(isinstance(DISPOSITION_PIN, str) and stages.SHA1.fullmatch(DISPOSITION_PIN),
         "PRE_USE_DISPOSITION_UNRESOLVED")
    d = stages.strict_json(stages.pinned(DISPOSITION_PATH, DISPOSITION_PIN))
    need(d["status"] == "REVIEWED_INTERNAL_HOSTED_USE" and
         d["plan_blob"] == stages.PLAN_PIN and d["redistribution"] == "NOT_AUTHORISED",
         "DISPOSITION_SCOPE")
    rehearsal = d["pure_rehearsal"]
    need(rehearsal["state"] == "PASS" and stages.SHA1.fullmatch(rehearsal["source"]) and
         rehearsal["plan_blob"] == stages.PLAN_PIN and rehearsal["count"] == plan["pure_rehearsal"]["expected_count"] and
         rehearsal["failed"] == rehearsal["skipped"] == rehearsal["xfailed"] == 0 and
         stages.SHA256.fullmatch(rehearsal["reviewed_receipt_sha256"]), "PURE_REHEARSAL_UNVERIFIED")
    result = d["profiles"][profile["id"]]
    need(set(result["archives"]) == {r["filename"] for r in profile["rows"]},
         "DISPOSITION_ARCHIVE_SET")
    for row in profile["rows"]:
        a = result["archives"][row["filename"]]
        algorithm, expected = identity(row)
        need(a[algorithm] == expected and a["use"] == "REVIEWED" and
             stages.SHA256.fullmatch(a["notice_inventory_sha256"]), "DISPOSITION_ARCHIVE")
    need(result["network_scope"] == "EXACT_APPROVED_ENDPOINTS_ONLY" and
         result["runner_reviewed"] is True, "RUNNER_DISPOSITION")
    need(result["interpreter"]["version"] == profile["existing_interpreter"]["version"] and
         result["interpreter"]["provenance"] == "INDEPENDENTLY_REVIEWED_INSTALLED_RUNTIME" and
         result["interpreter"]["licence_use"] == "REVIEWED", "INSTALLED_INTERPRETER_DISPOSITION")
    return result


def tool_identity(path, expected):
    require_live()
    p = Path(path)
    need(p.is_absolute() and p.is_file() and not p.is_symlink() and
         digest(p) == expected, "TRUSTED_TOOL_IDENTITY")
    return str(p)


def run(args, *, env, cwd, seconds=120):
    require_live()
    need(0 < seconds <= 180 and Path(args[0]).is_absolute(), "COMMAND_BOUND")
    # No shell, no inherited stdin, and bound captured output while reading.
    # A future activation review must also establish descendant supervision
    # for the selected tools/runner; this is a direct child process deadline.
    process = subprocess.Popen(list(args), cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = [bytearray(), bytearray()]
    lock = threading.Lock()
    overflow = threading.Event()

    def drain(pipe, dest):
        try:
            while True:
                data = pipe.read1(65536)
                if not data:
                    break
                with lock:
                    if sum(map(len, output)) + len(data) > MAX_STATUS:
                        overflow.set()
                        process.kill()
                        break
                    dest.extend(data)
        except (OSError, ValueError):
            overflow.set()
            if process.poll() is None:
                process.kill()

    threads = [threading.Thread(target=drain, args=(pipe, dest), daemon=True)
               for pipe, dest in zip((process.stdout, process.stderr), output)]
    for worker in threads:
        worker.start()
    try:
        process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        raise ValueError("COMMAND_TIMEOUT") from None
    finally:
        for worker in threads:
            worker.join(timeout=2)
        for pipe in (process.stdout, process.stderr):
            pipe.close()
    need(not overflow.is_set() and not any(worker.is_alive() for worker in threads),
         "COMMAND_OUTPUT_CAP")
    need(process.returncode == 0, "COMMAND_REFUSED")
    return bytes(output[0])

def response_headers(raw):
    """Single HTTP/1.x response, exact framing; never log signed Location."""
    need(isinstance(raw, bytes) and 0 < len(raw) <= MAX_HEADERS and
         raw.endswith(b"\r\n\r\n"), "HTTP_HEADER_BOUND")
    lines = raw[:-4].split(b"\r\n")
    m = re.fullmatch(rb"HTTP/1\.[01] ([0-9]{3})(?: [ -~]*)?", lines[0])
    need(m is not None, "HTTP_STATUS_HEADER")
    fields = {}
    for line in lines[1:]:
        name, sep, value = line.partition(b":")
        key = name.lower()
        value = value.strip()
        need(sep == b":" and re.fullmatch(rb"[A-Za-z0-9-]+", name) and
             all(32 <= c <= 126 for c in value), "HTTP_HEADER")
        if key in (b"content-length", b"transfer-encoding", b"content-encoding", b"location"):
            need(key not in fields, "HTTP_DUPLICATE_CONTROL")
            fields[key] = value.decode("ascii")
    need(fields.get(b"content-encoding", "identity").lower() == "identity" and
         b"transfer-encoding" not in fields and
         re.fullmatch(r"[0-9]{1,10}", fields.get(b"content-length", "")), "HTTP_FRAMING")
    return int(m[1]), int(fields[b"content-length"]), fields.get(b"location")


class Acquisition:
    """Single profile, one scratch and one cumulative budget, no retry."""
    def __init__(self, profile, scratch, curl, env):
        require_live()
        self.profile, self.scratch, self.curl, self.env = profile, scratch, curl, env
        self.rows = {r["filename"]: r for r in profile["rows"]}
        self.seen = set()
        self.requests = self.body = 0
        self.deadline = time.monotonic() + 3600

    def _hop(self, row, url, path):
        require_live()
        need(self.requests < len(self.rows) and time.monotonic() < self.deadline, "REQUEST_BUDGET")
        header = owned(path.with_suffix(path.suffix + ".headers"), self.scratch)
        need(not path.exists() and not header.exists(), "TRANSFER_DESTINATION")
        request = dict(row, url=url)
        command = old.curl_command(self.curl, request, path)
        # Preserve exact reviewed wheel command; add strict header/framing evidence.
        command[-1:-1] = ["--dump-header", str(header)]
        # Exact immutable font paths contain literal encoded brackets; disable curl globbing.
        command.insert(2, "--globoff")
        self.requests += 1
        try:
            output = run(command, env=self.env, cwd=self.scratch,
                         seconds=31)
        finally:
            if path.exists():
                self.body += path.stat().st_size
        need(self.body <= sum(r["bytes"] for r in self.rows.values()), "BODY_BUDGET")
        need(header.is_file() and header.stat().st_size <= MAX_HEADERS, "HEADER_CAP")
        status, length, location = response_headers(header.read_bytes())
        size = path.stat().st_size if path.is_file() else 0
        need(output.strip() == f"{status} {size}".encode("ascii") and size == length,
             "RESPONSE_ACCOUNTING")
        header.unlink()
        return status, length, location

    def get(self, row, destination):
        require_live()
        name = row["filename"]
        need(self.rows.get(name) == row and name not in self.seen, "EXACT_REQUEST_SET")
        self.seen.add(name)
        path = owned(destination / name, self.scratch)
        status, length, location = self._hop(row, row["url"], path)
        need(status == 200 and length == row["bytes"] and location is None, "HTTP_BODY")
        exact_file(path, row)
        return path


def archive_member_path(name):
    # Existing wheel path rules also prohibit Windows device names, ADS,
    # traversal, control characters and ambiguous separators.
    return wheelcheck.name(name.rstrip("/"))


def verified_existing_interpreter(profile, disposition):
    """Use only an independently reviewed pre-existing runner installation.

    The historical Windows archive is an installer; no setup scripts, cache
    population, relocation, or fallback are permitted.
    """
    require_live()
    approved = disposition["interpreter"]
    cache = Path(os.environ["RUNNER_TOOL_CACHE"])
    prefix = cache / "Python" / profile["existing_interpreter"]["version"] / "x64"
    need(cache.is_absolute() and prefix.is_dir(), "EXISTING_INTERPRETER_MISSING")
    root = prefix.resolve(strict=True)
    need(root == prefix.absolute() and approved["root"] == str(root),
         "INTERPRETER_ROOT")
    python = root / ("python.exe" if os.name == "nt" else "bin/python3.11")
    need(str(python) == approved["path"] and
         python.resolve(strict=True).is_relative_to(root), "INTERPRETER_PATH")
    # Independently reviewed full installed regular-file inventory, including
    # standard library, DLL/SO, executable and notice files, not version alone.
    expected = approved["files"]
    need(isinstance(expected, dict) and 0 < len(expected) <= 50000,
         "INTERPRETER_INVENTORY")
    observed = {}
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            attrs = getattr(path.lstat(), "st_file_attributes", 0)
            need(not attrs & 0x400, "INTERPRETER_REPARSE")
            key = path.relative_to(root).as_posix()
            if path.is_symlink():
                need(name in files and path.resolve(strict=True).is_relative_to(root),
                     "INTERPRETER_LINK")
                observed[key] = {"link": os.readlink(path)}
            elif name in files:
                need(path.is_file() and key in expected and
                     path.stat().st_size <= MAX_ARCHIVE_MEMBER, "INTERPRETER_FILE")
                total += path.stat().st_size
                need(total <= 2 * 1024**3, "INTERPRETER_EXPANDED")
                observed[key] = {"bytes": path.stat().st_size, "sha256": digest(path)}
            need(len(observed) <= 50000, "INTERPRETER_INVENTORY")
    need(observed == expected and python.relative_to(root).as_posix() in expected,
         "INTERPRETER_IDENTITY")
    need(approved["notice_members"] and all(n in observed and "sha256" in observed[n]
         for n in approved["notice_members"]), "INTERPRETER_NOTICE_SET")
    return python


def inspect_distribution(path, row, approved, destination=None):
    """Bounded ZIP/tar inventory against reviewed exact members.

    Only Node is extracted, into owned scratch. npm tgz is inspected as data;
    standard npm performs installation. Reviewed links in the Node tar are
    checked but never materialised; invoke npm-cli.js directly.
    """
    require_live()
    exact_file(path, row)
    expected = approved["members"]
    need(isinstance(expected, dict) and 0 < len(expected) <= MAX_ARCHIVE_MEMBERS,
         "DISTRIBUTION_INVENTORY")
    need((row["kind"] == "node") == (destination is not None), "EXTRACTION_SCOPE")
    if destination is not None:
        need(not destination.exists(), "DISTRIBUTION_DESTINATION")
        destination.mkdir()
    observed, directories, folded, parents = {}, set(), set(), {}
    total = 0

    def visit(name, size, mode, stream=None, link=None, directory=False):
        nonlocal total
        name = archive_member_path(name)
        key = name.casefold()
        need(key not in folded, "DISTRIBUTION_DUPLICATE")
        folded.add(key)
        parts = name.split("/")
        for length in range(1, len(parts)):
            parent = "/".join(parts[:length])
            need(parents.setdefault(parent.casefold(), parent) == parent, "DISTRIBUTION_CASE_COLLISION")
        need(len(observed) + len(directories) < MAX_ARCHIVE_MEMBERS and
             0 <= size <= MAX_ARCHIVE_MEMBER, "DISTRIBUTION_BOUNDS")
        if directory:
            need(size == 0, "DISTRIBUTION_DIRECTORY")
            directories.add(name.casefold())
            if destination is not None:
                owned(destination / name, destination).mkdir(parents=True, exist_ok=True)
            return
        need(name in expected, "DISTRIBUTION_MEMBER")
        if link is not None:
            need(row["kind"] == "node" and destination is not None and
                 name.endswith(("/bin/npm", "/bin/npx", "/bin/corepack")) and
                 expected[name] == {"link": link}, "DISTRIBUTION_LINK")
            # No links created; exact reviewed npm-cli.js is invoked by Node.
            observed[name] = {"link": link}
            return
        total += size
        need(total <= (1024**3 if row["kind"] == "node" else 512 * 1024**2),
             "DISTRIBUTION_EXPANSION")
        h = hashlib.sha256()
        target = None
        if destination is not None:
            target = owned(destination / name, destination)
            target.parent.mkdir(parents=True, exist_ok=True)
        remaining = size
        with (target.open("xb") if target is not None else open(os.devnull, "wb")) as out:
            while remaining:
                chunk = stream.read(min(65536, remaining))
                need(chunk, "DISTRIBUTION_TRUNCATED")
                h.update(chunk)
                out.write(chunk)
                remaining -= len(chunk)
            need(stream.read(1) == b"", "DISTRIBUTION_OVERFLOW")
        got = {"bytes": size, "sha256": h.hexdigest()}
        need(got == expected[name], "DISTRIBUTION_MEMBER_IDENTITY")
        observed[name] = got
        if target is not None and os.name != "nt":
            target.chmod(0o700 if mode & 0o111 else 0o600)

    if path.name.endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            need(len(archive.infolist()) <= MAX_ARCHIVE_MEMBERS, "DISTRIBUTION_COUNT")
            for entry in archive.infolist():
                mode = entry.external_attr >> 16
                need(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR) and
                     not entry.external_attr & 0x448 and not entry.flag_bits & 1,
                     "DISTRIBUTION_ZIP_MODE")
                with archive.open(entry) as stream:
                    visit(entry.filename, entry.file_size, mode, stream, directory=entry.is_dir())
    else:
        need(path.name.endswith((".tgz", ".tar.xz")), "DISTRIBUTION_FORMAT")
        with tarfile.open(path, mode="r|*") as archive:
            for entry in archive:
                if entry.isdir():
                    visit(entry.name, entry.size, entry.mode, directory=True)
                elif entry.issym():
                    visit(entry.name, entry.size, entry.mode, link=entry.linkname)
                else:
                    need(entry.isfile(), "DISTRIBUTION_TAR_MODE")
                    with archive.extractfile(entry) as stream:
                        visit(entry.name, entry.size, entry.mode, stream)
    need(observed == expected and not {n.casefold() for n in observed}.intersection(parents),
         "DISTRIBUTION_INVENTORY")
    names = approved["notice_members"]
    need(isinstance(names, list) and names and len(names) == len(set(names)) and
         all(n in observed and "sha256" in observed[n] for n in names),
         "DISTRIBUTION_NOTICE_SET")
    notices = [{"path": n, **observed[n]} for n in sorted(names)]
    need(hashlib.sha256(json.dumps(notices, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
         == approved["notice_inventory_sha256"], "DISTRIBUTION_NOTICE_INVENTORY")
    return total


def wheel_expectation(row, plan, disposition):
    """Join prior declarations, not merely a fresh self-declared licence."""
    if row["kind"] == "pip":
        # The old pip receipt contains PyPI JSON metadata, NOT wheel METADATA.
        # Require a separately reviewed actual metadata declaration.
        expectation = disposition["archives"][row["filename"]]["wheel_expectation"]
        need(expectation["name"] == "pip" and expectation["version"] == "26.3",
             "PIP_DECLARATION")
    elif row["name"] == "pypdfium2":
        source = "docs/C5_PDFIUM_TWO_WHEEL_RECEIPTS_45840503532.json"
        receipt = stages.strict_json(stages.pinned(source, plan["source_pins"][source]))
        old_row = next(x for x in receipt["wheels"] if x["filename"] == row["filename"])
        expectation = dict(row, license_files=old_row["declared_license_files"],
                           license_expression=None, requires_python=">= 3.6")
    else:
        source = "qa/c5_wheel_metadata/wheel_acquisition_plan_20261125.json"
        historical = stages.strict_json(stages.pinned(source, plan["source_pins"][source]))
        expectation = next(x for x in historical["wheels"] if x["filename"] == row["filename"])
    for key in ("filename", "bytes", "sha256", "metadata_sha256"):
        if key in row:
            need(expectation[key] == row[key], "WHEEL_EXPECTATION")
    return expectation


def inspect_wheel(path, row, plan, disposition, budget):
    require_live()
    exact_file(path, row)
    result = budget.inspect(path.read_bytes(), wheel_expectation(row, plan, disposition))
    approved = disposition["archives"][row["filename"]]
    notice_hash = hashlib.sha256(json.dumps(result["notices"], sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()
    need(notice_hash == approved["notice_inventory_sha256"], "NOTICE_INVENTORY")
    return result


def native_linkage(path, profile, disposition, scratch, env):
    """Read verified native member as data using pinned existing tools, never ldd/load."""
    require_live()
    expected, = profile["native"]
    dest = owned(scratch / Path(expected["path"]).name, scratch)
    with zipfile.ZipFile(path) as z, z.open(expected["path"]) as src, dest.open("xb") as out:
        raw = src.read(expected["bytes"] + 1)
        need(len(raw) == expected["bytes"] and hashlib.sha256(raw).hexdigest() ==
             expected["sha256"], "NATIVE_MEMBER")
        out.write(raw)
    tool = disposition["linkage"]
    exe = tool_identity(tool["path"], tool["sha256"])
    flags = ("--file-headers", "--coff-imports", "--coff-delay-imports") if \
        profile["id"].startswith("windows") else ("-h", "-d", "-V")
    need(tool["kind"] == ("llvm-readobj" if profile["id"].startswith("windows") else "readelf"),
         "LINKAGE_TOOL")
    evidence = run((exe, *flags, dest.name), env=env, cwd=scratch)
    # Exact reviewed output digest, not inferred absence of static linkage.
    need(hashlib.sha256(evidence).hexdigest() == tool["reviewed_output_sha256"],
         "LINKAGE_DISPOSITION_MISMATCH")
    return expected["sha256"]


def reconcile_resolution(report, rows, wheelhouse):
    need(report.is_file() and report.stat().st_size <= MAX_STATUS, "PIP_REPORT")
    doc = stages.strict_json(report.read_bytes())
    items = doc["install"]
    expected = {r["name"]: r for r in rows}
    seen = set()
    for item in items:
        meta, info = item["metadata"], item["download_info"]
        name = wheelcheck.norm(meta["name"])
        need(name in expected and name not in seen, "PIP_GRAPH")
        row = expected[name]
        # as_uri() handles drive-letter paths without platform-dependent URL guessing.
        need(info["url"] == (wheelhouse / row["filename"]).resolve().as_uri() and
             info["archive_info"]["hashes"]["sha256"] == row["sha256"] and
             meta["version"] == row["version"] and not item.get("is_direct"), "PIP_IDENTITY")
        seen.add(name)
    need(seen == set(expected), "PIP_GRAPH")
    return True


def exact_inventory(python, rows, scratch, env, pip_meta):
    # Run only after input/use clearance; exact installed versions and METADATA.
    script = r"""
import hashlib,importlib.metadata as m,json,pathlib,sys
prefix=pathlib.Path(sys.prefix).resolve()
rows=[]
for d in m.distributions():
    files=[f for f in (d.files or []) if f.name=='METADATA' and f.parent.name.endswith('.dist-info')]
    if len(files)!=1: raise RuntimeError('installed metadata missing or ambiguous')
    p=pathlib.Path(d.locate_file(files[0])).resolve(strict=True)
    if not p.is_relative_to(prefix) or p.stat().st_size>2*1024**2:
        raise RuntimeError('installed metadata outside exact environment')
    rows.append([d.metadata['Name'],d.version,hashlib.sha256(p.read_bytes()).hexdigest()])
print(json.dumps(rows))
"""
    items = stages.strict_json(run((str(python), "-I", "-B", "-c", script),
                                   cwd=scratch, env=env))
    expected = {r["name"]: (r["version"], r["metadata_sha256"]) for r in rows}
    need(stages.SHA256.fullmatch(pip_meta), "PIP_INSTALLED_METADATA_PIN")
    expected["pip"] = ("26.3", pip_meta)
    observed = {wheelcheck.norm(n): (v, h) for n, v, h in items}
    need(len(observed) == len(items) and observed == expected, "INSTALLED_INVENTORY")


def resolve_install(python, rows, lock, house, scratch, env, pip_meta=None):
    require_live()
    need({p.name for p in house.iterdir()} == {r["filename"] for r in rows},
         "WHEELHOUSE_INVENTORY")
    report = owned(scratch / "pip-report.json", scratch)
    need(not report.exists(), "PIP_REPORT_EXISTS")
    commands = stages.pip_arguments(python, house, lock, report)
    run(commands["dry_run"], cwd=scratch, env=env)
    reconcile_resolution(report, rows, house)
    run(commands["install"], cwd=scratch, env=env)
    run(commands["check"], cwd=scratch, env=env)
    exact_inventory(python, rows, scratch, env, pip_meta)
    report.unlink()


def pytest_witness(python, selection, scratch, env, expected=None):
    require_live()
    scratch.mkdir()
    home = owned(scratch / "home", scratch)
    home.mkdir()
    receipt = owned(scratch / "pytest-status.json", scratch)
    collected_receipt = owned(scratch / "pytest-collection.json", scratch)
    env = dict(env, PILOTODIN_HOME=str(home), C5_PDFIUM_TEST_STATUS=str(receipt))
    # Explicit standard pytest hooks; no ambient plugin discovery or external plugin.
    base = (str(python), "-B", "-m", "pytest", "-p", "no:cacheprovider",
            "-p", "qa.c5_pdfium.pytest_receipt", "--strict-markers", "-q")
    run(base + ("--collect-only", selection), cwd=ROOT,
        env=dict(env, C5_PDFIUM_TEST_STATUS=str(collected_receipt)), seconds=180)
    need(collected_receipt.is_file() and collected_receipt.stat().st_size <= MAX_STATUS,
         "PYTEST_COLLECTION_RECEIPT")
    collection = stages.strict_json(collected_receipt.read_bytes())
    need(collection["mode"] == "COLLECTION" and collection["exitstatus"] == 0 and
         collection["failed"] == collection["skipped"] == collection["xfailed"] == [] and
         collection["passed"] == [], "PYTEST_COLLECTION_REFUSED")
    collected = collection["collected"]
    need(collected and len(collected) == len(set(collected)), "PYTEST_COLLECTION_SET")
    if expected is not None:
        need(len(collected) == len(expected) and set(collected) == set(expected),
             "PYTEST_EXPECTED_SET")
    run(base + (selection,), cwd=ROOT, env=env, seconds=180)
    need(receipt.is_file() and receipt.stat().st_size <= MAX_STATUS, "PYTEST_RECEIPT")
    result = stages.strict_json(receipt.read_bytes())
    need(set(result) == {"collected", "passed", "failed", "skipped", "xfailed", "exitstatus", "mode"}
         and result["mode"] == "EXECUTION" and result["exitstatus"] == 0 and result["failed"] == result["skipped"] ==
         result["xfailed"] == [], "PYTEST_NOT_PASS")
    nodes = result["collected"]
    need(nodes and nodes == collected and len(nodes) == len(set(nodes)) and result["passed"] == nodes,
         "PYTEST_INCOMPLETE")
    if expected is not None:
        need(len(nodes) == len(expected) and set(nodes) == set(expected), "PYTEST_EXPECTED_SET")
    return {"collected": nodes, "passed": nodes, "state": "PASS"}


def mixed_witness(python, scratch, env):
    require_live()
    from tools.qa_foundation import create_run
    from tools.p2_mixed_report_devqa import worker_status_path, simple_status
    scratch.mkdir()
    run_dir, _ = create_run(scratch / "mixed", "P2-MIXED-REPORT", ROOT)
    child = dict(env, PILOTODIN_HOME=str(run_dir / "workspace"),
                 PILOTODIN_DEVQA_RUN=str(run_dir), PYTHONPATH=str(ROOT), RL_invariant="1")
    result = {}
    for kind, count in (("contract", 3), ("mixed", 9)):
        run((str(python), "-B", str(ROOT / "tools/p2_mixed_report_devqa.py"), "--worker", kind),
            cwd=ROOT, env=child, seconds=180)
        path = worker_status_path(run_dir, kind)
        need(path.is_file() and path.stat().st_size <= MAX_STATUS, "MIXED_STATUS")
        reply = stages.strict_json(path.read_bytes())
        need(simple_status(reply, count) == "PASS", "MIXED_REFUSED")
        result["mixed:" + kind] = {"collected": reply["cases"], "passed": reply["cases"],
                                   "state": "PASS"}
    return result


def font_witness(python, scratch, env, disposition, rows, extra):
    require_live()
    require_font_authority(disposition)
    fonts = owned(scratch / "PilotODIN/DevQA/font-candidates", scratch)
    fonts.mkdir(parents=True)
    selected = [r for r in rows if r["kind"] in ("font", "font_notice")]
    need(len(selected) == 6, "FONT_INPUT_SET")
    for row in selected:
        path = extra / row["filename"]
        exact_file(path, row)
        approved = disposition["archives"][row["filename"]]
        need(digest(path) == approved["measured_sha256"], "FONT_USE_IDENTITY")
        shutil.copyfile(path, fonts / row["filename"])
        exact_file(fonts / row["filename"], row)
    evidence = {}
    for mode in ("unit", "baseline", "corrected", "actual", "context", "coverage", "research"):
        home = owned(scratch / ("font-home-" + mode), scratch)
        home.mkdir()
        child = dict(env, PILOTODIN_HOME=str(home), PYTHONPATH=str(ROOT))
        reply = run((str(python), "-B", "-m", "qa.c5_pdfium.font_witness",
                     mode, str(fonts)), cwd=ROOT, env=child, seconds=180)
        evidence[mode] = stages.strict_json(reply)
    unit, baseline, corrected = (evidence[k] for k in ("unit", "baseline", "corrected"))
    need(unit == {"state": "PASS", "expected": 9, "executed": 9, "failures": 0,
                  "errors": 0, "skipped": 0}, "CMAP_UNIT")
    need(baseline["exact"] is False and corrected["exact"] is True and
         stages.SHA256.fullmatch(baseline["pixel_sha256"]) and
         baseline["pixel_sha256"] == corrected["pixel_sha256"] and
         baseline["reportlab_version"] == corrected["reportlab_version"] == "4.5.1",
         "CMAP_EQUIVALENCE")
    actual = evidence["actual"]
    for key in ("real_backend_report_pdf", "legacy_default_report_preserved",
                "unicode_title_narrative_table_chart", "chart_metric_values_unchanged",
                "immutable_revision_and_html", "footer_and_pages", "page_bounds"):
        need(actual[key] is True, "ACTUAL_REPORT_PREDICATE")
    need(type(actual["pages"]) is int and 1 <= actual["pages"] <= 4, "ACTUAL_REPORT_PAGES")
    context = evidence["context"]
    need(context["state"] == "SCOPED_FONT_CONTEXT_IN_MEMORY_PASS" and
         all(context[k] is True for k in ("paragraph_exact", "vector_label_exact",
                                         "one_page", "page_bounds_ok")), "FONT_CONTEXT")
    coverage = evidence["coverage"]
    samples = coverage["samples"]
    need(coverage["scope"] == "DEVELOPER_PROBE_NOT_ACCEPTANCE" and
         set(samples) == {"latin", "greek", "cyrillic", "rupee", "cjk", "emoji", "mixed"} and
         all(x["state"] in ("EXTRACTED_EXACT", "MISMATCH", "UNSUPPORTED", "RENDER_ERROR")
             for x in samples.values()), "FONT_COVERAGE_OUTCOME")
    # The historical probe is diagnostic, not a claim all scripts extract.
    # Compare exact previously reviewed outcome expectations; do not infer PASS.
    need({k: v["state"] for k, v in samples.items()} ==
         disposition["font_coverage_expected"], "FONT_COVERAGE_REGRESSION")
    research = evidence["research"]
    need(research["state"] == "RESEARCH_ONLY" and research["baseline_matches"] is False and
         research["corrected_matches"] is True and research["same_rendered_pixels"] is True and
         research["product_acceptance"] == research["visual_acceptance"] == "NOT_TESTED",
         "FONT_RESEARCH")
    return {"collected": list(stages.FONT_REQUIRED_NODES),
            "passed": list(stages.FONT_REQUIRED_NODES), "state": "PASS"}


def frontend_witness(scratch, env, disposition, rows, extra):
    require_live()
    node_row, = [r for r in rows if r["kind"] == "node"]
    packages = [r for r in rows if r["kind"] == "npm"]
    need(len(packages) == 30, "NPM_INPUT_SET")
    # Inspect all inputs and applicable notices before any Node/npm execution.
    expanded = 0
    for row in packages:
        expanded += inspect_distribution(extra / row["filename"], row,
                                         disposition["archives"][row["filename"]])
        need(expanded <= 2 * 1024**3, "NPM_PROFILE_EXPANSION")
    node_dir = owned(scratch / "node", scratch)
    approved = disposition["archives"][node_row["filename"]]
    inspect_distribution(extra / node_row["filename"], node_row, approved, node_dir)
    node = owned(node_dir / archive_member_path(approved["node_member"]), node_dir)
    cli = owned(node_dir / archive_member_path(approved["npm_member"]), node_dir)
    need(node.is_file() and cli.is_file(), "NODE_NPM_ENTRYPOINT")
    need(digest(node) == approved["members"][approved["node_member"]]["sha256"] and
         digest(cli) == approved["members"][approved["npm_member"]]["sha256"], "NODE_NPM_IDENTITY")
    work = owned(scratch / "frontend", scratch)
    work.mkdir()
    git = tool_identity(disposition["git"]["path"], disposition["git"]["sha256"])
    tracked = run((git, "ls-files", "-z", "--", "frontend"), cwd=ROOT, env=env)
    entries = tracked.decode("utf-8", "strict").split("\0")
    need(entries[-1] == "" and 0 < len(entries) <= 50000, "FRONTEND_TRACKED_SET")
    total = 0
    for name in entries[:-1]:
        need(name.startswith("frontend/"), "FRONTEND_SOURCE_SCOPE")
        source = ROOT / name
        target = owned(work / name[len("frontend/"):], scratch)
        need(source.is_file() and not source.is_symlink() and
             source.resolve().is_relative_to(ROOT.resolve()) and
             source.stat().st_size <= 32 * 1024**2, "FRONTEND_SOURCE_FILE")
        total += source.stat().st_size
        need(total <= 256 * 1024**2, "FRONTEND_SOURCE_BOUND")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    lock = work / "package-lock.json"
    lock_hash = digest(lock)
    cache = scratch / "npm-cache"
    cache.mkdir()
    config = scratch / "npmrc"
    config.touch(exist_ok=False)
    child = dict(env, PATH=str(node.parent), NPM_CONFIG_USERCONFIG=str(config),
                 NPM_CONFIG_GLOBALCONFIG=str(config), NPM_CONFIG_CACHE=str(cache),
                 NPM_CONFIG_OFFLINE="true", NPM_CONFIG_IGNORE_SCRIPTS="true",
                 NPM_CONFIG_AUDIT="false", NPM_CONFIG_FUND="false",
                 NPM_CONFIG_UPDATE_NOTIFIER="false", PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1")
    need(run((str(node), "--version"), cwd=work, env=child).strip() == b"v22.23.5",
         "NODE_VERSION")
    base = (str(node), str(cli))
    need(run(base + ("--version",), cwd=work, env=child).strip() == b"10.9.9", "NPM_VERSION")
    flags = ("--offline", "--ignore-scripts", "--no-audit", "--no-fund", "--cache", str(cache))
    for row in packages:
        # Local tarball cache population only. No fallback to a registry.
        exact_file(extra / row["filename"], row)
        run(base + ("cache", "add", str(extra / row["filename"]), *flags),
            cwd=work, env=child)
    run(base + ("ci", *flags), cwd=work, env=child, seconds=180)
    need(digest(lock) == lock_hash, "NPM_LOCK_MUTATION")
    # Exact package paths and versions, excluding only npm-owned .bin and
    # .package-lock.json bookkeeping; no unexpected dependency tree.
    modules = work / "node_modules"
    observed = {}
    for entry in modules.iterdir():
        if entry.name in (".bin", ".package-lock.json"):
            continue
        need(entry.is_dir() and not entry.is_symlink(), "NPM_INSTALLED_PATH")
        candidates = list(entry.iterdir()) if entry.name.startswith("@") else [entry]
        for candidate in candidates:
            package = owned(candidate / "package.json", scratch)
            need(package.is_file() and package.stat().st_size <= 2 * 1024**2,
                 "NPM_INSTALLED_METADATA")
            doc = stages.strict_json(package.read_bytes())
            key = candidate.relative_to(work).as_posix()
            need(doc["name"] == key[len("node_modules/"):], "NPM_INSTALLED_NAME")
            observed[key] = doc["version"]
    need(observed == {r["package_path"]: r["version"] for r in packages}, "NPM_INSTALLED_SET")
    # Match every installed package file against its independently reviewed
    # tar member identity, excluding npm-generated bin links outside packages.
    for row in packages:
        expected = disposition["archives"][row["filename"]]["members"]
        directory = work / row["package_path"]
        got = {}
        for folder, dirs, files in os.walk(directory, followlinks=False):
            for name in dirs + files:
                path = owned(Path(folder) / name, scratch)
                if name in files:
                    key = "package/" + path.relative_to(directory).as_posix()
                    need(key in expected and path.is_file() and
                         path.stat().st_size == expected[key]["bytes"], "NPM_INSTALLED_FILE")
                    got[key] = {"bytes": path.stat().st_size, "sha256": digest(path)}
        need(got == expected, "NPM_INSTALLED_BYTES")
    verifier = work / "scripts/verify-npm-lock.mjs"
    run((str(node), str(verifier), *(("--installed",) if os.name == "nt" else ())),
        cwd=work, env=child)
    # Invoke exact package CLI scripts directly, no npm lifecycle commands.
    run((str(node), str(modules / "typescript/bin/tsc"), "--noEmit"), cwd=work, env=child)
    run((str(node), str(modules / "vite/bin/vite.js"), "build"), cwd=work, env=child, seconds=180)
    need(digest(lock) == lock_hash, "NPM_LOCK_MUTATION")
    return {"collected": list(stages.FRONTEND_REQUIRED_NODES),
            "passed": list(stages.FRONTEND_REQUIRED_NODES), "state": "PASS"}


def bootstrap_python(interpreter, pip_wheel, scratch, env, disposition):
    require_live()
    # Existing interpreter identity independently reviewed before use;
    # the pip wheel has passed the exact declaration/notice gate.
    expected_version = disposition["interpreter"]["version"]
    output = run((str(interpreter), "-I", "-B", "-c",
                  "import platform,sys; print(platform.python_version()); print(sys.maxsize)"),
                 cwd=scratch, env=env).decode("ascii").splitlines()
    need(output == [expected_version, "9223372036854775807"], "INTERPRETER_VERSION")
    venv = owned(scratch / "venv", scratch)
    run((str(interpreter), "-I", "-B", "-m", "venv", "--without-pip", "--copies", str(venv)),
        cwd=scratch, env=env)
    python = owned(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
                   scratch)
    need(python.is_file(), "VENV_PYTHON")
    lock = owned(scratch / "pip-bootstrap.txt", scratch)
    row = disposition["archives"][pip_wheel.name]
    lock.write_text("pip==26.3 --hash=sha256:" + row["sha256"] + "\n", encoding="ascii")
    # Bootstrap exact pip wheel with zipimport, not ensurepip or online upgrade.
    script = ("import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); "
              "runpy.run_module('pip',run_name='__main__')")
    run((str(python), "-I", "-B", "-c", script, str(pip_wheel), "--isolated",
         "--disable-pip-version-check", "--no-input", "--keyring-provider", "disabled",
         "install", "--no-index", "--only-binary=:all:", "--require-hashes",
         "--no-cache-dir", "--find-links", str(pip_wheel.parent), "-r", str(lock)),
        cwd=scratch, env=env)
    exact_inventory(python, [], scratch, env, row["wheel_expectation"]["metadata_sha256"])
    return python


def verify_loaded_native(python, profile, scratch, env):
    """Verify installed member hash and actual loader mapping after authorised import."""
    require_live()
    expected, = profile["native"]
    script = r"""
import ctypes, hashlib, importlib.metadata as metadata, json, os, pathlib, sys
from importlib import util
spec = util.find_spec("pypdfium2_raw")
if spec is None or spec.origin is None: raise RuntimeError("native package absent")
pre = pathlib.Path(spec.origin).parent / pathlib.Path(sys.argv[1]).name
pre = pre.resolve(strict=True)
if not pre.is_relative_to(pathlib.Path(sys.prefix).resolve()) or pre.stat().st_size != int(sys.argv[4]):
    raise RuntimeError("native path/size mismatch before import")
with pre.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != sys.argv[3]:
        raise RuntimeError("native digest mismatch before import")
sys.path.insert(0, sys.argv[2])
from tools.pdf_test_inspection import require_pdfium
require_pdfium()
import pypdfium2
import pypdfium2_raw
path = pathlib.Path(pypdfium2_raw.__file__).parent / pathlib.Path(__import__('sys').argv[1]).name
path = path.resolve(strict=True)
if os.name == 'nt':
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    handle = kernel.GetModuleHandleW
    handle.argtypes = [ctypes.c_wchar_p]
    handle.restype = ctypes.c_void_p
    module = handle(str(path))
    if not module: raise RuntimeError('native member not loaded')
    getname = kernel.GetModuleFileNameW
    getname.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
    getname.restype = ctypes.c_uint32
    buf = ctypes.create_unicode_buffer(32768)
    size = getname(module, buf, len(buf))
    if not 0 < size < len(buf): raise RuntimeError('loader path unavailable')
    loaded = pathlib.Path(buf.value).resolve(strict=True) == path
else:
    loaded = False
    for line in pathlib.Path('/proc/self/maps').read_text().splitlines():
        parts = line.split(None, 5)
        if len(parts) == 6 and parts[5].startswith('/') and not parts[5].endswith(' (deleted)'):
            if pathlib.Path(parts[5]).resolve() == path: loaded = True
with path.open('rb') as f:
    sha = hashlib.file_digest(f, 'sha256').hexdigest()
print(json.dumps({'loaded': loaded, 'sha256': sha, 'bytes': path.stat().st_size,
                  'inside_venv': path.is_relative_to(pathlib.Path(__import__('sys').prefix).resolve()),
                  'version': metadata.version('pypdfium2')}))
"""
    got = stages.strict_json(run((str(python), "-I", "-B", "-c", script, expected["path"], str(ROOT), expected["sha256"], str(expected["bytes"])),
                                 cwd=scratch, env=env))
    need(got == {"loaded": True, "sha256": expected["sha256"], "bytes": expected["bytes"],
                 "inside_venv": True, "version": "5.15.2"}, "LOADED_NATIVE_IDENTITY")
    return expected["sha256"]


def run_profile(profile_id, generation, source, windows_receipt=None):
    require_live()
    plan = stages.read_plan()
    need(profile_id in stages.PROFILE_IDS and stages.SHA256.fullmatch(generation) and
         stages.SHA1.fullmatch(source), "PROFILE_IDENTITY")
    if profile_id == stages.PROFILE_IDS[1]:
        stages.linux_eligible(plan, windows_receipt, generation=generation, source=source)
    else:
        need(windows_receipt is None, "WINDOWS_FIRST")
    profile = next(p for p in plan["profiles"] if p["id"] == profile_id)
    need(sys.platform == ("win32" if profile_id.startswith("windows") else "linux"), "RUNNER_OS")
    disposition = read_disposition(plan, profile)
    if windows_receipt is not None:
        need(windows_receipt["stage_a"]["pre_use_disposition_sha256"] == hashlib.sha256(
            stages.pinned(DISPOSITION_PATH, DISPOSITION_PIN)).hexdigest(), "DISPOSITION_GENERATION")
    require_font_authority(disposition)
    verified_python = verified_existing_interpreter(profile, disposition)
    base = Path(os.environ["RUNNER_TEMP"])
    need(base.is_absolute() and base.is_dir() and
         not base.resolve().is_relative_to(ROOT.resolve()) and
         not ROOT.resolve().is_relative_to(base.resolve()), "RUNNER_SCRATCH")
    need(shutil.disk_usage(base).free >= MIN_FREE, "SCRATCH_CAPACITY")
    need(os.environ.get("GITHUB_ACTIONS") == "true" and
         os.environ.get("GITHUB_RUN_ATTEMPT") == "1" and
         os.environ.get("GITHUB_SHA") == source and
         os.environ.get("GITHUB_REF") != "refs/heads/feature/live-dev-workspace-20261023",
         "EXACT_HOSTED_SCOPE")
    receipt = None
    with tempfile.TemporaryDirectory(prefix="c5-pdfium-", dir=base) as directory:
        scratch = owned(Path(directory).resolve(), base)
        env = clean_env(scratch)
        git = tool_identity(disposition["git"]["path"], disposition["git"]["sha256"])
        actual = run((git, "rev-parse", "HEAD"), cwd=ROOT, env=env, seconds=10)
        need(actual.decode("ascii").strip() == source, "CHECKOUT_IDENTITY")
        need(not run((git, "status", "--porcelain", "--untracked-files=all"),
                     cwd=ROOT, env=env, seconds=10).strip(), "CHECKOUT_DIRTY")
        curl = tool_identity(disposition["curl"]["path"], disposition["curl"]["sha256"])
        version = run((curl, "-q", "--version"), cwd=scratch, env=env, seconds=10)
        match = re.match(rb"curl (\d+)\.(\d+)\.(\d+)", version)
        need(match and tuple(map(int, match.groups())) >= (8, 4, 0), "CURL_VERSION")
        acquisition = Acquisition(profile, scratch, curl, env)
        house, tools = scratch / "wheels", scratch / "toolchain"
        house.mkdir()
        tools.mkdir()
        budget = wheelcheck.InspectionBudget()
        a = [row for row in profile["rows"] if row["stage"] == "A"]
        b = [row for row in profile["rows"] if row["stage"] == "B"]
        smoke = [row for row in a if row["kind"] == "wheel"]
        for row in a:
            p = acquisition.get(row, house if row["kind"] == "wheel" else tools)
            inspect_wheel(p, row, plan, disposition, budget)
        pdf = next(row for row in smoke if row["name"] == "pypdfium2")
        native = native_linkage(house / pdf["filename"], profile, disposition, scratch, env)
        pip = next(row for row in a if row["kind"] == "pip")
        python = bootstrap_python(verified_python, tools / pip["filename"], scratch, env, disposition)
        lock = scratch / "smoke-lock.txt"
        lock.write_text(stages.smoke_lock(plan, profile_id), encoding="ascii")
        pip_meta = disposition["archives"][pip["filename"]]["wheel_expectation"]["metadata_sha256"]
        resolve_install(python, smoke, lock, house, scratch, env, pip_meta)
        need(verify_loaded_native(python, profile, scratch, env) == native, "NATIVE_IDENTITY")
        # Pure rehearsal must also have passed at the same source before
        # activation. Here the native case set remains the exact 19-node plan.
        expected = [plan["stage_a"]["test_file"] + "::" + node
                    for node in plan["stage_a"]["expected_node_ids"]]
        result = pytest_witness(python, plan["stage_a"]["test_file"],
                                scratch / "stage-a", env, expected)
        stage_a = dict(result, profile=profile_id, generation=generation, source=source,
                       stage="A", failed=[], skipped=[], xfailed=[], native_sha256=native,
                       pre_use_disposition_sha256=hashlib.sha256(
                           stages.pinned(DISPOSITION_PATH, DISPOSITION_PIN)).hexdigest())
        stages.stage_b_eligible(plan, stage_a, profile=profile_id, generation=generation, source=source)
        # Local A precedes local B. Reuse the same wheelhouse and venv.
        exact_inventory(python, smoke, scratch, env, pip_meta)
        extra = scratch / "supplemental"
        extra.mkdir()
        for row in b:
            if row["kind"] == "wheel":
                p = acquisition.get(row, house)
                inspect_wheel(p, row, plan, disposition, budget)
        rows = smoke + [r for r in b if r["kind"] == "wheel"]
        full_lock = ROOT / "backend/locks" / (profile_id + ".txt")
        resolve_install(python, rows, full_lock, house, scratch, env, pip_meta)
        need(verify_loaded_native(python, profile, scratch, env) == native, "NATIVE_IDENTITY")
        outcome = {}
        for number, command in enumerate(stages.stage_b_arguments(plan, python)):
            selection = command[-1]
            outcome[selection] = pytest_witness(python, selection, scratch / f"b-{number}", env)
        outcome.update(mixed_witness(python, scratch / "mixed-worker", env))
        for row in b:
            if row["kind"] != "wheel":
                acquisition.get(row, extra)
        outcome["font:equivalence"] = font_witness(python, scratch, env, disposition, b, extra)
        outcome["frontend:compatibility"] = frontend_witness(scratch, env, disposition, b, extra)
        receipt = {"profile": profile_id, "generation": generation, "source": source,
                   "attempt": 1, "state": "PASS", "stage_a": stage_a, "stage_b": outcome,
                   "archive_uses": len(acquisition.seen), "body_bytes": acquisition.body,
                   "requests": acquisition.requests, "cleanup": "OWNED_SCRATCH_REMOVED"}
    need(not scratch.exists(), "CLEANUP")
    stages.terminal_profile(plan, receipt, profile=profile_id, generation=generation, source=source)
    return receipt


def require_font_authority(disposition=None):
    if not isinstance(disposition, dict) or disposition.get("font_equivalence") != "REVIEWED_PINNED_SIX_FILES":
        raise RuntimeError("PINNED_FONT_EQUIVALENCE_UNRESOLVED")


def hosted_identity():
    require_live()
    source = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    need(stages.SHA1.fullmatch(source) and re.fullmatch(r"[0-9]{1,20}", run_id) and
         os.environ.get("GITHUB_RUN_ATTEMPT") == "1" and
         os.environ.get("GITHUB_ACTIONS") == "true", "HOSTED_GENERATION")
    generation = hashlib.sha256(f"{source}:{run_id}:1".encode("ascii")).hexdigest()
    return generation, source


def main():
    require_live()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=stages.PROFILE_IDS)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    need(bool(args.profile) != args.final, "COMMAND_SCOPE")
    generation, source = hosted_identity()

    def prior(key):
        raw = os.environ.get(key, "").encode("ascii")
        need(0 < len(raw) <= MAX_STATUS, "PRIOR_RECEIPT")
        return stages.strict_json(raw)

    if args.final:
        plan = stages.read_plan()
        stages.final_eligible(plan, [prior("C5_WINDOWS_RECEIPT"), prior("C5_LINUX_RECEIPT")],
                              generation=generation, source=source)
        print("C5_PDFIUM_BOTH_PLATFORM_EQUIVALENCE_PASS")
        return 0
    previous = prior("C5_WINDOWS_RECEIPT") if args.profile == stages.PROFILE_IDS[1] else None
    result = run_profile(args.profile, generation, source, previous)
    raw = json.dumps(result, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    need(len(raw.encode("ascii")) <= 400_000, "JOB_OUTPUT_CAP")
    # Only future reviewed Actions wiring can provide this owned runner output.
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.write("receipt=" + raw + "\n")
    print("C5_PDFIUM_PLATFORM_EQUIVALENCE_PASS", args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
