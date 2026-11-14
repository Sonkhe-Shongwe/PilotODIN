"""Run the existing strict fixture with an extra, known write and EOF resize."""
import json
import ctypes
import os
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue
from threading import Thread, get_native_id
from xml.etree import ElementTree as ET

NATIVE = Path(__file__).resolve().parents[2] / "p4_native"
sys.path.insert(0, str(NATIVE))
import n12_etw_probe as probe

SIZE = 173
RETAIN = 83
FLUSHED_PAYLOAD = b"F" * 127
STACKS = {"FileWrite", "FileSetInformation", "FileFlush"}
KEYWORDS = {"ProcessThread", "Loader"}
STOP_DWELL_SECONDS = 20
WRITE_GAP_SECONDS = 5
SECOND_WRITE_OFFSET = 65_536
STAGGERED_PAYLOADS = ((0, b"A" * 4_133), (SECOND_WRITE_OFFSET, b"B" * 4_155))


def calibration(path):
    with path.open("xb", buffering=0) as stream:
        probe.verify_handle_path(stream, path)
        start = probe.utc_ticks()
        if stream.write(b"S" * SIZE) != SIZE:
            raise RuntimeError("The known stack-control write was incomplete.")
        write = [start, probe.utc_ticks()]
        start = probe.utc_ticks()
        stream.truncate(RETAIN)
        resize = [start, probe.utc_ticks()]
        os.fsync(stream.fileno())
    if path.read_bytes() != b"S" * RETAIN:
        raise RuntimeError("The known stack-control bytes and resize did not match.")
    return {"pid": os.getpid(), "tid": get_native_id(), "write": write, "resize": resize,
            "path": str(path), "size": SIZE, "final_size": RETAIN}


def flushed_comparison(path):
    with path.open("xb", buffering=0) as stream:
        probe.verify_handle_path(stream, path)
        first = probe.utc_ticks()
        if stream.write(FLUSHED_PAYLOAD) != len(FLUSHED_PAYLOAD):
            raise RuntimeError("The separate flushed comparison write was incomplete.")
        write_window = [first, probe.utc_ticks()]
        first = probe.utc_ticks()
        os.fsync(stream.fileno())
        print(json.dumps({"path": str(path), "size": len(FLUSHED_PAYLOAD),
                          "pid": os.getpid(), "tid": get_native_id(),
                          "write_window": write_window,
                          "flush_window": [first, probe.utc_ticks()]}), flush=True)
        # Keep the write handle alive through WPR rundown. The parent releases
        # it by closing the pipe after capture, without sending any payload.
        sys.stdin.buffer.read(1)


def windows_file_identity(stream):
    import msvcrt
    from ctypes import wintypes

    class FileIdInfo(ctypes.Structure):
        _fields_ = [("volume_serial", ctypes.c_uint64), ("file_id", ctypes.c_ubyte * 16)]

    info = FileIdInfo()
    query = ctypes.WinDLL("kernel32", use_last_error=True).GetFileInformationByHandleEx
    query.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.POINTER(FileIdInfo), wintypes.DWORD)
    query.restype = wintypes.BOOL
    file_id_info_class = 18
    if not query(msvcrt.get_osfhandle(stream.fileno()), file_id_info_class, ctypes.byref(info), ctypes.sizeof(info)):
        raise RuntimeError("Windows did not provide the generated file identity.")
    file_id = bytes(info.file_id)
    if not any(file_id):
        raise RuntimeError("Windows returned an empty generated file identifier.")
    return info.volume_serial, file_id


def verify_same_file(writer, reader):
    if windows_file_identity(writer) != windows_file_identity(reader):
        raise RuntimeError("The two generated handles refer to different files.")


def staggered_comparison(root):
    paths = {
        "staggered-protected": root / "synthetic-protected" / "staggered.bin",
        "staggered-outside": root / "staggered.bin",
    }
    with ExitStack() as handles:
        streams = {label: handles.enter_context(path.open("xb", buffering=0))
                   for label, path in paths.items()}
        evidence = {label: {"path": str(path), "writes": []} for label, path in paths.items()}
        for label, stream in streams.items():
            probe.verify_handle_path(stream, paths[label])
        for index, (offset, payload) in enumerate(STAGGERED_PAYLOADS):
            if index:
                time.sleep(WRITE_GAP_SECONDS)
            for label, stream in streams.items():
                stream.seek(offset)
                first = probe.utc_ticks()
                if stream.write(payload) != len(payload):
                    raise RuntimeError("A staggered comparison write was incomplete.")
                evidence[label]["writes"].append({"offset": offset, "size": len(payload),
                                                  "start": first, "end": probe.utc_ticks()})
        for label, path in paths.items():
            # Open the read-only witness after both deliberate writes. Keep the
            # original handles unflushed and report only the comparison result.
            reader = handles.enter_context(path.open("rb", buffering=0))
            probe.verify_handle_path(reader, path)
            verify_same_file(streams[label], reader)
            evidence[label]["same_file_distinct_handles"] = True
        print(json.dumps({"pid": os.getpid(), "tid": get_native_id(), "files": evidence}), flush=True)
        # Keep the unflushed handles open through rundown.
        sys.stdin.buffer.read(1)


