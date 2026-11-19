"""Read the launch TMP of one generated Windows child at CDB's initial break."""
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_build as build


CONSENT = "I_APPROVE_ONE_N12_TMP_DEBUGGER_FIXTURE"


def matches_debugger_tmp(output, expected):
    sections = re.split(r"^\s*Environment:[ \t]+[0-9a-f`]+[ \t]*\r?$", output, flags=re.M | re.I)
    if len(sections) != 2:
        return False
    values = []
    for line in sections[1].lstrip("\r\n").splitlines():
        entry = re.fullmatch(r"[ \t]+([^=]+)=(.*)", line)
        if entry is None:
            break
        if entry[1].casefold() == "tmp":
            values.append(entry[2])
    try:
        return len(values) == 1 and trace.windows_path(values[0]) == trace.windows_path(str(expected))
    except ValueError:
        return False


def run_fixture():
    env = os.environ
    source = env.get("PILOTODIN_N12_TMP_DEBUGGER_SOURCE", "")
    trace.require(sys.platform == "win32" and struct.calcsize("P") == 8
                  and env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted"
                  and env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_RUN_ATTEMPT") == "1"
                  and env.get("GITHUB_REF_NAME") == build.BRANCH
                  and env.get("PILOTODIN_N12_TMP_DEBUGGER_CONSENT") == CONSENT
                  and re.fullmatch(r"[0-9a-f]{40}", source)
                  and build.git("rev-parse", "HEAD") == source
                  and not build.git("status", "--porcelain", "--untracked-files=no"),
                  "exact-source hosted Windows approval required")
    debugger = Path(env["ProgramFiles(x86)"]) / "Windows Kits" / "10" / "Debuggers" / "x64" / "cdb.exe"
    trace.require(debugger.is_file(), "cached x64 CDB is unavailable")
    with TemporaryDirectory(prefix="pilotodin-tmp-fixture-", dir=env["RUNNER_TEMP"]) as folder:
        work = trace.local_disposable_path(Path(folder), runner_temp_only=True)
        launch_tmp, fallback_temp = work / "launch-tmp", work / "fallback-temp"
        launch_tmp.mkdir()
        fallback_temp.mkdir()
        child = work / "child.py"
        child.write_text(
            "import os\nfrom pathlib import Path\n"
            "assert Path(os.environ['TMP']) == Path.cwd() / 'launch-tmp'\n"
            "Path('child.completed').touch(exist_ok=False)\n",
            encoding="ascii",
        )
        result = subprocess.run(
            [str(debugger), "-noshell", "-sins", "-netsyms:no", "-y", str(work), "-G",
             "-c", "!peb; g", sys.executable, "-I", "-S", str(child)],
            cwd=work, env={"SystemRoot": env["SystemRoot"], "TMP": str(launch_tmp), "TEMP": str(fallback_temp)},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", timeout=35, check=False,
        )
        trace.require(result.returncode == 0, "CDB did not complete the generated child run")
        trace.require((work / "child.completed").is_file(), "generated child did not complete")
        trace.require(matches_debugger_tmp(result.stdout, launch_tmp), "initial breakpoint TMP did not verify")
    return {"scope": "one-generated-child", "status": "PASS", "initial_breakpoint_tmp": "expected-tmp",
            "debugger_sha256": build.digest(debugger), "source_sha": source}


if __name__ == "__main__":
    try:
        print(json.dumps(run_fixture(), sort_keys=True))
    except trace.EvidenceValidationError as exc:
        print(f"N12 TMP debugger fixture blocked: {exc}", file=sys.stderr)
        sys.exit(2)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"N12 TMP debugger fixture blocked: {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
