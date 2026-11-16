"""Generated replay tests for the N12 collector lifetime control."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as XML

import pytest

from qa.p4_native import n12_lifetime_control as control


ROOT = Path(__file__).resolve().parents[1]
IMAGE = r"C:\private\Python\python.exe"
SOURCE = "a" * 40
BASE = datetime(2026, 11, 16, tzinfo=timezone.utc)
BASE_TICKS = control.trace.utc_ticks(BASE)


def generated():
    witnesses, records = {}, []
    for group, pair in enumerate(control.PAIRS, 1):
        witnesses[pair] = {}
        start = BASE_TICKS + group * 1_000_000
        for offset, role in enumerate(control.ROLES):
            pid = 8000 + group * 10 + offset
            birth, end = start + offset * 20_000, start + (6 - offset) * 20_000
            guid = f"private-guid-{pid}"
            witnesses[pair][role] = {"pid": pid, "birth": birth, "exit": end}
            records.extend((
                {"record": group * 10 + offset, "kind": 1, "pid": pid, "guid": guid, "ticks": birth - 5000,
                 "image": IMAGE, "parent": f"private-guid-{pid - 1}" if offset else "observer-guid"},
                {"record": group * 10 + 3 - offset, "kind": 5, "pid": pid, "guid": guid, "ticks": end - 5000,
                 "image": IMAGE},
            ))
    return witnesses, records


@pytest.mark.parametrize(("fault", "findings"), [
    ("clean", []),
    ("reported-failure", ["exit-before-birth", "exit-image-unverified", "exit-time-disagrees-with-windows"]),
    ("wrong-pid", ["exit-identity-or-order-unverified"]),
    ("wrong-parent", ["parent-unverified"]),
    ("reversed-records", ["exit-identity-or-order-unverified"]),
    ("duplicate-exit", ["exit-missing-or-ambiguous"]),
    ("missing-exit", ["exit-missing-or-ambiguous"]),
    ("missing-birth", ["birth-missing-or-ambiguous"]),
])
def test_redacted_packet_replays_findings(tmp_path, fault, findings):
    witnesses, records = generated()
    birth, end = records[2:4]
    if fault == "reported-failure":
        end.update(ticks=birth["ticks"] - 20_000, image="private invalid image")
    elif fault == "wrong-pid":
        end["pid"] = 9999
    elif fault == "wrong-parent":
        birth["parent"] = "unknown"
    elif fault == "reversed-records":
        end["record"] = birth["record"] - 1
    elif fault == "duplicate-exit":
        records.append(end.copy())
    elif fault == "missing-exit":
        records.remove(end)
    elif fault == "missing-birth":
        records.remove(birth)
    packet = control.redact(witnesses, records, [], IMAGE)
    result = control.replay(packet)
    assert result["verdict"] == ("BLOCKED" if findings else "PASS")
    assert result["findings"]["fast-child"] == findings
    if fault == "reported-failure":
        payload = json.dumps(packet)
        for value in ("private", "8011", "2026", "9999"):
            assert value not in payload
        path = tmp_path / "evidence.json"
        path.write_text(payload, encoding="utf-8")
        replayed = subprocess.run([sys.executable, "-B", "-m", control.__name__, "--replay", str(path)],
                                  capture_output=True, text=True, cwd=ROOT, check=False)
        assert replayed.returncode == 2
        assert json.loads(replayed.stdout) == result


def test_bounded_xml_keeps_known_guid_with_conflicting_pid(tmp_path):
    path = tmp_path / "sysmon.xml"
    ns = control.trace.EVENT_NS
    root = XML.Element("Events")
    for record, kind, pid, guid in [(11, 1, 40, "fixture"), (13, 5, 41, "fixture"), (14, 16, 0, "collector")]:
        event = XML.SubElement(root, ns + "Event")
        system = XML.SubElement(event, ns + "System")
        XML.SubElement(system, ns + "EventRecordID").text = str(record)
        XML.SubElement(system, ns + "EventID").text = str(kind)
        data = XML.SubElement(event, ns + "EventData")
        for key, value in {"ProcessId": str(pid), "ProcessGuid": guid, "Image": IMAGE,
                           "UtcTime": (BASE + timedelta(milliseconds=record)).strftime("%Y-%m-%d %H:%M:%S.%f")}.items():
            XML.SubElement(data, ns + "Data", Name=key).text = value
    XML.ElementTree(root).write(path, encoding="utf-8")
    rows, issues = control.read_records(path, 11, 14, {40})
    assert [r["pid"] for r in rows] == [40, 41]
    assert issues == ["collector-state-or-error", "record-gap"]
    witnesses, records = generated()
    assert control.replay(control.redact(witnesses, records, issues, IMAGE))["verdict"] == "BLOCKED"


def test_replay_rejects_invalid_counts_and_unknown_channel_issues():
    witnesses, records = generated()
    packet = control.redact(witnesses, records, [], IMAGE)
    packet["cases"][0]["birth_count"] = True
    with pytest.raises(control.trace.EvidenceValidationError, match="invalid-lifetime-replay-count"):
        control.replay(packet)
    packet["channel_issues"].append("private-unknown")
    with pytest.raises(control.trace.EvidenceValidationError, match="invalid-lifetime-replay-envelope"):
        control.replay(packet)


@pytest.mark.parametrize(("boundary", "finding"), [
    ("birth", "parent-start-after-child-birth"),
    ("exit", "parent-exit-before-child-birth"),
])
def test_replay_checks_parent_lifetime_even_when_individual_deltas_are_within_bound(boundary, finding):
    witnesses, records = generated()
    parent, child = witnesses["fast"].values()
    parent_birth, parent_exit, child_birth, child_exit = records[:4]
    if boundary == "birth":
        child["birth"] = parent["birth"] + 1000
        parent_birth["ticks"] = parent["birth"] + 5000
        child_birth["ticks"] = child["birth"] - 5000
    else:
        child["birth"] = child["exit"] = parent["exit"] - 1000
        child_birth["ticks"] = child["birth"] + 5000
        child_exit["ticks"] = child["exit"] + 6000
    packet = control.redact(witnesses, records, [], IMAGE)
    result = control.replay(packet)
    assert result["verdict"] == "BLOCKED"
    assert result["findings"]["fast-parent"] == []
    assert result["findings"]["fast-child"] == [finding]
    assert control.replay({**packet, "schema_version": 1})["verdict"] == "PASS"
    packet["cases"][1]["windows_birth_after_parent_ticks"] = -1
    with pytest.raises(control.trace.EvidenceValidationError, match="invalid-lifetime-replay-parent-window"):
        control.replay(packet)


def test_collector_mode_refuses_unapproved_execution(tmp_path):
    env = {key: value for key, value in os.environ.items() if key != "PILOTODIN_N12_LIFETIME_CONTROL_CONSENT"}
    result = subprocess.run([sys.executable, "-B", "-m", control.__name__, "--capture", str(tmp_path)],
                            cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "lifetime-control-requires-approved-hosted-windows" in result.stderr
    assert not list(tmp_path.iterdir())


def test_capture_retains_replay_before_returning_blocked(tmp_path, monkeypatch, capsys):
    witnesses, records = generated()
    records[3]["image"] = "private invalid image"
    tails = iter((10, 23))
    collected = []

    def run_fixture(command):
        pair = command[-1]
        collected.append(pair)
        return witnesses[pair]["parent"], json.dumps(witnesses[pair]["child"]).encode()

    def read(path, first, last, pids):
        assert path == tmp_path / "lifetime-sysmon.xml"
        assert (first, last) == (11, 23)
        assert pids == {8010, 8011, 8020, 8021}
        return records, []

    monkeypatch.setattr(control, "run_process", run_fixture)
    monkeypatch.setattr(control.sys, "executable", IMAGE)
    monkeypatch.setattr(control.time, "sleep", lambda _: None)
    monkeypatch.setattr(control.journey, "sysmon_tail", lambda: next(tails))
    monkeypatch.setattr(control.journey, "export_sysmon", lambda *args: None)
    monkeypatch.setattr(control, "read_records", read)
    assert control.capture(tmp_path, SOURCE) == 2
    assert collected == list(control.PAIRS)
    persisted = json.loads((tmp_path / "lifetime-replay.json").read_text(encoding="utf-8"))
    packet_line, verdict_line = [line for line in capsys.readouterr().out.splitlines()
                                 if line.startswith("N12 lifetime ")]
    assert json.loads(packet_line.removeprefix("N12 lifetime replay ")) == persisted
    assert json.loads(verdict_line.removeprefix("N12 lifetime verdict ")) == control.replay(persisted)
    assert "private" not in packet_line + verdict_line


@pytest.mark.parametrize("failure", ["lifetime-sysmon-export", "lifetime-reduction", "lifetime-local-copy"])
def test_capture_retains_completed_stages_and_logs_replay_before_local_write(tmp_path, monkeypatch, capsys, failure):
    witnesses, records = generated()
    tails = iter((10, 23))

    def stage(name, result=None):
        def run(*args):
            if name == failure:
                raise OSError("private path")
            return result
        return run

    def run_fixture(command):
        pair = witnesses[command[-1]]
        return pair["parent"], json.dumps(pair["child"]).encode()

    monkeypatch.setattr(control, "run_process", run_fixture)
    monkeypatch.setattr(control.sys, "executable", IMAGE)
    monkeypatch.setattr(control.time, "sleep", lambda _: None)
    monkeypatch.setattr(control.journey, "sysmon_tail", lambda: next(tails))
    monkeypatch.setattr(control.journey, "export_sysmon", stage("lifetime-sysmon-export"))
    monkeypatch.setattr(control, "read_records", stage("lifetime-reduction", (records, [])))
    monkeypatch.setattr(control.journey, "report_file", stage("lifetime-local-copy"))
    with pytest.raises(OSError):
        control.capture(tmp_path, SOURCE)
    lines = capsys.readouterr().out.splitlines()
    checkpoints = [json.loads(line.removeprefix("N12 checkpoint ")) for line in lines
                   if line.startswith("N12 checkpoint ")]
    assert [(row["stage"], row["status"]) for row in checkpoints[:2]] == [
        ("lifetime-window-open", "completed"), ("lifetime-fixtures", "completed"),
    ]
    assert checkpoints[-1] == {"stage": failure, "status": "interrupted", "source_sha": SOURCE}
    results = [line for line in lines if line.startswith("N12 lifetime ")]
    if failure == "lifetime-local-copy":
        packet_line, verdict_line = results
        packet = json.loads(packet_line.removeprefix("N12 lifetime replay "))
        verdict = json.loads(verdict_line.removeprefix("N12 lifetime verdict "))
        assert lines.index(verdict_line) < len(lines) - 1
        assert verdict == control.replay(packet)
    else:
        assert not results
    assert "private" not in "\n".join(lines)
