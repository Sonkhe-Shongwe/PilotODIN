"""Checksum metadata only; live capability remains disarmed."""
import base64
from contextlib import contextmanager
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import ssl
import sys
from urllib.parse import urlsplit, parse_qsl

ROOT=Path(__file__).resolve().parents[2]
DIR="qa/c5_wheel_metadata/"
OP="C5-TOOLCHAIN-CHECKSUMS-ONCE-20261125"
WORKFLOW="C5 toolchain checksums offline review"
LIVE_ENABLED=False
CAPABILITY=object()
MARKER=ROOT/(DIR+"APPROVAL_TOOLCHAIN_CHECKSUMS_20261125.txt")
MARKER_BYTES=(OP+"\nFour documents, at most six requests, 5 MiB body cap; no binaries or retries.\n").encode()
HEX=re.compile("[0-9a-f]{64}")
TOTAL=5*1024*1024
HOSTS={"github.com","release-assets.githubusercontent.com","objects.githubusercontent.com","nodejs.org","static.rust-lang.org"}

class Refused(ValueError): pass

def need(ok,reason):
    if not ok: raise Refused(reason)

def digest(b): return hashlib.sha256(b).hexdigest()

def canonical(obj):
    return json.dumps(obj,sort_keys=True,ensure_ascii=True,separators=(",",":")).encode("ascii")+b"\n"

def load():
    p=ROOT/(DIR+"review_input_proposals.py")
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<65536,"REVIEWER_PATH")
    raw=p.read_bytes()
    need(hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()=="092b806e11badc9ad8d559cf1a2d1660ef95de07","REVIEWER_PIN")
    spec=importlib.util.spec_from_file_location("pinned_proposals",p)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    plan=m.load(DIR+"toolchain_checksum_plan_20261125.json",m.CHECKSUM_PLAN)
    release=m.load(DIR+"toolchain_release_metadata_20261125.json",m.RELEASE_PIN)
    return m,m.check_checksum(plan,release)

def authorize():
    need(LIVE_ENABLED,"FRESH_APPROVAL_REQUIRED")
    need(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("GITHUB_EVENT_NAME")=="push"
         and os.environ.get("GITHUB_REF")=="refs/heads/feature/live-dev-workspace-20261023"
         and os.environ.get("GITHUB_WORKFLOW")==WORKFLOW and os.environ.get("GITHUB_RUN_ATTEMPT")=="1"
         and os.environ.get("C5_APPROVED_ONCE")==OP
         and re.fullmatch(r"[0-9a-f]{40}",os.environ.get("GITHUB_SHA",""))
         and os.environ.get("GITHUB_SHA")==os.environ.get("C5_EXPECTED_SOURCE_SHA")
         and re.fullmatch(r"[0-9]{1,20}",os.environ.get("GITHUB_RUN_ID","")),"ONE_USE_CONTEXT")
    need(MARKER.is_file() and not MARKER.is_symlink() and MARKER.stat().st_size==len(MARKER_BYTES)
         and MARKER.read_bytes()==MARKER_BYTES,"MARKER")
    return CAPABILITY

@contextmanager
def deadline():
    need(hasattr(signal,"setitimer") and signal.getitimer(signal.ITIMER_REAL)==(0.,0.),"TIMER")
    def alarm(*_): raise Refused("REQUEST_DEADLINE")
    prior=signal.signal(signal.SIGALRM,alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL,15)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,prior)

def url_parts(url):
    need(type(url) is str and 0<len(url)<=8192 and all(33<=ord(c)<=126 for c in url),"URL_SYNTAX")
    u=urlsplit(url)
    need(u.scheme=="https" and u.netloc in HOSTS and not u.fragment and u.path.startswith("/"),"URL_ORIGIN")
    return u

