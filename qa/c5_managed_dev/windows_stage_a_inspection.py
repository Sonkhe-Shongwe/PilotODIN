"""Standalone Windows A archive evidence adapter (inert; local bytes only).

Reuse the existing bounded ZIP/TAR reader. No transport, extraction, CLI,
subprocess, installation, native load, provenance claim, or use clearance.
"""
import hashlib
import json

from . import inspection_core as core

LIVE_ENABLED = False
PLAN_PIN = "bd7bf96a067af2277728818b6aa4f759f6babac9"


def exact_plan(raw):
    core.need(len(raw) <= core.MAX_META and
              core.digest(b"blob " + str(len(raw)).encode() + b"\0" + raw, "sha1") == PLAN_PIN,
              "STANDALONE_PLAN_PIN")
    plan = core.strict_json(raw)
    runtime = plan["runtime_candidate"]
    inputs = plan["inputs"]
    core.need(plan["execution_enabled"] is False and plan["python_qualified_patch"] is None
              and runtime["approved_runtime_archive_requests"] == 0
              and plan["limits"]["approved_application_archive_requests"] == 0,
              "STANDALONE_DISARM")
    core.need(plan["profile"] == "windows-x64-cp311-source-test"
              and runtime["target"] == "x86_64-pc-windows-msvc"
              and runtime["version"] == "3.11.18" and len(inputs) == 8
              and len({r["filename"] for r in [runtime, *inputs]}) == 9
              and len({r["url"] for r in [runtime, *inputs]}) == 9
              and sum(r["bytes"] for r in inputs) == 8000481
              and runtime["bytes"] == 49096635 and plan["expected_count"] == 19,
              "STANDALONE_SCOPE")
    return plan


def runtime_inventory(raw, row):
    core.need(len(raw) == row["bytes"] == 49096635
              and core.digest(raw) == row["sha256"], "RUNTIME_IDENTITY")
    paths = core.Paths()
    notices, native, embedded_wheels = [], [], []
    notice_total = 0

    def consume(reader, name, size, directory):
        nonlocal notice_total
        core.need(name == "python" and directory or name.startswith("python/"),
                  "RUNTIME_ROOT")
        if directory:
            return
        base = name.rsplit("/", 1)[-1]
        is_notice = bool(core.NOTICE.fullmatch(base) or
                         "/licenses/" in name.lower() or
                         ".dist-info/licenses/" in name.lower())
        if is_notice:
            notice_total += size
            core.need(notice_total <= core.MAX_NOTICES, "NOTICE_CAP")
        h = hashlib.sha256()
        prefix = b""
        left = size
        while left:
            chunk = core.exact(reader, min(left, core.CHUNK))
            if not prefix:
                prefix = chunk[:8]
            h.update(chunk)
            left -= len(chunk)
        item = {"path": name, "bytes": size, "sha256": h.hexdigest()}
        if is_notice:
            notices.append(item)
        if core.NATIVE.search(name) or prefix.startswith((b"MZ", b"\x7fELF", b"!<arch>\n")):
            native.append(dict(item, format="PE" if prefix.startswith(b"MZ") else "UNRESOLVED"))
        if name.lower().endswith(".whl"):
            embedded_wheels.append(item)

    # The existing npm branch is the strict, bounded gzip/TAR reader; it is
    # used only as a container format here, not to apply npm package semantics.
    # Unsupported TAR record types are refused, not extracted or normalised.
    core.members(raw, "npm", paths, consume)
    core.need({"python/python.exe", "python/python311.dll"}.issubset(
        {r["path"].casefold() for r in native if r["format"] == "PE"}),
        "RUNTIME_EXPECTED_PE")
    core.need(bool(notices), "RUNTIME_NOTICES_MISSING")
    return {"filename": row["filename"], "members": len(paths.seen),
            "expanded_bytes": paths.total, "notices": notices,
            "native": native, "embedded_wheels": embedded_wheels,
            "status": "UNRESOLVED_PROVENANCE_COMPONENTS_RIGHTS_SECURITY"}


def inspect_archive(raw_plan, filename, raw):
    """Return bounded local archive facts; caller must separately qualify use."""
    plan = exact_plan(raw_plan)
    runtime = plan["runtime_candidate"]
    matches = [r for r in [runtime, *plan["inputs"]] if r["filename"] == filename]
    core.need(len(matches) == 1, "ARCHIVE_SCOPE")
    row = matches[0]
    if row is runtime:
        receipt = runtime_inventory(raw, row)
    else:
        facts = dict(row, kind="pip" if filename.startswith("pip-") else "wheel")
        receipt = core.inspect(raw, facts)
        if row.get("name") == "pypdfium2":
            expected = [dict(n, format="PE") for n in row["native"]]
            core.need(receipt["native"] == expected, "PDFIUM_NATIVE_IDENTITY")
        else:
            core.need(not receipt["native"], "UNEXPECTED_SMOKE_NATIVE")
    core.need(len(json.dumps(receipt, ensure_ascii=True).encode()) <= core.MAX_OUTPUT,
              "RECEIPT_CAP")
    return receipt


if __name__ == "__main__":
    raise SystemExit("STANDALONE_A_INSPECTION_DISARMED")
