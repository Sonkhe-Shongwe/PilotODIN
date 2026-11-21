#!/usr/bin/env python3
"""P2 real React + FastAPI integration using ephemeral localhost and synthetic SQLite.

A real API process is started ONLY with PILOTODIN_HOME set to a newly created
temporary directory. No user checkout data, services, browsers or ports changed.
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
FRONTEND=ROOT/"frontend"

class ResultParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside=False
        self.status=None
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="pre" and a.get("id")=="p2-live-result":
            self.inside=True
            self.status=a.get("data-status")
    def handle_endtag(self,tag):
        if tag=="pre" and self.inside:
            self.inside=False
    def handle_data(self,data):
        if self.inside:
            self.parts.append(data)

def choose_browser():
    paths=[]
    for key in ("PROGRAMFILES","PROGRAMFILES(X86)","LOCALAPPDATA"):
        root=os.environ.get(key)
        if root:
            paths.extend((Path(root)/"Google"/"Chrome"/"Application"/"chrome.exe",
                         Path(root)/"Microsoft"/"Edge"/"Application"/"msedge.exe"))
    for name in ("chrome.exe","msedge.exe","chrome","chromium"):
        binary=shutil.which(name)
        if binary:
            paths.append(Path(binary))
    return next((p for p in paths if p.is_file()),None)

def free_backend_port()->int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]

def free_vite_port()->int:
    # Real FastAPI only permits these development-origin ports for CORS.
    for port in range(5174,5180):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1",port))
            except OSError:
                continue
            return port
    raise RuntimeError("All permitted isolated Vite ports 5174-5179 are busy.")

def ready(url:str,seconds=45)->None:
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen(url,timeout=1) as result:
                if result.status==200:
                    return
        except (urllib.error.URLError,OSError):
            pass
        time.sleep(0.3)
    raise RuntimeError("Isolated local service unavailable: "+url)

def create_fixture(home:Path):
    # Set environment BEFORE importing backend modules.
    os.environ["PILOTODIN_HOME"]=str(home)
    os.environ.pop("PILOTODIN_DESKTOP_SESSION",None)
    sys.path.insert(0,str(ROOT))
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend import storage
    client=TestClient(app)
    source_a=b"OrderID,Region,Revenue,Optional\n0001,North,120,yes\n0002,South,230,\n0003,North,250,yes\n0004,South,300,no\n"
    source_b=b"OrderID,Region,Revenue,Optional\n0001,East,45,no\n0002,West,50,\n0003,East,70,yes\n0004,West,90,no\n"
    items=[]
    for name,data in (("synthetic-a.csv",source_a),("synthetic-b.csv",source_b)):
        response=client.post("/api/projects",files={"file":(name,data,"text/csv")})
        if response.status_code!=201:
            raise RuntimeError("Synthetic project creation failed: "+response.text[:300])
        pid=response.json()["id"]
        p=storage.get_project(pid)
        path=Path(p["dataset_path"]).resolve()
        if not path.is_relative_to((home/"datasets").resolve()):
            raise RuntimeError("Refusing fixture file outside isolated directory.")
        if path.read_bytes()!=data:
            raise RuntimeError("Fixture uploaded bytes do not match.")
        items.append((pid,path,hashlib.sha256(data).hexdigest()))
    a,_,_=items[0]
    audit=client.post(f"/api/projects/{a}/report-quality",json={"expected_version":0})
    if audit.status_code!=201:
        raise RuntimeError("Synthetic Quality audit failed: "+audit.text[:300])
    aid=audit.json()["id"]
    saved=client.post(f"/api/projects/{a}/reports",json={
        "title":"Synthetic Baseline Report",
        "narrative":"Only synthetic audit findings are included.",
        "evidence_ids":[aid],
    })
    if saved.status_code!=201:
        raise RuntimeError("Synthetic report creation failed: "+saved.text[:300])
    return {
        "project_a":a,"project_b":items[1][0],
        "report_id":saved.json()["id"],"audit_id":aid,
    },items

def verify_pdf_responses(backend_port: int, vite_port: int, report_id: str) -> list[str]:
    """Real HTTP, binary and CORS checks for actual PDF attachment responses.

    Headless Chromium's fetch/download handling is deliberately not part of this
    PDF check. The real FastAPI endpoint and existing attachment headers are.
    """
    findings=[]
    origin=f"http://127.0.0.1:{vite_port}"
    for revision in (1,2):
        uri=(f"http://127.0.0.1:{backend_port}/api/reports/{report_id}"
             f"/export/pdf?revision={revision}")
        request=urllib.request.Request(
            uri,headers={"Origin":origin,"Accept":"application/pdf"},method="GET"
        )
        with urllib.request.urlopen(request,timeout=15) as response:
            status=response.status
            content_type=response.headers.get("Content-Type","")
            disposition=response.headers.get("Content-Disposition","")
            cors=response.headers.get("Access-Control-Allow-Origin","")
            no_sniff=response.headers.get("X-Content-Type-Options","")
            cache=response.headers.get("Cache-Control","")
            length=response.headers.get("Content-Length")
            body=response.read()
        if status!=200:
            raise AssertionError(f"PDF revision {revision}: HTTP {status}, expected 200")
        if not content_type.lower().startswith("application/pdf"):
            raise AssertionError(f"PDF revision {revision}: unexpected MIME {content_type}")
        if f"_rev{revision}.pdf" not in disposition or "attachment" not in disposition.lower():
            raise AssertionError(f"PDF revision {revision}: missing revision-specific attachment filename")
        if cors!=origin:
            raise AssertionError(f"PDF revision {revision}: unexpected CORS origin {cors!r}")
        if no_sniff.lower()!="nosniff" or "no-store" not in cache.lower():
            raise AssertionError(f"PDF revision {revision}: missing secure response headers")
        if not body.startswith(b"%PDF-") or b"%%EOF" not in body[-1024:]:
            raise AssertionError(f"PDF revision {revision}: PDF signature/trailer invalid")
        if len(body)<300 or (length is not None and len(body)!=int(length)):
            raise AssertionError(f"PDF revision {revision}: truncated or inconsistent body")
        findings.append(f"revision={revision} status={status} bytes={len(body)} "
                        f"mime={content_type} filename_ok=true cors_ok=true "
                        f"pdf_signature=true pdf_eof=true length_ok=true")
    return findings


def stop(proc):
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=7)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=7)

def main()->int:
    output=Path(tempfile.mkdtemp(prefix="pilotodin-p2-full-stack-"))
    home=output/"workspace"
    for d in (home,home/"datasets",home/"models"):
        d.mkdir(exist_ok=True)
    env=os.environ.copy()
    env["PILOTODIN_HOME"]=str(home)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env.pop("PILOTODIN_DESKTOP_SESSION",None)
    # No cloud inference, installer, model loading or hosted CI.
    results=[]
    artifacts=[]
    def phase(name,ok,log,detail=""):
        results.append({"phase":name,"status":"PASS" if ok else "FAIL",
                        "log":log.name,"detail":detail[:350]})
        artifacts.append(log)
        print(name+": "+results[-1]["status"],flush=True)
    buildlog=output/"frontend-typescript-vite.log"
    npm=shutil.which("npm.cmd") or shutil.which("npm")
    if npm:
        try:
            with buildlog.open("w",encoding="utf-8",errors="replace") as stream:
                buildrc=subprocess.run([npm,"run","build"],cwd=FRONTEND,
                  env=env,stdin=subprocess.DEVNULL,stdout=stream,
                  stderr=subprocess.STDOUT,timeout=300,check=False).returncode
        except (OSError,subprocess.TimeoutExpired) as exc:
            buildlog.write_text(str(exc),encoding="utf-8")
            buildrc=-1
    else:
        buildlog.write_text("npm unavailable.\n",encoding="utf-8")
        buildrc=-1
    phase("frontend-typescript-vite",buildrc==0,buildlog)

    backendlog=output/"isolated-fastapi.log"
    vitelog=output/"isolated-vite.log"
    browserlog=output/"full-stack-browser.log"
    dom=output/"full-stack-browser-dom.txt"
    integritylog=output/"source-integrity.log"
    pdflog=output/"real-pdf-http.log"
    backend=None
    vite=None
    backend_stream=None
    vite_stream=None
    fixture=None
    originals=[]
    browser_ok=False
    backend_ok=False
    pdf_ok=False
    try:
        if buildrc!=0:
            raise RuntimeError("Frontend build failed; browser and backend tests not started.")
        fixture,originals=create_fixture(home)
        backend_port=free_backend_port()
        vite_port=free_vite_port()
        node=shutil.which("node.exe") or shutil.which("node")
        browser=choose_browser()
        entry=FRONTEND/"node_modules"/"vite"/"bin"/"vite.js"
        if not node or not entry.is_file():
            raise RuntimeError("Local Node/Vite unavailable; no package installation performed.")
        if browser is None:
            raise RuntimeError("Chrome/Edge was not located; cannot claim a browser PASS.")
        backend_stream=backendlog.open("w",encoding="utf-8",errors="replace")
        backend=subprocess.Popen([sys.executable,"-m","uvicorn","backend.main:app",
             "--host","127.0.0.1","--port",str(backend_port),
             "--lifespan","off"],
             cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
             stdout=backend_stream,stderr=subprocess.STDOUT)
        ready(f"http://127.0.0.1:{backend_port}/api/projects/{fixture['project_a']}/reports")
        backend_ok=True
        vite_stream=vitelog.open("w",encoding="utf-8",errors="replace")
        vite=subprocess.Popen([node,str(entry),"--host","127.0.0.1",
            "--port",str(vite_port),"--strictPort"],
            cwd=FRONTEND,env=env,stdin=subprocess.DEVNULL,
            stdout=vite_stream,stderr=subprocess.STDOUT)
        from urllib.parse import urlencode
        page=f"http://127.0.0.1:{vite_port}/p2_full_stack_test.html?"+urlencode({
            "backend_port":backend_port,**fixture
        })
        ready(page)
        command=[str(browser),"--headless=new","--disable-gpu",
           "--disable-extensions","--disable-background-networking",
           "--disable-sync","--no-first-run","--no-default-browser-check",
           "--no-proxy-server","--user-data-dir="+str(output/"browser-profile"),
           "--virtual-time-budget=45000","--dump-dom",page]
        process=subprocess.run(command,cwd=FRONTEND,env=env,
           stdin=subprocess.DEVNULL,capture_output=True,text=True,
           errors="replace",timeout=170,check=False)
        dom.write_text(process.stdout[-120000:],encoding="utf-8",errors="replace")
        parser=ResultParser()
        parser.feed(process.stdout)
        value="".join(parser.parts)
        browserlog.write_text("Browser exit "+str(process.returncode)+"\n"+value+
               "\nSTDERR tail:\n"+process.stderr[-6500:],encoding="utf-8")
        if parser.status!="PASS":
            raise RuntimeError("Browser fixture reported "+str(parser.status))
        report=json.loads(value)
        if report.get("overall")!="PASS" or report.get("passed")!=3 or report.get("total")!=3:
            raise RuntimeError("Real FastAPI mounted browser scenarios were not 3/3 PASS.")
        if process.returncode!=0:
            raise RuntimeError("Browser exited nonzero.")
        browser_ok=True
        phase("p2-real-fastapi-mounted-react",True,browserlog,"3/3 browser scenarios")
    except Exception as exc:
        with browserlog.open("a",encoding="utf-8") as f:
            f.write("\nFAILED: "+str(exc)+"\n")
        phase("p2-real-fastapi-mounted-react",False,browserlog,str(exc))
    finally:
        # Keep this test-owned backend alive until PDF response bytes and headers
        # have been verified through real HTTP, independently of headless Chrome.
        if backend_ok and fixture is not None and backend is not None and backend.poll() is None:
            try:
                findings=verify_pdf_responses(backend_port,vite_port,fixture["report_id"])
                pdflog.write_text("\n".join(findings)+"\n",encoding="utf-8")
                pdf_ok=True
            except Exception as exc:
                pdflog.write_text("PDF HTTP verification FAILED: "+str(exc)+"\n",encoding="utf-8")
        else:
            pdflog.write_text("PDF HTTP verification unavailable: fixture or server not running.\n",encoding="utf-8")
        phase("p2-real-pdf-binary-http",pdf_ok,pdflog)
        stop(vite)
        stop(backend)
        if vite_stream:vite_stream.close()
        if backend_stream:backend_stream.close()
        if not backendlog.exists():
            backendlog.write_text("Backend not launched.\n",encoding="utf-8")
        if not vitelog.exists():
            vitelog.write_text("Vite not launched.\n",encoding="utf-8")
        if not dom.exists():
            dom.write_text("Browser DOM unavailable.\n",encoding="utf-8")
        artifacts.extend((backendlog,vitelog,dom))
    # Check SHA of both originals even if browser/API fails. This never touches
    # an existing dataset outside the temporary test directory.
    unchanged=bool(originals) and all(
        path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest
        for _,path,digest in originals)
    integritylog.write_text("Synthetic original source files unchanged: "+str(unchanged)+
        "\nBackend bound only to ephemeral loopback: "+str(backend_ok)+"\n",
        encoding="utf-8")
    phase("synthetic-original-file-integrity",unchanged,integritylog)
    report={
      "scope":"P2 real FastAPI/SQLite plus mounted React on synthetic isolated projects",
      "utc":datetime.now(timezone.utc).isoformat(),
      "overall":"PASS" if len(results)==4 and all(p["status"]=="PASS" for p in results) else "FAIL",
      "phases":results,"expected_real_browser_scenarios":3,
      "expected_real_pdf_http_revisions":2,
      "headless_chrome_pdf_attachment_fetch":"NOT_VALIDATED",
      "native_browser_or_tauri_save_as":"NOT_TESTED",
      "user_projects_or_datasets":"NOT_ACCESSED",
      "backend_isolation":"PILOTODIN_HOME temporary, random loopback port, no desktop session",
      "native_tauri_save_as":"NOT_TESTED",
      "offline_qwen_8gb_and_final_installer":"NOT_TESTED",
      "old_p0_p1_p3_p4_p5_suites":"NOT_RERUN"
    }
    metadata=output/"result.json"
    metadata.write_text(json.dumps(report,indent=2),encoding="utf-8")
    archive=output.with_suffix(".zip")
    with ZipFile(archive,"w",ZIP_DEFLATED) as zipped:
        for f in [*artifacts,metadata]:
            if f.exists():
                zipped.write(f,arcname=f.name)
    print("P2 real API reporting integration:",report["overall"],flush=True)
    print("One diagnostic ZIP (may contain test-local paths):",archive,flush=True)
    return 0 if report["overall"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
