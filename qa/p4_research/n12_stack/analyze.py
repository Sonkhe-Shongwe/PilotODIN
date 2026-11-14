"""Link exact classic StackWalk identities and report only redacted evidence."""
import json
import ntpath
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "p4_native"))
from n12_etw_correlate import (
    canonical_file_path, name_transition_key, number, preopened_report, successful_completion,
    timing_comparison_identity, write_paging_flag,
)
if __package__:
    from .capture import STAGGERED_PAYLOADS, WRITE_GAP_SECONDS
else:
    from capture import STAGGERED_PAYLOADS, WRITE_GAP_SECONDS


class Image(NamedTuple):
    stamp: int
    opcode: int
    pid: int
    base: int
    size: int
    checksum: int
    timestamp: int
    name: str


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
                data[tag].append(Image(*map(int, fields[:-1]), ntpath.basename(fields[-1]).casefold()))
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


def frame_image(address, pid, qpc, images):
    loaded = defaultdict(list)
    kernel = address >= 0xFFFF000000000000
    for item in images:
        eligible = item.pid in (0, 4) if kernel else item.pid == pid
        if eligible and item.base <= address < item.base + item.size:
            identity = (item.base, item.size, item.checksum, item.timestamp, item.name)
            loaded[identity].append((item.stamp, 1 if item.opcode == 10 else item.opcode))
    matches = [key for key, records in loaded.items() if lifecycle(records, qpc, preexisting=True)]
    return matches[0] if len(matches) == 1 else None


def module_frames(frames, pid, qpc, images, symbol_frames=None):
    counts = Counter()
    for index, address in enumerate(frames):
        image = frame_image(address, pid, qpc, images)
        if image is None:
            counts["unresolved"] += 1
            continue
        base, size, checksum, timestamp, name = image
        public = {"ntoskrnl.exe", "ntkrnlmp.exe", "ntfs.sys", "fltmgr.sys",
                  "ntdll.dll", "kernelbase.dll", "kernel32.dll"}
        if name.startswith("python") and name.endswith((".exe", ".dll")):
            counts["python"] += 1
        else:
            counts[name if name in public else "other-module"] += 1
        if symbol_frames is not None and name in {"ntoskrnl.exe", "ntkrnlmp.exe", "ntfs.sys", "fltmgr.sys"}:
            symbol_frames.append({"frame": index, "module": name, "rva": address - base,
                                  "size": size, "checksum": checksum, "timestamp": timestamp})
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


def staggered_writes(capture, experiment, events, by_irp, names, devices, occupied):
    """Verify the four declared writes independently of the strict controls."""
    pid, tid = experiment["pid"], experiment["tid"]
    if not (type(pid) is int and pid > 4 and pid != capture["preopened"]["pid"]
            and type(tid) is int and tid > 0):
        raise ValueError("Invalid staggered comparison writer identity.")
    files = experiment["files"]
    if set(files) != {"staggered-protected", "staggered-outside"}:
        raise ValueError("Both staggered comparison files are required.")
    root = canonical_file_path(capture["protected_root"], devices)
    if root is None:
        raise ValueError("Invalid staggered comparison root.")
    expected_paths = {"staggered-protected": ntpath.join(root, "staggered.bin"),
                      "staggered-outside": ntpath.join(ntpath.dirname(root), "staggered.bin")}
    result = {}
    for label, file in files.items():
        expected = canonical_file_path(file["path"], devices)
        first, second = file["writes"]
        if (expected != expected_paths[label]
                or not capture["start_ticks"] <= first["start"] <= first["end"] < second["start"]
                <= second["end"] < capture["rundown_start_ticks"]
                or second["start"] - first["end"] < WRITE_GAP_SECONDS * 10_000_000):
            raise ValueError("Invalid staggered comparison path or timing.")
        verified = []
        for write, (offset, payload) in zip((first, second), STAGGERED_PAYLOADS):
            if (write["offset"], write["size"]) != (offset, len(payload)):
                raise ValueError("Invalid staggered comparison byte range.")
            candidates = []
            for row in events:
                if (row["lifecycle"] or row["id"] != 16 or row["pid"] != pid
                        or not write["start"] - 10 <= row["ticks"] <= write["end"] + 10):
                    continue
                data = row["data"]
                if (number(data.get("IssuingThreadId", data.get("ThreadId"))) != tid
                        or number(data.get("ByteOffset")) != offset
                        or number(data.get("IOSize")) != len(payload)):
                    continue
                irp = number(data.get("Irp"))
                identity = tuple(number(data.get(name)) for name in ("FileKey", "FileObject"))
                completion = successful_completion(by_irp.get(irp, ()), row, capture["rundown_start_ticks"])
                if completion is not None:
                    candidates.append((identity, completion))
            if len(candidates) == 1:
                identity, completion = candidates[0]
                if (all(value is not None and value > 0 for value in identity)
                        and names.get(identity[0]) == {expected}):
                    verified.append({**write, "identity": identity, "completed": completion})
        identity = verified[0]["identity"] if len(verified) == 2 else None
        if identity is not None and (identity != verified[1]["identity"] or any(
            identity[0] == key or identity[1] == obj for key, obj in occupied
        )):
            identity = None
        if identity is not None:
            occupied.add(identity)
        result[label] = {"identity": identity, "writes": verified if identity is not None else [],
                         "verified_write_count": len(verified),
                         "same_file_distinct_handles": file.get("same_file_distinct_handles") is True}
    return result


