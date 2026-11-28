// PilotODIN continuation validator. Read-only; no network, subprocess, writes or permission grant.
import {readFileSync, realpathSync, statSync} from "node:fs";
import {dirname, resolve, relative, isAbsolute} from "node:path";
import {fileURLToPath} from "node:url";

function validateState(s,scoreText,hasPath){
  const errors=[];
  const need=(ok,msg)=>{if(!ok)errors.push(msg)};
  const sha=x=>typeof x==="string"&&/^[0-9a-f]{40}$/.test(x);
  const text=x=>typeof x==="string"&&x.trim().length>0;
  const pair=x=>Array.isArray(x)&&x.length===2&&x.every(Number.isSafeInteger)&&x[0]>=0&&x[1]>0&&x[0]<=x[1];
  const taskStates=["READY","PREPARED","IN_PROGRESS","PUBLISHED","VERIFYING","BLOCKED","CLOSED"];
  const opStates=["NONE","PREPARED","ISSUED","UNKNOWN","RECONCILED"];
  const uncertain=x=>["ISSUED","UNKNOWN"].includes(x);
  const object=x=>x!==null&&typeof x==="object"&&!Array.isArray(x);
  if(!object(s))return ["State must be an object"];
  try {
    need(s.schema_version===2,"Unsupported schema version");
    need(s.repository.name==="Sonkhe-Shongwe/PilotODIN"&&s.repository.branch==="feature/live-dev-workspace-20261023","Repository or branch mismatch");
    need(sha(s.checkpoint.parent_sha)&&sha(s.checkpoint.previous_snapshot_sha)&&text(s.checkpoint.operation_id)&&text(s.checkpoint.scope)&&opStates.includes(s.checkpoint.state),"Invalid checkpoint");
    need(sha(s.product.sha)&&text(s.product.scope)&&Array.isArray(s.product.verification),"Invalid product baseline");
    const runIds=new Set();
    for(const run of s.product.verification){
      need(Number.isSafeInteger(run.run_id)&&run.run_id>0&&!runIds.has(run.run_id)&&run.sha===s.product.sha&&["SUCCESS","FAILURE","CANCELLED","SKIPPED"].includes(run.status)&&text(run.scope),"Invalid/duplicate baseline run or mismatched source");
      runIds.add(run.run_id);
    }
    need(/^P[0-8]$/.test(s.phase.active)&&typeof s.phase.next_phase_authorized==="boolean"&&typeof s.phase.installer_frozen==="boolean"&&typeof s.phase.release_certified==="boolean","Invalid phase state");
    const p=s.phase.source_progress;
    need(["A","B","C","D","total"].every(k=>pair(p[k])),"Invalid source progress");
    need(p.total[0]===p.A[0]+p.B[0]+p.C[0]+p.D[0]&&p.total[1]===p.A[1]+p.B[1]+p.C[1]+p.D[1],"Source progress total mismatch");
    need(pair(s.phase.c5_checklist),"Invalid C5 checklist");
    const proj=s.phase.official_score_projection;
    need(pair([proj.earned,proj.total])&&Array.isArray(proj.open)&&object(proj.owner),"Invalid official projection");
    const match=scoreText.match(/^## P4 engineering scorecard\s*$([\s\S]*?)(?=^## |\s*$)/m);
    // Section extraction uses line slicing rather than the permissive regex end.
    const lines=scoreText.split(/\r?\n/);
    const start=lines.findIndex(x=>x==="## P4 engineering scorecard");
    const end=lines.findIndex((x,i)=>i>start&&/^## /.test(x));
    const rows=lines.slice(start+1,end<0?lines.length:end).map(l=>l.split("|").map(x=>x.trim())).filter(c=>c.length>=6&&/^(Core \d+|R\d+\.\d+)$/.test(c[1])&&/^(0|5)$/.test(c[c.length-2]));
    need(start>=0&&rows.length===proj.total&&new Set(rows.map(c=>c[1])).size===rows.length,"Official scorecard rows missing or duplicate");
    need(rows.filter(c=>c[c.length-2]==="5").length===proj.earned,"Official score projection disagrees with scorecard");
    const open=rows.filter(c=>c[c.length-2]==="0").map(c=>c[1]).sort();
    need(JSON.stringify(open)===JSON.stringify([...proj.open].sort()),"Open official checks disagree with scorecard");
    need(taskStates.includes(s.task.status)&&text(s.task.id)&&text(s.task.scope)&&text(s.task.next_action)&&Array.isArray(s.task.read)&&s.task.read.length>0,"Invalid active task");
    if(s.task.status==="BLOCKED")need(text(s.task.blocker)&&["OWNER_DECISION","MISSING_EVIDENCE","MISSING_ACCESS","RECONCILE"].includes(s.task.next_action_kind),"Blocked task must name a decision/evidence/access/reconciliation");
    const ids=new Set();
    for(const op of [s.operation,...s.pending_operations]){
      need(text(op.id)&&!ids.has(op.id)&&opStates.includes(op.state)&&sha(op.starting_sha)&&typeof op.reconcile_before_retry==="boolean","Invalid or duplicate operation");
      ids.add(op.id);
      if(uncertain(op.state))need(op.reconcile_before_retry===true,"Uncertain operation must reconcile before retry");
      if(["PREPARED","ISSUED","UNKNOWN"].includes(op.state)){
        need(text(op.scope)&&text(op.recovery)&&text(op.expected_evidence)&&Array.isArray(op.intended_paths)&&op.intended_paths.length>0&&object(op.authority_ref),"In-flight operation missing write-ahead fields");
      }
      if(op.state==="RECONCILED")need(text(op.outcome)&&object(op.receipt),"Reconciled operation missing outcome/receipt");
    }
    need(Array.isArray(s.pending_runs),"Pending runs not an array");
    for(const run of s.pending_runs){need(Number.isSafeInteger(run.run_id)&&run.run_id>0&&!runIds.has(run.run_id)&&sha(run.sha)&&["QUEUED","IN_PROGRESS","UNKNOWN"].includes(run.status)&&text(run.scope),"Invalid/duplicate pending run");runIds.add(run.run_id)}
    need(Number.isSafeInteger(s.authority.consumed_disarmed_count)&&s.authority.consumed_disarmed_count>=0&&Array.isArray(s.authority.restricted_active)&&Array.isArray(s.authority.forbidden)&&s.authority.forbidden.length>0,"Invalid permission record");
    const approvalIds=new Set();
    for(const a of s.authority.restricted_active){need(text(a.id)&&!approvalIds.has(a.id)&&["APPROVED","ISSUED","UNKNOWN"].includes(a.state)&&sha(a.source_sha)&&text(a.scope)&&object(a.owner_authority_ref)&&typeof a.reconcile_before_retry==="boolean","Invalid/consumed/duplicate active approval");approvalIds.add(a.id);if(uncertain(a.state))need(a.reconcile_before_retry===true,"Uncertain approval must reconcile before retry")}
    need(text(s.unpublished.owner_local)&&Array.isArray(s.unpublished.detached)&&s.unpublished.detached.every(x=>sha(x.sha)&&text(x.scope)),"Invalid unpublished-work record");
    need(sha(s.context.archive.commit)&&Array.isArray(s.context.archive.paths)&&s.context.archive.paths.length>0,"Missing historical snapshot");
    const safePath=p=>text(p)&&p.length<=512&&!p.startsWith("/")&&!p.includes("\\")&&!p.includes(":")&&!p.split("/").some(x=>x===".."||x==="."||!x);
    function walk(x){
      if(Array.isArray(x)){x.forEach(walk);return}
      if(!object(x))return;
      if("path" in x){need(safePath(x.path),"Unsafe reference path");if(safePath(x.path))need(hasPath(x.path),"Missing reference: "+x.path);if("anchor" in x)need(text(x.anchor),"Empty reference anchor")}
      Object.values(x).forEach(walk);
    }
    walk(s);
    for(const path of s.context.archive.paths)need(safePath(path)&&hasPath(path),"Missing compatibility path: "+path);
  }catch(e){errors.push("Malformed state structure: "+String(e.message))}
  return errors;
}

function recoveryDecision(o){
  if(!o.gitAvailable)return "STOP_UNVERIFIED";
  if(o.concurrentHead)return "INSPECT_CONFLICT";
  if(o.restrictedUncertain)return "PROTECT_AND_RECONCILE";
  if(o.matchingCommit)return "RECONCILE_EXISTING";
  if(o.operation==="UNKNOWN"||o.operation==="ISSUED")return "INSPECT_BEFORE_RETRY";
  if(o.pendingRun)return "RECONCILE_PENDING";
  if(o.failedRun)return "RECORD_FAILURE";
  if(o.localUnknown)return "PRESERVE_LOCAL_UNKNOWN";
  if(o.requiresApproval&&!o.approved)return "AWAIT_APPROVAL";
  if(o.sourcePass&&!o.nativeAcceptanceRequiredComplete)return "KEEP_SCOPE_OPEN";
  if(o.task==="CLOSED")return "SELECT_NEXT";
  if(o.operation==="PREPARED"&&o.expectedParentMatches)return "RESUME_PREPARED";
  return "MANUAL_REVIEW";
}

function selfTests(s,scoreText,hasPath){
  const results=[];
  const clone=x=>JSON.parse(JSON.stringify(x));
  const check=(label,ok)=>results.push({label,pass:!!ok});
  check("migrated state validates",validateState(s,scoreText,hasPath).length===0);
  const mutations=[
    ["unsupported schema",x=>x.schema_version=999],
    ["incorrect branch",x=>x.repository.branch="main"],
    ["malformed SHA",x=>x.product.sha="fake"],
    ["CI wrong source",x=>x.product.verification[0].sha="0".repeat(40)],
    ["duplicate CI run",x=>x.product.verification.push(x.product.verification[0])],
    ["inflated source total",x=>x.phase.source_progress.total[0]++],
    ["inflated official projection",x=>x.phase.official_score_projection.earned++],
    ["omitted open check",x=>x.phase.official_score_projection.open.pop()],
    ["blocked task without blocker",x=>{x.task.status="BLOCKED";x.task.blocker=""}],
    ["unknown operation without reconciliation",x=>{x.operation.state="UNKNOWN";x.operation.reconcile_before_retry=false}],
    ["consumed approval active",x=>x.authority.restricted_active.push({id:"consumed",state:"CONSUMED"})],
    ["missing reference",x=>x.task.read.push({path:"docs/nonexistent-continued-test.md"})],
    ["unsafe reference",x=>x.task.read.push({path:"../private"})],
    ["missing detached SHA",x=>x.unpublished.detached.push({sha:"wrong",scope:"unknown"})],
    ["missing archive",x=>x.context.archive.commit=""],
    ["terminal CI listed pending",x=>x.pending_runs.push({run_id:123,sha:x.product.sha,status:"SUCCESS",scope:"fixture"})]
  ];
  for(const [label,mutate] of mutations){const v=clone(s);mutate(v);check(label,validateState(v,scoreText,hasPath).length>0)}
  const scenarios=[
    [{operation:"PREPARED",expectedParentMatches:true},"RESUME_PREPARED"],
    [{matchingCommit:true,operation:"ISSUED"},"RECONCILE_EXISTING"],
    [{operation:"UNKNOWN"},"INSPECT_BEFORE_RETRY"],
    [{pendingRun:true},"RECONCILE_PENDING"],
    [{failedRun:true},"RECORD_FAILURE"],
    [{requiresApproval:true,approved:false},"AWAIT_APPROVAL"],
    [{restrictedUncertain:true,matchingCommit:true},"PROTECT_AND_RECONCILE"],
    [{concurrentHead:true,operation:"PREPARED"},"INSPECT_CONFLICT"],
    [{localUnknown:true},"PRESERVE_LOCAL_UNKNOWN"],
    [{task:"CLOSED"},"SELECT_NEXT"],
    [{sourcePass:true,nativeAcceptanceRequiredComplete:false},"KEEP_SCOPE_OPEN"],
    [{gitAvailable:false},"STOP_UNVERIFIED"]
  ];
  for(const [o,expected] of scenarios)check(expected,recoveryDecision({gitAvailable:true,...o})===expected);
  return results;
}

export {validateState, recoveryDecision, selfTests};

function main(){
  const root=realpathSync(resolve(dirname(fileURLToPath(import.meta.url)),"../.."));
  const local=p=>{const f=realpathSync(resolve(root,p));const rel=relative(root,f);if(rel===".."||rel.startsWith("../")||rel.startsWith("..\\")||isAbsolute(rel)||!statSync(f).isFile())throw Error("outside repository or not a regular file");return f};
  const read=(p,cap)=>{const f=local(p);if(statSync(f).size>cap)throw Error("file bound exceeded");return readFileSync(f,"utf8")};
  const exists=p=>{try{local(p);return true}catch{return false}};
  const args=process.argv.slice(2);if(args.length>1||args.length===1&&args[0]!=="--self-test")throw Error("usage: node docs/continuation/validate_state.mjs [--self-test]");
  const s=JSON.parse(read("CONTINUATION_STATE.json",262144));
  const score=read("docs/PROJECT_STATUS_CURRENT.md",2097152);
  const errors=validateState(s,score,exists);
  if(errors.length){console.error(errors.join("\n"));process.exitCode=1;return}
  console.log("STATE_STRUCTURE_OK (not live Git/CI, approval or acceptance proof)");
  if(args[0]==="--self-test"){const results=selfTests(s,score,exists);for(const r of results)console.log((r.pass?"PASS ":"FAIL ")+r.label);console.log(results.filter(r=>r.pass).length+"/"+results.length+" pure checks");if(results.some(r=>!r.pass))process.exitCode=1}
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){try{main()}catch(e){console.error("CONTINUATION_VALIDATION_FAILED: "+e.message);process.exitCode=1}}
