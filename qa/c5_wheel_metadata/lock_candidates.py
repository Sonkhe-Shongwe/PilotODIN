"""Evidence-only candidate inventories. Never writes a lock or invokes pip."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = "qa/c5_wheel_metadata/combined_graph.py"
GRAPH_BLOB = "7d7eaa012faf08ca9248f3918c6d776f6bbeb2a1"
GRAPH_RECEIPT = "qa/c5_wheel_metadata/combined_graph_receipt_45702239980.json"
GRAPH_RECEIPT_BLOB = "6c95b4263e9d0f831aa00cfa68e9cb8268aebbd7"
PRODUCTION_INTENT = "qa/c5_wheel_metadata/freezer_source_intent_20261125.json"


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path, pin=None):
    p = ROOT / path
    need(p.is_file() and not p.is_symlink() and p.stat().st_size <= 2*1024*1024, "PIN_PATH")
    raw = p.read_bytes()
    if pin:
        need(hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()==pin,"PIN_DIGEST")
    return raw


def graph_module():
    read(GRAPH_PATH,GRAPH_BLOB)
    spec = importlib.util.spec_from_file_location("reviewed_graph",ROOT/GRAPH_PATH)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def selected_records(g):
    # The combined reader validates exact pinned manifests, all eleven shard
    # digests, the raw bytes, selected identities and both terminal receipts.
    groups,prior = g.missing_inventory()
    new = g.new_receipt(groups)
    verified = {**prior,**new}
    full = {w["filename"]:w for rows in g.inventory().values() for w in rows}
    need(len(prior)==33 and len(new)==29 and not set(prior)&set(new)
         and set(full)==set(verified),"COVERAGE")
    return full,verified,prior


def candidates(g):
    full,verified,prior = selected_records(g)
    receipt = g.parse(read(GRAPH_RECEIPT,GRAPH_RECEIPT_BLOB))
    runtime,test = g.roots()
    inv = g.parse(read(g.OBSERVED,g.OBSERVED_BLOB))
    reports = [g.graph(p,verified,r,label) for p in inv["profiles"]
               for r,label in [(test,"source-test"),(runtime,"runtime-root-subset")]]
    need(reports == receipt["reports"],"GRAPH_RECEIPT_DRIFT")
    result=[]
    for p in reports:
        rows=[]
        for node in p["nodes"]:
            filename=node["filename"]
            w=full[filename]
            m=verified[filename]
            d=m["declarations"]
            need(node["name"]==w["name"] and node["version"]==w["version"]
                 and g.HEX.fullmatch(w["wheel_sha256"]) and g.HEX.fullmatch(m["metadata_sha256"]),
                 "CANDIDATE_IDENTITY")
            rows.append({"name":w["name"],"version":w["version"],"filename":filename,
                         "expected_wheel_bytes":w["wheel_bytes"],"expected_wheel_sha256":w["wheel_sha256"],
                         "observed_wheel_url":w["url"],"verified_metadata_sha256":m["metadata_sha256"],
                         "metadata_receipt_run":"45700172241" if filename in prior else "45701493997",
                         "metadata_version":d["metadata_version"],"requires_python":d["requires_python"],
                         "license_expression":d["license_expression"],"license_files":d["license_files"],
                         "license_classifiers":d["license_classifiers"],"license_text_present":d["license"] is not None,
                         "actual_wheel_bytes_verified":False,"license_reviewed":False})
        need(len(rows)==p["reachable"] and not p["issues"],"CANDIDATE_GRAPH")
        result.append({"profile":p["profile"],"scope":p["scope"],"python_candidate":p["python"],
                       "status":"BLOCKED_NON_INSTALLABLE","rows":rows,"count":len(rows),
                       "total_expected_wheel_bytes":sum(r["expected_wheel_bytes"] for r in rows),
                       "active_edges":p["active_edges"],"extras":p["extras"],
                       "unknown_requires_python":p["unknown_python"],
                       "graph_receipt":GRAPH_RECEIPT,"graph_receipt_blob":GRAPH_RECEIPT_BLOB})
    return result


def production(g, rows):
    intent=g.parse(read(PRODUCTION_INTENT))
    # Validate reviewed historical intent sources, not run them.
    for source in intent["local_source_pins"]:
        read(source["path"],source["blob"])
    win=next(p for p in rows if p["profile"]=="windows-x64-cp311-source-test" and p["scope"]=="runtime-root-subset")
    test=next(p for p in rows if p["profile"]=="windows-x64-cp311-source-test" and p["scope"]=="source-test")
    known={r["name"]:r for r in win["rows"]}
    observed={r["name"]:r for r in test["rows"]}
    env=g.environment("3.11.9","win32")
    missing={}
    retained={}
    inactive=[]
    for source,decls in intent["candidate_declarations"].items():
        for declaration in decls:
            req=g.Requirement(declaration)
            name=g.canonicalize_name(req.name)
            if not g.marker_active(req,env,[]):
                inactive.append({"from":source,"requirement":declaration})
                continue
            target=known.get(name) or observed.get(name)
            if target is not None:
                need(req.specifier.contains(g.Version(target["version"])),"FREEZER_OBSERVED_VERSION_CONFLICT")
                retained.setdefault(name,{"version":target["version"],"scope":"RUNTIME_SUBSET" if name in known else "SOURCE_TEST_ONLY_REUSE_CANDIDATE","requirements":[]})["requirements"].append({"from":source,"requirement":declaration})
            else:
                missing.setdefault(name,[]).append({"from":source,"requirement":declaration})
    need(set(missing)=={"pyinstaller","pyinstaller-hooks-contrib","setuptools","altgraph","pefile","pywin32-ctypes"},"FREEZER_GAP_SET")
    need(set(retained)=={"packaging"},"FREEZER_REUSE")
    return {"profile":"windows-x64-cp311-production-build","status":"BLOCKED_NO_PRODUCTION_LOCK",
            "runtime_subset_count":win["count"],"runtime_subset_not_production_selection":True,
            "candidate_extra_names":sorted(missing),"missing_requirements":missing,
            "reuse_candidates":retained,"inactive_declared_edges":inactive,
            "minimum_candidate_nodes_before_transitive_review":win["count"]+len(missing)+len(set(retained)-set(known)),
            "source_intent":PRODUCTION_INTENT,"production_interpreter_unverified":True,
            "historical_devqa_python":"3.12.3","actual_wheel_bytes_verified":False,
            "transitive_freezer_graph_complete":False}


def main():
    need(sys.argv[1:]==["--review"],"REVIEW_ONLY")
    g=graph_module()
    rows=candidates(g)
    prod=production(g,rows)
    need([p["count"] for p in rows]==[49,36,49,37],"PROFILE_COUNTS")
    need(all(p["status"]=="BLOCKED_NON_INSTALLABLE" and p["unknown_requires_python"]==["pytz"] for p in rows),"PROFILE_BLOCKERS")
    test=[p for p in rows if p["scope"]=="source-test"]
    unique={r["filename"]:r for p in test for r in p["rows"]}
    need(len(unique)==62 and sum(r["expected_wheel_bytes"] for r in unique.values())==222779129,"UNIQUE_EXPECTED_BYTES")
    for p in rows:
        print("C5_LOCK_CANDIDATE "+json.dumps(p,sort_keys=True,ensure_ascii=True),flush=True)
    print("C5_FREEZER_GAPS "+json.dumps(prod,sort_keys=True,ensure_ascii=True),flush=True)
    print("C5_LOCK_SUMMARY "+json.dumps({"status":"CANDIDATES_ONLY","profiles":4,"source_test_rows":98,
           "unique_wheels":62,"unique_expected_wheel_bytes":222779129,"freezer_missing":len(prod["candidate_extra_names"]),
           "live_requests":0,"installable_locks":0,"actual_wheels_verified":0},sort_keys=True),flush=True)


if __name__=="__main__":
    main()