def redirect(doc,location):
    # The authenticated exact GitHub endpoint is the authority for the opaque
    # release asset UUID. It is not inferred from the numeric release asset ID.
    need(doc["id"] in {"python-windows","python-linux"},"REDIRECT_SCOPE")
    u=url_parts(location)
    need(u.netloc in {"release-assets.githubusercontent.com","objects.githubusercontent.com"}
         and re.fullmatch(r"/github-production-release-asset(?:-2e65be)?/250077933/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",u.path),
         "REDIRECT_ASSET_PATH")
    need(0<len(u.query)<=7000,"REDIRECT_QUERY")
    pairs=parse_qsl(u.query,keep_blank_values=False,strict_parsing=True,max_num_fields=32)
    keys={k.lower() for k,v in pairs}
    need(len(keys)==len(pairs) and all(0<len(v)<=4096 and all(32<=ord(c)<=126 for c in v) for _,v in pairs),
         "REDIRECT_QUERY")
    q={k.lower():v for k,v in pairs}
    disposition=q.get("response-content-disposition",q.get("rscd",""))
    need(disposition in ('attachment; filename=hashes.sha256','attachment; filename="hashes.sha256"'),"REDIRECT_FILENAME")
    need(("sig" in q and "se" in q) or ("x-amz-signature" in q and "x-amz-credential" in q and "x-amz-expires" in q),
         "REDIRECT_SIGNATURE_FIELDS")
    return location

def header(resp,name,maxlen=256):
    vals=[v for k,v in resp.getheaders() if k.lower()==name.lower()]
    need(len(vals)<=1,"DUPLICATE_HEADER")
    if not vals: return None
    v=vals[0]
    need(type(v) is str and len(v)<=maxlen and all(32<=ord(c)<=126 for c in v),"HEADER_SYNTAX")
    return v

class MemorySocket:
    def __init__(self,raw): self.raw=raw
    def makefile(self,*_): return io.BytesIO(self.raw)

class Replay:
    responses={}
    requests=[]
    def __init__(self,host,port,**kw):
        need(host in HOSTS and port==443,"FIXTURE_HOST")
        self.host=host
    def request(self,method,path,headers):
        url="https://"+self.host+path
        need(method=="GET" and headers["Accept-Encoding"]=="identity" and url in self.responses,"FIXTURE_REQUEST")
        self.requests.append(url); self.raw=self.responses[url]
    def getresponse(self):
        r=http.client.HTTPResponse(MemorySocket(self.raw));r.begin();return r
    def close(self): pass