def start_comparison(mode, path, handles):
    command = [sys.executable, "-B", __file__, mode, str(path)]
    child = handles.enter_context(subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True,
    ))

    def release():
        child.stdin.close()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()

    handles.callback(release)
    lines = Queue(maxsize=1)
    Thread(target=lambda: lines.put(child.stdout.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=15)
    except Empty as exc:
        raise RuntimeError("The comparison helper did not report readiness.") from exc
    if not line:
        raise RuntimeError("The comparison helper exited before reporting readiness.")
    evidence = json.loads(line)
    if evidence["pid"] != child.pid or evidence["pid"] == os.getpid() or child.poll() is not None:
        raise RuntimeError("The comparison helper identity was not established.")
    if mode == "flushed" and evidence["path"] != str(path):
        raise RuntimeError("The flushed comparison path was not established.")
    return evidence, child


def profile_for_capture(directory, run):
    exported = directory / "fileio.wprp"
    if run("-exportprofile", "FileIO", str(exported)).returncode != 0:
        raise RuntimeError("WPR could not export the built-in FileIO profile.")
    tree = ET.parse(exported)
    profiles = tree.getroot().find("Profiles")
    profile = next((item for item in profiles.findall("Profile")
                    if item.get("LoggingMode") == "Memory" and item.get("DetailLevel") == "Verbose"), None)
    reference = profile.find("./Collectors/SystemCollectorId/SystemProviderId") if profile is not None else None
    if reference is None:
        raise RuntimeError("The exported FileIO profile has no verbose memory system provider.")
    provider = next((item for item in profiles.findall("SystemProvider")
                     if item.get("Id") == reference.get("Value")), None)
    if provider is None:
        raise RuntimeError("The exported FileIO profile does not define its referenced system provider.")
    settings = {}
    changed = False
    for section, tag, required in (("Keywords", "Keyword", KEYWORDS), ("Stacks", "Stack", STACKS)):
        element = provider.find(section)
        present = {item.get("Value") for item in element} if element is not None else set()
        missing = required - present
        settings[section.casefold()] = sorted(required & present)
        if missing:
            changed = True
            if element is None:
                element = ET.SubElement(provider, section)
            for name in sorted(missing):
                ET.SubElement(element, tag, Value=name)
    settings["selected"] = "extended-fileio" if changed else "builtin-fileio"
    if not changed:
        return "FileIO", settings
    custom = directory / "fileio-with-stacks.wprp"
    profile_name = profile.get("Name")
    if not profile_name:
        raise RuntimeError("The exported profile has no selectable name.")
    tree.write(custom, encoding="utf-8", xml_declaration=True)
    return f"{custom}!{profile_name}", settings


def capture(root, metadata_path):
    with ExitStack() as handles:
        return capture_with_handles(root, metadata_path, handles)


def capture_with_handles(root, metadata_path, handles):
    run_process = subprocess.run
    run_fixture = probe.capture_fixture
    wpr = Path(os.environ["SystemRoot"]) / "System32" / "wpr.exe"

    def run_wpr(*args):
        return run_process([str(wpr), *args], timeout=45, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)

    profile, coverage = profile_for_capture(metadata_path.parent, run_wpr)
    print("N12 stack profile preflight: " + json.dumps(coverage), file=sys.stderr, flush=True)
    known = None
    comparisons = {}
    flushed_helper = None
    staggered_helper = None
    flushed_path = root / "flushed.bin"
    untouched_path = root / "untouched.bin"
    untouched_payload = b"pre-capture comparison"

    def prepare_comparisons():
        with untouched_path.open("xb", buffering=0) as seed:
            if seed.write(untouched_payload) != len(untouched_payload):
                raise RuntimeError("The untouched comparison seed write was incomplete.")
            os.fsync(seed.fileno())

    def open_comparisons():
        nonlocal flushed_helper
        comparisons["flushed"], flushed_helper = start_comparison("flushed", flushed_path, handles)
        first = probe.utc_ticks()
        stream = handles.enter_context(untouched_path.open("rb", buffering=0))
        open_window = [first, probe.utc_ticks()]
        probe.verify_handle_path(stream, untouched_path)
        first = probe.utc_ticks()
        payload = stream.read(len(untouched_payload))
        read_window = [first, probe.utc_ticks()]
        if payload != untouched_payload:
            raise RuntimeError("The untouched comparison seed could not be read.")
        comparisons["untouched"] = {"path": str(untouched_path), "size": len(payload),
                                    "open_window": open_window, "read_window": read_window}
        # The base fixture uses a returned comparison to trigger a primary
        # protected fsync. This hook only records the separate untouched file.
        return None

    class FixtureSubprocess:
        # Keep the existing isolated WPR instance and stop-time rundown.
        def __getattr__(self, name):
            return getattr(subprocess, name)

        def run(self, args, *positional, **options):
            if [str(item).casefold() for item in args[:3]] == [str(wpr).casefold(), "-start", "fileio"]:
                prepare_comparisons()
                args = [*args[:2], profile, *args[3:]]
                print("N12 stack trace start requested.", file=sys.stderr, flush=True)
            return run_process(args, *positional, **options)

    def capture_with_calibration(*args, **kwargs):
        stop = kwargs["before_stop"]

        def calibrate():
            nonlocal known
            command = [sys.executable, "-B", __file__, "control", str(root / "stack-control.bin")]
            child = run_process(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=15, check=False)
            if child.returncode:
                raise RuntimeError("The application stack controls did not complete.")
            known = json.loads(child.stdout)

        def calibrate_and_stop():
            nonlocal staggered_helper
            try:
                calibrate()
                staggered = os.environ.get("PILOTODIN_N12_STAGGERED_WRITES") == "1"
                if staggered:
                    comparisons["staggered"], staggered_helper = start_comparison("staggered", root, handles)
                if staggered or os.environ.get("PILOTODIN_N12_STOP_DWELL") == "1":
                    start = probe.utc_ticks()
                    time.sleep(STOP_DWELL_SECONDS)
                    comparisons["stop_dwell_start"] = start
            finally:
                comparisons["wpr_stop_start"] = probe.utc_ticks() // 10 * 10
                stopped = stop()
            return stopped

        kwargs["before_stop"] = calibrate_and_stop
        kwargs["open_comparison"] = open_comparisons
        print("N12 stack trace started.", file=sys.stderr, flush=True)
        return run_fixture(*args, **kwargs)

    probe.subprocess = FixtureSubprocess()
    probe.capture_fixture = capture_with_calibration
    try:
        fixture = probe.preopened_control(root, rundown=True)
    finally:
        probe.subprocess = subprocess
        probe.capture_fixture = run_fixture
    if flushed_helper is None or flushed_helper.poll() is not None:
        raise RuntimeError("The flushed comparison handle did not survive capture.")
    fixture["rundown_start_ticks"] = comparisons.pop("wpr_stop_start")
    for label, expected in (("protected", b"x" * 53), ("outside", b"x" * 79)):
        if Path(fixture["preopened"]["writes"][label]["path"]).read_bytes() != expected:
            raise RuntimeError("An original strict control payload did not match.")
    if flushed_path.read_bytes() != FLUSHED_PAYLOAD or untouched_path.read_bytes() != untouched_payload:
        raise RuntimeError("A separate comparison payload did not match.")
    if staggered_helper is not None:
        if staggered_helper.poll() is not None:
            raise RuntimeError("The staggered comparison handles did not survive capture.")
        (_, first), (offset, second) = STAGGERED_PAYLOADS
        expected = first + bytes(offset - len(first)) + second
        for path in (root / "synthetic-protected" / "staggered.bin", root / "staggered.bin"):
            if path.read_bytes() != expected:
                raise RuntimeError("A staggered comparison payload did not match.")
    metadata_path.write_text(json.dumps({"root": str(root), "known": known, "profile": coverage,
                                         "comparisons": comparisons}), encoding="utf-8")
    return fixture


if __name__ == "__main__":
    try:
        if sys.argv[1] in ("control", "flushed", "staggered"):
            path = Path(sys.argv[2])
            guard_path = path / "synthetic-protected" if sys.argv[1] == "staggered" else path.parent
            probe.local_disposable_path(guard_path, runner_temp_only=True)
            if sys.argv[1] == "flushed":
                flushed_comparison(path)
            elif sys.argv[1] == "staggered":
                staggered_comparison(path)
            else:
                print(json.dumps(calibration(path)))
        else:
            root = probe.local_disposable_path(Path(sys.argv[1]), runner_temp_only=True)
            result = capture(root, Path(os.environ["PILOTODIN_N12_STACK_META"]))
            print(json.dumps(result))
    except RuntimeError as exc:
        sys.exit(str(exc))
    except (OSError, ValueError, IndexError, ET.ParseError, subprocess.SubprocessError):
        sys.exit("The hosted stack capture could not complete.")