def range_evidence(offset, size, ticks, writes, paging):
    returned = [ticks > max(write["end"], write["completed"]) for write in writes]
    result = {"range_status": "unverified", "overlaps": [], "completed_writes_at_request": sum(returned)}
    if not paging or offset is None or size is None or offset < 0 or size <= 0:
        return result
    overlaps = []
    for index, write in enumerate(writes, 1):
        begin = max(offset, write["offset"])
        end = min(offset + size, write["offset"] + write["size"])
        if begin < end:
            lag = ticks - write["end"]
            overlaps.append({"write": index, "bytes": end - begin,
                             "after_write_completed_and_returned": returned[index - 1],
                             "ms_from_write_return": round(lag / 10_000, 3)})
    return {**result, "range_status": "overlap" if overlaps else "disjoint", "overlaps": overlaps,
            "offset": offset, "size": size}


def staggered_candidates(events, companion_irps, rundown_names, event_names, open_names, expected, identity,
                         writer, end_ticks, phase):
    """Count weaker candidates without admitting them to the stack or range join."""
    counts = Counter()
    exact = []
    for row in events:
        if row["lifecycle"] or row["id"] not in (16, 17):
            continue
        data = row["data"]
        if row["id"] == 17 and number(data.get("InfoClass")) != 20:
            continue
        key, obj = (number(data.get(field)) for field in ("FileKey", "FileObject"))
        key_matches = key == identity[0]
        object_matches = obj == identity[1]
        if key_matches and object_matches:
            relation = "exact-pair"
        elif key_matches:
            relation = "key-only"
        elif object_matches:
            relation = "object-only"
        elif expected is not None and rundown_names.get(key) == {expected}:
            relation = "rundown-name-only"
        elif expected is not None and expected in event_names.get(key, ()):
            relation = "trace-name-candidate-only"
        elif expected is not None and expected in open_names.get(obj, ()):
            relation = "open-path-candidate-only"
        else:
            continue
        operation = "write" if row["id"] == 16 else "resize"
        header = {4: "system", writer: "fixture-writer", 0: "zero", 0xFFFFFFFF: "sentinel"}.get(
            row["pid"], "other",
        )
        irp = number(data.get("Irp"))
        finished = successful_completion(companion_irps.get(irp, ()), row, end_ticks + 1)
        completion = "success" if finished is not None else "unverified"
        paging = write_paging_flag(data) if operation == "write" else "not-applicable"
        counts[f"{operation}:{phase(row['ticks'])}:{relation}:{header}:{completion}:{paging}"] += 1
        if relation == "exact-pair" and header == "system" and finished is not None:
            exact.append((row, finished))
    return exact, dict(counts)


