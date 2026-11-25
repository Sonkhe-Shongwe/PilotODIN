"""Offline production candidate evidence only. No registry, resolver, installer or lock writer."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]
BASE="qa/c5_wheel_metadata/combined_graph.py"
BASE_BLOB="7d7eaa012faf08ca9248f3918c6d776f6bbeb2a1"
MANIFEST="qa/c5_wheel_metadata/freezer_receipt_45704870236_manifest.json"
MANIFEST_BLOB="602556d9bb5ebe800bb44f9eb251b7a67ba6f0b8"
RECORDS="qa/c5_wheel_metadata/freezer_receipt_45704870236.jsonl"
DIGEST="d38a37b49f1755f9970c86f890504c272253d0d907f09620fbd1820a48030cf6"
INTENT="qa/c5_wheel_metadata/freezer_source_intent_20261125.json"
INTENT_BLOB="71293a827b880f3c48b858a52ad783f6cd5411be"
CANDIDATES="qa/c5_wheel_metadata/platform_lock_candidates_45703125465.json"
CANDIDATES_BLOB="6b27407f4b24942c385179bb253f692370f21df7"
VERSIONS={"altgraph":"0.17.5","pefile":"2024.8.26","pyinstaller":"6.22.3",
          "pyinstaller-hooks-contrib":"2026.9","pywin32-ctypes":"0.2.3","setuptools":"84.2.1"}
RULES={"altgraph":"","pefile":">=2022.5.30","pyinstaller":"==6.22.3",
       "pyinstaller-hooks-contrib":"==2026.9","pywin32-ctypes":">=0.2.1","setuptools":">=42.0.0"}

def need(ok,reason):
    if not ok: raise ValueError(reason)

def read(path,pin=None):
    p=ROOT/path
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<=2*1024*1024,"PIN_PATH")
    raw=p.read_bytes()
    if pin:
        need(hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()==pin,"PIN_DIGEST")
    return raw

def load():
    read(BASE,BASE_BLOB)
    spec=importlib.util.spec_from_file_location("reviewed_graph",ROOT/BASE)
    g=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    need(g.packaging_version=="24.0","REVIEWER_VERSION")
    return g

def verify_freezer(g,records):
    need(len(records)==36 and records[-1]["kind"]=="RESULT","RECORD_COUNT")
    reqs,selected,buffers,verified,names={},{},{},{},set()
    digest=hashlib.sha256()
    for wrapper in records[:-1]:
        kind,row=wrapper["kind"],wrapper["record"]
        need(kind in {"REQUEST","INDEX","BYTES","VERIFIED"},"RECORD_KIND")
        if kind!="REQUEST": digest.update(g.canonical(wrapper))
        if kind=="REQUEST":
            cap={"index":32*g.MIB,"metadata":g.MIB}[row["kind"]]
            need(row["url"] not in reqs and row["fixture"] is False and row["complete"] is True
                 and row["http_status"]==200 and type(row["bytes"]) is int and 0<row["bytes"]<=cap
                 and row["response_cap_bytes"]==cap and g.HEX.fullmatch(row["response_sha256"]),"REQUEST")
            reqs[row["url"]]=row
        elif kind=="INDEX":
            name=row["name"]
            r=reqs.get("https://pypi.org/simple/"+name+"/",{})
            need(name in VERSIONS and name not in names and r.get("kind")=="index"
                 and r.get("response_sha256")==row["response_sha256"] and len(row["selected"])==1,"INDEX")
            names.add(name)
            w=row["selected"][0]; fn=w["filename"]; u=urlsplit(w["url"])
            pn,pv,_,tags=g.parse_wheel_filename(fn)
            need(fn not in selected and w["name"]==pn==name and w["version"]==VERSIONS[name]
                 and pv==g.Version(VERSIONS[name]) and bool(tags & g.candidate_tags("win32"))
                 and w["constraint"]==RULES[name] and w["candidate_only"] is True
                 and w["selection"]==("HISTORICAL_EXACT" if RULES[name].startswith("==") else "HIGHEST_STABLE_ELIGIBLE")
                 and g.HEX.fullmatch(w["wheel_sha256"]) and g.HEX.fullmatch(w["metadata_sha256"])
                 and type(w["wheel_bytes"]) is int and w["wheel_bytes"]>0
                 and u.scheme=="https" and u.netloc=="files.pythonhosted.org" and not u.query and not u.fragment
                 and re.fullmatch(r"/packages/[a-f0-9]{2}/[a-f0-9]{2}/[a-f0-9]{60}/"+re.escape(fn),u.path)
                 and w["metadata_url"]==w["url"]+".metadata","IDENTITY")
            if w["index_requires_python"] is not None:
                need(g.SpecifierSet(w["index_requires_python"]).contains(g.Version("3.11.9")),"INDEX_PYTHON")
            selected[fn]=w
        elif kind=="BYTES":
            fn=row["filename"]; old=buffers.get(fn,"")
            need(fn in selected and fn not in verified and row["offset"]==len(old)
                 and type(row["base64"]) is str and 0<len(row["base64"])<=8192,"CHUNK")
            buffers[fn]=old+row["base64"]
            need(len(buffers[fn])<=4*((g.MIB+2)//3),"CHUNK_CAP")
        else:
            fn=row["filename"]
            need(fn in buffers and fn not in verified,"VERIFIED")
            raw=base64.b64decode(buffers[fn],validate=True); w=selected[fn]
            r=reqs.get(w["metadata_url"],{})
            need(r.get("kind")=="metadata" and 0<len(raw)<=g.MIB
                 and len(raw)==row["bytes"]==r.get("bytes")
                 and g.sha(raw)==w["metadata_sha256"]==row["metadata_sha256"]==r.get("response_sha256")
                 and g.metadata(raw,w)==row["declarations"],"METADATA")
            verified[fn]=row
    r=records[-1]["record"]
    need(names==set(VERSIONS) and set(selected)==set(buffers)==set(verified) and len(verified)==6
         and set(reqs)=={"https://pypi.org/simple/"+n+"/" for n in VERSIONS}|{w["metadata_url"] for w in selected.values()}
         and len(reqs)==12 and digest.hexdigest()==DIGEST==r["receipt_sha256"]
         and r["run_id"]=="45704870236" and r["run_attempt"]==1
         and r["source_sha"]=="e11d637138a7542f78934e1ace55c9575ad93a2b"
         and r["operation"]=="C5-FREEZER-METADATA-ONCE-20261125" and r["fixture"] is False
         and r["status"]=="METADATA_ONLY_COMPLETE" and r["failure"] is None and r["missing"]==[]
         and r["artifact_requests"]==0 and r["verified"]==6 and r["requests"]=={"index":6,"metadata":6}
         and r["response_bytes"]==1359876==sum(x["bytes"] for x in reqs.values())
         and sum(x["bytes"] for x in verified.values())==43923
         and sum(x["wheel_bytes"] for x in selected.values())==2920851,"TERMINAL")
    return selected,verified

def graph(g,selected,verified,roots):
    env=g.environment("3.11.9","win32"); tags=g.candidate_tags("win32")
    byname={}; issues=set(); unknown=[]; extras={}
    for fn,w in selected.items():
        name=w["name"]; d=verified[fn]["declarations"]
        pn,pv,_,wt=g.parse_wheel_filename(fn)
        need(name not in byname and pn==name==g.canonicalize_name(d["name"])
             and pv==g.Version(w["version"]) and d["version"]==w["version"],"GRAPH_IDENTITY")
        byname[name]=(w,d,bool(wt&tags))
    def add(req,source):
        name=g.canonicalize_name(req.name)
        if req.url or name not in byname:
            issues.add((source,str(req),"DIRECT_URL" if req.url else "MISSING")); return False
        w,d,_=byname[name]
        if not req.specifier.contains(g.Version(w["version"])):
            issues.add((source,str(req),"VERSION_CONFLICT"))
        wanted={g.canonicalize_name(x) for x in req.extras}
        if wanted-{g.canonicalize_name(x) for x in d["provides_extra"]}:
            issues.add((source,str(req),"EXTRA_NOT_PROVIDED"))
        changed=name not in extras or not wanted<=extras.get(name,set())
        extras.setdefault(name,set()).update(wanted)
        return changed
    for req in roots: add(req,"ROOT")
    for _ in range(len(byname)*4):
        changed=False
        for name in sorted(extras):
            for declaration in byname[name][1]["requires_dist"]:
                req=g.Requirement(declaration)
                if g.marker_active(req,env,extras[name]): changed=add(req,name) or changed
        if not changed: break
    else: raise ValueError("FIXED_POINT_LIMIT")
    edges=[]; inactive=[]
    for name in sorted(extras):
        w,d,tag=byname[name]
        if d["requires_python"] is None: unknown.append(name)
        elif not g.SpecifierSet(d["requires_python"]).contains(g.Version("3.11.9")):
            issues.add((name,d["requires_python"],"PYTHON_CONFLICT"))
        if not tag: issues.add((name,w["filename"],"TAG_CONFLICT"))
        for declaration in d["requires_dist"]:
            req=g.Requirement(declaration)
            edge={"from":name,"to":g.canonicalize_name(req.name),"requirement":declaration}
            (edges if g.marker_active(req,env,extras[name]) else inactive).append(edge)
    unused=sorted(set(byname)-set(extras))
    if unused: issues.add(("PROFILE",",".join(unused),"UNEXPLAINED_SELECTED"))
    return {"profile":"windows-x64-cp311-production-build","python_candidate":"3.11.9",
            "roots":[str(x) for x in roots],"reachable":len(extras),"active_edges":edges,"inactive":inactive,
            "enabled_extras":{n:sorted(v) for n,v in sorted(extras.items()) if v},
            "unknown_requires_python":unknown,"unused":unused,
            "issues":[{"source":a,"requirement":b,"reason":c} for a,b,c in sorted(issues)],
            "status":"BLOCKED_NON_INSTALLABLE",
            "declared_graph":"COMPATIBLE" if not issues else "BLOCKED"}

def main():
    need(sys.argv[1:]==["--review"],"REVIEW_ONLY")
    g=load()
    m=g.parse(read(MANIFEST,MANIFEST_BLOB))
    raw=read(RECORDS)
    need(m["record_file"]==RECORDS and len(raw)==75996==m["record_file_bytes"]
         and g.sha(raw)==m["record_file_sha256"]=="3b498f911c861689e73709b36b971758b3e9ddeba49a9b1f13d7b9640f03df6e"
         and m["receipt_sha256"]==DIGEST,"RECEIPT_PIN")
    records=[g.parse(line) for line in raw.splitlines()]
    freezer,fmeta=verify_freezer(g,records)
    groups,prior=g.missing_inventory(); new=g.new_receipt(groups)
    original={**prior,**new}
    full={w["filename"]:w for rows in g.inventory().values() for w in rows}
    need(len(original)==62 and set(original)==set(full) and not set(original)&set(fmeta),"ORIGINAL_COVERAGE")
    runtime,_=g.roots()
    inv=g.parse(read(g.OBSERVED,g.OBSERVED_BLOB))
    win=next(p for p in inv["profiles"] if p["profile"]=="windows-x64-cp311-source-test")
    base=g.graph(win,original,runtime,"runtime-root-subset")
    need(base["reachable"]==36 and not base["issues"],"RUNTIME_SUBSET")
    cand=g.parse(read(CANDIDATES,CANDIDATES_BLOB))
    p=next(p for p in cand["candidates"] if p["profile"]==win["profile"] and p["scope"]=="runtime-root-subset")
    need({x["filename"] for x in p["rows"]}=={x["filename"] for x in base["nodes"]},"RUNTIME_RECEIPT")
    pack=next(x for x in win["selected_wheels"] if x["name"]=="packaging")
    need(pack["version"]=="26.4","PACKAGING_REUSE")
    keep={x["filename"] for x in base["nodes"]}|{pack["filename"]}
    selected={**{fn:full[fn] for fn in keep},**freezer}
    verified={**original,**fmeta}
    roots=runtime+[g.Requirement("pyinstaller==6.22.3"),g.Requirement("pyinstaller-hooks-contrib==2026.9")]
    result=graph(g,selected,verified,roots)
    # Compare only active source-declared requirements; exact normalized
    # requirement forms are compared by name, specifier and extras.
    intent=g.parse(read(INTENT,INTENT_BLOB))
    env=g.environment("3.11.9","win32")
    def key(r):
        return (g.canonicalize_name(r.name),str(r.specifier),tuple(sorted(r.extras)))
    for src in ["pyinstaller","pyinstaller-hooks-contrib"]:
        source=intent["candidate_declarations"][src+"-"+VERSIONS[src]]
        expected={key(r) for d in source if g.marker_active(r:=g.Requirement(d),env,[])}
        actual={key(g.Requirement(e["requirement"])) for e in result["active_edges"] if e["from"]==src}
        need(expected==actual,"UPSTREAM_ACTIVE_DECLARATION_DRIFT")
    # Negative controls are independent of live inputs and never write files.
    controls=g.controls()
    tampered=copy.deepcopy(records)
    next(x for x in tampered if x["kind"]=="BYTES")["record"]["offset"]=1
    try: verify_freezer(g,tampered)
    except ValueError as e: need(str(e)=="CHUNK","TEST_TAMPER_REASON"); controls+=1
    else: raise ValueError("TEST_TAMPER_ACCEPTED")
    omit=next(fn for fn,w in selected.items() if w["name"]=="altgraph")
    missing=graph(g,{fn:w for fn,w in selected.items() if fn!=omit},verified,roots)
    need(any(x["reason"]=="MISSING" for x in missing["issues"]),"TEST_MISSING"); controls+=1
    conflict=graph(g,selected,verified,roots+[g.Requirement("packaging<22")])
    need(any(x["reason"]=="VERSION_CONFLICT" for x in conflict["issues"]),"TEST_CONFLICT"); controls+=1
    badextra=graph(g,selected,verified,roots+[g.Requirement("pyinstaller[nonexistent]")])
    need(any(x["reason"]=="EXTRA_NOT_PROVIDED" for x in badextra["issues"]),"TEST_EXTRA"); controls+=1
    result["nodes"]=[{"name":w["name"],"version":w["version"],"filename":fn,
                      "expected_wheel_bytes":w["wheel_bytes"],"expected_wheel_sha256":w["wheel_sha256"],
                      "observed_wheel_url":w["url"],"verified_metadata_sha256":verified[fn]["metadata_sha256"],
                      "requires_python":verified[fn]["declarations"]["requires_python"],
                      "license_expression":verified[fn]["declarations"]["license_expression"],
                      "license_files":verified[fn]["declarations"]["license_files"],
                      "actual_wheel_bytes_verified":False,"license_reviewed":False}
                     for fn,w in sorted(selected.items())]
    result["total_expected_wheel_bytes"]=sum(w["wheel_bytes"] for w in selected.values())
    result["controls"]=controls
    result["verified_sidecars"]=68
    result["live_requests"]=0
    print("C5_PRODUCTION_GRAPH "+json.dumps(result,sort_keys=True,ensure_ascii=True),flush=True)
    print("C5_PRODUCTION_SUMMARY "+json.dumps({k:v for k,v in result.items() if k not in {"nodes","active_edges","inactive"}}|
          {"active_edges":len(result["active_edges"]),"inactive":len(result["inactive"])} ,sort_keys=True),flush=True)

if __name__=="__main__": main()
