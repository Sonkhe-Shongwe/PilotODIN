"""Test what the pinned Procmon CSV exposes for one generated child."""
import argparse
import csv
import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_build as build
from qa.p4_research.n12_webview_storage_probe import process_start_environment, process_start_path


CONSENT = "I_APPROVE_ONE_N12_PROCMON_ENVIRONMENT_CONTROL"
PAYLOAD = b"PilotODIN generated environment control"
SEPARATOR_LABELS = {";": "semicolon", ",": "comma", "|": "pipe", "\t": "tab",
                    "\r\n": "crlf", "\r": "cr", "\n": "lf", "\0": "nul"}
SEPARATOR_PATTERN = r"( *)(\r\n|[;,|\t\r\n\0])( *)"
CHILD = """
import os
from pathlib import Path
import sys

tmp, temp, target = map(Path, sys.argv[1:])
assert Path(os.environ["TMP"]) == tmp
assert Path(os.environ["TEMP"]) == temp
with target.open("xb") as stream:
    stream.write(b"PilotODIN generated environment control")
"""


def capture(root):
    paths = {key: root / key.lower() for key in ("TMP", "TEMP")}
    for path in paths.values():
        path.mkdir()
    target = paths["TMP"] / "known-create.tmp"
    script = root / "environment-child.py"
    script.write_text(CHILD, encoding="ascii")
    args = [sys.executable, "-I", "-S", str(script), *map(str, paths.values()), str(target)]
    # Keep the exported control environment small and free of inherited CI variables.
    env = {key: str(path) for key, path in paths.items()}
    if os.name == "nt":
        env["SystemRoot"] = os.environ["SystemRoot"]
    with subprocess.Popen(args, cwd=root, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as child:
        try:
            trace.require(child.wait(timeout=10) == 0 and target.read_bytes() == PAYLOAD,
                          "generated child did not verify its environment and file")
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
            raise
    return {"pid": child.pid, "parent_pid": os.getpid(), "image": ntpath.basename(sys.executable),
            "command": subprocess.list2cmdline(args), "target": str(target),
            "paths": {key: str(p) for key, p in paths.items()}}


def boundary_shape(text, *, left):
    pattern = SEPARATOR_PATTERN + r"\Z" if left else r"\A" + SEPARATOR_PATTERN
    match = re.search(pattern, text)
    if match:
        before, separator, after = match.groups()
        label = SEPARATOR_LABELS[separator]
        if before:
            label += "-space-before"
        if after:
            label += "-space-after"
        return label, True
    if not text.strip(" "):
        return ("field-start" if left else "field-end"), True
    edge = text[-1] if left else text[0]
    return ("space-only" if edge == " " else "unrecognized"), False


def assignment_shape(environment, key, expected):
    """Report the shape around the known fixture value without publishing text."""
    tokens = list(re.finditer(rf"(?<![\w=]){key}([ \t]*)([=:])([ \t]*)", environment, re.I))
    if len(tokens) != 1:
        return {"token": "ambiguous" if tokens else "missing"}
    match = tokens[0]
    left, left_bounded = boundary_shape(environment[:match.start()], left=True)
    prefix, operator, suffix = match.groups()
    remainder = environment[match.end():]
    wrapper = remainder[:1]
    quote = wrapper if wrapper in ("'", '"') else ""
    literal = quote + expected + quote
    report = {
        "token": "unique", "before_key": left, "operator": "equals" if operator == "=" else "colon",
        "padding_before_operator": bool(prefix), "padding_after_operator": bool(suffix),
        "value_wrapper": {"": "none", "'": "single-quote", '"': "double-quote"}[quote],
        "expected_value": "not-found", "after_value": "unverified",
    }
    if remainder[:len(literal)].casefold() == literal.casefold():
        right, right_bounded = boundary_shape(remainder[len(literal):], left=False)
        report["after_value"] = right
        report["expected_value"] = "bounded-literal-match" if left_bounded and right_bounded else "unbounded-literal"
    return report


def inspect_rows(rows, child, start, end, *, private_timing=None):
    trace.require(start.date() == end.date() and start < end, "invalid same-day Procmon window")
    first, last = trace.utc_ticks(start), trace.utc_ticks(end)
    starts, creates = [], []
    expected_path = trace.windows_path(child["target"])
    for row in rows:
        trace.require(None not in row and all(value is not None for value in row.values()), "malformed Procmon row")
        if row["PID"] != str(child["pid"]) or row["Operation"] not in {"Process Start", "CreateFile"}:
            continue
        ticks = trace.etw_payload_ticks(f"{start.date()}T{row['Time of Day'].strip()}Z")
        if not first <= ticks <= last:
            continue
        same_image = row["Process Name"].casefold() == child["image"].casefold()
        if row["Operation"] == "Process Start":
            starts.append((ticks, row, same_image))
        elif same_image and trace.file_mutation(row) == "create":
            try:
                path = trace.windows_path(row["Path"])
            except ValueError:
                continue
            if path == expected_path:
                creates.append(ticks)

    report = {"process_start": "start-record-unobserved", "tmp": "unverified", "temp": "unverified",
              "environment_contents": "unverified", "key_rendering": {"tmp": "unverified", "temp": "unverified"},
              "assignment_shape": {},
              "known_create": "observed" if len(creates) == 1 else "unverified",
              "start_before_create": False}
    if len(starts) != 1:
        if starts:
            report["process_start"] = "start-record-ambiguous"
        return report

    stamp, row, same_image = starts[0]
    if not same_image or row["Result"].strip() != "SUCCESS":
        report["process_start"] = "start-image-or-result-unverified"
        return report
    status, environment = process_start_environment(row["Detail"], child["parent_pid"], child["command"])
    report["process_start"] = status
    report["start_before_create"] = len(creates) == 1 and stamp < creates[0]
    if private_timing is not None and len(creates) == 1:
        private_timing.update(process_start=stamp, create=creates[0])
    if environment is not None:
        report["environment_contents"] = "nonempty" if environment.strip(" \t\r\n;\0") else "empty"
        for key in ("TMP", "TEMP"):
            label = key.casefold()
            status, observed = process_start_path(environment, key)
            shape = assignment_shape(environment, key, child["paths"][key])
            rendering = "recognized-assignment"
            if status == f"{label}-not-observed":
                # A token is a format hint only. It does not verify a key or its value.
                rendering = "assignment-like-token" if shape["token"] != "missing" else "no-assignment-token"
            if observed is not None:
                status = "expected" if observed == trace.windows_path(child["paths"][key]) else "mismatch"
            report[label] = status
            report["key_rendering"][label] = rendering
            report["assignment_shape"][label] = shape
    return report


def replay_create_timing(rows, child, start, end, *, before, after, writer_guid, etw_creates):
    """Compare one Procmon create with the ETW reducer's verified create observations.

    ETW tuples contain a verified writer GUID, canonical path, request ticks and
    completion ticks. A future capture adapter supplies those from the same run.
    """
    if (type(before) is not int or type(after) is not int or
            not trace.utc_ticks(start) <= before < after <= trace.utc_ticks(end)):
        return {"status": "BLOCKED", "reason": "invalid-create-window"}
    if not isinstance(writer_guid, str) or not writer_guid:
        return {"status": "BLOCKED", "reason": "etw-writer-unverified"}
    timing = {}
    procmon = inspect_rows(rows, child, start, end, private_timing=timing)
    if (procmon["process_start"] != "environment-observed"
            or procmon["tmp"] != "expected" or procmon["temp"] != "expected"):
        return {"status": "BLOCKED", "reason": "procmon-start-unverified"}
    if procmon["known_create"] != "observed":
        return {"status": "BLOCKED", "reason": "procmon-create-missing-or-ambiguous"}
    target = trace.windows_path(child["target"])
    matching = [(requested, completed) for guid, path, requested, completed in etw_creates
                if guid == writer_guid and path == target]
    if len(matching) != 1:
        return {"status": "BLOCKED", "reason": "etw-create-missing-or-ambiguous"}
    requested, completed = matching[0]
    if type(requested) is not int or type(completed) is not int:
        return {"status": "BLOCKED", "reason": "invalid-etw-timestamp"}
    launch, create = timing["process_start"], timing["create"]
    stamps = {"procmon_create": create, "etw_request": requested, "etw_completion": completed}
    report = {
        "procmon_minus_etw_request_ticks": create - requested,
        "procmon_minus_etw_completion_ticks": create - completed,
        "from_open_begin_ticks": {label: stamp - before for label, stamp in stamps.items()},
        "to_open_return_ticks": {label: after - stamp for label, stamp in stamps.items()},
    }
    if not all(before <= stamp <= after for stamp in stamps.values()):
        return {**report, "status": "BLOCKED", "reason": "create-timestamp-outside-window"}
    if not (launch < min(create, requested) and requested < completed):
        return {**report, "status": "BLOCKED", "reason": "create-order-unverified"}
    return {**report, "status": "PASS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "reduce"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    try:
        env = os.environ
        source = env.get("PILOTODIN_N12_PROCMON_ENVIRONMENT_SOURCE", "")
        trace.require(env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_RUN_ATTEMPT") == "1"
                      and env.get("GITHUB_REF_NAME") == build.BRANCH
                      and env.get("PILOTODIN_N12_PROCMON_ENVIRONMENT_CONSENT") == CONSENT
                      and re.fullmatch(r"[0-9a-f]{40}", source)
                      and build.git("rev-parse", "HEAD") == source,
                      "exact-source hosted Process Monitor approval required")
        root = trace.local_disposable_path(args.root, runner_temp_only=True)
        control_path = root / "private-environment-child.json"
        if args.action == "capture":
            with control_path.open("x", encoding="utf-8") as stream:
                json.dump(capture(root), stream)
            print("Generated child verified both environment values and its known create.")
            return 0
        with trace.evidence_stage("Process Monitor environment control"):
            child = trace.read_json(control_path)
            window = trace.read_json(root / "environment-window.json")
            trace.require(window["clock_utc"] is True, "Procmon host clock was not UTC")
            with (root / "capture-utf8.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = csv.DictReader(stream, strict=True)
                trace.require({"Time of Day", "PID", "Process Name", "Operation", "Path", "Result", "Detail"}
                              <= set(rows.fieldnames or ()), "Procmon export columns missing")
                result = inspect_rows(rows, child, trace.utc_time(window["start_utc"]),
                                      trace.utc_time(window["end_utc"]))
            observed = (result["tmp"] == result["temp"] == "expected" and result["start_before_create"])
            shutdown_verified = window["shutdown_verified"] is True
            passed = observed and shutdown_verified
            print(json.dumps({**result, "scope": "one-generated-child", "source_sha": source,
                              "shutdown_verified": shutdown_verified, "loss_reviewed": False,
                              "status": "PASS" if passed else "BLOCKED"}, sort_keys=True))
            return 0 if passed else 2
    except trace.EvidenceValidationError as exc:
        print(f"N12 Process Monitor environment control blocked: {exc}", file=sys.stderr)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"N12 Process Monitor environment control blocked: {type(exc).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
