"""Run the existing strict fixture with an extra, known write and EOF resize."""
import json
import os
import subprocess
import sys
from pathlib import Path
from threading import get_native_id
from xml.etree import ElementTree as ET

NATIVE = Path(__file__).resolve().parents[2] / "p4_native"
sys.path.insert(0, str(NATIVE))
import n12_etw_probe as probe

SIZE = 173
RETAIN = 83
STACKS = {"FileWrite", "FileSetInformation", "FileFlush"}
KEYWORDS = {"ProcessThread", "Loader"}


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
    run_process = subprocess.run
    run_fixture = probe.capture_fixture
    wpr = Path(os.environ["SystemRoot"]) / "System32" / "wpr.exe"

    def run_wpr(*args):
        return run_process([str(wpr), *args], timeout=45, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)

    profile, coverage = profile_for_capture(metadata_path.parent, run_wpr)
    print("N12 stack profile preflight: " + json.dumps(coverage), file=sys.stderr, flush=True)
    known = None

    class FixtureSubprocess:
        # Keep the existing isolated WPR instance and stop-time rundown.
        def __getattr__(self, name):
            return getattr(subprocess, name)

        def run(self, args, *positional, **options):
            if [str(item).casefold() for item in args[:3]] == [str(wpr).casefold(), "-start", "fileio"]:
                args = [*args[:2], profile, *args[3:]]
                print("N12 stack trace start requested.", file=sys.stderr, flush=True)
            return run_process(args, *positional, **options)

    def capture_with_calibration(*args, **kwargs):
        compare = kwargs["open_comparison"]

        def with_calibration():
            nonlocal known
            print("N12 stack trace started.", file=sys.stderr, flush=True)
            command = [sys.executable, "-B", __file__, "control", str(root / "stack-control.bin")]
            child = run_process(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=15, check=False)
            if child.returncode:
                raise RuntimeError("The application stack controls did not complete.")
            known = json.loads(child.stdout)
            return compare()

        kwargs["open_comparison"] = with_calibration
        return run_fixture(*args, **kwargs)

    probe.subprocess = FixtureSubprocess()
    probe.capture_fixture = capture_with_calibration
    try:
        fixture = probe.preopened_control(root, rundown=True, system_timing=True)
    finally:
        probe.subprocess = subprocess
        probe.capture_fixture = run_fixture
    metadata_path.write_text(json.dumps({"root": str(root), "known": known, "profile": coverage}),
                             encoding="utf-8")
    return fixture


if __name__ == "__main__":
    try:
        if sys.argv[1] == "control":
            path = Path(sys.argv[2])
            probe.local_disposable_path(path.parent, runner_temp_only=True)
            print(json.dumps(calibration(path)))
        else:
            root = probe.local_disposable_path(Path(sys.argv[1]), runner_temp_only=True)
            result = capture(root, Path(os.environ["PILOTODIN_N12_STACK_META"]))
            print(json.dumps(result))
    except RuntimeError as exc:
        sys.exit(str(exc))
    except (OSError, ValueError, IndexError, ET.ParseError, subprocess.SubprocessError):
        sys.exit("The hosted stack capture could not complete.")
