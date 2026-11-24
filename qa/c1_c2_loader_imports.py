"""Paired, static MSVC import/export diagnosis. Never launch a test executable.

The comparison is intentionally bounded: named eager imports in two generated
test PE files, against direct System32 export tables. API-set mapping, ordinal
imports, forwarded targets, delay loads and transitive DLL resolution are not
proved here. A missing named export is a candidate, not automatic root cause.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

DLL = re.compile(r"^\s+([A-Za-z0-9_.-]+\.dll)\s*$", re.I)
IMPORT = re.compile(r"^\s+([0-9A-Fa-f]+)\s+([^\s]+)\s*$")
EXPORT = re.compile(r"^\s+\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]{8}\s+(\S+)(?:\s.*)?$")
FORWARD = re.compile(r"^\s+\d+\s+[0-9A-Fa-f]+\s+(\S+)\s+\(forwarded to .+\)\s*$", re.I)


def parse_imports(text):
    result = {}
    current = None
    eager = False
    for line in text.splitlines():
        if "Section contains the following imports:" in line:
            eager = True
            current = None
            continue
        if "Section contains the following delay load imports:" in line or line.strip() == "Summary":
            eager = False
            current = None
        if not eager:
            continue
        dll = DLL.fullmatch(line)
        if dll:
            current = dll[1].lower()
            result.setdefault(current, set())
        elif current:
            name = IMPORT.fullmatch(line)
            if name:
                result[current].add(name[2])
    if not result or not any(result.values()):
        raise ValueError("No named eager import table parsed")
    return result


def parse_exports(text):
    names = set()
    for line in text.splitlines():
        match = EXPORT.fullmatch(line) or FORWARD.fullmatch(line)
        if match:
            names.add(match[1])
    if not names:
        raise ValueError("No named exports parsed")
    return names


class ParserTests(unittest.TestCase):
    def test_eager_only(self):
        text = """  Section contains the following imports:
    KERNEL32.dll
          14000 Import Address Table
              0 time date stamp
                 10F GetModuleHandleW
                 12A CreateFileW
    USER32.dll
                  45 MessageBoxW
  Section contains the following delay load imports:
    other.dll
                  10 Delayed
  Summary"""
        self.assertEqual(parse_imports(text), {"kernel32.dll": {"GetModuleHandleW", "CreateFileW"}, "user32.dll": {"MessageBoxW"}})

    def test_exports_and_forward(self):
        self.assertEqual(parse_exports("""  ordinal hint RVA      name
      1    0 00012345 Present
      2    1 Forwarded (forwarded to KERNELBASE.Other)
      3    2 00012500 Decorated = Other
  Summary"""), {"Present", "Forwarded", "Decorated"})

    def test_refuse_unparsed(self):
        for parser in (parse_imports, parse_exports):
            with self.assertRaises(ValueError):
                parser("not a table")


def owned_file(path, root):
    p = Path(path).resolve(strict=True)
    if not p.is_file() or not p.is_relative_to(root):
        raise ValueError("Diagnostic path outside exact owned root")
    return p


def dump(tool, kind, path):
    r = subprocess.run([str(tool), kind, str(path)], capture_output=True,
                       text=True, errors="replace", timeout=30, check=True)
    if len(r.stdout) > 16 * 1024 * 1024:
        raise ValueError("Unexpected dumpbin output size")
    return r.stdout


def diagnose(args):
    if (os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or os.environ.get("PILOTODIN_C1_C2_LOADER_APPROVAL") != "STATIC_IMPORT_DIAGNOSIS_ONCE"):
        raise RuntimeError("Static diagnostic not authorized")
    runner = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    root = Path(args.root).resolve(strict=True)
    if root.parent != runner or not root.name.startswith("pilotodin-c1-c2-loader-"):
        raise ValueError("Diagnostic root not isolated")
    old = owned_file(args.baseline, root / "baseline")
    new = owned_file(args.fixture, root / "fixture")
    if old.suffix.lower() != ".exe" or new.suffix.lower() != ".exe":
        raise ValueError("Expected compiled test executables")
    tool = Path(args.dumpbin).resolve(strict=True)
    if tool.name.lower() != "dumpbin.exe" or not tool.is_file():
        raise ValueError("Expected hosted MSVC dumpbin")
    system = (Path(os.environ["SystemRoot"]) / "System32").resolve(strict=True)
    tables = {}
    for label, exe in (("baseline", old), ("fixture", new)):
        data = dump(tool, "/imports", exe)
        (root / (label + "-imports.txt")).write_text(data, encoding="utf-8")
        tables[label] = parse_imports(data)
        print("IMPORT-COUNTS", label, len(tables[label]),
              sum(map(len, tables[label].values())))
    delta = {dll: sorted(names - tables["baseline"].get(dll, set()))
             for dll, names in tables["fixture"].items()}
    delta = {dll: names for dll, names in delta.items() if names}
    if sum(map(len, delta.values())) > 2000:
        raise ValueError("Unexpectedly large new named-import inventory")
    missing, unresolved = [], []
    for dll, names in sorted(delta.items()):
        print("FIXTURE-ONLY-IMPORTS", dll, json.dumps(names))
        if dll.startswith(("api-ms-", "ext-ms-")):
            unresolved.append((dll, "API-set mapping not evaluated"))
            continue
        candidate = system / dll
        if not candidate.is_file():
            unresolved.append((dll, "Not found directly in System32"))
            continue
        # No LoadLibrary, injection, process observation, or DLL replacement.
        try:
            exports = parse_exports(dump(tool, "/exports", candidate))
        except (ValueError, subprocess.SubprocessError):
            unresolved.append((dll, "Export table unavailable or unparsed"))
            continue
        for name in names:
            if name not in exports:
                missing.append((dll, name))
    print("DIRECT-SYSTEM32-MISSING-EXPORT-CANDIDATES", json.dumps(missing))
    print("UNRESOLVED-IMPORT-MODULES", json.dumps(unresolved))
    print("STATIC-IMPORT-DIAGNOSIS-COMPLETE: not loader proof; no test executable run")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    else:
        p = argparse.ArgumentParser()
        for arg in ("root", "baseline", "fixture", "dumpbin"):
            p.add_argument("--" + arg, required=True)
        diagnose(p.parse_args())
