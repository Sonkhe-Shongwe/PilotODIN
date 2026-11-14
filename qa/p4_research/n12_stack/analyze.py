"""Link exact classic StackWalk identities and report only redacted evidence."""
import json
import ntpath
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "p4_native"))
from n12_etw_correlate import (
    canonical_file_path, number, preopened_report, successful_completion,
    timing_comparison_identity,
)


class Request(NamedTuple):
    qpc: int
    opcode: int
    pid: int
    tid: int
    issuing: int
    irp: int
    key: int
    obj: int
    detail: int
    flags: int
    offset: int


def json_file(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_rows(path):
    with path.open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream]


def read_classic(path, devices):
    data = defaultdict(list)
    names = defaultdict(set)
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            tag, *fields = line.rstrip("\n").split("\t")
            if tag == "name":
                names[int(fields[0])].add(canonical_file_path(fields[1], devices))
            elif tag == "image":
                data[tag].append((*map(int, fields[:-1]), ntpath.basename(fields[-1]).casefold()))
            else:
                data[tag].append(tuple(map(int, fields)))
    return data, names


def lifecycle(records, qpc, *, preexisting=False):
    prior = [record for record in records if record[0] <= qpc and record[1] in (1, 2)]
    if prior:
        latest = max(record[0] for record in prior)
        actions = [opcode for stamp, opcode in prior if stamp == latest]
        return actions == [1]
    return preexisting and any(opcode in (3, 4) for _, opcode in records)


def stack_identity(request, pid, issuing, processes, threads):
    # The FileIO header may omit execution identity. Only substitute the
    # independently established issuing TID when Windows used the sentinel.
    if request.pid not in (pid, 0xFFFFFFFF) or request.issuing != issuing:
        return None
    tid = issuing if request.tid == 0xFFFFFFFF else request.tid
    owners = {owner for owner, thread_id in threads if thread_id == tid and
              lifecycle(threads[owner, thread_id], request.qpc, preexisting=True)}
    if (not tid or owners != {pid} or
            not lifecycle(processes[pid], request.qpc, preexisting=True)):
        return None
    return request.qpc, pid, tid


def stack_frames(identity, stacks, refs, definitions):
    direct = stacks[identity]
    keyed = refs[identity]
    if len(direct) == 1 and not keyed:
        return direct[0]
    if direct or not keyed or len({opcode for opcode, _ in keyed}) != len(keyed):
        return ()
    groups = [definitions[key] for _, key in sorted(keyed)]
    if any(len(group) != 1 for group in groups):
        return ()
    return tuple(frame for group in groups for frame in next(iter(group)))


def module_frames(frames, pid, qpc, images):
    counts = Counter()
    for address in frames:
        loaded = defaultdict(list)
        for stamp, opcode, owner, base, size, name in images:
            kernel = address >= 0xFFFF000000000000
            eligible = owner in (0, 4) if kernel else owner == pid
            if eligible and base <= address < base + size:
                loaded[owner, base, name].append((stamp, 1 if opcode == 10 else opcode))
        names = {name for (_, _, name), records in loaded.items() if lifecycle(records, qpc, preexisting=True)}
        if len(names) == 1:
            name = names.pop()
            public = {"ntoskrnl.exe", "ntkrnlmp.exe", "ntfs.sys", "fltmgr.sys",
                      "ntdll.dll", "kernelbase.dll", "kernel32.dll"}
            if name.startswith("python") and name.endswith((".exe", ".dll")):
                counts["python"] += 1
            else:
                counts[name if name in public else "other-module"] += 1
        else:
            counts["unresolved"] += 1
    return dict(counts)


