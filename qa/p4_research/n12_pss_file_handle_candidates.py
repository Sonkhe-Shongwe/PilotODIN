"""G2.10 inert process-scoped PSS file-handle *candidate* admission.

No Win32 API calls, process enumeration, file reads, ETW or acceptance.
A matching handle number across snapshots does not establish same object.
"""
MAX_HANDLES = 256
MAX_TICKS = 50_000_000
SOURCE = "PSS_WALK_HANDLES"
BLOCKERS = frozenset({"NONE", "SCHEMA", "PROCESS", "SCOPE", "CLOCK",
                      "TABLE", "HANDLE", "TYPE"})


def fixed(reason, candidate=False):
    return {
        "scope": "g2-10-process-scoped-pss-candidate-only",
        "status": "CANDIDATE_ONLY" if candidate else "BLOCKED",
        "blocker": "NONE" if candidate else reason if reason in BLOCKERS else "SCHEMA",
        "witness_origin": "UNVERIFIED_CALLER_INPUT",
        "original_file_handle_provenance": "NOT_VERIFIED",
        "handle_reuse_excluded": False,
        "kernel_fileobject_etw_join": "NOT_ESTABLISHED",
        "same_object_at_write": "NOT_ESTABLISHED",
        "physical_destination": "NOT_VERIFIED",
        "native_N12_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }


def positive(x):
    return type(x) is int and x > 0


def parse_rows(rows):
    if type(rows) is not list or len(rows) > MAX_HANDLES:
        return None
    result = {}
    for row in rows:
        if (type(row) is not dict
                or set(row) != {"handle", "type_name", "object_type", "flags"}
                or not positive(row["handle"])
                or type(row["type_name"]) is not str or len(row["type_name"]) > 64
                or type(row["object_type"]) is not int or not 0 <= row["object_type"] <= 6
                or type(row["flags"]) is not int or not 0 <= row["flags"] <= 15
                or row["handle"] in result):
            return None
        result[row["handle"]] = row
    return result


def review_candidate(*, process, before, after, write):
    """Assess caller-supplied snapshot shapes, never authenticate Win32 facts."""
    if any(type(x) is not dict for x in (process, before, after, write)):
        return fixed("SCHEMA")
    if (set(process) != {"pid", "birth", "exit", "original_process_handle_verified",
                         "etw_sequence_verified", "image_verified", "disposable_qa_verified"}
            or any(set(s) != {"source", "pid", "birth", "tick", "complete", "rows"}
                   for s in (before, after))
            or set(write) != {"pid", "birth", "handle", "request", "completion"}):
        return fixed("SCHEMA")
    if (not all(positive(process[k]) for k in ("pid", "birth", "exit"))
            or process["birth"] >= process["exit"]
            or not all(process[k] is True for k in
                       ("original_process_handle_verified", "etw_sequence_verified",
                        "image_verified", "disposable_qa_verified"))
            or not all(positive(write[k]) for k in ("pid", "birth"))
            or (write["pid"], write["birth"]) != (process["pid"], process["birth"])):
        return fixed("PROCESS")
    for snap in (before, after):
        if (snap["source"] != SOURCE or snap["complete"] is not True
                or not all(positive(snap[k]) for k in ("pid", "birth"))
                or (snap["pid"], snap["birth"]) != (process["pid"], process["birth"])):
            return fixed("SCOPE")
    if (not all(positive(n) for n in
                (before["tick"], after["tick"], write["request"], write["completion"]))
            or not process["birth"] < before["tick"] < write["request"]
            < write["completion"] < after["tick"] < process["exit"]
            or after["tick"] - before["tick"] > MAX_TICKS):
        return fixed("CLOCK")
    left, right = parse_rows(before["rows"]), parse_rows(after["rows"])
    if left is None or right is None:
        return fixed("TABLE")
    handle = write["handle"]
    if not positive(handle) or handle not in left or handle not in right:
        return fixed("HANDLE")
    for row in (left[handle], right[handle]):
        # PSS_OBJECT_TYPE has no File enum. File TypeName is only a hypothesis.
        if (row["type_name"] != "File" or row["object_type"] != 0
                or (row["flags"] & 1) != 1):
            return fixed("TYPE")
    # Identical numeric handles may still refer to different file objects.
    return fixed("NONE", candidate=True)
