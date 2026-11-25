"""Build A security and migration regression tests; no external services required."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
from secrets import token_hex
import sqlite3

from backend.main import app
from backend.request_auth import RequestTrust, desktop_trust_from_environ
from desktop.Migrate_Existing_Workspace import migrate
from tests.fixture_http import fixture_client


def _desktop_contract(debug=False):
    return desktop_trust_from_environ({
        "PILOTODIN_DESKTOP_SESSION": token_hex(32),
        "PILOTODIN_DESKTOP_PORT": "8000",
        "PILOTODIN_DESKTOP_ALLOW_DEV": "1" if debug else "0",
    })


def test_browser_dev_mode_remains_compatible():
    trust = RequestTrust("dev", 8000, token_hex(32), "http://127.0.0.1:5173")
    with closing(fixture_client(app, trust=trust)) as client:
        response = client.get("/api/health", headers={"Origin": trust.dev_origin})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    with closing(fixture_client(app, trust=trust, authenticated=False)) as denied:
        assert denied.get("/api/health", headers={"Origin": trust.dev_origin}).status_code == 401


def test_desktop_session_requires_secret_on_every_route():
    trust = _desktop_contract()
    with closing(fixture_client(app, trust=trust, authenticated=False)) as client:
        assert client.get("/api/health").status_code == 401
        assert client.get("/api/projects").status_code == 401
        assert client.post("/api/projects", files={"file": ("x.csv", b"x\n1", "text/csv")}).status_code == 401
        assert client.get("/api/health", headers={"X-PilotODIN-Session": "incorrect"}).status_code == 401


def test_desktop_session_accepts_only_private_authorised_requests():
    trust = _desktop_contract()
    allowed = {"Origin": "http://tauri.localhost"}
    with closing(fixture_client(app, trust=trust)) as client:
        accepted = client.get("/api/health", headers=allowed)
        assert accepted.status_code == 200
        assert accepted.headers.get("access-control-allow-origin") == "http://tauri.localhost"
        assert client.get("/api/ai/settings", headers=allowed).status_code == 200
        bad_origin = {"Origin": "https://malicious.example"}
        assert client.get("/api/health", headers=bad_origin).status_code == 403
        assert client.get("/api/ai/settings", headers=bad_origin).status_code == 403
        assert client.get("/api/projects", headers={"Origin": "http://127.0.0.1:5173"}).status_code == 403
        assert client.get("/api/health", headers={"X-PilotODIN-Dev-Capability": token_hex(32)}).status_code == 401


def test_desktop_dev_origin_only_in_explicit_debug_mode(monkeypatch):
    # Startup captures the mode, not subsequent changes to process flags.
    trust = _desktop_contract(debug=True)
    headers = {"Origin": "http://127.0.0.1:5173"}
    with closing(fixture_client(app, trust=trust)) as client:
        monkeypatch.setenv("PILOTODIN_DESKTOP_ALLOW_DEV", "0")
        assert client.get("/api/projects", headers=headers).status_code == 200
        assert client.get("/api/ai/settings", headers=headers).status_code == 200
        assert client.get("/api/projects", headers={"Origin": "https://attacker.example"}).status_code == 403
    strict = _desktop_contract()
    with closing(fixture_client(app, trust=strict)) as client:
        monkeypatch.setenv("PILOTODIN_DESKTOP_ALLOW_DEV", "1")
        assert client.get("/api/projects", headers=headers).status_code == 403


def test_desktop_cors_rejects_untrusted_preflights():
    trust = _desktop_contract()
    headers = {"Origin": "http://tauri.localhost", "Access-Control-Request-Method": "GET",
               "Access-Control-Request-Headers": "x-pilotodin-session"}
    with closing(fixture_client(app, trust=trust, authenticated=False)) as client:
        good = client.options("/api/projects", headers=headers)
        assert good.status_code == 204
        assert good.headers["access-control-allow-origin"] == headers["Origin"]
        assert "x-pilotodin-session" in good.headers["access-control-allow-headers"]
        assert not good.content
        bad = client.options("/api/projects", headers={**headers, "Origin": "https://attacker.example"})
        assert bad.status_code == 403
        assert "access-control-allow-origin" not in bad.headers
        assert client.options("/api/projects", headers={**headers, "Access-Control-Request-Headers": "content-type"}).status_code == 403
        assert client.get("/api/projects", headers={"Origin": headers["Origin"]}).status_code == 401
    with closing(fixture_client(app, trust=trust)) as client:
        assert client.options("/api/projects", headers=headers).status_code == 403


def synthetic_old_workspace(tmp_path: Path) -> Path:
    old = tmp_path / "old" / "PilotODIN"
    data = old / "data"
    (data / "datasets").mkdir(parents=True)
    (data / "models" / "exp1").mkdir(parents=True)
    (data / "datasets" / "sample.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (data / "models" / "exp1" / "model.joblib").write_bytes(b"fixture-model")
    with sqlite3.connect(data / "pilotodin.sqlite3") as con:
        con.execute("CREATE TABLE projects (id TEXT, dataset_path TEXT)")
        con.execute("CREATE TABLE experiments (id TEXT)")
        con.execute("INSERT INTO projects VALUES (?,?)", ("project1", str(data / "datasets" / "sample.csv")))
        con.execute("INSERT INTO experiments VALUES ('exp1')")
    return old


def test_suspended_migration_preserves_source_and_never_creates_destination(tmp_path):
    old = synthetic_old_workspace(tmp_path)
    target = tmp_path / "userAppData" / "com.pilotodin.studio" / "data"
    before = {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    try:
        migrate(old, target)
    except ValueError as exc:
        assert "suspended" in str(exc)
    else:
        raise AssertionError("Legacy desktop migration must remain disabled")
    assert not target.parent.exists()
    assert before == {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}


def test_suspended_migration_preserves_existing_destination(tmp_path):
    old = synthetic_old_workspace(tmp_path)
    target = tmp_path / "existing" / "data"
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("important")
    try:
        migrate(old, target)
    except ValueError as exc:
        assert "suspended" in str(exc)
    else:
        raise AssertionError("Legacy desktop migration must remain disabled")
    assert (target / "keep.txt").read_text() == "important"
    assert sorted(p.name for p in target.iterdir()) == ["keep.txt"]


def test_frontend_all_fetch_methods_include_session_header():
    source = (Path(__file__).resolve().parents[1]/'frontend'/'src'/'api.ts').read_text()
    # C3 centralizes every HTTP operation in the confined transport. Check
    # each method, not just a global substring or an obsolete inline URL.
    get = source[source.index('export async function get<'):source.index('export async function post<')]
    post = source[source.index('export async function post<'):source.index('export async function put<')]
    put = source[source.index('export async function put<'):source.index('export async function upload(')]
    upload = source[source.index('export async function upload('):source.index('/** Read-only download:')]
    transport = source[source.index('async function fetchLocal('):source.index('// Passive health checks')]
    target = source[source.index('function localTarget('):source.index('async function fetchLocal(')]
    assert 'fetchLocal(path,{headers:authHeaders()' in get
    assert "fetchLocal(path,{method:'POST',headers:{...authHeaders()," in post
    assert "fetchLocal(path,{method:'PUT',headers:{...authHeaders()," in put
    assert 'const form=new FormData()' in upload
    assert "form.append('file',file)" in upload
    assert "fetchLocal('/projects',{method:'POST',headers:authHeaders(),body:form})" in upload
    assert 'const target=localTarget(path)' in transport
    assert "fetch(target.href,{...options,redirect:'error'})" in transport
    assert 'response.redirected' in transport
    assert 'target.origin!==new URL(base).origin' in target
    assert "target.pathname.startsWith('/api/')" in target
    # Actual method/header/destination and redirect behavior remains exercised
    # by frontend/tests/desktop-ai-boundaries.test.cjs.


def test_tauri_shell_permissions_do_not_expose_arbitrary_executables():
    base = Path(__file__).resolve().parents[1]/'frontend'/'src-tauri'
    cfg = json.loads((base / 'tauri.conf.json').read_text())
    perms = json.loads((base / 'capabilities' / 'default.json').read_text())
    assert cfg['bundle']['externalBin'] == ['binaries/pilotodin-engine', 'binaries/pilotodin-inference']
    assert cfg['bundle']['windows']['webviewInstallMode']['type'] == 'offlineInstaller'
    assert cfg['bundle']['resources']['resources/models/qwen3-1.7b-q4_k_m.gguf'] == 'models/qwen3-1.7b-q4_k_m.gguf'
    assert perms['permissions'] == ['core:default']
    assert cfg['bundle']['targets'] == ['nsis']
    assert 'localhost:8000' not in json.dumps(cfg)



def test_desktop_sidecar_does_not_inherit_source_or_install_working_directory():
    """Source contract; the Windows native build still needs owner approval."""
    source = (Path(__file__).resolve().parents[1] /
              "frontend" / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    start = source.index("fn launch_backend(")
    next_command = source.index("#[tauri::command]", start + 1)
    block = source[start:next_command]
    assert ".env(\"PILOTODIN_HOME\", data_dir.to_string_lossy().to_string())" in block
    assert ".current_dir(&data_dir)" in block
    preparation = "worker_data_home(&app, &mut storage_pins)?"
    assert block.index(preparation) < block.index(".current_dir(&data_dir)")
    assert block.index(".current_dir(&data_dir)") < block.index("storage_pins.verify()?") < block.index(".spawn()")
    home_start = source.index("fn worker_data_home(")
    home_end = source.index("fn worker_temp_directory(", home_start)
    home = source[home_start:home_end]
    assert 'app.path().app_local_data_dir()' in home
    assert 'pins.prepare(&app_root)?' in home
    assert 'pins.prepare(&root.join("data"))?' in home
    assert 'pins.prepare(&home.join(profile))' in home
