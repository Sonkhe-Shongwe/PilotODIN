"""C3 local DevQA seed authentication, using disposable synthetic allocations only.

No Tauri, network listener, live owner workspace, inference, or installer.
The managed report-chain and P3 seeders retain their existing focused tests.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools.qa_foundation import create_run

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("P2-NATIVE-DELIVER-CONSENT", "Seed_P2_Native_Deliver_Consent_Local.py",
     "synthetic-consent-manifest.json", 1),
    ("P2-NATIVE-TWO-WINDOW-DELIVER", "Seed_P2_Native_Two_Window_Local.py",
     "two-window-manifest.json", 2),
)


@pytest.mark.parametrize("phase,script,filename,count", CASES)
@pytest.mark.parametrize("dirty", (False, True))
def test_p2_seed_only_in_disposable_workspace(tmp_path, phase, script, filename, count, dirty):
    run, _ = create_run(tmp_path / "devqa", phase, repo=ROOT)
    home = run / "workspace"
    manifest = run / "fixtures" / filename
    if dirty:
        marker = home / "preserve.txt"
        marker.write_bytes(b"untouched")
    env = {**os.environ, "PILOTODIN_HOME": str(home)}
    for key in ("PILOTODIN_DESKTOP_SESSION", "PILOTODIN_DEV_CAPABILITY",
                "PILOTODIN_DEV_PORT", "PILOTODIN_DEV_ORIGIN"):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools" / script), str(manifest)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=40,
    )
    if dirty:
        assert result.returncode != 0
        assert not manifest.exists()
        assert list(home.iterdir()) == [marker]
        assert marker.read_bytes() == b"untouched"
        return
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(manifest.read_text(encoding="utf-8"))
    assert record["phase"] == phase and record["run_id"] == run.name
    projects = record["projects"] if count == 2 else [record]
    assert len(projects) == count
    if count == 2:
        assert len({p["id"] for p in projects}) == 2
    for project in projects:
        assert project["rows"] == 4
        source = (home / project["source_relative"]).resolve(strict=True)
        assert source.is_relative_to(home / "datasets")
        expected = project["sha256"] if count == 2 else project["synthetic_csv_sha256"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    assert not any((home / "models").iterdir())


@pytest.mark.parametrize("origin", ("http://127.0.0.1:5176", "http://127.0.0.1:5177",
                                    "http://127.0.0.1:5178"))
def test_seed_fixture_contract_enforces_exact_origin_and_capability(origin):
    from fastapi import FastAPI
    from secrets import token_hex
    from backend.request_auth import RequestTrust
    from tests.fixture_http import fixture_client

    calls = []
    app = FastAPI()

    @app.get("/api/health")
    def health():
        calls.append("route")
        return {"ok": True}

    trust = RequestTrust("local-devqa", 8000, token_hex(32), origin)
    denied = fixture_client(app, trust=trust, authenticated=False)
    assert denied.get("/api/health", headers={"Origin": origin}).status_code == 401
    client = fixture_client(app, trust=trust)
    wrong_origin = "http://127.0.0.1:5177" if origin.endswith("5176") else "http://127.0.0.1:5176"
    assert client.get("/api/health", headers={"Origin": wrong_origin}).status_code == 403
    assert calls == []
    assert client.get("/api/health", headers={"Origin": origin}).json() == {"ok": True}
    assert calls == ["route"]