class Transport:
    def __init__(self,docs,connection,record,capability=None):
        need(connection is Replay or (LIVE_ENABLED and capability is CAPABILITY and connection is http.client.HTTPSConnection),"OFFLINE_FIXTURE_ONLY")
        self.docs={x["id"]:x for x in docs}; self.connection=connection
        self.record=record; self.requests=0; self.total=0; self.seen=set()
        self.fixture=connection is Replay

    def get(self,doc):
        need(self.docs.get(doc["id"])==doc and doc["id"] not in self.seen,"REQUEST_SCOPE")
        self.seen.add(doc["id"])
        url=doc["url"]; need(not url_parts(url).query,"ORIGINAL_QUERY")
        for hop in (0,1):
            need(self.requests<6 and self.total<TOTAL,"REQUEST_BUDGET")
            u=url_parts(url); self.requests+=1
            status=None; received=0; h=hashlib.sha256(); complete=False; conn=None
            try:
                with deadline():
                    conn=self.connection(u.hostname,443,timeout=15,context=ssl.create_default_context())
                    conn.request("GET",u.path+("?" + u.query if u.query else ""),headers={
                        "Accept":"text/plain, application/octet-stream, application/toml, */*;q=0.1",
                        "Accept-Encoding":"identity","User-Agent":"PilotODIN-C5-checksum-metadata/1"})
                    resp=conn.getresponse(); status=resp.status
                    if status in (301,302,303,307,308):
                        need(hop==0,"REDIRECT_LIMIT")
                        url=redirect(doc,header(resp,"Location",8192)); complete=True
                        continue
                    need(status==200,"HTTP_STATUS")
                    typ=header(resp,"Content-Type")
                    need(typ is not None and typ.split(";",1)[0].strip().lower() in
                        {"text/plain","application/octet-stream","binary/octet-stream","application/toml","text/x-toml"},"CONTENT_TYPE")
                    enc=header(resp,"Content-Encoding")
                    need(enc is None or enc.lower()=="identity","CONTENT_ENCODING")
                    length=header(resp,"Content-Length"); transfer=header(resp,"Transfer-Encoding")
                    need(transfer is None or (transfer.lower()=="chunked" and length is None),"FRAMING")
                    cap=min(doc["max_bytes"],TOTAL-self.total)
                    if length is not None:
                        need(re.fullmatch(r"[0-9]{1,10}",length) and 0<int(length)<=cap,"BODY_LENGTH")
                        length=int(length)
                        need(doc["exact_bytes"] is None or length==doc["exact_bytes"],"BODY_LENGTH")
                    chunks=[]
                    while length is None or received<length:
                        room=min(cap-received,TOTAL-self.total)
                        need(room>0,"BODY_BUDGET")
                        chunk=resp.read1(min(65536,room if length is None else min(room,length-received)))
                        if not chunk: break
                        need(len(chunk)<=room,"BODY_BUDGET")
                        received+=len(chunk); self.total+=len(chunk); h.update(chunk); chunks.append(chunk)
                    need(received>0 and (length is None or length==received),"INCOMPLETE_BODY")
                    complete=True
                    return b"".join(chunks)
            finally:
                if conn is not None: conn.close()
                # Never retain the signed redirect URL or exception messages.
                self.record("REQUEST",{"id":doc["id"],"hop":hop,"host":u.netloc,"status":status,
                    "bytes":received,"sha256":h.hexdigest(),"complete":complete,"fixture":self.fixture})
        raise Refused("REDIRECT_LIMIT")

def collect(parser,docs,connection,record,capability=None):
    t=Transport(docs,connection,record,capability)
    verified=[]; failure=None
    try:
        for d in docs:
            raw=t.get(d)
            # Preserve complete bounded response bytes even when parsing fails.
            b64=base64.b64encode(raw).decode("ascii")
            for offset in range(0,len(b64),8192):
                record("BYTES",{"id":d["id"],"offset":offset,"base64":b64[offset:offset+8192]})
            parsed=parser(d,raw)
            record("VERIFIED",{"id":d["id"],"bytes":len(raw),"sha256":digest(raw),"published":parsed})
            verified.append(d["id"])
    except (ValueError,KeyError,TypeError,AttributeError,OSError,http.client.HTTPException) as exc:
        failure=str(exc) if isinstance(exc,Refused) else "DOCUMENT_OR_TRANSPORT_REFUSED"
    result={"status":"METADATA_ONLY_COMPLETE" if len(verified)==4 and failure is None else "BLOCKED",
        "requests":t.requests,"response_bytes":t.total,"verified":verified,"missing":[d["id"] for d in docs if d["id"] not in verified],
        "failure":failure,"artifact_requests":0,"fixture":t.fixture}
    record("RESULT",result)
    return result

