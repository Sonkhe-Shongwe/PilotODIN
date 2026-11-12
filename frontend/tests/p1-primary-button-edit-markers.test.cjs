const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const start=app.indexOf('  function toggleModelChoice(key:string){');
const end=app.indexOf('  async function startTrain(){',start);
assert.ok(start>0&&end>start,'real App button handlers must exist');
const source=app.slice(start,end);
const compiled=ts.transpileModule(source+'\nexports.methods={toggleModelChoice,applyHighRiskExclusionSuggestions};',{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true,
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
function harness({models=['logistic_regression'],excluded=[],embedded=false,
 highRisk=['risk_id'],hints=[{column:'amount',risk:'high'}],
 available=['risk_id','amount'],prepPresent=true,reviewOpen=true}={}){
 const events=[];
 let selected=[...models],out=[...excluded];
 const exports={};
 const fn=new Function('models','excluded','embedded','prep','featureHints',
   'onPrimaryDraftEdited','setModels','setExcluded','reviewHighRiskExclusions',
   'setReviewHighRiskExclusions','exports',
   compiled.outputText+'\nreturn exports.methods;')(
     selected,out,embedded,prepPresent?{high_risk_features:highRisk,available_features:available}:null,
     hints,view=>events.push(view),next=>{selected=next},
     next=>{out=typeof next==='function'?next(out):next},reviewOpen,
     ()=>{},exports);
 return {...fn,events,getModels:()=>selected,getExcluded:()=>out,
   simulateQueuedCheckboxSelection:column=>{out=[...out,column]}};
}

const hintScopeSource=fs.readFileSync(path.resolve(__dirname,'../src/featureHintScope.ts'),'utf8');
const hintScopeCompiled=ts.transpileModule(hintScopeSource,{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true,
});
assert.equal((hintScopeCompiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const hintScopeExports={};
new Function('exports','module',hintScopeCompiled.outputText)(
 hintScopeExports,{exports:hintScopeExports});
const {visibleFeatureHints}=hintScopeExports;

test('Prepare feature hints match project, target and Quality version before they can affect exclusions',()=>{
 const advice=[{column:'risk_id',risk:'high',reasons:['possible leakage']}];
 const snapshot={projectId:'project-A',target:'churn',version:4,features:advice};
 assert.deepEqual(visibleFeatureHints(snapshot,'project-A','churn',4),advice);
 assert.deepEqual(visibleFeatureHints(snapshot,'project-B','churn',4),[]);
 assert.deepEqual(visibleFeatureHints(snapshot,'project-A','fraud',4),[]);
 assert.deepEqual(visibleFeatureHints(snapshot,'project-A','churn',5),[]);
 assert.deepEqual(visibleFeatureHints(snapshot,'project-A','',4),[]);
 assert.deepEqual(visibleFeatureHints(snapshot,undefined,'churn',4),[]);
 assert.deepEqual(visibleFeatureHints(null,'project-A','churn',4),[]);
 // A late old request must still be ignored after switching back to a
 // different Quality version, even if its field names happen to be identical.
 const lateOld={...snapshot,version:3};
 assert.deepEqual(visibleFeatureHints(lateOld,'project-A','churn',4),[]);
 assert.equal(snapshot.features[0].column,'risk_id');
});

test('Model button can add and remove choices while reporting each real edit',()=>{
 const add=harness();add.toggleModelChoice('random_forest');
 assert.deepEqual(add.getModels(),['logistic_regression','random_forest']);
 assert.deepEqual(add.events,['model']);
 const remove=harness();remove.toggleModelChoice('logistic_regression');
 assert.deepEqual(remove.getModels(),[]);
 assert.deepEqual(remove.events,['model']);
});
test('at the five-model cap, refused sixth selection is not an unsaved edit',()=>{
 const initial=['a','b','c','d','e'];
 const h=harness({models:initial});h.toggleModelChoice('f');
 assert.deepEqual(h.getModels(),initial);
 assert.deepEqual(h.events,[]);
});
test('Prepare suggestions report only a newly excluded feature, not a no-op',()=>{
 const changed=harness({excluded:['risk_id']});changed.applyHighRiskExclusionSuggestions();
 assert.deepEqual(changed.getExcluded(),['risk_id','amount']);
 assert.deepEqual(changed.events,['prepare']);
 const already=harness({excluded:['risk_id','amount']});already.applyHighRiskExclusionSuggestions();
 assert.deepEqual(already.getExcluded(),['risk_id','amount']);
 assert.deepEqual(already.events,[]);
 const notReady=harness({prepPresent:false});notReady.applyHighRiskExclusionSuggestions();
 assert.deepEqual(notReady.events,[]);
});
test('reviewed exclusions cannot be applied without explicit preview approval',()=>{
 const h=harness({reviewOpen:false});
 h.applyHighRiskExclusionSuggestions();
 assert.deepEqual(h.getExcluded(),[]);
 assert.deepEqual(h.events,[]);
});

test('suggestions preserve a newer checkbox choice absent from the handler closure',()=>{
 const h=harness({excluded:['prior_manual']});
 h.simulateQueuedCheckboxSelection('later_manual');
 h.applyHighRiskExclusionSuggestions();
 assert.deepEqual(h.getExcluded(),['prior_manual','later_manual','risk_id','amount']);
 assert.deepEqual(h.events,['prepare']);
});
test('docked button edits never masquerade as primary Studio edits',()=>{
 const h=harness({embedded:true});h.toggleModelChoice('random_forest');
 h.applyHighRiskExclusionSuggestions();
 assert.deepEqual(h.events,[]);
 assert.deepEqual(h.getModels(),['logistic_regression','random_forest']);
 assert.deepEqual(h.getExcluded(),['risk_id','amount']);
});
test('real buttons are wired through the guarded handlers and never persist draft fields',()=>{
 assert.match(app,/className=\{cls\('model-choice',models\.includes\(key\)&&'chosen'\)\} onClick=\{\(\)=>toggleModelChoice\(key\)\}/);
 assert.match(app,/Review high-risk exclusion suggestions<\/button>/);
 assert.match(app,/onClick=\{\(\)=>setReviewHighRiskExclusions\(open=>!open\)\}/);
 assert.match(app,/Apply reviewed exclusions<\/button>/);
 assert.match(app,/Cancel exclusion review<\/button>/);
 assert.match(app,/onClick=\{applyHighRiskExclusionSuggestions\}/);
 assert.match(source,/if\(!embedded\)onPrimaryDraftEdited\?\.\('model'\)/);
 assert.match(source,/if\(!embedded\)onPrimaryDraftEdited\?\.\('prepare'\)/);
 assert.doesNotMatch(source,/localStorage|sessionStorage|fetch\(|post\(|upload\(|train\(/);
});
