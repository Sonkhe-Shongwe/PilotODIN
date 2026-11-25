"""Non-executable C5 review inventory. Does not install, resolve or acquire.

Source identity, expected registry digest, declared licence and actual byte
verification are separate. The report is deliberately BLOCKED and is not
a lockfile, release SBOM, redistribution decision or trust authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tomllib

from qa.c5_metadata import graph_review as graph
from tools.build_input_preflight import (
    Blocked, audit_policy, checked_directory, fields, read_exact, require, strict_json,
)

ROOT = graph.ROOT
CATALOG = "qa/c5_metadata/input_provenance_20261125.json"
VENDOR = "third_party/tauri-plugin-shell-2.6.0"
VENDOR_TREE = "54514a2feed82db5a61e9c37e8d43f6fe99b7696"
SOURCE_LIMIT = 1024 * 1024
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
PATH_PART = re.compile(r"[A-Za-z0-9_.-]+")


def read_pinned(root, path, expected_sha, expected_size):
    # Git canonical source identity, never normalise actual artifact bytes.
    folder = root
    parts = path.split("/")
    require(all(PATH_PART.fullmatch(x) and x not in (".", "..") for x in parts),
            "CATALOG_UNSAFE_PATH")
    checked_directory(root)
    for part in parts[:-1]:
        folder /= part
        checked_directory(folder)
    target = folder / parts[-1]
    _, raw = read_exact(target, size=target.lstat().st_size, collect=True, limit=SOURCE_LIMIT)
    if len(raw) != expected_size or graph.git_blob(raw) != expected_sha:
        raw = raw.replace(b"\r\n", b"\n")
    require(len(raw) == expected_size and graph.git_blob(raw) == expected_sha,
            "CATALOG_SOURCE_PIN_MISMATCH")
    return raw


def tree_digest(rows):
    """Reconstruct canonical Git tree ID from exact paths, modes and blobs."""
    root = {}
    for row in rows:
        fields(row, {"path", "mode", "git_blob", "bytes"})
        parts = row["path"].split("/")
        require(all(PATH_PART.fullmatch(x) and x not in (".", "..") for x in parts)
                and row["mode"] == "100644" and HEX40.fullmatch(row["git_blob"])
                and type(row["bytes"]) is int and 0 < row["bytes"] <= SOURCE_LIMIT,
                "VENDOR_ROW_INVALID")
        parent = root
        for part in parts[:-1]:
            parent = parent.setdefault(part, {})
            require(type(parent) is dict, "VENDOR_PATH_CONFLICT")
        require(parts[-1] not in parent, "VENDOR_DUPLICATE_PATH")
        parent[parts[-1]] = row["git_blob"]
    def digest(node):
        raw = bytearray()
        for name, value in sorted(node.items(), key=lambda x: x[0] + ("/" if type(x[1]) is dict else "")):
            directory = type(value) is dict
            raw.extend(("40000" if directory else "100644").encode("ascii") + b" "
                       + name.encode("ascii") + b"\0"
                       + bytes.fromhex(digest(value) if directory else value))
        return hashlib.sha1(b"tree " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    return digest(root)


def audit_vendor(root, doc, policy):
    fields(doc, {"tree", "files"})
    rows = doc["files"]
    require(type(rows) is list and len(rows) == 37 and doc["tree"] == VENDOR_TREE
            and policy["vendored_shell_tree"] == VENDOR_TREE
            and tree_digest(rows) == VENDOR_TREE, "VENDOR_TREE_PIN")
    expected = {x["path"]: x for x in rows}
    folders = {""}
    for name in expected:
        parts = name.split("/")
        for i in range(1, len(parts)):
            folders.add("/".join(parts[:i]))
    base = root / VENDOR
    checked_directory(root / "third_party")
    for rel in sorted(folders):
        folder = base / rel
        checked_directory(folder)
        names = {x.rsplit("/", 1)[-1] for x in expected if x.rpartition("/")[0] == rel}
        names.update(x.rsplit("/", 1)[-1] for x in folders if x and x.rpartition("/")[0] == rel)
        seen = set()
        with os.scandir(folder) as entries:
            for entry in entries:
                require(entry.name in names and entry.name not in seen, "VENDOR_EXTRA_PATH")
                seen.add(entry.name)
        require(seen == names, "VENDOR_MISSING_PATH")
    raw = {}
    for name, row in expected.items():
        raw[name] = read_pinned(root, VENDOR + "/" + name, row["git_blob"], row["bytes"])
    upstream = strict_json(raw["UPSTREAM.json"])
    original = upstream["original_git_blobs"]
    require(set(expected) == set(original) | {"UPSTREAM.json"}
            and upstream["registry_archive_verified"] is False, "VENDOR_PROVENANCE_SCOPE")
    changed = sorted(name for name in original if original[name] != expected[name]["git_blob"])
    require(changed == sorted(upstream["modified"]) and len(changed) == 3,
            "VENDOR_PATCH_SET")
    return {"tree": VENDOR_TREE, "files": rows, "unchanged_upstream_blobs": 33,
            "modified_files": changed, "upstream": upstream,
            "registry_archive_verified": False, "release_licence_review": "UNVERIFIED"}


def npm_inventory(lock):
    require(lock["lockfileVersion"] == 3, "NPM_LOCK_VERSION")
    packages = lock["packages"]
    require(len(packages) == 91 and "" in packages, "NPM_LOCK_COUNT")
    rows, edges = [], []
    kinds = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
    for path, item in sorted(packages.items()):
        if path:
            require(path.startswith("node_modules/") and "/node_modules/" not in path
                    and type(item["integrity"]) is str and item["integrity"].startswith("sha512-")
                    and item["resolved"].startswith("https://registry.npmjs.org/"),
                    "NPM_LOCK_ROW")
            rows.append({"path": path, "version": item["version"], "source": item["resolved"],
                         "expected_integrity": item["integrity"], "bytes": None,
                         "declared_licence": item.get("license"), "dev": item.get("dev", False),
                         "optional": item.get("optional", False),
                         "os": item.get("os"), "cpu": item.get("cpu"), "libc": item.get("libc"),
                         "has_install_script": item.get("hasInstallScript", False),
                         "artifact_bytes_verified": False, "redistribution": "UNREVIEWED"})
        for kind in kinds:
            for name, version_range in sorted(item.get(kind, {}).items()):
                target = "node_modules/" + name
                optional_peer = kind == "peerDependencies" and item.get(
                    "peerDependenciesMeta", {}).get(name, {}).get("optional") is True
                require(target in packages or optional_peer, "NPM_DECLARATION_UNRESOLVED")
                edges.append({"from": path or "ROOT", "kind": kind, "to": target,
                              "range": version_range, "present": target in packages,
                              "optional_peer": optional_peer})
    return {"status": "BLOCKED", "graph_scope": "LOCK_DECLARATIONS_NOT_TARGET_RESOLUTION",
            "root": packages[""], "rows": rows, "edges": edges}


def cargo_inventory(lock):
    require(lock["version"] == 4 and len(lock["package"]) == 457, "CARGO_LOCK_COUNT")
    packages = lock["package"]
    keys = {}
    for item in packages:
        key = (item["name"], item["version"])
        require(key not in keys, "CARGO_AMBIGUOUS_ID")
        keys[key] = item
    rows, edges = [], []
    for key, item in sorted(keys.items()):
        name, version = key
        source, checksum = item.get("source"), item.get("checksum")
        if source is not None:
            require(source == "registry+https://github.com/rust-lang/crates.io-index"
                    and type(checksum) is str and HEX64.fullmatch(checksum), "CARGO_REGISTRY_IDENTITY")
        else:
            require(key in {("pilotodin-desktop", "1.0.0-alpha.1"),
                            ("tauri-plugin-shell", "2.6.0")} and checksum is None,
                    "CARGO_UNKNOWN_LOCAL")
        rows.append({"name": name, "version": version, "source": source,
                     "expected_sha256": checksum, "bytes": None,
                     "local_source": VENDOR if name == "tauri-plugin-shell" and source is None
                     else "frontend/src-tauri" if source is None else None,
                     "declared_licence": None, "redistribution": "UNREVIEWED",
                     "artifact_bytes_verified": False})
        for dep in item.get("dependencies", []):
            parts = dep.split()
            require(len(parts) in (1, 2), "CARGO_DEPENDENCY_FORMAT")
            matches = [k for k in keys if k[0] == parts[0] and
                       (len(parts) == 1 or k[1] == parts[1])]
            require(len(matches) == 1, "CARGO_DEPENDENCY_UNRESOLVED")
            edges.append({"from": list(key), "to": list(matches[0]), "lock_reference": dep})
    return {"status": "BLOCKED", "graph_scope": "LOCK_UNION_NOT_TARGET_FEATURE_RESOLUTION",
            "rows": rows, "edges": edges}


def review(root=ROOT):
    root = Path(root)
    policy = audit_policy(root)
    pins = {x["path"]: x for x in policy["source_inputs"]}
    def source(path):
        pin = pins[path]
        return read_pinned(root, path, pin["git_blob_sha1"], pin["bytes"])
    doc = strict_json(graph.canonical_source(root, CATALOG))
    fields(doc, {"schema_version", "status", "evidence_scope", "source_commit",
                 "vendored_shell", "ui_font_notices", "toolchain", "assets"})
    require(type(doc["schema_version"]) is int and doc["schema_version"] == 1
            and doc["status"] == "BLOCKED" and doc["evidence_scope"] == "SOURCE_AND_PUBLIC_METADATA_ONLY",
            "CATALOG_MUST_REMAIN_BLOCKED")
    vendor = audit_vendor(root, doc["vendored_shell"], policy)
    require({x["path"] for x in doc["ui_font_notices"]} ==
            {"frontend/public/licenses/inter-OFL.txt", "frontend/public/licenses/manrope-OFL.txt"}
            and len(doc["ui_font_notices"]) == 2, "UI_NOTICE_SET")
    for notice in doc["ui_font_notices"]:
        fields(notice, {"path", "git_blob", "bytes"})
        read_pinned(root, notice["path"], notice["git_blob"], notice["bytes"])
    npm = npm_inventory(strict_json(source("frontend/package-lock.json")))
    cargo = cargo_inventory(tomllib.loads(source("frontend/src-tauri/Cargo.lock").decode("utf-8")))
    python = graph.review(root)
    _, releases, _ = graph.load_inputs(root)
    files = {}
    for p in python["profiles"]:
        for node in p["nodes"]:
            key = node["filename"]
            row = releases[(node["name"], node["version"])]
            value = {"name": node["name"], "version": node["version"], "filename": key,
                     "expected_sha256": node["sha256"], "expected_bytes": node["bytes"],
                     "source": node["source"], "metadata_source": node["metadata_source"],
                     "declared_licence_expression": row["license_expression"],
                     "declared_licence_excerpt": row["license_declared_excerpt"],
                     "declared_licence_truncated": row["license_declared_truncated"],
                     "declared_licence_classifiers": row["license_classifiers"],
                     "release_requires_dist": row["requires_dist_release_level"],
                     "selected_wheel_metadata_verified": False, "artifact_bytes_verified": False,
                     "redistribution": "UNREVIEWED"}
            require(key not in files or files[key] == value, "WHEEL_IDENTITY_CONFLICT")
            files[key] = value
    require(len(files) == 62, "WHEEL_COUNT")
    return {"schema_version": 1, "status": "BLOCKED", "not_a_lock_or_release_sbom": True,
            "source_inputs": policy["source_inputs"], "profiles": policy["profiles"],
            "python": {**python, "distinct_files": [files[k] for k in sorted(files)]},
            "npm": npm, "cargo": cargo, "vendored_shell": vendor,
            "ui_font_notices": doc["ui_font_notices"], "toolchain": doc["toolchain"],
            "assets": doc["assets"], "actual_artifact_verification": False,
            "production_activation": False}


def summary(report):
    return {"status": report["status"], "profiles_blocked": len(report["profiles"]),
            "python_distinct_files": len(report["python"]["distinct_files"]),
            "python_platform_selections": sum(len(x["nodes"]) for x in report["python"]["profiles"]),
            "npm_entries": len(report["npm"]["rows"]), "npm_edges": len(report["npm"]["edges"]),
            "npm_absent_optional_peers": sum(not x["present"] for x in report["npm"]["edges"]),
            "cargo_entries": len(report["cargo"]["rows"]), "cargo_edges": len(report["cargo"]["edges"]),
            "cargo_registry_checksums": sum(x["expected_sha256"] is not None for x in report["cargo"]["rows"]),
            "vendored_source_files": len(report["vendored_shell"]["files"]),
            "actual_artifact_verification": False, "production_activation": False}


if __name__ == "__main__":
    try:
        require(sys.argv[1:] in ([], ["--summary"]), "UNSUPPORTED_INVENTORY_ARGUMENT")
        report = review()
        if sys.argv[1:]:
            print("C5_INPUT_INVENTORY " + json.dumps(summary(report), sort_keys=True))
        else:
            print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("C5_INPUT_INVENTORY_BLOCKED: " + (str(exc) if type(exc) is Blocked
                                                 else type(exc).__name__), file=sys.stderr)
        raise SystemExit(2)
