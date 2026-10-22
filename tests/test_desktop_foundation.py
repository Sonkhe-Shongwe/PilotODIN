"""Build A security and migration regression tests; no external services required."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from backend.main import app
from desktop.Migrate_Existing_Workspace import migrate

client = TestClient(app)


def test_browser_dev_mode_remains_compatible(monkeypatch):
    monkeypatch.delenv("PILOTODIN_DESKTOP_SESSION", raising=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_desktop_session_requires_secret_on_every_route(monkeypatch):
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION", "Q" * 64)
    monkeypatch.delenv("PILOTODIN_DESKTOP_ALLOW_DEV", raising=False)
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", files={"file": ("x.csv", b"x\n1", "text/csv")}).status_code == 401
    assert client.get("/api/health", headers={"X-PilotODIN-Session": "incorrect"}).status_code == 401


def test_desktop_session_accepts_only_private_authorised_requests(monkeypatch):
    secret = "p" * 64
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION", secret)
    monkeypatch.delenv("PILOTODIN_DESKTOP_ALLOW_DEV", raising=False)
    allowed = {"X-PilotODIN-Session": secret, "Origin": "http://tauri.localhost"}
    accepted = client.get("/api/health", headers=allowed)
    assert accepted.status_code == 200
    assert accepted.headers.get('access-control-allow-origin') == "http://tauri.localhost"
    assert client.get("/api/ai/settings", headers=allowed).status_code == 200
    bad_origin = {**allowed, "Origin": "https://malicious.example"}
    assert client.get("/api/health", headers=bad_origin).status_code == 403
    assert client.get("/api/ai/settings", headers=bad_origin).status_code == 403
    legacy_dev_origin = {**allowed, "Origin": "http://127.0.0.1:5173"}
    assert client.get("/api/projects", headers=legacy_dev_origin).status_code == 403


def test_desktop_dev_origin_only_in_explicit_debug_mode(monkeypatch):
    secret = "q" * 64
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION", secret)
    monkeypatch.setenv("PILOTODIN_DESKTOP_ALLOW_DEV", "1")
    headers = {"X-PilotODIN-Session": secret, "Origin": "http://127.0.0.1:5173"}
    assert client.get("/api/projects", headers=headers).status_code == 200
    assert client.get("/api/ai/settings", headers=headers).status_code == 200
    assert client.get("/api/projects", headers={**headers, "Origin":"https://attacker.example"}).status_code == 403


def test_desktop_cors_rejects_untrusted_preflights(monkeypatch):
    monkeypatch.setenv("PILOTODIN_DESKTOP_SESSION", "a" * 64)
    good = client.options("/api/projects", headers={"Origin": "http://tauri.localhost", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-pilotodin-session"})
    assert good.status_code == 200
    bad = client.options("/api/projects", headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "GET"})
    assert bad.status_code == 400


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


def test_migrate_workspace_copies_then_rewrites_paths(tmp_path):
    old = synthetic_old_workspace(tmp_path)
    target = tmp_path / "userAppData" / "com.pilotodin.studio" / "data"
    before = (old / "data" / "pilotodin.sqlite3").read_bytes()
    assert migrate(old, target) == (1, 1)
    with sqlite3.connect(target / "pilotodin.sqlite3") as con:
        saved = con.execute("SELECT dataset_path FROM projects").fetchone()[0]
    assert saved == str(target / "datasets" / "sample.csv")
    assert (target / "models" / "exp1" / "model.joblib").read_bytes() == b"fixture-model"
    assert (old / "data" / "pilotodin.sqlite3").read_bytes() == before


def test_migrate_refuses_existing_destination(tmp_path):
    old = synthetic_old_workspace(tmp_path)
    target = tmp_path / "existing" / "data"
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("important")
    try:
        migrate(old, target)
    except ValueError as exc:
        assert 'already exists' in str(exc) or 'overwrite' in str(exc)
    else:
        raise AssertionError("Should refuse to touch existing work")
    assert (target / "keep.txt").read_text() == "important"


def test_frontend_all_fetch_methods_include_session_header():
    source = (Path(__file__).resolve().parents[1]/'frontend'/'src'/'api.ts').read_text()
    assert 'headers:authHeaders()' in source # GET and upload
    assert '...authHeaders()' in source # POST and PUT
    assert '`${apiBase()}/projects`' in source
    assert 'const form=new FormData()' in source


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