def verify_receipt(parser,docs,records):
    # Independently reconstruct all complete response bodies, including a
    # refused parse. Validate ordered request/document identity and stop state.
    need(records and records[-1]["kind"]=="RESULT","RESULT")
    reqs={}; buffers={}; verified={}; known={d["id"]:d for d in docs}
    order=list(known); current=0
    terminal=records[-1]["record"]
    need(terminal["fixture"] is True or terminal["fixture"] is False,"RECEIPT_FIXTURE")
    for w in records[:-1]:
        k,r=w["kind"],w["record"]; name=r["id"]
        need(name in known and current<len(order) and name==order[current],"RECEIPT_SCOPE")
        if k=="REQUEST":
            key=(name,r["hop"]); d=known[name]
            need(set(r)=={"id","hop","host","status","bytes","sha256","complete","fixture"}
                 and key not in reqs and type(r["hop"]) is int and r["hop"] in (0,1)
                 and type(r["bytes"]) is int and 0<=r["bytes"]<=d["max_bytes"]
                 and HEX.fullmatch(r["sha256"]) and r["fixture"] is terminal["fixture"]
                 and type(r["complete"]) is bool and name not in buffers,"RECEIPT_REQUEST")
            if r["hop"]==0:
                need(r["host"]==url_parts(d["url"]).netloc,"RECEIPT_ORIGIN")
            else:
                prev=reqs.get((name,0),{})
                need(name in {"python-windows","python-linux"}
                    and prev.get("status") in (301,302,303,307,308) and prev.get("complete") is True
                    and r["host"] in {"release-assets.githubusercontent.com","objects.githubusercontent.com"},"RECEIPT_REDIRECT")
            if r["status"]!=200:
                need(r["bytes"]==0 and r["sha256"]==digest(b""),"RECEIPT_NONBODY")
            reqs[key]=r
        elif k=="BYTES":
            old=buffers.get(name,"")
            rr=reqs.get((name,1),reqs.get((name,0),{}))
            need(rr.get("status")==200 and rr.get("complete") is True
                 and name not in verified and r["offset"]==len(old)
                 and type(r["base64"]) is str and 0<len(r["base64"])<=8192,"RECEIPT_CHUNK")
            buffers[name]=old+r["base64"]
            need(len(buffers[name])<=4*((known[name]["max_bytes"]+2)//3),"RECEIPT_CAP")
        elif k=="VERIFIED":
            need(name in buffers and name not in verified,"RECEIPT_VERIFIED")
            raw=base64.b64decode(buffers[name],validate=True)
            rr=reqs.get((name,1),reqs.get((name,0),{}))
            need(rr.get("complete") is True and rr.get("status")==200 and len(raw)==r["bytes"]==rr["bytes"]
                 and digest(raw)==r["sha256"]==rr["sha256"] and parser(known[name],raw)==r["published"],"RECEIPT_BODY")
            verified[name]=r; current+=1
        else: raise Refused("RECEIPT_KIND")
    # A complete response is always preserved, even if its parser refused.
    complete_bodies={name for (name,_),r in reqs.items() if r["status"]==200 and r["complete"]}
    need(set(buffers)==complete_bodies,"RECEIPT_BODY_COVERAGE")
    for name,b64 in buffers.items():
        raw=base64.b64decode(b64,validate=True)
        rr=reqs.get((name,1),reqs.get((name,0),{}))
        need(len(raw)==rr["bytes"] and digest(raw)==rr["sha256"],"RECEIPT_RAW_HASH")
    result=terminal
    need(result["requests"]==len(reqs)<=6 and result["response_bytes"]==sum(r["bytes"] for r in reqs.values())<=TOTAL
         and result["verified"]==list(verified) and result["missing"]==order[current:]
         and result["artifact_requests"]==0,"RECEIPT_TOTAL")
    if result["status"]=="METADATA_ONLY_COMPLETE":
        need(current==len(order) and result["failure"] is None,"RECEIPT_COMPLETE")
    else:
        need(result["status"]=="BLOCKED" and current<len(order) and type(result["failure"]) is str
            and bool(result["failure"]),"RECEIPT_BLOCKED")
    return result

def wire(body=b"",status="200 OK",headers=(),length=True):
    return ("HTTP/1.1 "+status+"\r\n"+"".join(k+": "+v+"\r\n" for k,v in headers)
          +("Content-Length: "+str(len(body))+"\r\n" if length else "")+"\r\n").encode()+body

def fixtures(docs):
    # Use exact document URLs, synthetic bytes with synthetic document pins.
    ds=[dict(d) for d in docs]; bodies={}
    for d in ds[:3]:
        raw="".join("a"*64+"  "+n+"\n" for n in d["targets"]).encode()
        d.update(max_bytes=len(raw)+8,exact_bytes=len(raw),expected_sha256=digest(raw),known_target_sha256=None)
        bodies[d["id"]]=raw
    d=ds[3]; lines=['manifest-version = "2"','date = "2026-11-12"','[pkg.rust]','version = "1.100.0"']
    for n in d["components"]:
        lines += [f"[pkg.{n}]",'version = "1.100.0"']
        for target in d["targets"]:
            lines += [f"[pkg.{n}.target.{target}]",'available = true',
                f'xz_url = "https://static.rust-lang.org/dist/2026-11-12/{n}-1.100.0-{target}.tar.xz"',
                'xz_hash = "'+"b"*64+'"']
    bodies[d["id"]]=("\n".join(lines)+"\n").encode()
    responses={}
    redirects=[]
    for i,d in enumerate(ds):
        dest=d["url"]
        if i<2:
            dest=f"https://release-assets.githubusercontent.com/github-production-release-asset/250077933/00000000-0000-0000-0000-00000000000{i}?sig=fixture{i}&se=fixture&rscd=attachment%3B%20filename%3Dhashes.sha256"
            redirects.append(dest)
            responses[d["url"]]=wire(status="302 Found",headers=(("Location",dest),))
        responses[dest]=wire(bodies[d["id"]],headers=(("Content-Type","text/plain"),))
    return ds,responses,redirects

def self_test():
    import copy
    m,docs=load(); ds,responses,redirs=fixtures(docs); count=0
    def check(ok,reason):
        nonlocal count
        need(ok,reason); count+=1
    def refuse(fn,reason):
        try: fn()
        except Refused as e: check(str(e)==reason,"REFUSAL_"+reason)
        else: raise Refused("ACCEPTED_"+reason)
    def run(reply):
        Replay.responses=reply; Replay.requests=[]; records=[]
        r=collect(m.parse_document,ds,Replay,lambda k,v:records.append({"kind":k,"record":v}))
        return r,records,list(Replay.requests)
    r,rec,req=run(responses)
    check(r["status"]=="METADATA_ONLY_COMPLETE" and r["requests"]==6 and len(set(req))==6,"FULL")
    check(verify_receipt(m.parse_document,ds,rec)==r,"RECEIPT")
    check("sig=fixture" not in str(rec) and "rscd=" not in str(rec),"REDACTION")
    bad=copy.deepcopy(rec);next(x for x in bad if x["kind"]=="BYTES")["record"]["offset"]=1
    refuse(lambda:verify_receipt(m.parse_document,ds,bad),"RECEIPT_CHUNK")
    for key,value,reason in [("host","example.invalid","RECEIPT_ORIGIN"),
                             ("fixture",False,"RECEIPT_REQUEST"),
                             ("bytes",10000000,"RECEIPT_REQUEST")]:
        bad=copy.deepcopy(rec)
        next(x for x in bad if x["kind"]=="REQUEST")["record"][key]=value
        refuse(lambda:verify_receipt(m.parse_document,ds,bad),reason)
    bad=copy.deepcopy(rec)
    bad[-1]["record"]["missing"]=["rust"]
    refuse(lambda:verify_receipt(m.parse_document,ds,bad),"RECEIPT_TOTAL")

    for loc,reason in [(redirs[0].replace("https:","http:"),"URL_ORIGIN"),
          (redirs[0].replace("release-assets.githubusercontent.com","example.invalid"),"URL_ORIGIN"),
          (redirs[0].replace("250077933","123"),"REDIRECT_ASSET_PATH"),
          (redirs[0].replace("hashes.sha256","python.zip"),"REDIRECT_FILENAME"),
          (redirs[0].replace("sig=fixture0&",""),"REDIRECT_SIGNATURE_FIELDS"),
          (redirs[0]+"&sig=duplicate","REDIRECT_QUERY")]:
        refuse(lambda:redirect(ds[0],loc),reason)
    refuse(lambda:redirect(ds[2],redirs[0]),"REDIRECT_SCOPE")
    refuse(lambda:Transport(ds,http.client.HTTPSConnection,lambda *_:None),"OFFLINE_FIXTURE_ONLY")
    t=Transport(ds,Replay,lambda *_:None)
    refuse(lambda:t.get({**ds[0],"url":"https://github.com/other"}),"REQUEST_SCOPE")
    for reply,reason in [(wire(status="302 Found",headers=(("Location",redirs[1]),)),"REDIRECT_LIMIT"),
        (wire(b"x",headers=(("Content-Type","text/html"),)),"CONTENT_TYPE"),
        (wire(b"x",headers=(("Content-Type","text/plain"),("Content-Encoding","gzip"))),"CONTENT_ENCODING"),
        (wire(b"",headers=(("Content-Type","text/plain"),("Content-Length","100000")),length=False),"BODY_LENGTH"),
        (wire(b"x",headers=(("Content-Type","text/plain"),("Content-Length","1"),("Content-Length","1")),length=False),"DUPLICATE_HEADER"),
        (wire(b"x",status="404 Not Found"),"HTTP_STATUS"),
        (wire(b"x",headers=(("Content-Type","text/plain"),("Content-Length",str(ds[0]["exact_bytes"]))),length=False),"INCOMPLETE_BODY")]:
        r,_,req=run({**responses,redirs[0]:reply})
        check(r["failure"]==reason and len(req)==2 and not r["verified"],"TRANSPORT_"+reason)
    r,partial,req=run({**responses,redirs[0]:wire(b"x"*ds[0]["exact_bytes"],headers=(("Content-Type","text/plain"),))})
    check(r["status"]=="BLOCKED" and len(req)==2 and r["failure"]=="DOCUMENT_OR_TRANSPORT_REFUSED","DIGEST")
    check(verify_receipt(m.parse_document,ds,partial)==r,"REFUSED_BODY_RECEIPT")
    bad=copy.deepcopy(partial)
    next(x for x in bad if x["kind"]=="BYTES")["record"]["base64"]="AAAA"
    refuse(lambda:verify_receipt(m.parse_document,ds,bad),"RECEIPT_RAW_HASH")
    if not LIVE_ENABLED: refuse(authorize,"FRESH_APPROVAL_REQUIRED")
    else:
        old=os.environ.pop("C5_APPROVED_ONCE",None)
        try: refuse(authorize,"ONE_USE_CONTEXT")
        finally:
            if old is not None: os.environ["C5_APPROVED_ONCE"]=old
    print("C5_CHECKSUM_REVIEW "+json.dumps({"status":"PASS","checks":count,"synthetic_requests":6,"live_requests":0,
          "live_enabled":LIVE_ENABLED,"documents":4,"receipt_reconstructed":True},sort_keys=True),flush=True)

def live_collect():
    cap=authorize(); m,docs=load(); records=[]
    def record(k,r):
        w={"kind":k,"record":r};records.append(w)
        print("C5_CHECKSUM_"+k+" "+json.dumps(r,sort_keys=True,ensure_ascii=True),flush=True)
    result=collect(m.parse_document,docs,http.client.HTTPSConnection,record,cap)
    verify_receipt(m.parse_document,docs,records)
    print("C5_CHECKSUM_RECEIPT "+json.dumps({"run_id":os.environ["GITHUB_RUN_ID"],"source_sha":os.environ["GITHUB_SHA"],
        "attempt":1,"records":len(records),"sha256":digest(b"".join(canonical(x) for x in records))},sort_keys=True),flush=True)
    return 0 if result["status"]=="METADATA_ONLY_COMPLETE" else 2

if __name__=="__main__":
    try:
        if sys.argv[1:]==["--self-test"]: self_test()
        elif sys.argv[1:]==["--collect"]: raise SystemExit(live_collect())
        else: raise Refused("COMMAND_REFUSED")
    except Refused as exc:
        print("C5_CHECKSUM_REFUSAL "+json.dumps({"reason":str(exc)},sort_keys=True),flush=True)
        raise SystemExit(2)
