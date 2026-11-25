"""C3 candidate inventory from committed first-party source, not runtime acceptance.

Only Git tree/blob reads and static Python AST/lexical analysis. No working
tree data, application imports, listeners, test execution or source excerpts.
Candidates require semantic review (comments, assertions, embedded code,
aliases and dynamically constructed calls can produce false positives/negatives).
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
import io
import json
import os
from pathlib import PurePosixPath
import re
import subprocess

SELF = "tools/c3_source_caller_inventory.py"
EXTENSIONS = frozenset("""
.py .pyw .ps1 .psm1 .bat .cmd .sh .js .jsx .mjs .cjs .ts .tsx
.rs .c .cpp .h .hpp .rb .yml .yaml .json .toml .html .spec
.ini .cfg .config .xml .env .lock
""".split())
METHODS = frozenset(("get", "post", "put", "patch", "delete", "options", "head"))
PATTERNS = {
    "transport-construction": r"\b(?:TestClient|ASGITransport)\s*\(",
    "transport-reference": r"\b(?:TestClient|ASGITransport|testclient)\b",
    "fixture-adapter": r"\b(?:async_)?fixture_client\s*\(",
    "request-guard": r"\b(?:RequestGuard|RequestTrust|request_authorized)\b",
    "main-module": r"\bbackend[./:]main\b|\bfrom\s+backend\s+import[^\n]*\bmain\b|\bimport\s+main\b|\bmain\.app\b",
    "synthetic-request": r"\bRequest\s*\(|[\"']type[\"']\s*:\s*[\"']http[\"']|\btestserver\b",
    "desktop-session": r"PILOTODIN_DESKTOP_(?:SESSION|ALLOW_DEV|PORT)|x-pilotodin-session",
    "development-capability": r"PILOTODIN_DEV_(?:CAPABILITY|PORT|ORIGIN)|x-pilotodin-dev-capability|x-pilotodin-dev-request",
    "serving-mode": r"PILOTODIN_SERVER_MODE|owned_app|owned_wakeup_app|owned_diagnostic_app|desktop_runner|uvicorn",
    "loopback-address": r"(?:localhost|127\.0\.0\.1):(?:8000|517[3-9])\b|tauri(?:\.localhost|://localhost)",
    "http-client": r"\b(?:urlopen|urlretrieve|Invoke-WebRequest|Invoke-RestMethod|HttpWebRequest|WebClient|AsyncClient|HTTPConnection|HTTPSConnection|fetch|axios)\b|\b(?:requests|httpx)\.(?:get|post|put|patch|delete|request|Client)\b",
    "api-path": r"/api(?:/|[\"'])",
    "frontend-bootstrap": r"\b(?:apiBase|authHeaders|configureDevelopmentAPI|configureDesktopAPI|desktopBootstrap)\b|VITE_PILOTODIN_(?:AUTH_DEV|NATIVE_SMOKE)",
}
COMPILED = {key: re.compile(value, re.IGNORECASE) for key, value in PATTERNS.items()}


def git(*args: str, input_bytes: bytes | None = None) -> bytes:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1"}
    result = subprocess.run(["git", *args], input=input_bytes, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, check=False)
    if result.returncode:
        raise RuntimeError("Read-only Git inventory command failed")
    return result.stdout


def eligible(path: str) -> bool:
    name = PurePosixPath(path)
    return (not path.startswith("third_party/") and
            (name.suffix.lower() in EXTENSIONS or name.name.startswith(".env")
             or name.name in {"Dockerfile", "Makefile"}
             or (name.name.startswith("requirements") and name.suffix == ".txt")))


def committed_sources(sha: str) -> tuple[dict[str, str], list[str], dict[str, int]]:
    entries = git("ls-tree", "-r", "-z", "--full-tree", sha).split(b"\0")
    paths: list[tuple[str, str]] = []
    counts: Counter = Counter()
    for entry in filter(None, entries):
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid = meta.decode("ascii").split()
        path = name.decode("utf-8")
        counts["tree_entries"] += 1
        if kind != "blob" or mode not in ("100644", "100755"):
            counts["non_regular_entries"] += 1
        elif not eligible(path):
            counts["out_of_scope_blobs"] += 1
        else:
            paths.append((path, oid))
    # Fetch exact object IDs from the committed tree, not working-tree paths.
    oids = sorted({oid for _, oid in paths})
    raw = io.BytesIO(git("cat-file", "--batch",
                         input_bytes=("".join(oid + "\n" for oid in oids)).encode("ascii")))
    blobs: dict[str, bytes] = {}
    for oid in oids:
        returned, kind, size = raw.readline().decode("ascii").split()
        if returned != oid or kind != "blob":
            raise RuntimeError("Unexpected committed Git object")
        size = int(size)
        data = raw.read(size)
        if len(data) != size or raw.read(1) != b"\n":
            raise RuntimeError("Truncated committed Git object")
        blobs[oid] = data
    if raw.read(1):
        raise RuntimeError("Unexpected extra Git output")
    sources, undecodable = {}, []
    for path, oid in sorted(paths):
        data = blobs[oid]
        try:
            encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            sources[path] = data.decode(encoding)
        except UnicodeError:
            undecodable.append(path)
    counts["eligible_blobs"] = len(paths)
    counts["decoded_blobs"] = len(sources)
    counts["undecodable_blobs"] = len(undecodable)
    return sources, undecodable, dict(counts)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return prefix + "." + node.attr if prefix else ""
    return ""


def route_inventory(main: str, plan: str) -> dict[tuple[str, str], str]:
    registered = {}
    for node in ast.parse(main).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            target = dotted(decorator.func)
            if not target.startswith("app.") or target[4:] not in METHODS:
                continue
            path = ast.literal_eval(decorator.args[0])
            key = (target[4:].upper(), path)
            if not isinstance(path, str) or key in registered:
                raise RuntimeError("Nonliteral or duplicate registered route")
            registered[key] = node.name
    declared = {}
    for node in ast.parse(plan).body:
        if not isinstance(node, ast.Assign) or not any(dotted(t) == "ROUTES" for t in node.targets):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or not isinstance(value.args[0], ast.Dict):
            raise RuntimeError("Unexpected static route plan")
        for key_node, entry in zip(value.args[0].keys, value.args[0].values):
            key = ast.literal_eval(key_node)
            if key in declared or not isinstance(entry, ast.Call):
                raise RuntimeError("Invalid static route plan")
            declared[key] = ast.literal_eval(entry.args[0])
    if not registered or registered != declared:
        raise RuntimeError("Registered routes differ from C1 static inventory")
    return registered


def python_references(tree: ast.AST, endpoints: set[str], found: dict[str, set[int]]) -> None:
    modules = {"main", "backend.main"}
    direct = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("backend.main", "main"):
                    modules.add(alias.asname or alias.name)
                    found["main-import-ast"].add(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if module in ("backend", "") and alias.name == "main":
                    modules.add(alias.asname or "main")
                    found["main-import-ast"].add(node.lineno)
                elif module in ("backend.main", "main"):
                    found["main-import-ast"].add(node.lineno)
                    if alias.name in endpoints or alias.name == "*":
                        found["direct-route-import"].add(node.lineno)
                        direct.add(alias.asname or alias.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            base = dotted(node.value)
            if base in modules and node.attr in endpoints:
                found["direct-route-reference"].add(node.lineno)
        elif isinstance(node, ast.Call):
            name = dotted(node.func)
            if name in direct:
                found["direct-route-call"].add(node.lineno)
            elif name == "getattr" and node.args and dotted(node.args[0]) in modules:
                found["dynamic-main-reference"].add(node.lineno)


def classify(path: str, source: str, endpoints: set[str]) -> tuple[dict[str, set[int]], bool]:
    found: dict[str, set[int]] = defaultdict(set)
    for key, pattern in COMPILED.items():
        for number, line in enumerate(source.splitlines(), 1):
            if pattern.search(line):
                found[key].add(number)
    # Include direct qualified route references even in embedded Python strings.
    route_pattern = re.compile(r"\bmain\.(" + "|".join(sorted(map(re.escape, endpoints))) + r")\b")
    for number, line in enumerate(source.splitlines(), 1):
        if route_pattern.search(line):
            found["qualified-route-text"].add(number)
    parse_failed = False
    if path.endswith((".py", ".pyw")):
        try:
            tree = ast.parse(source, filename=path)
        except (SyntaxError, ValueError):
            parse_failed = True
        else:
            python_references(tree, endpoints, found)
    return dict(found), parse_failed


def emit(kind: str, value: dict) -> None:
    print("C3_" + kind + " " + json.dumps(value, sort_keys=True, ensure_ascii=True))


def main() -> None:
    sha = git("rev-parse", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Expected exact committed Git SHA")
    if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_SHA") != sha:
        raise RuntimeError("CI checkout is not the expected exact SHA")
    sources, undecodable, counts = committed_sources(sha)
    routes = route_inventory(sources["backend/main.py"], sources["backend/resource_routes.py"])
    endpoints = set(routes.values())
    for (method, path), endpoint in sorted(routes.items()):
        emit("ROUTE", {"method": method, "path": path, "endpoint": endpoint})
    category_counts: Counter = Counter()
    parse_failed, candidate_paths = [], 0
    for path, source in sources.items():
        if path == SELF:
            continue  # Scanner pattern definitions are not serving callers.
        found, failed = classify(path, source, endpoints)
        if failed:
            parse_failed.append(path)
        if not found:
            continue
        candidate_paths += 1
        category_counts.update(found.keys())
        emit("INV", {"path": path, "matches": {
            key: {"lines": sorted(lines)[:12], "count": len(lines)}
            for key, lines in sorted(found.items())}})
    for path in undecodable:
        emit("UNDECODED", {"path": path})
    for path in parse_failed:
        emit("AST_UNPARSED", {"path": path})
    emit("SUMMARY", {"sha": sha, **counts, "registered_routes": len(routes),
                     "candidate_paths": candidate_paths, "category_path_counts": dict(category_counts),
                     "ast_unparsed": len(parse_failed), "self_excluded": SELF,
                     "scope": "first-party committed code/config; candidates only, not semantic closure",
                     "line_preview_limit_per_category": 12})


if __name__ == "__main__":
    main()
