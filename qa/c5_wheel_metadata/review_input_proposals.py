"""Offline verification of proposals; deliberately no transport or artifact reader."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[2]
DIR="qa/c5_wheel_metadata/"
WHEEL_PLAN="1aa96a7172508f94b2cdc4b7aabd65e3b8f21f89"
CHECKSUM_PLAN="6f4fca2a429f1bc76982190450cd5b49d89d303a"
TEST_PIN="6b27407f4b24942c385179bb253f692370f21df7"
PROD_PIN="70cdac979b732aadfad0c51d7e159a60840cc1ef"
RELEASE_PIN="7200bc2f37b2989b6d9f3a42707c45f27218987c"
HEX=re.compile("[0-9a-f]{64}")

def require(ok,reason):
    if not ok: raise ValueError(reason)

def unique(pairs):
    out={}
    for k,v in pairs:
        require(k not in out,"DUPLICATE_JSON_KEY")
        out[k]=v
    return out

def load(path,blob):
    p=ROOT/path
    require(p.is_file() and not p.is_symlink() and p.stat().st_size<=2*1024*1024,"PIN_PATH")
    raw=p.read_bytes()
    require(hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==blob,"PIN_DIGEST")
    return json.loads(raw,object_pairs_hook=unique)

def reconstruct(test,prod):
    profiles=[(p["profile"],p["rows"]) for p in test["candidates"] if p["scope"]=="source-test"]
    profiles.append((prod["profile"],prod["nodes"]))
    require([len(rows) for _,rows in profiles]==[49,49,43],"PROFILE_COUNTS")
    unique_rows={}
    for profile,rows in profiles:
        seen=set()
        for r in rows:
            fn=r["filename"]
            require(fn not in seen and re.fullmatch(r"[A-Za-z0-9_.+!-]{1,235}\.whl",fn),"FILENAME")
            seen.add(fn)
            row={"filename":fn,"name":r["name"],"version":r["version"],
                 "url":r["observed_wheel_url"],"bytes":r["expected_wheel_bytes"],
                 "sha256":r["expected_wheel_sha256"],"metadata_sha256":r["verified_metadata_sha256"],
                 "license_files":r["license_files"],"license_expression":r["license_expression"],
                 "requires_python":r["requires_python"]}
            require(type(row["bytes"]) is int and row["bytes"]>0 and HEX.fullmatch(row["sha256"])
                    and HEX.fullmatch(row["metadata_sha256"]) and re.fullmatch(
                    r"https://files\.pythonhosted\.org/packages/[a-f0-9]{2}/[a-f0-9]{2}/[a-f0-9]{60}/"+re.escape(fn),row["url"]),
                    "WHEEL_IDENTITY")
            require(r["actual_wheel_bytes_verified"] is False and r["license_reviewed"] is False,"FALSE_CLEARANCE")
            if fn in unique_rows:
                require(all(unique_rows[fn][k]==v for k,v in row.items()),"SHARED_IDENTITY")
                unique_rows[fn]["profiles"].append(profile)
            else:
                unique_rows[fn]={**row,"profiles":[profile]}
    return [{"id":p,"count":len(r)} for p,r in profiles],[unique_rows[k] for k in sorted(unique_rows)]

def check_wheel(plan,test,prod):
    profiles,rows=reconstruct(test,prod)
    require(plan["status"]=="PROPOSAL_ONLY_DISABLED" and plan["profiles"]==profiles
            and plan["wheels"]==rows and len(rows)==plan["unique_count"]==plan["max_requests"]==68
            and len({w["url"] for w in rows})==68
            and sum(w["bytes"] for w in rows)==plan["expected_bytes"]==225699980
            and max(w["bytes"] for w in rows)==plan["largest_wheel_bytes"]==36607512
            and plan["redirects"]==plan["retries"]==0,"WHEEL_SCOPE")
    require(plan["inspection_limits"]=={"max_members_per_wheel":50000,
        "max_uncompressed_member_bytes":536870912,"max_uncompressed_wheel_bytes":1073741824,
        "max_uncompressed_total_bytes":4294967296,"max_notice_bytes_per_file":1048576,
        "max_notice_bytes_total":33554432},"INSPECTION_BOUNDS")
    return rows

def check_checksum(plan,release):
    d=plan["documents"]
    require(plan["status"]=="PROPOSAL_ONLY_DISABLED" and plan["logical_documents"]==len(d)==4
        and plan["max_http_requests"]==6 and plan["max_total_body_bytes"]==5*1024*1024
        and plan["retries"]==plan["artifact_downloads"]==0 and plan["timeout_seconds_per_request"]==15
        and plan["max_job_minutes"]==10,"CHECKSUM_SCOPE")
    for i,p in enumerate(release["python_candidates"]):
        expected={"id":["python-windows","python-linux"][i],"url":p["checksum_manifest"]["url"],
             "max_bytes":p["checksum_manifest"]["bytes"],"exact_bytes":p["checksum_manifest"]["bytes"],
             "expected_sha256":p["checksum_manifest"].get("published_sha256"),"targets":[p["filename"]],
             "kind":"sha256-lines","known_target_sha256":p["published_sha256"]}
        require(d[i]==expected,"PYTHON_DOCUMENT")
    require(d[2]=={"id":"node","url":"https://nodejs.org/dist/v22.23.5/SHASUMS256.txt",
          "max_bytes":65536,"exact_bytes":None,"expected_sha256":None,
          "targets":["node-v22.23.5-win-x64.zip","node-v22.23.5-linux-x64.tar.xz"],"kind":"sha256-lines"},"NODE_DOCUMENT")
    require(d[3]=={"id":"rust","url":"https://static.rust-lang.org/dist/channel-rust-1.100.0.toml",
          "max_bytes":4*1024*1024,"exact_bytes":None,"expected_sha256":None,
          "kind":"rust-channel-toml","version":"1.100.0","components":["rustc","cargo","rust-std"],
          "targets":["x86_64-pc-windows-msvc","x86_64-unknown-linux-gnu"]},"RUST_DOCUMENT")
    require(sum(x["max_bytes"] for x in d)<plan["max_total_body_bytes"],"TOTAL_CAP")
    return d

def parse_document(d,raw):
    require(type(raw) is bytes and 0<len(raw)<=d["max_bytes"],"BODY_CAP")
    require(d["exact_bytes"] is None or len(raw)==d["exact_bytes"],"BODY_LENGTH")
    sha=hashlib.sha256(raw).hexdigest()
    require(d["expected_sha256"] is None or sha==d["expected_sha256"],"BODY_HASH")
    text=raw.decode("utf-8",errors="strict")
    if d["kind"]=="sha256-lines":
        rows={}
        for line in text.splitlines():
            match=re.fullmatch(r"([0-9a-f]{64}) [ *]([A-Za-z0-9_.+/-]+)",line)
            require(match is not None,"CHECKSUM_GRAMMAR")
            digest,name=match.groups()
            require(not name.startswith("/") and all(p not in ("",".","..") for p in name.split("/"))
                and name not in rows,"CHECKSUM_IDENTITY")
            rows[name]=digest
        require(all(t in rows for t in d["targets"]),"TARGET_MISSING")
        result={t:rows[t] for t in d["targets"]}
        require(d.get("known_target_sha256") is None or list(result.values())==[d["known_target_sha256"]],"TARGET_HASH")
        return result
    require(d["kind"]=="rust-channel-toml","DOCUMENT_KIND")
    m=tomllib.loads(text)
    require(m["manifest-version"]=="2" and re.fullmatch(r"\d{4}-\d{2}-\d{2}",m["date"])
        and re.fullmatch(re.escape(d["version"])+r"(?: \([^\r\n]+\))?",m["pkg"]["rust"]["version"]),"RUST_IDENTITY")
    rows=[]
    for name in d["components"]:
        pkg=m["pkg"][name]
        for target in d["targets"]:
            item=pkg["target"][target]
            fn=f"{name}-{d['version']}-{target}.tar.xz"
            require(item["available"] is True and HEX.fullmatch(item["xz_hash"])
                and item["xz_url"]=="https://static.rust-lang.org/dist/"+m["date"]+"/"+fn,"RUST_COMPONENT")
            rows.append({"component":name,"target":target,"declared_version":pkg["version"],
                         "url":item["xz_url"],"sha256":item["xz_hash"]})
    return rows

def main():
    require(sys.argv[1:]==["--review"],"OFFLINE_REVIEW_ONLY")
    w=load(DIR+"wheel_acquisition_plan_20261125.json",WHEEL_PLAN)
    c=load(DIR+"toolchain_checksum_plan_20261125.json",CHECKSUM_PLAN)
    t=load(DIR+"platform_lock_candidates_45703125465.json",TEST_PIN)
    p=load(DIR+"production_graph_receipt_45705552265.json",PROD_PIN)
    release=load(DIR+"toolchain_release_metadata_20261125.json",RELEASE_PIN)
    rows=check_wheel(w,t,p); docs=check_checksum(c,release)
    count=2
    def refuse(fn,reason):
        nonlocal count
        try: fn()
        except ValueError as exc: require(str(exc)==reason,"UNEXPECTED_REFUSAL_"+str(exc)); count+=1
        else: raise ValueError("REFUSAL_FAILED_"+reason)
    for mutation in ["remove","duplicate","url","hash","budget","enable"]:
        bad=copy.deepcopy(w)
        if mutation=="remove": bad["wheels"].pop()
        elif mutation=="duplicate": bad["wheels"].append(bad["wheels"][0])
        elif mutation=="url": bad["wheels"][0]["url"]+=".metadata"
        elif mutation=="hash": bad["wheels"][0]["sha256"]="0"*64
        elif mutation=="budget": bad["expected_bytes"]+=1
        else: bad["status"]="ENABLED"
        refuse(lambda:check_wheel(bad,t,p),"WHEEL_SCOPE")
    for mutation in ["url","target","cap","retry","enable"]:
        bad=copy.deepcopy(c)
        if mutation=="url": bad["documents"][2]["url"]="https://example.invalid/SHASUMS256.txt"
        elif mutation=="target": bad["documents"][2]["targets"].append("other.zip")
        elif mutation=="cap": bad["documents"][3]["max_bytes"]*=2
        elif mutation=="retry": bad["retries"]=1
        else: bad["status"]="ENABLED"
        refuse(lambda:check_checksum(bad,release),"NODE_DOCUMENT" if mutation in {"url","target"} else "RUST_DOCUMENT" if mutation=="cap" else "CHECKSUM_SCOPE")
    d=docs[2]; raw=("1"*64+"  "+d["targets"][0]+"\n"+"2"*64+" *"+d["targets"][1]+"\n").encode()
    require(parse_document(d,raw)=={d["targets"][0]:"1"*64,d["targets"][1]:"2"*64},"SHA_FIXTURE"); count+=1
    refuse(lambda:parse_document(d,raw+raw),"CHECKSUM_IDENTITY")
    refuse(lambda:parse_document(d,raw+b"not a checksum\n"),"CHECKSUM_GRAMMAR")
    refuse(lambda:parse_document(d,raw.splitlines()[0]),"TARGET_MISSING")
    refuse(lambda:parse_document(d,b"x"*(d["max_bytes"]+1)),"BODY_CAP")
    refuse(lambda:parse_document({**d,"exact_bytes":len(raw)+1},raw),"BODY_LENGTH")
    refuse(lambda:parse_document({**d,"expected_sha256":"0"*64},raw),"BODY_HASH")
    refuse(lambda:parse_document({**d,"known_target_sha256":"0"*64},raw),"TARGET_HASH")
    refuse(lambda:parse_document(d,raw+("3"*64+"  ../escape\n").encode()),"CHECKSUM_IDENTITY")
    d=docs[3]; parts=['manifest-version = "2"','date = "2026-11-12"','[pkg.rust]','version = "1.100.0"']
    for name in d["components"]:
        parts += [f"[pkg.{name}]",'version = "1.100.0"']
        for target in d["targets"]:
            parts += [f"[pkg.{name}.target.{target}]",'available = true',
                f'xz_url = "https://static.rust-lang.org/dist/2026-11-12/{name}-1.100.0-{target}.tar.xz"',
                'xz_hash = "'+"3"*64+'"']
    raw=("\n".join(parts)+"\n").encode()
    require(len(parse_document(d,raw))==6,"RUST_FIXTURE"); count+=1
    refuse(lambda:parse_document(d,raw.replace(b"available = true",b"available = false",1)),"RUST_COMPONENT")
    refuse(lambda:parse_document(d,raw.replace(b"static.rust-lang.org",b"example.invalid",1)),"RUST_COMPONENT")
    refuse(lambda:parse_document(d,raw.replace(b'version = "1.100.0"',b'version = "1.101.0"',1)),"RUST_IDENTITY")
    print("C5_INPUT_PROPOSALS "+json.dumps({"status":"PASS","checks":count,"wheel_count":len(rows),
        "wheel_bytes":w["expected_bytes"],"documents":len(docs),"max_metadata_requests":6,
        "live_requests":0,"artifact_downloads":0,"transport_implemented":False,"archive_inspector_implemented":False},sort_keys=True),flush=True)

if __name__=="__main__": main()
