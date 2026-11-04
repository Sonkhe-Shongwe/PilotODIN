const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const quality=fs.readFileSync(path.resolve(__dirname,'../src/QualityWorkspace.tsx'),'utf8');
function extract(startText,endText,exported){
  const start=quality.indexOf(startText),end=quality.indexOf(endText,start);
  assert.ok(start>=0&&end>start,'Production Quality handler must be extractable: '+startText);
  const compiled=ts.transpileModule(quality.slice(start,end)+'\nexports.fn='+exported+';',{
    compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true
  });
  assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
  return compiled.outputText;
}
const investigateJs=extract('  async function investigateFinding(selectedIssue:QualityIssue){',
 '\n  function showAffectedRecords(){','investigateFinding');
const missingnessJs=extract('  async function diagnoseMissing(column:string){',
 '\n  async function approveMedian()','diagnoseMissing');

function harness(){
 const investigationRequest={current:0},missingnessRequest={current:0};
 const requests=[];
 let selected='issue-a',version=0,investigation=null,investigating=false,
     diagnostics=null,diagnosing=false,error='';
 function bind(js){
  const scope={
   investigationRequest,missingnessRequest,projectId:'synthetic',
   quality:{version},get:url=>new Promise((resolve,reject)=>requests.push({url,resolve,reject})),
   setInvestigating:v=>{investigating=v},
   setInvestigation:v=>{investigation=v},
   setDiagnosing:v=>{diagnosing=v},
   setDiagnostics:v=>{diagnostics=v},setError:v=>{error=v}
  };
  const keys=Object.keys(scope),exports={};
  return new Function(...keys,'exports',js+'\nreturn exports.fn;')(...Object.values(scope),exports);
 }
 return {
  investigate:(issue={id:selected,column:'Amount'})=>bind(investigateJs)(issue),
  diagnose:(column='Amount')=>bind(missingnessJs)(column),
  changeContext:(issueId,nextVersion=version)=>{
   selected=issueId;version=nextVersion;
   // Same ref increments and state resets as the actual useEffect below.
   investigationRequest.current+=1;missingnessRequest.current+=1;
   investigation=null;investigating=false;diagnostics=null;diagnosing=false;
  },
  requests, state:()=>({investigation,investigating,diagnostics,diagnosing,error}),
  refs:()=>({investigation:investigationRequest.current,missingness:missingnessRequest.current})
 };
}
test('current finding investigation accepts matching project/issue/version GET only',async()=>{
 const h=harness(),pending=h.investigate();
 assert.equal(h.state().investigating,true);
 assert.match(h.requests[0].url,/investigate\?issue_id=issue-a&expected_version=0$/);
 const result={project_id:'synthetic',issue_id:'issue-a',version:0,kind:'outliers'};
 h.requests[0].resolve(result);await pending;
 assert.equal(h.state().investigation,result);
 assert.equal(h.state().investigating,false);
 assert.equal(h.state().error,'');
});
test('older investigation success never replaces a newer issue investigation or unlocks spinner',async()=>{
 const h=harness(),old=h.investigate();
 const fresh=h.investigate();
 h.requests[0].resolve({project_id:'synthetic',issue_id:'issue-a',version:0,marker:'old'});
 await old;
 assert.equal(h.state().investigating,true);
 assert.equal(h.state().investigation,null);
 const expected={project_id:'synthetic',issue_id:'issue-a',version:0,marker:'fresh'};
 h.requests[1].resolve(expected);await fresh;
 assert.equal(h.state().investigation,expected);
 assert.equal(h.state().investigating,false);
});
test('changed finding context invalidates an in-flight investigation and its stale error',async()=>{
 const h=harness(),pending=h.investigate();
 h.changeContext('issue-b',1);
 h.requests[0].reject(new Error('disconnected old finding'));
 await pending;
 assert.equal(h.state().investigation,null);
 assert.equal(h.state().error,'');
 assert.equal(h.state().investigating,false);
});
test('wrong finding or project in a current investigation response is refused',async()=>{
 const h=harness(),pending=h.investigate();
 h.requests[0].resolve({project_id:'other',issue_id:'issue-a',version:0});
 await pending;
 assert.equal(h.state().investigation,null);
 assert.match(h.state().error,/did not match/);
});
test('missingness diagnosis accepts only a current matching-column GET',async()=>{
 const h=harness(),pending=h.diagnose('Amount');
 assert.equal(h.state().diagnosing,true);
 assert.match(h.requests[0].url,/missingness\?column=Amount$/);
 const report={column:'Amount',missing_rows:3};
 h.requests[0].resolve(report);await pending;
 assert.equal(h.state().diagnostics,report);
 assert.equal(h.state().diagnosing,false);
});
test('older missingness success cannot replace a new column or dismiss its spinner',async()=>{
 const h=harness(),old=h.diagnose('Amount');
 h.changeContext('issue-b');
 const fresh=h.diagnose('Outcome');
 h.requests[0].resolve({column:'Amount',missing_rows:5});await old;
 assert.equal(h.state().diagnostics,null);
 assert.equal(h.state().diagnosing,true);
 const report={column:'Outcome',missing_rows:1};
 h.requests[1].resolve(report);await fresh;
 assert.equal(h.state().diagnostics,report);
 assert.equal(h.state().diagnosing,false);
});
test('stale missingness error is suppressed after finding changes, mismatch is refused',async()=>{
 const h=harness(),old=h.diagnose();
 h.changeContext('issue-b',1);
 h.requests[0].reject(new Error('previous column failed'));await old;
 assert.equal(h.state().error,'');
 const pending=h.diagnose('Outcome');
 h.requests[1].resolve({column:'Amount',missing_rows:6});await pending;
 assert.equal(h.state().diagnostics,null);
 assert.match(h.state().error,/did not match/);
});
test('actual Quality context effect invalidates both request families and clears stale results',()=>{
 const start=quality.indexOf('  useEffect(()=>{\n    // A different finding or working Quality version');
 const end=quality.indexOf('\n  const issue=',start);
 assert.ok(start>=0&&end>start);
 const body=quality.slice(start,end);
 for(const token of [
  'investigationRequest.current+=1',
  'missingnessRequest.current+=1',
  'setInvestigation(null);setInvestigating(false)',
  'setDiagnostics(null);setDiagnosing(false)',
  '[projectId,selected,quality?.version]'
 ])assert.ok(body.includes(token),'Missing context invalidation: '+token);
 assert.doesNotMatch(body,/post\(|commitProposal\(|mutate\(|localStorage/);
});
