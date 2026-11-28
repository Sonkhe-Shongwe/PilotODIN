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
TMP_BEGIN = "PILOTODIN_TMP_BEGIN"
TMP_END = "PILOTODIN_TMP_END"


def debugger_tmp_status(output, expected):
    lines = output.splitlines()
    markers = [(index, line.strip()) for index, line in enumerate(lines)
               if line.strip() in (TMP_BEGIN, TMP_END)]
    if not markers:
        return "initial-break-output-missing"
    if [marker for _, marker in markers] != [TMP_BEGIN, TMP_END]:
        return "initial-break-output-incomplete"
    lines = lines[markers[0][0] + 1:markers[1][0]]
    headers = [(index, line.strip()) for index, line in enumerate(lines)
               if line.lstrip().casefold().startswith("environment:")]
    if not headers:
        if re.search(r"type information missing|symbols are not available|symbol file could not be found",
                     "\n".join(lines), re.I):
            return "debugger-symbols-unavailable"
        return "environment-section-missing"
    if len(headers) != 1:
        return "environment-section-ambiguous"
    index, header = headers[0]
    if not re.fullmatch(r"Environment:[ \t]+(?:0x[0-9a-f]+|[0-9a-f]+(?:`[0-9a-f]+)?)", header, re.I):
        return "environment-section-unrecognized"
    values = []
    for line in "\n".join(lines[index + 1:]).lstrip("\n").splitlines():
        entry = re.fullmatch(r"[ \t]+([^=]+)=(.*)", line)
        if entry is None:
            break
        if entry[1].casefold() == "tmp":
            values.append(entry[2])
    if not values:
        return "tmp-not-observed"
    if len(values) > 1:
        return "tmp-ambiguous"
    try:
        observed = trace.windows_path(values[0])
    except ValueError:
        return "tmp-path-invalid"
    return "expected-tmp" if observed == trace.windows_path(str(expected)) else "tmp-value-mismatch"


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
             "-c", f".echo {TMP_BEGIN}; !peb; .echo {TMP_END}; g", sys.executable, "-I", "-S", str(child)],
            cwd=work, env={"SystemRoot": env["SystemRoot"], "TMP": str(launch_tmp), "TEMP": str(fallback_temp)},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", timeout=35, check=False,
        )
        trace.require(result.returncode == 0, "CDB did not complete the generated child run")
        trace.require((work / "child.completed").is_file(), "generated child did not complete")
        status = debugger_tmp_status(result.stdout, launch_tmp)
    return {"scope": "one-generated-child", "status": "PASS" if status == "expected-tmp" else "BLOCKED",
            "initial_breakpoint_tmp": status, "child_completed": True,
            "debugger_sha256": build.digest(debugger), "source_sha": source}


if __name__ == "__main__":
    try:
        result = run_fixture()
        print(json.dumps(result, sort_keys=True))
        sys.exit(0 if result["status"] == "PASS" else 2)
    except trace.EvidenceValidationError as exc:
        print(f"N12 TMP debugger fixture blocked: {exc}", file=sys.stderr)
        sys.exit(2)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"N12 TMP debugger fixture blocked: {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
