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
    "indirect-http": r"\b(?:build_opener|install_opener|OpenerDirector|ProxyHandler|HTTPRedirectHandler|createConnection|XMLHttpRequest|Invoke-WebRequest|Invoke-RestMethod|curl(?:\.exe)?)\b|\b(?:opener|http_opener|url_opener)\s*\.\s*open\s*\(",
    "process-launch": r"\b(?:Popen|Start-Process|Start-Job|spawnSync|execFileSync|execFile|spawn|Command::new|Command\.new|create_subprocess_exec|create_subprocess_shell)\b|\b(?:subprocess\.(?:run|call|check_call|check_output)|uvicorn\.(?:run|Server|Config))\b",
    "credential-boundary": r"PILOTODIN_(?:HOSTED_NATIVE_AUTH|CONTROL_(?:MODE|GENERATION|CAPABILITY)|BUNDLED_LLM_(?:TOKEN|PORT)|DATASET_EXPORT_KEY|DESKTOP_WATCH_STDIN)|VITE_PILOTODIN_(?:AUTH_DEV|NATIVE_SMOKE)|x-pilotodin-(?:session|dev-capability|export-mac)|\bAuthorization\b|\bBearer\b",
    "dynamic-import": r"\b(?:import_module|__import__|spec_from_file_location|exec_module|runpy\.run_module|runpy\.run_path)\s*\(",
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


# Candidate-only alias tracking, intentionally not a Python interpreter or
# scope/data-flow proof. Keep old lexical/AST categories unchanged.
_HTTP_FACTORIES = {
    "urllib.request.build_opener": "@opener",
    "urllib.request.OpenerDirector": "@opener",
    "http.client.HTTPConnection": "@connection",
    "http.client.HTTPSConnection": "@connection",
    "httpx.Client": "@http-client",
    "httpx.AsyncClient": "@http-client",
    "requests.Session": "@http-client",
    "requests.sessions.Session": "@http-client",
    "fastapi.testclient.TestClient": "@http-client",
    "starlette.testclient.TestClient": "@http-client",
    "httpx.ASGITransport": "@transport",
}
_HTTP_FUNCTIONS = frozenset((
    "urllib.request.urlopen", "urllib.request.urlretrieve",
    "urllib.request.build_opener", "urllib.request.install_opener",
    "urllib.request.Request",
)) | frozenset(_HTTP_FACTORIES)
_LAUNCH_FUNCTIONS = frozenset((
    "subprocess.Popen", "subprocess.run", "subprocess.call",
    "subprocess.check_call", "subprocess.check_output",
    "asyncio.create_subprocess_exec", "asyncio.create_subprocess_shell",
    "uvicorn.run", "uvicorn.Config", "uvicorn.Server",
))
_DYNAMIC_FUNCTIONS = frozenset((
    "importlib.import_module", "__import__", "importlib.util.spec_from_file_location",
    "runpy.run_module", "runpy.run_path",
))
_HTTP_METHODS = METHODS | {"open", "request", "send", "stream", "getresponse",
                           "urlopen", "connect", "open_local_file"}
_RELEVANT_ROOTS = frozenset(("backend", "main", "urllib", "http", "httpx",
                             "requests", "fastapi", "starlette", "subprocess",
                             "asyncio", "uvicorn", "importlib", "runpy"))


def python_indirect_references(tree: ast.AST, endpoints: set[str],
                               found: dict[str, set[int]]) -> None:
    nodes = tuple(ast.walk(tree))
    aliases: dict[str, set[str]] = defaultdict(set)

    def relevant(value: str) -> bool:
        return value.startswith("@") or value.split(".", 1)[0] in _RELEVANT_ROOTS

    def resolve(node: ast.AST) -> set[str]:
        # Preserve raw spelling as a conservative candidate, even if shadowed.
        if isinstance(node, ast.Name):
            return {node.id} | aliases.get(node.id, set())
        if isinstance(node, ast.Attribute):
            return {base + "." + node.attr for base in resolve(node.value)}
        if isinstance(node, ast.Call):
            names = resolve(node.func)
            result = {_HTTP_FACTORIES[name] for name in names if name in _HTTP_FACTORIES}
            if (names & _DYNAMIC_FUNCTIONS and node.args and
                    isinstance(node.args[0], ast.Constant) and
                    node.args[0].value in ("backend.main", "main")):
                result.add("backend.main")
            return result
        return set()

    for node in nodes:
        if isinstance(node, ast.Import):
            for item in node.names:
                if relevant(item.name):
                    bound = item.asname or item.name.split(".", 1)[0]
                    aliases[bound].add(item.name if item.asname else bound)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ("backend" if node.level else "")
            for item in node.names:
                full = module + "." + item.name if module else item.name
                if relevant(full):
                    aliases[item.asname or item.name].add(full)

    # A finite conservative propagation pass for ordinary assignment aliases,
    # including aliased constructors and bound methods. Bound rounds explicitly:
    # arbitrary dynamic expressions and longer chains still require review.
    for _ in range(4):
        changed = False
        for node in nodes:
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            elif isinstance(node, ast.NamedExpr):
                targets, value = [node.target], node.value
            else:
                continue
            values = {name for name in resolve(value) if relevant(name)}
            for target in targets:
                if not isinstance(target, ast.Name) or not values:
                    continue
                known = aliases[target.id]
                if not values <= known:
                    known.update(values)
                    changed = True
        if not changed:
            break

    for node in nodes:
        if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load):
            for name in resolve(node):
                if name in ("backend.main.app", "main.app"):
                    found["python-main-app-reference"].add(node.lineno)
                if name.rsplit(".", 1)[0] in ("backend.main", "main") and name.rsplit(".", 1)[-1] in endpoints:
                    found["python-route-alias-reference"].add(node.lineno)
        if not isinstance(node, ast.Call):
            continue
        names = resolve(node.func)
        if any(
            name in _HTTP_FUNCTIONS or
            (name.rsplit(".", 1)[0] in ("httpx", "requests", "@opener", "@connection", "@http-client")
             and name.rsplit(".", 1)[-1] in _HTTP_METHODS)
            for name in names
        ):
            found["python-http-call"].add(node.lineno)
        if names & _LAUNCH_FUNCTIONS:
            found["python-launch-call"].add(node.lineno)
        if names & _DYNAMIC_FUNCTIONS:
            found["python-dynamic-import-call"].add(node.lineno)
        if any(name.rsplit(".", 1)[0] in ("backend.main", "main")
               and name.rsplit(".", 1)[-1] in endpoints for name in names):
            found["python-route-alias-call"].add(node.lineno)
        if "getattr" in names and node.args and resolve(node.args[0]) & {"backend.main", "main"}:
            found["python-dynamic-main-reference"].add(node.lineno)


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
            python_indirect_references(tree, endpoints, found)
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
                     "alias_propagation_round_limit": 4,
                     "line_preview_limit_per_category": 12})


if __name__ == "__main__":
    main()