def classic_candidates(requests, item, opcode, identity, name_agrees):
    """Return the original exact candidates and fixed-label rejection counts."""
    data = item["data"]
    irp = number(data.get("Irp"))
    issuing = number(data.get("IssuingThreadId", data.get("ThreadId")))
    counts = Counter()
    candidates = []
    for row in requests:
        if row.irp != irp or row.opcode != opcode:
            continue
        if not name_agrees:
            counts["classic-name-unverified"] += 1
        elif (row.key, row.obj) != identity:
            counts["classic-file-identity-mismatch"] += 1
        elif row.issuing != issuing or row.pid not in (4, 0xFFFFFFFF):
            counts["classic-process-or-thread-mismatch"] += 1
        elif (opcode == 68 and (row.flags != number(data.get("IOFlags"))
                                or row.detail != number(data.get("IOSize"))
                                or row.offset != number(data.get("ByteOffset")))
              or opcode == 69 and row.detail != 20):
            counts["classic-operation-fields-mismatch"] += 1
        else:
            candidates.append(row)
    return candidates, counts


def report(root, known, decoder, comparisons, symbol_targets):
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
    staggered = {}
    event_names = defaultdict(set)
    open_names = defaultdict(set)
    if "staggered" in comparisons:
        for row in events:
            data = row["data"]
            if row["lifecycle"] or not data.get("FileName"):
                continue
            if row["id"] == 10:
                key = name_transition_key(10, data)
                if key:
                    event_names[key].add(canonical_file_path(data["FileName"], devices))
            elif row["id"] == 12 and (obj := number(data.get("FileObject"))):
                open_names[obj].add(canonical_file_path(data["FileName"], devices))
        occupied = set(primary.values()) | {value["identity"] for value in comparison.values()
                                            if value["identity"] is not None}
        staggered = staggered_writes(capture, comparisons["staggered"], events,
                                     companion_irps, rundown_names, devices, occupied)

    stop_start = capture["rundown_start_ticks"]
    dwell_start = comparisons.get("stop_dwell_start")
    writes = capture["preopened"]["writes"]
    if dwell_start is not None and not (max(item["end"] for item in writes.values())
                                        < dwell_start < stop_start):
        raise ValueError("Invalid pre-stop dwell window.")

    def phase(ticks):
        if ticks < stop_start:
            return "before-wpr-stop"
        if ticks <= capture["rundown_stop_ticks"]:
            return "during-wpr-stop"
        return "after-wpr-stop"

    def completed_companion(row):
        irp = number(row["data"].get("Irp"))
        return successful_completion(companion_irps.get(irp, ()), row, capture["end_ticks"] + 1)

    def matches(row, opcode, pid, issuing, identity):
        data = row["data"]
        return (row["pid"] == pid and number(data.get("IssuingThreadId", data.get("ThreadId"))) == issuing
                and row["id"] == {68: 16, 69: 17, 73: 21}[opcode]
                and (opcode != 69 or number(data.get("InfoClass")) == 20)
                and (number(data.get("FileKey")), number(data.get("FileObject"))) == identity
                and completed_companion(row) is not None)

    def assess(row, pid, issuing, symbol_frames=None):
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
        result["modules"] = module_frames(frames, pid, row.qpc, classic["image"], symbol_frames)
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
    for label in ("protected", "outside", "flushed", "untouched", *staggered):
        control = (comparisons["staggered"]["files"][label] if label in staggered
                   else capture["preopened"]["writes"].get(label, comparisons.get(label)))
        expected = canonical_file_path(control["path"], devices)
        evidence = comparison.get(label, staggered.get(label, {}))
        identity = primary.get(label, evidence.get("identity"))
        name_agrees = identity is not None and names[identity[0]] == {expected}
        result = {"identity": "confirmed" if name_agrees else "unverified", "write": [], "resize": [],
                  "companion_successful": {"write": 0, "resize": 0},
                  "unmatched_companion_operations": 0}
        result.update({key: value for key, value in evidence.items() if key not in {"identity", "writes"}})
        if label == "flushed":
            result["explicit_flush"] = bool(name_agrees and evidence["explicit_flush"])
        if identity is not None:
            join_counts = Counter()
            if label in staggered:
                observed, counts = staggered_candidates(
                    events, companion_irps, rundown_names, event_names, open_names, expected, identity,
                    comparisons["staggered"]["pid"], capture["end_ticks"], phase,
                )
                result["companion_candidate_counts"] = counts
            else:
                observed = [(row, completed_companion(row)) for row in events
                            if not row["lifecycle"] and row["id"] in (16, 17) and row["pid"] == 4
                            and (row["id"] != 17 or number(row["data"].get("InfoClass")) == 20)
                            and (number(row["data"].get("FileKey")),
                                 number(row["data"].get("FileObject"))) == identity]
            for item, completed_ticks in observed:
                data = item["data"]
                irp = number(data.get("Irp"))
                issuing = number(data.get("IssuingThreadId", data.get("ThreadId")))
                operation, opcode = ("write", 68) if item["id"] == 16 else ("resize", 69)
                if completed_ticks is None:
                    continue
                result["companion_successful"][operation] += 1
                candidates, rejected = classic_candidates(requests, item, opcode, identity, name_agrees)
                join_counts.update({f"{operation}:{reason}": count for reason, count in rejected.items()})
                matching = [other for other in companion_irps[irp]
                            if matches(other, opcode, 4, issuing, identity)]
                if len(candidates) != 1 or len(matching) != 1:
                    result["unmatched_companion_operations"] += 1
                    if len(candidates) != 1:
                        status = "classic-match-missing" if not candidates else "classic-match-ambiguous"
                        join_counts[f"{operation}:{status}"] += 1
                    if len(matching) != 1:
                        status = "companion-match-missing" if not matching else "companion-match-ambiguous"
                        join_counts[f"{operation}:{status}"] += 1
                    continue
                row = candidates[0]
                symbol_frames = []
                outcome = assess(row, 4, issuing, symbol_frames)
                join_counts[f"{operation}:{outcome['stack_status']}"] += 1
                request_phase = phase(item["ticks"])
                completion_phase = phase(completed_ticks)
                outcome.update(request_phase=request_phase, completion_phase=completion_phase)
                if opcode == 68:
                    outcome["paging_flag"] = bool(row.flags & 2)
                if dwell_start is not None:
                    outcome.update(
                        request_ms_from_stop=round((item["ticks"] - stop_start) / 10_000, 3),
                        completion_ms_from_stop=round((completed_ticks - stop_start) / 10_000, 3),
                    )
                    if label in writes:
                        outcome["request_ms_after_fixture_write_return"] = round(
                            (item["ticks"] - writes[label]["end"]) / 10_000, 3,
                        )
                if label in staggered:
                    outcome["comparison_event"] = result["companion_successful"][operation]
                    if outcome["stack_status"] == "matched":
                        outcome["staggered_range"] = range_evidence(
                            row.offset, row.detail, item["ticks"], evidence["writes"],
                            outcome.get("paging_flag", False),
                        )
                    else:
                        outcome["staggered_range"] = {"range_status": "unverified", "overlaps": []}
                if (label in writes or label in staggered) and symbol_frames:
                    target = {"control": label, "operation": operation,
                              "request_phase": request_phase, "completion_phase": completion_phase,
                              "stack_frames": outcome["stack_frames"], "frames": symbol_frames}
                    if label in staggered:
                        target["comparison_event"] = outcome["comparison_event"]
                    symbol_targets.append(target)
                result[operation].append(outcome)
            if label in staggered:
                result["stack_join_counts"] = dict(join_counts)
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
            "pre_stop_dwell_ms": (round((stop_start - dwell_start) / 10_000, 3)
                                  if dwell_start is not None else None),
            "function_symbols": "not-resolved", "application_initiator": "unverified"}


if __name__ == "__main__":
    try:
        metadata = json_file(Path(sys.argv[1]))
        root = Path(metadata["root"])
        symbol_targets = []
        result = report(root, metadata["known"], json.loads(sys.argv[2]),
                        metadata["comparisons"], symbol_targets)
        (root / "symbol-targets.json").write_text(json.dumps(symbol_targets), encoding="utf-8")
        print("N12 stack correlation: " + json.dumps(result), flush=True)
        controls = result["system_context"]
        if (not result["calibrated"] or not controls["flushed"]["explicit_flush"]
                or controls["untouched"]["identity"] != "confirmed"):
            sys.exit("The N12 stack calibration or comparison controls did not pass.")
        if "staggered" in metadata["comparisons"] and any(
            controls[label]["identity"] != "confirmed" for label in ("staggered-protected", "staggered-outside")
        ):
            sys.exit("The staggered comparison writes did not establish both file identities.")
    except (KeyError, OSError, ValueError, IndexError, TypeError):
        sys.exit("The N12 stack correlation could not validate the captured evidence.")
