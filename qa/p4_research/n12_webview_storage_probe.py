"""Attribute WebView2 storage in one approved startup and close capture."""
import argparse
from collections import Counter
import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from qa.p4_native import n12_trace as trace
from qa.p4_native.n12_exit_corroboration import EtwLifetimes, SOURCE_COVERAGE_ISSUES
from qa.p4_research import n12_app_journey as journey
from qa.p4_research import n12_app_lifetime as lifetime
from qa.p4_research.n12_journey_diagnostics import FILE_TYPES, WEBVIEW_ROLES


PROBE_DIR = "storage"
STAGES = ("launch", "ready", "close", "profile-exit")
CONTROL = (
    "from pathlib import Path; import sys, time; "
    "time.sleep(0.5); "
    "f = Path(sys.argv[1]).open('xb'); f.write(b'PilotODIN control'); f.close(); "
    "time.sleep(0.5)"
)


def unresolved_family_counts(unresolved_files):
    """Diagnostic-only counts; never filters the blocking unresolved records."""
    return (
        sum(row["count"] for row in unresolved_files if row["kind"] == "named-pipe"),
        sum(row["count"] for row in unresolved_files if row["kind"] != "named-pipe"),
    )


def file_control(manifest, label, path, *, env=None):
    with subprocess.Popen([sys.executable, "-B", "-c", CONTROL, str(path)],
                          env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as child:
        try:
            trace.require(child.wait(timeout=10) == 0 and path.read_bytes() == b"PilotODIN control",
                          "generated file control did not write its expected bytes")
        finally:
            journey.cleanup_process(child)
        manifest["processes"].append({"role": "calibration", "pid": child.pid, "image": sys.executable,
                                      "label": label, "target": str(path)})


def runner_control_temp(env):
    inherited = Path(env["TEMP"])
    trace.require(inherited.is_absolute() and ".." not in inherited.parts,
                  "inherited temp is not an absolute local directory")
    ambient = inherited.resolve(strict=True)
    if os.name == "nt":
        trace.windows_path(str(ambient))
    user_temp = Path(env["LOCALAPPDATA"]).resolve(strict=True) / "Temp"
    runner_temp = Path(env["RUNNER_TEMP"]).resolve(strict=True)
    trace.require(ambient.is_dir(), "inherited temp does not resolve to a directory")
    trace.require(ambient.is_relative_to(user_temp) or ambient.is_relative_to(runner_temp),
                  "resolved temp is outside the hosted user-temp and runner-temp roots")
    return ambient


def capture(root, staged, node, source, expected_hash, *, variant="debug-netlog"):
    trace.require(variant in lifetime.STORAGE_DIAGNOSTIC_VARIANTS,
                  "unknown WebView storage diagnostic variant")
    ambient = runner_control_temp(os.environ)
    manifest, _, profile, fixture, _ = journey.prepare_journey(root, source, expected_hash)
    tmp_witness = profile / journey.APP_TEMP_DIR / lifetime.STORAGE_TMP_DIR
    tmp_witness.mkdir()
    manifest["probe_user_temp"] = str(ambient)
    manifest["startup_tmp_probe"] = True
    manifest["storage_diagnostic_variant"] = variant
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    trace.require(re.fullmatch(r"[1-9][0-9]{0,18}", run_id) is not None
                  and os.environ.get("GITHUB_RUN_ATTEMPT") == "1",
                  "one-use GitHub capture identity is not verified")
    manifest["storage_capture_run_id"] = run_id
    manifest["storage_capture_attempt"] = 1
    fixture.write_text("fixture,value\nwebview-storage,1\n", encoding="utf-8")
    before = journey.snapshots(manifest)
    journey.mark(manifest, "fixture-ready")
    file_control(manifest, "scratch", profile / journey.APP_TEMP_DIR / "storage-control.tmp",
                 env={**os.environ, "TMP": str(tmp_witness)})
    lifetime.launch_and_close(root, staged, node, source, expected_hash, storage_manifest=manifest)
    with TemporaryDirectory(prefix="pilotodin-storage-control-", dir=ambient) as folder:
        file_control(manifest, "user-temp", Path(folder) / "storage-control.tmp")
    snapshot, issues = trace.compare_snapshots(before, journey.snapshots(manifest), manifest)
    manifest["protected_snapshot_comparison"] = snapshot["protected_snapshot_comparison"]
    manifest["snapshot_issues"] = sorted(issues)
    journey.report_file(root / "private-storage-capture.json", manifest)


def component(process, role, browser_guid):
    if process.guid == browser_guid:
        return "browser"
    if role == "webview-network":
        return "network-service"
    matches = re.findall(r"(?:^|\s)--type=([a-z-]+)(?=\s|$)", process.command)
    return matches[0] if len(matches) == 1 and matches[0] in {"renderer", "gpu-process", "utility"} else "unclassified"


def process_start_environment(detail, parent_pid, command):
    """Bind the exported environment to a known parent and command."""
    match = re.fullmatch(
        r"Parent PID: (\d+), Command line: (.*?), Current directory: (.*)", detail, re.S,
    )
    if match is None:
        return "start-detail-unrecognized", None
    if (parent_pid is None or int(match[1]) != parent_pid
            or not command.strip() or match[2].strip() != command.strip()):
        return "start-identity-mismatch", None
    _, separator, environment = match[3].partition(", Environment:")
    if not separator:
        return "environment-field-unobserved", None
    return "environment-observed", environment


def redacted_environment_format(detail, parent_pid, command):
    """Distinguish absent Procmon keys from unparseable assignment shapes.

    These are token-format hints, never evidence of inherited environment values.
    Return fixed labels only; do not leak the raw Detail or environment payload.
    """
    keys = ("TEMP", "TMP", "WEBVIEW2_USER_DATA_FOLDER")
    status, environment = process_start_environment(detail, parent_pid, command)
    if environment is None:
        return {"receipt": status, "contents": "unverified",
                "keys": {key.casefold(): "unverified" for key in keys}}
    contents = "nonempty" if environment.strip(" \t\r\n;\0") else "empty"
    findings = {}
    for key in keys:
        matches = list(re.finditer(
            rf"(?<![A-Za-z0-9_=]){key}[ \t]*([=:])", environment, re.I,
        ))
        if not matches:
            label = "assignment-token-absent"
        elif len(matches) > 1:
            label = "assignment-token-ambiguous"
        else:
            preceding = environment[:matches[0].start()]
            bounded = (not preceding.strip(" \t\r\n;\0") or
                       re.search(r"(?:\r\n|[;,|\t\r\n\0])[ \t]*$", preceding) is not None)
            if not bounded:
                label = "unbounded-assignment-like-token"
            else:
                label = "equals-token" if matches[0][1] == "=" else "colon-token"
        findings[key.casefold()] = label
    return {"receipt": "environment-observed", "contents": contents, "keys": findings}


def process_start_path(environment, key):
    # Procmon 4.13 can put a tab directly before an environment assignment.
    fields = re.split(r" ; |\r?\n|\t", environment)
    label = key.casefold()
    values = []
    for field in fields:
        name, separator, value = field.lstrip(" ").partition("=")
        if separator and name.casefold() == label:
            values.append(value)
    if not values:
        return f"{label}-not-observed", None
    if len(values) > 1:
        return f"{label}-ambiguous", None
    try:
        trace.require("\r" not in values[0] and "\0" not in values[0], "invalid environment path field")
        return f"{label}-observed", trace.windows_path(values[0])
    except (ValueError, trace.EvidenceValidationError):
        return f"{label}-path-invalid", None


def storage_environment_context(detail, process, parent, profile, app_temp, ambient, witness):
    """Classify only verified Process Start environment paths, never publish their values."""
    names = (("temp", "TEMP"), ("tmp", "TMP"), ("udf", "WEBVIEW2_USER_DATA_FOLDER"))
    status, environment = process_start_environment(
        detail, parent.pid if parent else None, process.command,
    )
    if environment is None:
        return {"receipt": status, **{name: "unverified" for name, _ in names}}
    context = {"receipt": "environment-observed"}
    for name, key in names:
        path_status, path = process_start_path(environment, key)
        if path is None:
            context[name] = path_status
        elif name == "udf":
            context[name] = ("declared-profile" if path == profile
                             else "profile-subpath" if trace.inside(path, profile) else "other-path")
        elif witness is not None and trace.inside(path, witness):
            context[name] = "startup-tmp"
        elif trace.inside(path, app_temp):
            context[name] = "declared-app-temp"
        elif trace.inside(path, profile):
            context[name] = "other-profile-location"
        elif ambient is not None and trace.inside(path, ambient):
            context[name] = "ambient-temp"
        else:
            context[name] = "other-path"
    return context


def process_start_tmp(detail, process, parent):
    status, environment = process_start_environment(detail, parent.pid if parent else None, process.command)
    return (status, None) if environment is None else process_start_path(environment, "TMP")


def replay_startup_creates(manifest, etw, start, ready, processes, roles, browser_guid, receipt,
                           destination_roots, capture_issues):
    """Join a verified Procmon TMP receipt to completed ETW creates for the same browser."""
    if receipt is None:
        return {"status": "procmon-tmp-receipt-unverified"}
    if capture_issues & (SOURCE_COVERAGE_ISSUES | {"procmon-capture-configuration-unverified"}):
        return {"status": "source-coverage-unverified"}
    browser = processes[browser_guid]
    receipt_time, launch_tmp = receipt
    if receipt_time < browser.start:
        return {"status": "procmon-start-before-browser-lifetime"}
    receipt_ticks, ready_ticks = trace.utc_ticks(receipt_time), trace.utc_ticks(ready)
    destination_families = set()
    identity = "etw-browser-lifetime-unverified"

    def observe_lifetimes(events, devices, window, issues):
        nonlocal identity
        if "etw-event-or-buffer-loss" in issues:
            identity = "etw-event-or-buffer-loss"
            return
        lifetimes = EtwLifetimes(events, devices, window)
        starts = lifetimes.starts[browser.pid]
        if (len(starts) != 1 or not starts[0].creation <= receipt_ticks
                or starts[0].emission < starts[0].creation
                or any(min(stop.emission, stop.exit) < ready_ticks for stop in lifetimes.stops[browser.pid])):
            return
        identity = lifetimes.parent_sequence_comparison(browser, processes.get(browser.parent))

    def observe_create(guid, target, requested, completed):
        if (guid == browser_guid and receipt_ticks < requested < completed < ready_ticks
                and ntpath.splitext(target)[1] == ".tmp"):
            family = next((label for label, base in destination_roots if trace.inside(target, base)), "other-path")
            destination_families.add(family)

    try:
        trace.inspect_etw_files(
            manifest, etw, start, ready, processes, roles, (), {}, set(),
            observe_lifetimes=observe_lifetimes, observe_create=observe_create,
        )
    except trace.EvidenceValidationError:
        return {"status": "etw-evidence-invalid"}
    if identity != "etw-parent-sequence-agrees":
        return {"status": identity}
    if not destination_families:
        return {"status": "no-matched-etw-startup-create"}
    return {"status": "matched", "launch_tmp": launch_tmp, "destination_families": sorted(destination_families)}


def reduce(root, staged, manifest, sysmon, procmon, *, replay_etw=None):
    variant = manifest.get("storage_diagnostic_variant", "debug-netlog")
    trace.require(variant in lifetime.STORAGE_DIAGNOSTIC_VARIANTS,
                  "unknown WebView storage diagnostic variant")
    start, end, processes, _, issues = trace.load_capture(manifest, sysmon)
    # This is a direct-path diagnosis. Track the existing capture-loss limitation separately.
    loss_reviewed = "procmon-coverage-not-confirmed" not in issues
    issues.discard("procmon-coverage-not-confirmed")
    shutdown_verified = manifest.get("procmon_shutdown_verified") is True
    if not shutdown_verified:
        issues.add("procmon-shutdown-unverified")
    if not manifest["procmon_all_events"] or not manifest["procmon_clock_utc"]:
        issues.add("procmon-capture-configuration-unverified")
    protected, permitted = trace.scope(manifest)
    immutable = [trace.windows_path(manifest["observed_roots"][key]) for key in manifest["immutable_observed"]]
    protected.extend(immutable)
    declared = [item for item in manifest["processes"] if item["role"] in {"app", "calibration"}]
    roles, bindings = trace.bind_processes(declared, processes, issues)
    apps = [process for binding, process in bindings if binding["role"] == "app"]
    app_verified = len(apps) == 1 and apps[0].sha256 == manifest["executable_sha256"]
    if not app_verified:
        issues.add("app-source-identity-unverified")
    webviews = [process for guid, process in processes.items() if roles.get(guid) in WEBVIEW_ROLES]
    if not webviews:
        issues.add("webview-process-lifetime-unverified")
    runtime_dirs = {ntpath.basename(ntpath.dirname(process.image)) for process in webviews}
    versions = {version for version in runtime_dirs if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version)}
    if len(versions) != 1 or versions != runtime_dirs:
        issues.add("webview-runtime-version-unverified")
    launch, ready, close, exited = (trace.utc_time(manifest["markers"][name]) for name in STAGES)
    fixture_ready = trace.utc_time(manifest["markers"]["fixture-ready"])
    trace.require(start <= fixture_ready < launch < ready <= close < exited <= end,
                  "storage probe stages out of order")
    browser_pid = manifest.get("cdp_browser_pid")
    browser_guid = None
    if app_verified and type(browser_pid) is int and browser_pid > 0:
        candidates = [p for p in processes.values() if p.pid == browser_pid and p.start <= close
                      and (p.end is None or p.end >= ready)]
        if len(candidates) == 1:
            candidate = candidates[0]
            if (roles.get(candidate.guid) == "webview" and candidate.start <= ready
                    and candidate.end is not None and candidate.end >= close
                    and not re.search(r"(?:^|\s)--type(?:[=\s]|$)", candidate.command)):
                browser_guid = candidate.guid
    expected = {binding["label"]: (process.guid, trace.windows_path(binding["target"]))
                for binding, process in bindings if binding["role"] == "calibration"}
    control_creates = {}
    diagnostics = Counter()
    paths = journey.diagnostic_paths(root, staged, manifest, user_temp=manifest.get("probe_user_temp"))
    app_temp = tmp_witness = None
    if manifest.get("startup_tmp_probe") is True:
        profile = trace.windows_path(manifest["observed_roots"]["qa-webview"])
        app_temp = ntpath.join(profile, journey.APP_TEMP_DIR)
        tmp_witness = ntpath.join(app_temp, lifetime.STORAGE_TMP_DIR)
    startup_candidates = {}
    if tmp_witness is not None:
        scratch = next((process for binding, process in bindings if binding.get("label") == "scratch"), None)
        pid_counts = Counter(process.pid for process in processes.values())
        for label, process, first, last in (
            ("scratch", scratch, fixture_ready, launch),
            ("browser", processes.get(browser_guid), launch, ready),
        ):
            if process is not None and pid_counts[process.pid] == 1:
                startup_candidates[str(process.pid)] = (label, process, first, last)
    # The dedicated TMP control remains independent. This second diagnostic
    # links each WebView writer to its own uniquely identified Process Start.
    pid_counts_all = Counter(process.pid for process in processes.values())
    webview_start_candidates = {
        str(process.pid): process for process in webviews if pid_counts_all[process.pid] == 1
    }
    webview_start_receipts = {process.guid: [] for process in webviews}
    webview_start_formats = {process.guid: [] for process in webviews}
    startup_formats = {"scratch": [], "browser": []}
    storage_profile = trace.windows_path(manifest["observed_roots"]["qa-webview"])
    storage_app_temp = ntpath.join(storage_profile, journey.APP_TEMP_DIR)
    storage_ambient = (trace.windows_path(manifest["probe_user_temp"])
                       if manifest.get("probe_user_temp") else None)
    writer_operations = Counter()
    # Private normalized path strings are held in memory only. The public
    # receipt reports numeric cardinality and cross-stage lexical reuse, never
    # a filename, path hash, PID or per-target record.
    browser_ambient_target_stages = {}
    startup_values = {"scratch": [], "browser": []}
    first_browser_tmp_create = None
    protected_details = Counter()

    def observe_protected(role, operation, targets, identity):
        families = {"immutable-input" if any(trace.inside(target, path) for path in immutable)
                    else "protected-app-data" for target in targets}
        for family in families:
            protected_details[role, operation, family, identity] += 1

    def observe_process_start(row):
        if row["Result"] != "SUCCESS":
            return
        candidate = startup_candidates.get(row["PID"])
        webview_process = webview_start_candidates.get(row["PID"])
        if candidate is None and webview_process is None:
            return
        try:
            stamp = trace.capture_time(row["Time of Day"], start)
        except (ValueError, trace.EvidenceValidationError):
            return
        if candidate is not None:
            label, process, first, last = candidate
            if (row["Process Name"].casefold() == ntpath.basename(process.image)
                    and first <= stamp < last):
                status, value = process_start_tmp(row["Detail"], process, processes.get(process.parent))
                startup_values[label].append((stamp, status, value))
                startup_formats[label].append(redacted_environment_format(
                    row["Detail"], processes.get(process.parent).pid
                    if processes.get(process.parent) else None, process.command,
                ))
        if webview_process is not None:
            process = webview_process
            if (row["Process Name"].casefold() == ntpath.basename(process.image)
                    and process.start <= stamp <= (process.end or end)):
                webview_start_receipts[process.guid].append(storage_environment_context(
                    row["Detail"], process, processes.get(process.parent),
                    storage_profile, storage_app_temp, storage_ambient, tmp_witness,
                ))
                webview_start_formats[process.guid].append(redacted_environment_format(
                    row["Detail"], processes.get(process.parent).pid
                    if processes.get(process.parent) else None, process.command,
                ))

    def observe(stamp, process, role, operation, path):
        nonlocal first_browser_tmp_create
        if operation == "create" and role == "calibration":
            for label, identity in expected.items():
                if identity == (process.guid, path) and (
                    (label == "scratch" and stamp < launch) or (label == "user-temp" and exited < stamp)
                ):
                    control_creates[label] = min(control_creates.get(label, stamp), stamp)
        if role not in WEBVIEW_ROLES or operation not in {"create", "overwrite", "write"}:
            return
        stage = ("startup" if stamp < ready else "ready-probe" if stamp < close else
                 "close" if stamp <= exited else "after-profile-exit")
        extension = ntpath.splitext(path)[1]
        if process.guid == browser_guid and stage == "startup" and operation == "create" and extension == ".tmp":
            first_browser_tmp_create = min(first_browser_tmp_create or stamp, stamp)
        category = next((label for label, base in paths.roots if trace.inside(path, base)), None)
        if (app_temp is not None and stage == "startup" and operation == "create"
                and extension == ".tmp" and trace.inside(path, app_temp)):
            family = "startup-tmp" if trace.inside(path, tmp_witness) else "qa-app-temp"
        elif category in {"user-temp", "runner-temp"}:
            if operation != "create":
                return
            family = category
        elif category == "user-local":
            family = next((label for label, base in paths.webview_local_families if trace.inside(path, base)),
                          "other-user-local")
        else:
            return
        if (process.guid == browser_guid and operation == "create"
                and family in {"user-temp", "runner-temp"}):
            normalized_path = ntpath.normcase(path)
            browser_ambient_target_stages.setdefault(normalized_path, set()).add(stage)
        file_type = FILE_TYPES.get(extension, "other-extension" if extension else "no-extension")
        diagnostics[family, operation, component(process, role, browser_guid), stage, file_type] += 1
        writer_operations[process.guid, family, operation, stage] += 1

    file_coverage_issues = set()
    _, violations, _, unresolved_files = trace.inspect_files(
        procmon, fixture_ready, end, processes, roles, protected, permitted, file_coverage_issues, observe=observe,
        observe_process_start=observe_process_start if startup_candidates or webview_start_candidates else None,
        observe_protected=observe_protected,
    )
    protected_operations = []
    for key, count in sorted(violations.items()):
        if key.startswith("protected:"):
            _, role, operation = key.split(":")
            protected_operations.append({"role": role, "operation": operation, "count": count})
    controls = {name: name in control_creates for name in ("scratch", "user-temp")}
    if not all(controls.values()):
        issues.add("known-create-controls-unverified")
    startup_receipts = {}
    # Compare timestamps within the Procmon export. Equal times cannot prove order.
    first_creates = {"scratch": control_creates.get("scratch"), "browser": first_browser_tmp_create}
    for label, records in startup_values.items():
        if len(records) == 1:
            stamp, status, _ = records[0]
            first_create = first_creates[label]
            startup_receipts[label] = (
                "start-order-unverified" if status == "tmp-observed" and first_create is not None
                and stamp >= first_create else status
            )
        elif records:
            startup_receipts[label] = "start-record-ambiguous"
        elif any(candidate[0] == label for candidate in startup_candidates.values()):
            startup_receipts[label] = "start-record-unobserved"
        else:
            startup_receipts[label] = "start-identity-unverified"
    scratch_record = startup_values["scratch"]
    scratch_matches = (startup_receipts["scratch"] == "tmp-observed"
                       and tmp_witness is not None and scratch_record[0][2] == tmp_witness)
    if scratch_matches:
        startup_receipts["scratch"] = "expected-tmp" if controls["scratch"] else "file-control-unverified"
    elif startup_receipts["scratch"] == "tmp-observed":
        startup_receipts["scratch"] = "tmp-value-mismatch"
    tmp_control_verified = scratch_matches and controls["scratch"]
    browser_startup_tmp = "unverified"
    if tmp_control_verified and startup_receipts["browser"] == "tmp-observed":
        _, _, observed = startup_values["browser"][0]
        if observed is not None:
            ambient = manifest.get("probe_user_temp")
            labels = {tmp_witness: "expected-tmp", app_temp: "app-temp"}
            if ambient is not None:
                labels[trace.windows_path(ambient)] = "ambient-temp"
            browser_startup_tmp = labels.get(observed, "different")
    if "file-event-process-ambiguous" in file_coverage_issues:
        issues.add("file-event-process-ambiguous")
    if (manifest["protected_snapshot_comparison"] != "MATCH" or
            "protected-create-result-unresolved" in file_coverage_issues or
            protected_operations):
        issues.add("protected-files-changed-or-unverified")
    rows = [{"destination_family": family, "operation": operation, "component": kind,
             "stage": stage, "file_type": file_type, "count": count}
            for (family, operation, kind, stage, file_type), count in sorted(diagnostics.items())]
    ambient_creates = sum(row["count"] for row in rows if row["destination_family"] in {"user-temp", "runner-temp"})
    browser_ambient_creates = sum(
        row["count"] for row in rows
        if row["component"] == "browser" and row["operation"] == "create"
        and row["destination_family"] in {"user-temp", "runner-temp"}
    )
    browser_ambient_target_summary = {
        "scope": "observed-browser-ambient-createfile-only",
        "observed_create_events": browser_ambient_creates,
        "distinct_normalized_path_count": len(browser_ambient_target_stages),
        "normalized_paths_seen_in_multiple_stages": sum(
            len(stages) > 1 for stages in browser_ambient_target_stages.values()
        ),
        "filesystem_object_identity_verified": False,
        "capture_completeness_verified": False,
    }

    def verified_writer_context(process):
        if pid_counts_all[process.pid] != 1:
            state = "process-lifetime-ambiguous"
        else:
            receipts = webview_start_receipts[process.guid]
            if len(receipts) == 1:
                return receipts[0]
            state = "start-record-ambiguous" if receipts else "start-record-unobserved"
        return {"receipt": state, "temp": "unverified", "tmp": "unverified", "udf": "unverified"}

    writer_context_counts = Counter()
    for (guid, family, operation, stage), count in writer_operations.items():
        process = processes[guid]
        context = verified_writer_context(process)
        writer_context_counts[(
            component(process, roles.get(guid), browser_guid),
            context["receipt"], context["temp"], context["tmp"], context["udf"],
            family, operation, stage,
        )] += count
    writer_storage_context = [
        dict(zip(("component", "receipt", "temp", "tmp", "udf",
                  "destination_family", "operation", "stage"), key), count=count)
        for key, count in sorted(writer_context_counts.items())
    ]
    def observed_format(records):
        if len(records) == 1:
            return records[0]
        return {"receipt": "start-record-ambiguous" if records else "start-record-unobserved",
                "contents": "unverified",
                "keys": {key: "unverified" for key in ("temp", "tmp", "webview2_user_data_folder")}}

    browser_environment_format = observed_format(
        webview_start_formats[browser_guid] if browser_guid is not None else [],
    )
    scratch_environment_format = observed_format(startup_formats["scratch"])
    browser_launch_flags = {"status": "browser-identity-unverified"}
    browser_storage_context = {"receipt": "browser-identity-unverified",
                               "temp": "unverified", "tmp": "unverified", "udf": "unverified"}
    if browser_guid is not None:
        browser = processes[browser_guid]
        browser_storage_context = verified_writer_context(browser)
        browser_launch_flags = {
            "status": verified_writer_context(browser)["receipt"],
            "remote_debugging": "present" if re.search(
                r"(?:^|\s)--remote-debugging-port(?:=|\s|$)", browser.command
            ) else "absent",
            "netlog": "present" if re.search(
                r"(?:^|\s)--log-net-log(?:=|\s|$)", browser.command
            ) else "absent",
        }
    # The variant label is a capture declaration, not proof that WebView2
    # applied its flags. Require the independently captured browser command
    # and uniquely identified Process Start receipt before corroboration.
    if browser_launch_flags["status"] != "environment-observed":
        variant_corroboration = "unverified"
    elif browser_launch_flags["remote_debugging"] != "present":
        variant_corroboration = "disagrees"
    elif browser_launch_flags["netlog"] == ("present" if variant == "debug-netlog" else "absent"):
        variant_corroboration = "agrees"
    else:
        variant_corroboration = "disagrees"
    if any(row["stage"] == "after-profile-exit" for row in rows):
        issues.add("webview-writes-after-profile-exit")
    named_pipe_unresolved, other_path_unresolved = unresolved_family_counts(unresolved_files)
    collector_exit_status = manifest.get("procmon_capture_exit_status")
    if collector_exit_status not in {"EXITED", "NONZERO_EXIT", "TIMEOUT"}:
        collector_exit_status = "unverified"
    report = {"scope": "one-startup-and-close-storage-diagnostic",
            "storage_diagnostic_variant": variant,
            "browser_variant_corroboration": variant_corroboration,
            "source_sha": manifest["source_sha"],
            "executable_sha256": manifest["executable_sha256"],
            "storage_capture_run_id": manifest.get("storage_capture_run_id"),
            "storage_capture_attempt": manifest.get("storage_capture_attempt"),
            "verdict": "BLOCKED" if issues else "REPRODUCED" if ambient_creates else "INCONCLUSIVE",
            "issues": sorted(issues), "procmon_shutdown_verified": shutdown_verified,
            "procmon_stop_command_verified": manifest.get("procmon_stop_command_verified") is True,
            "procmon_capture_exit_status": collector_exit_status,
            "procmon_loss_reviewed": loss_reviewed,
            "file_coverage_issues": sorted(file_coverage_issues),
            "protected_snapshot_comparison": manifest["protected_snapshot_comparison"],
            "protected_operations": protected_operations, "unresolved_file_events": unresolved_files,
            "named_pipe_unresolved_event_count": named_pipe_unresolved,
            "other_unresolved_path_event_count": other_path_unresolved,
            "named_pipe_events_excluded_from_coverage": False,
            "protected_operation_details": [
                {"role": role, "operation": operation, "target": family, "identity": identity, "count": count}
                for (role, operation, family, identity), count in sorted(protected_details.items())
            ],
            "startup_tmp_probe": manifest.get("startup_tmp_probe") is True,
            "startup_tmp_control_verified": tmp_control_verified,
            "startup_tmp_receipts": startup_receipts,
            "browser_startup_tmp": browser_startup_tmp,
            "browser_process_corroborated": browser_guid is not None,
            "webview_runtime_versions": sorted(versions), "known_create_controls": controls,
            "ambient_temp_creates": ambient_creates, "storage_events": rows,
            "browser_ambient_target_summary": browser_ambient_target_summary,
            "writer_storage_context": writer_storage_context,
            "browser_storage_context": browser_storage_context,
            "browser_environment_format": browser_environment_format,
            "scratch_environment_format": scratch_environment_format,
            "browser_launch_flags": browser_launch_flags,
            "storage_context_is_acceptance_evidence": False}
    if replay_etw is not None:
        receipt = ((startup_values["browser"][0][0], browser_startup_tmp)
                   if browser_startup_tmp != "unverified" else None)
        roots = [("startup-tmp", tmp_witness), ("qa-app-temp", app_temp)] if tmp_witness is not None else []
        report["startup_tmp_etw"] = replay_startup_creates(
            manifest, replay_etw, start, ready, processes, roles, browser_guid, receipt, roots + paths.roots, issues,
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "reduce"))
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-exe-sha256", required=True)
    parser.add_argument("--diagnostic-variant", choices=lifetime.STORAGE_DIAGNOSTIC_VARIANTS,
                        default="debug-netlog")
    args = parser.parse_args()
    try:
        trace.require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
                      and args.source == os.environ.get("PILOTODIN_N12_APPROVED_SOURCE"),
                      "the storage diagnostic requires its first source-pinned run")
        _, staged, _, node = lifetime.preflight(args.source, args.expected_exe_sha256, storage=True)
        base = trace.local_disposable_path(args.capture_root, runner_temp_only=True)
        root = base / PROBE_DIR
        if args.action == "capture":
            with journey.checkpoint_stage("webview-storage-launch-and-controls", args.source, args.expected_exe_sha256):
                capture(root, staged, node, args.source, args.expected_exe_sha256,
                        variant=args.diagnostic_variant)
            return 0
        manifest = trace.read_json(root / "private-storage-capture.json")
        trace.require(manifest["source_sha"] == args.source and manifest["executable_sha256"] == args.expected_exe_sha256,
                      "storage capture provenance mismatch")
        trace.require(manifest.get("storage_diagnostic_variant", "debug-netlog") == args.diagnostic_variant,
                      "requested storage variant disagrees with captured variant")
        window = trace.read_json(base / "storage-window.json")
        manifest.update({key: window[key] for key in (
            "schema_version", "disposable", "start_utc", "end_utc", "sysmon_first_record",
            "sysmon_last_record", "procmon_all_events", "procmon_loss_reviewed", "procmon_clock_utc",
        )})
        manifest["procmon_shutdown_verified"] = window.get("procmon_shutdown_verified")
        manifest["procmon_stop_command_verified"] = window.get("procmon_stop_command_verified")
        manifest["procmon_capture_exit_status"] = window.get("procmon_capture_exit_status")
        with journey.checkpoint_stage("webview-storage-reduction", args.source, args.expected_exe_sha256):
            report = reduce(root, staged, manifest, base / "sysmon.xml", base / "capture-utf8.csv")
        print("N12 WebView storage " + json.dumps(report), flush=True)
        return 2 if report["verdict"] == "BLOCKED" else 0
    except trace.EvidenceValidationError as exc:
        print(f"N12 WebView storage blocked: {exc}", file=sys.stderr)
    except (*trace.EVIDENCE_ERRORS, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"N12 WebView storage blocked: {type(exc).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
