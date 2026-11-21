"""Compare disposable Windows driver-like process exits with retained handles."""

from collections import Counter
import json
import ntpath
import os
from pathlib import Path
import shutil
import subprocess
import time

from qa.p4_native import n12_etw_probe, n12_lifetime_control as lifetime, n12_lifetime_etw as etw
from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_journey as journey


HISTORICAL_DELTA_TICKS = -7 * lifetime.MILLISECOND
KINDS = {"cmd.exe": "cmd", "node.exe": "node", "powershell.exe": "powershell", "conhost.exe": "conhost"}


def candidates(root):
    system = Path(os.environ["SystemRoot"]) / "System32"
    node = shutil.which("node.exe")
    trace.require(node is not None, "driver-control-node-unavailable")
    script = root / "driver-exit-fixture.ps1"
    with script.open("x", encoding="ascii") as stream:
        stream.write("$null = [Console]::ReadLine()\nexit 0\n")
    return (
        ("cmd", [str(system / "cmd.exe"), "/d", "/q"], b"exit /b 0\r\n"),
        ("powershell", [str(system / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
                        "-NoProfile", "-NonInteractive", "-STA", "-File", str(script)], b"1\r\n"),
        ("node", [node, "-e", "process.stdin.once('data', () => process.exit(0));"], b"1\r\n"),
    )


def exit_pair(birth, exits, expected_image):
    if len(exits) != 1 or exits[0]["pid"] != birth["pid"] or exits[0]["guid"] != birth["guid"]:
        return {"exit_count": len(exits), "identity_matches": False}
    stop = exits[0]
    try:
        image = trace.sysmon_image(stop["image"], 5, stop["record"], birth_image=expected_image)
        form = "birth-image-match" if image == expected_image else "different-image"
        unsupported = False
    except trace.InvalidSysmonImage as exc:
        form = exc.category
        unsupported = True
    return {"exit_count": 1, "identity_matches": True, "ordered_records": birth["record"] < stop["record"],
            "exit_minus_birth_ticks": stop["ticks"] - birth["ticks"], "exit_image_form": form,
            "unsupported_exit_image": unsupported}


def sysmon_case(witness, records, expected_image):
    pid = witness["pid"]
    births = [row for row in records if row["kind"] == 1 and row["pid"] == pid]
    if len(births) != 1:
        return {"birth_count": len(births), "historical_pattern": False}
    birth = births[0]
    exits = [row for row in records if row["kind"] == 5 and (row["pid"] == pid or row["guid"] == birth["guid"])]
    result = exit_pair(birth, exits, expected_image)
    try:
        image_matches = trace.sysmon_image(birth["image"], 1, birth["record"]) == expected_image
    except trace.InvalidSysmonImage:
        image_matches = False
    return {"birth_count": 1, **result, "birth_image_matches": image_matches,
            "birth_minus_handle_ticks": birth["ticks"] - witness["birth"],
            "historical_pattern": image_matches and result.get("ordered_records", False)
            and result.get("unsupported_exit_image", False)
            and result.get("exit_minus_birth_ticks") == HISTORICAL_DELTA_TICKS}


def descendant_summary(records, known_pids):
    exits_by_guid = {}
    for row in records:
        if row["kind"] == 5:
            exits_by_guid.setdefault(row["guid"], []).append(row)
    categories = Counter()
    for birth in records:
        if birth["kind"] != 1 or birth["pid"] in known_pids:
            continue
        try:
            image = trace.sysmon_image(birth["image"], 1, birth["record"])
        except trace.InvalidSysmonImage:
            image = ""
        pair = exit_pair(birth, exits_by_guid.get(birth["guid"], ()), image)
        key = KINDS.get(ntpath.basename(image), "other"), pair.get("exit_minus_birth_ticks"), pair.get("exit_image_form")
        categories[key] += 1
    return [{"process_family": family, "exit_minus_birth_ticks": delta, "exit_image_form": form, "count": count}
            for (family, delta, form), count in categories.items()]


def capture(root, source):
    commands = candidates(root)
    first = journey.sysmon_tail() + 1
    witnesses = []
    with etw.process_session(root, source) as session:
        with journey.checkpoint_stage("driver-exit-fixtures", source, ""):
            for trial in range(1, 4):
                for family, command, signal in commands:
                    for pace, hold in (("immediate", 0), ("paced", 0.15)):
                        witness, _ = lifetime.run_process(
                            command, with_images=True, fixture_input=signal,
                            creationflags=subprocess.CREATE_NO_WINDOW, hold_seconds=hold,
                        )
                        witnesses.append((family, pace, trial, command[0], witness))
    pids = {witness["pid"] for _, _, _, _, witness in witnesses}
    trace.require(len(pids) == len(witnesses), "driver-exit-fixture-pid-reused")
    xml = root / "driver-exit-sysmon.xml"
    with journey.checkpoint_stage("driver-exit-sysmon-export", source, ""):
        time.sleep(3)
        last = journey.sysmon_tail()
        trace.require(first <= last < first + 4096, "driver-exit-sysmon-window-invalid")
        journey.export_sysmon(first, last, xml)
        sysmon, issues = lifetime.read_records(xml, first, last, pids, include_descendants=True)
    with journey.checkpoint_stage("driver-exit-etw-export", source, ""):
        journey.powershell(journey.HELPER, "etw-process-export", root, timeout=90)
        kernel = etw.read_process_events(root / "lifetime-etw.jsonl", pids, session["start"], session["end"])
        devices = trace.etw_device_aliases(n12_etw_probe.volume_devices())
    cases = []
    for family, pace, trial, executable, witness in witnesses:
        pair = etw.stop_image_report(witness, kernel, session, devices, executable)
        observed = sysmon_case(witness, sysmon, trace.windows_path(executable))
        cases.append({"family": family, "pace": pace, "trial": trial,
                      "handle_lifetime_ticks": witness["exit"] - witness["birth"], "sysmon": observed,
                      "etw_handle_match": pair["verdict"] == "PASS", "etw_issues": pair["issues"]})
    corroborated = sum(row["sysmon"]["historical_pattern"] and row["etw_handle_match"] for row in cases)
    bound = sum(row["sysmon"].get("birth_image_matches", False)
                and row["sysmon"].get("ordered_records", False) for row in cases)
    report = {"cases": cases, "sysmon_channel_issues": issues, "etw_counters": session["counters"],
              "sysmon_pairs_bound_to_expected_image": bound,
              "descendants_without_handles": descendant_summary(sysmon, pids),
              "handle_corroborated_historical_pattern": corroborated}
    print("N12 driver exit control " + json.dumps(report), flush=True)
    return 0 if not issues and bound == len(cases) and all(row["etw_handle_match"] for row in cases) else 2
