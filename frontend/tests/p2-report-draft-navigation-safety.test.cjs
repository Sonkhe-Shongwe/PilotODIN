const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const vm=require('node:vm');

const root=path.resolve(__dirname,'../src');
const code=fs.readFileSync(path.join(root,'reportDraftNavigationGuard.ts'),'utf8');
const out=ts.transpileModule(code,{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021},
 reportDiagnostics:true,fileName:'reportDraftNavigationGuard.ts'
});
assert.equal(out.diagnostics?.length,0);
const mod={exports:{}};
vm.runInNewContext(out.outputText,{module:mod,exports:mod.exports},{filename:'reportDraftNavigationGuard.js'});
const {hasUnsavedReportDraft}=mod.exports;
const ui=fs.readFileSync(path.join(root,'ReportWorkspace.tsx'),'utf8');
const css=fs.readFileSync(path.join(root,'report-workspace.css'),'utf8');
const baseline={
 title:'Investigation report',narrative:'',selected:[],defaultTitle:'Investigation report',saved:null
};
const frozen={title:'Original title',narrative:'Verified interpretation',
 evidence:[{id:'a'.repeat(32)},{id:'b'.repeat(32)}]};

test('BEHAVIOR: initial auto-title alone is not unsaved work',()=>{
 assert.equal(hasUnsavedReportDraft(baseline),false);
 assert.equal(hasUnsavedReportDraft({...baseline,title:'  Investigation report'}),true);
});
test('BEHAVIOR: a new unsaved narrative, blank spacing, title or evidence choice demands consent',()=>{
 for(const state of [
  {...baseline,narrative:'Draft analyst findings'},
  {...baseline,narrative:'\n'},
  {...baseline,selected:['a'.repeat(32)]},
  {...baseline,title:'Draft title'},
 ])assert.equal(hasUnsavedReportDraft(state),true);
});
test('BEHAVIOR: unchanged saved revision does not prompt even if title is different from default',()=>{
 assert.equal(hasUnsavedReportDraft({...baseline,...frozen,selected:frozen.evidence.map(x=>x.id),saved:frozen}),false);
});
test('BEHAVIOR: changed saved title, narrative, evidence order or membership requires consent',()=>{
 const clean={...baseline,title:frozen.title,narrative:frozen.narrative,
  selected:frozen.evidence.map(x=>x.id),saved:frozen};
 assert.equal(hasUnsavedReportDraft(clean),false);
 for(const state of [
  {...clean,title:clean.title+' changed'},
  {...clean,narrative:clean.narrative+' changed'},
  {...clean,selected:[...clean.selected].reverse()},
  {...clean,selected:clean.selected.slice(0,1)},
  {...clean,selected:[...clean.selected,'c'.repeat(32)]},
 ])assert.equal(hasUnsavedReportDraft(state),true);
 assert.equal(hasUnsavedReportDraft({...clean,narrative:clean.narrative+'X'}),true);
 assert.equal(hasUnsavedReportDraft({...clean,narrative:clean.narrative}),false);
});
test('INTEGRATION: both New and saved-report/revision navigation use same explicit discard gate',()=>{
 assert.match(ui,/function requestNewReport\(\)/);
 assert.match(ui,/function requestOpenReport\(id:string,number\?:number\)/);
 assert.match(ui,/if\(hasUnsavedWork\)\{[\s\S]*setPendingDiscard\(\{kind:'new',projectId\}\)/);
 assert.match(ui,/setPendingDiscard\(\{kind:'open',projectId,id,number\}\)/);
 assert.match(ui,/onClick=\{requestNewReport\}/);
 assert.match(ui,/onClick=\{\(\)=>requestOpenReport\(item\.id\)\}/);
 assert.match(ui,/onChange=\{e=>requestOpenReport\(opened\.id,Number\(e\.target\.value\)\)\}/);
 assert.match(ui,/const hasUnsavedWork=hasUnsavedReportDraft\(/);
});
test('INTEGRATION: keep preserves state; approve invokes existing navigation and vetoes stale project approvals',()=>{
 assert.match(ui,/function approveReportDiscard\(\)/);
 assert.match(ui,/if\(!action\|\|action\.projectId!==activeProjectRef\.current\)return/);
 assert.match(ui,/if\(action\.kind==='new'\)newReport\(\)/);
 assert.match(ui,/else void openReport\(action\.id,action\.number\)/);
 assert.match(ui,/onClick=\{\(\)=>setPendingDiscard\(null\)\}/);
 assert.match(ui,/Discard unsaved report edits\?/);
 assert.match(ui,/Nothing will be saved automatically/);
 assert.match(ui,/setPendingDiscard\(null\);\s*if\(!projectId\)return/);
 assert.match(ui,/disabled=\{busy==='save'\|\|busy==='quality'\|\|busy==='export'\}/);
});
test('INTEGRATION: modal has focus, tab containment, Escape cancellation and a visible close choice',()=>{
 assert.match(ui,/role="dialog" aria-modal="true" aria-labelledby="pd-report-discard-title"/);
 assert.match(ui,/ref=\{discardDialogRef\}/);
 assert.match(ui,/keep\?\.focus\(\)/);
 assert.match(ui,/if\(event\.key==='Escape'\)/);
 assert.match(ui,/if\(event\.key!=='Tab'\)return/);
 assert.match(ui,/document\.addEventListener\('keydown',onKeyDown,true\)/);
 assert.match(ui,/document\.removeEventListener\('keydown',onKeyDown,true\)/);
 assert.match(ui,/if\(opener\?\.isConnected&&!opener\.matches\(':disabled'\)\)opener\.focus\(\)/);
 assert.match(css,/\.pd-report-discard-backdrop\{/);
 assert.match(css,/\.pd-report-discard-dialog\{/);
});