def comparison_identities(capture, comparisons, events, devices, names, primary, by_irp):
    control = capture["preopened"]
    result = {}
    flushed = comparisons["flushed"]
    start, end = flushed["write_window"]
    flush_start, flush_end = flushed["flush_window"]
    if not (capture["start_ticks"] <= start <= end <= flush_start <= flush_end
            <= capture["rundown_start_ticks"]):
        raise ValueError("Invalid flushed-control windows.")

    helper_pid, helper_tid = flushed["pid"], flushed["tid"]
    if not (helper_pid > 0 and helper_tid > 0 and helper_pid != control["pid"]):
        raise ValueError("The flushed comparison must have a distinct process identity.")

    def completed_request(row, event_id, begin, finish):
        data = row["data"]
        return (row["id"] == event_id and begin <= row["ticks"] <= finish
                and row["pid"] == helper_pid
                and number(data.get("IssuingThreadId", data.get("ThreadId"))) == helper_tid
                and successful_completion(by_irp.get(number(data.get("Irp")), ()), row, finish + 1)
                is not None)

    def identity(row):
        return tuple(number(row["data"].get(name)) for name in ("FileKey", "FileObject"))

    expected = canonical_file_path(flushed["path"], devices)
    writes = [row for row in events if not row["lifecycle"]
              and completed_request(row, 16, start, end)
              and number(row["data"].get("IOSize")) == flushed["size"]
              and number(row["data"].get("ByteOffset")) == 0
              and all(identity(row)) and expected is not None
              and names.get(identity(row)[0]) == {expected}]
    flushed_identity = identity(writes[0]) if len(writes) == 1 else None
    if flushed_identity is not None and any(
        flushed_identity[0] == key or flushed_identity[1] == obj for key, obj in primary.values()
    ):
        flushed_identity = None
    flushes = [row for row in events if flushed_identity is not None and not row["lifecycle"]
               and identity(row) == flushed_identity and completed_request(row, 21, flush_start, flush_end)]
    result["flushed"] = {"identity": flushed_identity, "explicit_flush": len(flushes) == 1}
    comparison_capture = {**capture, "preopened": {**control, "untouched": comparisons["untouched"]}}
    established = {**primary}
    if flushed_identity is not None:
        established["flushed"] = flushed_identity
    untouched_identity, evidence = timing_comparison_identity(
        comparison_capture, events, devices, names, established, by_irp,
    )
    result["untouched"] = {"identity": untouched_identity, "evidence": evidence}
    return result


def calibration_candidates(requests, names, companion_irps, known, label, opcode, expected_path, end_ticks):
    counts = Counter()
    selected = []
    start, end = known[label]
    for row in requests:
        if row.opcode != opcode or row.issuing != known["tid"]:
            continue
        counts["classic-operation-and-thread"] += 1
        if expected_path is None or names.get(row.key) != {expected_path}:
            counts["classic-name-unverified"] += 1
            continue
        if (opcode == 68 and (row.detail != known["size"] or row.offset != 0)
                or opcode == 69 and row.detail != 20):
            counts["classic-operation-fields-mismatch"] += 1
            continue
        if not (row.key and row.obj and row.irp):
            counts["classic-file-identity-unverified"] += 1
            continue

        irp_records = companion_irps.get(row.irp, ())
        completed = []
        for event in irp_records:
            data = event["data"]
            if event["id"] != {68: 16, 69: 17}[opcode]:
                continue
            counts["companion-operation-and-irp"] += 1
            if (event["pid"] != known["pid"]
                    or number(data.get("IssuingThreadId", data.get("ThreadId"))) != known["tid"]):
                counts["companion-process-or-thread-mismatch"] += 1
                continue
            if (number(data.get("FileKey")), number(data.get("FileObject"))) != (row.key, row.obj):
                counts["companion-file-identity-mismatch"] += 1
                continue
            if opcode == 69 and number(data.get("InfoClass")) != 20:
                counts["companion-operation-fields-mismatch"] += 1
                continue
            if not start - 10 <= event["ticks"] <= end + 10:
                counts["companion-outside-calibration-window"] += 1
                continue
            if successful_completion(irp_records, event, end_ticks + 1) is None:
                counts["companion-success-unverified"] += 1
                continue
            completed.append(event)
        if len(completed) == 1:
            selected.append(row)
        else:
            counts["companion-match-missing" if not completed else "companion-match-ambiguous"] += 1
    return selected, dict(counts)

