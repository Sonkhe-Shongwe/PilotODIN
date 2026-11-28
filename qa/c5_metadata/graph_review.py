"""Offline candidate graph review of the exact C5 release metadata receipt.

Uses packaging already present in the reviewed source-test environment.
No installer, resolver, subprocess, network access, or lock-writing interface.
Release-level declarations are not selected-wheel METADATA or approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import cpython_tags, compatible_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from tools.build_input_preflight import (
    Blocked, checked_directory, read_exact, require, strict_json, audit_policy,
)

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = "qa/c5_metadata/release_metadata_receipt_20261125.jsonl"
RECEIPT_SHA = "2c9329e146f75fe3ba8c832f165660fd1e01027447c5adff28984093472e866b"
OBSERVED = "contracts/c5_observed_python_wheels_2026-11-25.json"
OBSERVED_BLOB = "6ccd3d47efe363ecf87fd13ce7d867cba4bef020"
TARGETS = {
    "windows-x64-cp311-source-test": ("3.11.9", "win32"),
    "linux-x64-cp311-source-test": ("3.11.18", "linux"),
}
UNKNOWN_MARKER_VARS = {"platform_release", "platform_version"}
MAX_SOURCE = 1024 * 1024


def canonical_source(root, relative):
    """Read a fixed source path; normalize only canonical Git text line endings."""
    checked_directory(root)
    path = root
    parts = relative.split("/")
    for part in parts[:-1]:
        path = path / part
        checked_directory(path)
    path = path / parts[-1]
    _, raw = read_exact(path, size=path.lstat().st_size, collect=True,
                        limit=MAX_SOURCE)
    return raw.replace(b"\r\n", b"\n")


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def load_inputs(root=ROOT):
    audit_policy(root)
    raw = canonical_source(root, RECEIPT)
    require(hashlib.sha256(raw).hexdigest() == RECEIPT_SHA, "METADATA_RECEIPT_PIN")
    lines = raw.splitlines()
    require(len(lines) == 50, "RECEIPT_RELEASE_COUNT")
    releases = {}
    for line in lines:
        row = strict_json(line)
        key = (row["name"], row["version"])
        require(row["status"] == "RELEASE_JSON_OBSERVED" and key not in releases,
                "RECEIPT_RELEASE_IDENTITY")
        releases[key] = row
    raw = canonical_source(root, OBSERVED)
    require(git_blob(raw) == OBSERVED_BLOB, "OBSERVED_INVENTORY_PIN")
    inv = strict_json(raw)
    require(len(inv["profiles"]) == 2 and
            {p["profile"] for p in inv["profiles"]} == set(TARGETS),
            "TARGET_PROFILE_SET")
    roots = []
    for rel in ("backend/requirements.txt", "backend/requirements-test.txt"):
        for rawline in canonical_source(root, rel).decode("utf-8").splitlines():
            line = rawline.strip()
            if not line or line.startswith("#"):
                continue
            if rel.endswith("-test.txt") and line == "-r requirements.txt":
                continue
            require(not line.startswith("-"), "UNSUPPORTED_ROOT_DIRECTIVE")
            req = Requirement(line)
            require(not req.url and req.marker is None, "UNSUPPORTED_ROOT_REQUIREMENT")
            roots.append(req)
    require(len(roots) == 14 and len({canonicalize_name(x.name) for x in roots}) == 14,
            "ROOT_SET")
    return inv, releases, roots


def target_environment(python, platform):
    require((python, platform) in TARGETS.values(), "UNREVIEWED_TARGET")
    # Override every host default used by PEP 508. Unknown OS release/version
    # is not guessed: markers requiring either are explicitly refused.
    return {
        "implementation_name": "cpython", "implementation_version": python,
        "python_full_version": python, "python_version": "3.11",
        "platform_python_implementation": "CPython",
        "sys_platform": platform, "os_name": "nt" if platform == "win32" else "posix",
        "platform_system": "Windows" if platform == "win32" else "Linux",
        "platform_machine": "AMD64" if platform == "win32" else "x86_64",
        "platform_release": "", "platform_version": "", "extra": "",
    }


def marker_active(req, environment, extras):
    if req.marker is None:
        return True
    # Strip quoted literal values before checking unsupported environment vars.
    unquoted = re.sub(r'"[^"]*"|\'[^\']*\'', "", str(req.marker))
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", unquoted))
    require(not words.intersection(UNKNOWN_MARKER_VARS | {"extras", "dependency_groups"}),
            "UNVERIFIED_MARKER_ENVIRONMENT")
    return any(req.marker.evaluate(environment={**environment, "extra": x})
               for x in sorted(set(extras) | {""}))


def candidate_tags(platform):
    if platform == "win32":
        platforms = ["win_amd64"]
    elif platform == "linux":
        # Conservative candidate policy: all observed Linux tags are at most
        # manylinux_2_28. This is not evidence of the runner's actual glibc.
        platforms = [f"manylinux_2_{n}_x86_64" for n in range(28, 4, -1)]
        platforms += ["manylinux2014_x86_64", "manylinux2010_x86_64",
                      "manylinux1_x86_64"]
    else:
        raise Blocked("UNREVIEWED_PLATFORM")
    return set(cpython_tags((3, 11), abis=["cp311"], platforms=platforms)) | set(
        compatible_tags((3, 11), interpreter="cp311", platforms=platforms))


def check_python(declared, python):
    if declared is None:
        return "UNKNOWN"
    require(type(declared) is str and bool(declared.strip()), "INVALID_REQUIRES_PYTHON")
    require(SpecifierSet(declared).contains(Version(python)), "REQUIRES_PYTHON_CONFLICT")
    return "COMPATIBLE_DECLARATION"


def check_requirement(req, selected):
    name = canonicalize_name(req.name)
    require(req.url is None, "DIRECT_URL_REQUIREMENT")
    require(name in selected, "DECLARED_DEPENDENCY_MISSING")
    require(req.specifier.contains(Version(selected[name]["version"])),
            "DECLARED_VERSION_CONFLICT")
    return name


def review_profile(profile, releases, roots):
    profile_id = profile["profile"]
    python, platform = TARGETS[profile_id]
    require(profile["observed_cpython"] == python and profile["platform"] == platform
            and profile["architecture"] == "x64" and profile["status"] == "OBSERVED_ONLY_BLOCKED"
            and len(profile["selected_wheels"]) == 49, "TARGET_PROFILE_IDENTITY")
    env, tags = target_environment(python, platform), candidate_tags(platform)
    selected, metadata, nodes = {}, {}, []
    for item in profile["selected_wheels"]:
        name, version, filename = item["name"], item["version"], item["filename"]
        require(name not in selected, "DUPLICATE_SELECTED_PACKAGE")
        row = releases.get((name, version))
        require(row is not None, "RELEASE_METADATA_MISSING")
        matches = [w for w in row["selected_wheels"] if w["filename"] == filename]
        require(len(matches) == 1, "WHEEL_METADATA_MISSING")
        wheel = matches[0]
        parsed_name, parsed_version, _, wheel_tags = parse_wheel_filename(filename)
        require(parsed_name == name and parsed_version == Version(version)
                and bool(tags.intersection(wheel_tags)), "WHEEL_TAG_OR_IDENTITY_CONFLICT")
        require(wheel["yanked"] is False and type(wheel["bytes"]) is int and wheel["bytes"] > 0
                and re.fullmatch("[0-9a-f]{64}", wheel["sha256"]), "WHEEL_METADATA_INVALID")
        selected[name], metadata[name] = item, row
        nodes.append({
            "name": name, "version": version, "filename": filename,
            "sha256": wheel["sha256"], "bytes": wheel["bytes"],
            "source": wheel["url"], "metadata_source": row["metadata_url"],
            "release_python": check_python(row["requires_python"], python),
            "wheel_python": check_python(wheel["requires_python"], python),
            "license_expression": row["license_expression"],
            "license_state": "DECLARED_NOT_REVIEWED",
            "selected_wheel_metadata": "UNVERIFIED",
            "release_requires_dist": "UNKNOWN" if row["requires_dist_release_level"] is None
            else "DECLARED",
        })
    extras, root_names = {}, set()
    for req in roots:
        name = check_requirement(req, selected)
        root_names.add(name)
        extras.setdefault(name, set()).update(canonicalize_name(e) for e in req.extras)
    # Fixed point propagates newly requested extras even through cycles.
    for _ in range(len(selected) * 4):
        changed = False
        for name, enabled in list(extras.items()):
            declarations = metadata[name]["requires_dist_release_level"]
            for declaration in declarations or []:
                req = Requirement(declaration)
                if not marker_active(req, env, enabled):
                    continue
                target = check_requirement(req, selected)
                requested = {canonicalize_name(x) for x in req.extras}
                if target not in extras:
                    extras[target] = set()
                    changed = True
                if not requested <= extras[target]:
                    extras[target].update(requested)
                    changed = True
        if not changed:
            break
    else:
        raise Blocked("EXTRAS_CLOSURE_LIMIT")
    require(set(extras) == set(selected), "UNEXPLAINED_SELECTED_PACKAGE")
    edges, inactive = [], 0
    for name in sorted(extras):
        for declaration in metadata[name]["requires_dist_release_level"] or []:
            req = Requirement(declaration)
            if marker_active(req, env, extras[name]):
                edges.append({"from": name, "to": check_requirement(req, selected),
                              "requirement": declaration})
            else:
                inactive += 1
    return {
        "profile": profile_id, "python_candidate": python, "platform": platform,
        "status": "BLOCKED", "declared_graph": "COMPATIBLE_PARTIAL",
        "root_requirements": sorted(str(x) for x in roots),
        "reachable_packages": len(extras), "active_edges": edges,
        "inactive_declarations": inactive,
        "enabled_extras": {k: sorted(v) for k, v in extras.items() if v},
        "unknown_release_dependencies": sorted(n for n, row in metadata.items()
                                               if row["requires_dist_release_level"] is None),
        "nodes": sorted(nodes, key=lambda x: x["name"]),
        "blockers": ["selected_wheel_metadata", "unknown_release_dependencies",
                     "actual_wheel_bytes", "exact_interpreter_and_pip",
                     "physical_platform_tag_evidence", "license_review",
                     "installed_graph_and_native_inventory"],
    }


def review(root=ROOT):
    inv, releases, roots = load_inputs(root)
    return {"schema_version": 1, "status": "BLOCKED",
            "receipt_sha256": RECEIPT_SHA,
            "profiles": [review_profile(p, releases, roots) for p in inv["profiles"]]}


def main():
    report = review()
    for p in report["profiles"]:
        summary = {
            "profile": p["profile"], "status": p["status"],
            "declared_graph": p["declared_graph"], "roots": len(p["root_requirements"]),
            "reachable": p["reachable_packages"], "active_edges": len(p["active_edges"]),
            "inactive": p["inactive_declarations"],
            "unknown_release_dependencies": p["unknown_release_dependencies"],
            "unknown_python": [n["name"] for n in p["nodes"]
                               if "UNKNOWN" in (n["release_python"], n["wheel_python"])],
        }
        print("C5_CANDIDATE_GRAPH " + json.dumps(summary, sort_keys=True))
    # Successful review is not permission to install or a profile READY result.
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("C5_GRAPH_REVIEW_BLOCKED: " + (str(exc) if type(exc) is Blocked
                                             else type(exc).__name__), file=sys.stderr)
        raise SystemExit(2)
