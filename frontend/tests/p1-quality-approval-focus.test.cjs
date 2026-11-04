const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const Module=require('node:module');
const sourcePath=path.resolve(__dirname,'../src/qualityApprovalFocus.ts');
const compiled=ts.transpileModule(fs.readFileSync(sourcePath,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const m=new Module(sourcePath,module);m.filename=sourcePath;m.paths=module.paths;m._compile(compiled.outputText,sourcePath);
const {handleQualityApprovalKeyDown}=m.exports;
function fixture(count=3){
  let focused='opener',cancelled=0;
  const controls=Array.from({length:count},(_,i)=>({
    tabIndex:0,closest:()=>null,focus:()=>{focused=i}
  }));
  const dialog={querySelectorAll:()=>controls,contains:el=>el===dialog||controls.includes(el),focus:()=>{focused='dialog'}};
  const keyboard=(key,shiftKey=false,active=controls[0],busy=false)=>{
    const event={key,shiftKey,prevented:false,stopped:false,preventDefault(){this.prevented=true},stopPropagation(){this.stopped=true}};
    handleQualityApprovalKeyDown(event,dialog,active,busy,()=>{cancelled++});return event;
  };
  return {keyboard,dialog,controls,state:()=>({focused,cancelled})};
}
test('Tab from last control wraps to first without reaching background',()=>{
  const f=fixture();const e=f.keyboard('Tab',false,f.controls[2]);
  assert.equal(e.prevented,true);assert.equal(f.state().focused,0);assert.equal(f.state().cancelled,0);
});
test('Shift+Tab from first control wraps to last',()=>{
  const f=fixture();const e=f.keyboard('Tab',true,f.controls[0]);
  assert.equal(e.prevented,true);assert.equal(f.state().focused,2);
});
test('Tab within modal leaves normal interior navigation to browser',()=>{
  const f=fixture();const e=f.keyboard('Tab',false,f.controls[0]);
  assert.equal(e.prevented,false);assert.equal(f.state().focused,'opener');
});
test('a lost or outside focus is recovered back inside consent dialog',()=>{
  const f=fixture();const external={};
  assert.equal(f.keyboard('Tab',false,external).prevented,true);assert.equal(f.state().focused,0);
  assert.equal(f.keyboard('Tab',true,external).prevented,true);assert.equal(f.state().focused,2);
});
test('when all controls are disabled, Tab cannot leave the modal',()=>{
  const f=fixture(0);const e=f.keyboard('Tab',false,null,true);
  assert.equal(e.prevented,true);assert.equal(f.state().focused,'dialog');
});
test('Escape cancels review without approving or modifying data',()=>{
  const f=fixture();const e=f.keyboard('Escape');
  assert.equal(e.prevented,true);assert.equal(e.stopped,true);assert.equal(f.state().cancelled,1);
});
test('Escape during an in-flight commit is consumed but never dismisses the review',()=>{
  const f=fixture();const e=f.keyboard('Escape',false,f.controls[0],true);
  assert.equal(e.prevented,true);assert.equal(e.stopped,true);assert.equal(f.state().cancelled,0);
});
test('unrelated keyboard events do not alter focus or consent',()=>{
  const f=fixture();const e=f.keyboard('Enter');
  assert.equal(e.prevented,false);assert.equal(e.stopped,false);assert.deepEqual(f.state(),{focused:'opener',cancelled:0});
});
test('production dialog installs capture, initial focus, and cleanup bound to review ID',()=>{
  const s=fs.readFileSync(path.resolve(__dirname,'../src/QualityWorkspace.tsx'),'utf8');
  assert.match(s,/import \{handleQualityApprovalKeyDown\} from '\.\/qualityApprovalFocus'/);
  assert.match(s,/approvalDialogRef=useRef<HTMLElement\|null>\(null\)/);
  assert.match(s,/const approvalId=pendingApproval\?\.proposal\.proposal_id/);
  assert.match(s,/document\.addEventListener\('keydown',onApprovalKeyDown,true\)/);
  assert.match(s,/document\.removeEventListener\('keydown',onApprovalKeyDown,true\)/);
  assert.match(s,/if\(opener\?\.isConnected&&!opener\.matches\(':disabled'\)\)opener\.focus\(\)/);
  assert.match(s,/ref=\{approvalDialogRef\} tabIndex=\{-1\} role="dialog" aria-modal="true"/);
  assert.match(s,/aria-label="Cancel approval"/);
  assert.match(s,/disabled=\{busy\} onClick=\{\(\)=>void commitProposal\(\)\}/);
});