def report(root, known, decoder, comparisons):
    capture = json_file(root / "fixture.json")
    events = sorted(json_rows(root / "events.jsonl"), key=lambda row: row["ticks"])
    rundown = json_rows(root / "rundown.jsonl")
    keys, objects = {}, {}
    companion = preopened_report(capture, events, rundown, file_keys=keys, file_objects=objects)
    drive = capture["protected_root"][:2].casefold()
    devices = {capture["device"].casefold(): drive}
    classic, names = read_classic(root / "stack-rows.tsv", devices)
    requests = [Request(*row) for row in classic["request"]]
    request_counts = Counter((row.qpc, row.pid, row.tid) for row in requests)
    by_irp = defaultdict(list)
    for stamp, irp, status in classic["end"]:
        by_irp[irp].append((stamp, status))
    for stamp, irp in classic["other"]:
        by_irp[irp].append((stamp, None))
    for row in requests:
        by_irp[row.irp].append((row.qpc, None))

    def completed(row):
        later = sorted((item for item in by_irp[row.irp] if item[0] >= row.qpc),
                       key=lambda item: item[0])
        return (row.irp and sum(item[0] == row.qpc for item in later) == 1 and
                len(later) >= 2 and later[1][1] == 0 and
                (len(later) == 2 or later[2][0] > later[1][0]))

    processes, threads, stacks, refs, definitions = (defaultdict(list) for _ in range(5))
    for qpc, opcode, pid in classic["process"]:
        processes[pid].append((qpc, opcode))
    for qpc, opcode, pid, tid in classic["thread"]:
        threads[pid, tid].append((qpc, opcode))
    for qpc, pid, tid, *frames in classic["stack"]:
        stacks[qpc, pid, tid].append(tuple(frames))
    for qpc, pid, tid, opcode, key in classic["reference"]:
        refs[qpc, pid, tid].append((opcode, key))
    for key, *frames in classic["definition"]:
        definitions[key].append(tuple(frames))
    definitions = defaultdict(set, {key: set(value) for key, value in definitions.items()})
    integrity = (decoder["pointer_size"] == 8 and
                 not any(decoder[k] for k in ("events_lost", "header_events_lost", "buffers_lost", "decode_errors")) and
                 not any(capture["counters"][k] for k in ("events_lost", "log_buffers_lost", "realtime_buffers_lost")))

    companion_irps = defaultdict(list)
    for row in events:
        if not row["lifecycle"] and (irp := number(row["data"].get("Irp"))):
            companion_irps[irp].append(row)

    primary = {}
    for label, evidence in companion["targets"].items():
        if (label in keys and label in objects and evidence["request_candidates"] == 1
                and evidence["completion"] == "success" and evidence["issuing_thread"] == "matches"
                and evidence["rundown_name"] == "matches-target"):
            primary[label] = (keys[label], objects[label])
    rundown_names = defaultdict(set)
    for entry in rundown:
        rundown_names[number(entry["key"])].add(canonical_file_path(entry["path"], devices))
    comparison = comparison_identities(capture, comparisons, events, devices, rundown_names,
                                       primary, companion_irps)

    def phase(ticks):
        if ticks < capture["rundown_start_ticks"]:
            return "before-wpr-stop"
        if ticks <= capture["rundown_stop_ticks"]:
            return "during-wpr-stop"
        return "after-wpr-stop"

    def matches(row, opcode, pid, issuing, identity):
        data = row["data"]
        return (row["pid"] == pid and number(data.get("IssuingThreadId", data.get("ThreadId"))) == issuing
                and row["id"] == {68: 16, 69: 17, 73: 21}[opcode]
                and (opcode != 69 or number(data.get("InfoClass")) == 20)
                and (number(data.get("FileKey")), number(data.get("FileObject"))) == identity
                and successful_completion(companion_irps[number(data.get("Irp"))], row, capture["end_ticks"] + 1)
                is not None)

    def assess(row, pid, issuing):
        result = {"classic_success": bool(completed(row))}
        identity = stack_identity(row, pid, issuing, processes, threads)
        result["lifetime"] = "confirmed" if identity is not None else "unverified"
        if not integrity:
            status = "capture-integrity-unverified"
        elif not result["classic_success"]:
            status = "classic-completion-unverified"
        elif identity is None:
            status = "process-or-thread-lifetime-unverified"
        elif request_counts[row.qpc, row.pid, row.tid] != 1:
            status = "classic-event-identity-ambiguous"
        else:
            status = "stack-unavailable-or-ambiguous"
        frames = ()
        if status == "stack-unavailable-or-ambiguous":
            frames = stack_frames(identity, stacks, refs, definitions)
        result["stack_status"] = "matched" if frames else status
        result["stack_frames"] = len(frames)
        result["modules"] = module_frames(frames, pid, row.qpc, classic["image"])
        return result

    calibrations = {}
    expected_path = canonical_file_path(known["path"], devices)
    for label, opcode in (("write", 68), ("resize", 69)):
        selected, diagnostics = calibration_candidates(
            requests, names, companion_irps, known, label, opcode, expected_path, capture["end_ticks"],
        )
        outcome = {"candidate_count": len(selected), "candidate_diagnostics": diagnostics}
        if len(selected) == 1:
            outcome.update(assess(selected[0], known["pid"], known["tid"]))
        calibrations[label] = outcome
    calibrated = all(item.get("stack_frames", 0) for item in calibrations.values())

    systems = {}
    for label in ("protected", "outside", "flushed", "untouched"):
        control = capture["preopened"]["writes"].get(label, comparisons.get(label))
        expected = canonical_file_path(control["path"], devices)
        evidence = comparison.get(label, {})
        identity = primary.get(label, evidence.get("identity"))
        name_agrees = identity is not None and names[identity[0]] == {expected}
        result = {"identity": "confirmed" if name_agrees else "unverified", "write": [], "resize": [],
                  "companion_successful": {"write": 0, "resize": 0},
                  "unmatched_companion_operations": 0}
        result.update({key: value for key, value in evidence.items() if key != "identity"})
        if label == "flushed":
            result["explicit_flush"] = bool(name_agrees and evidence["explicit_flush"])
        if identity is not None:
            observed = [row for row in events if not row["lifecycle"] and row["pid"] == 4
                        and row["id"] in (16, 17)
                        and (row["id"] != 17 or number(row["data"].get("InfoClass")) == 20)
                        and (number(row["data"].get("FileKey")), number(row["data"].get("FileObject"))) == identity]
            for item in observed:
                data = item["data"]
                irp = number(data.get("Irp"))
                issuing = number(data.get("IssuingThreadId", data.get("ThreadId")))
                operation, opcode = ("write", 68) if item["id"] == 16 else ("resize", 69)
                completed_ticks = successful_completion(companion_irps[irp], item, capture["end_ticks"] + 1)
                if completed_ticks is None:
                    continue
                result["companion_successful"][operation] += 1
                candidates = [row for row in requests
                              if name_agrees and row.irp == irp and row.opcode == opcode
                              and (row.key, row.obj) == identity and row.issuing == issuing
                              and row.pid in (4, 0xFFFFFFFF)
                              and (opcode != 68 or (
                                  row.flags == number(data.get("IOFlags"))
                                  and row.detail == number(data.get("IOSize"))
                                  and row.offset == number(data.get("ByteOffset"))))
                              and (opcode != 69 or row.detail == 20)]
                matching = [other for other in companion_irps[irp]
                            if matches(other, opcode, 4, issuing, identity)]
                if len(candidates) != 1 or len(matching) != 1:
                    result["unmatched_companion_operations"] += 1
                    continue
                row = candidates[0]
                outcome = assess(row, 4, issuing)
                outcome.update(request_phase=phase(item["ticks"]), completion_phase=phase(completed_ticks))
                if opcode == 68:
                    outcome["paging_flag"] = bool(row.flags & 2)
                result[operation].append(outcome)
        systems[label] = result

    file_roles = {identity: label for label, identity in primary.items()}
    file_roles.update({evidence["identity"]: label for label, evidence in comparison.items()
                       if evidence["identity"] is not None})
    fixture_writes = Counter()
    for row in events:
        if row["lifecycle"] or row["id"] != 16 or row["pid"] != capture["preopened"]["pid"]:
            continue
        data = row["data"]
        irp = number(data.get("Irp"))
        if successful_completion(companion_irps.get(irp, ()), row, capture["end_ticks"] + 1) is not None:
            identity = (number(data.get("FileKey")), number(data.get("FileObject")))
            role = file_roles.get(identity, "other-file")
            fixture_writes[f"{role}:{phase(row['ticks'])}"] += 1

    return {"loss_and_decode_checks_pass": integrity, "classic_stack_records": len(classic["stack"]),
            "classic_stack_references": len(classic["reference"]), "classic_file_requests": len(requests),
            "known_application_controls": calibrations, "calibrated": calibrated,
            "system_context": systems, "fixture_process_successful_writes": dict(fixture_writes),
            "function_symbols": "not-resolved", "application_initiator": "unverified"}


if __name__ == "__main__":
    try:
        metadata = json_file(Path(sys.argv[1]))
        result = report(Path(metadata["root"]), metadata["known"], json.loads(sys.argv[2]),
                        metadata["comparisons"])
        print("N12 stack correlation: " + json.dumps(result), flush=True)
        controls = result["system_context"]
        if (not result["calibrated"] or not controls["flushed"]["explicit_flush"]
                or controls["untouched"]["identity"] != "confirmed"):
            sys.exit("The N12 stack calibration or comparison controls did not pass.")
    except (KeyError, OSError, ValueError, IndexError, TypeError):
        sys.exit("The N12 stack correlation could not validate the captured evidence.")
