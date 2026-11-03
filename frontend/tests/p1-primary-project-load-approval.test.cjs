const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
const begin=app.indexOf('  async function loadProject(pid:string,approvedBeforeUpload=false):Promise<boolean>{');
const end=app.indexOf('\n  useEffect(()=>{if(!project||!target)',begin);
assert.ok(begin>=0&&end>begin,'The actual loadProject body must be present');
const body=app.slice(begin,end);
const compiled=ts.transpileModule(body+'\nexport {loadProject};',{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);

const guardPath=path.resolve(__dirname,'../src/projectSelectionCommitGuard.ts');
const guardJs=ts.transpileModule(fs.readFileSync(guardPath,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}});
const guardMod=new Module(guardPath,module);
guardMod.filename=guardPath;guardMod.paths=module.paths;
guardMod._compile(guardJs.outputText,guardPath);
const {mayCommitProjectSelection}=guardMod.exports;

function harness({approved=false,embedded=false,pid='B',current='A',shellCallback=true,
 fail=false,preapproved=false,selectedWhenStarted='A',selectedAfterFetch=null}={}){
 const operations={approved:[],generation:[],mutations:[],reads:[],storage:[],notice:[],uploadCommits:[]};
 const currentProject={id:current};
 let sharedSelection=selectedWhenStarted;
 const setters=['setProject','setPrep','setExperiment','setPrediction','setTarget',
  'setQualityFocus','setDeliverEvidenceId','setQualityVersion','setFeatureHints',
  'setExcluded','setPredictVals','setConfirmSplit','setPage','setVisitedStages',
  'setUploadOpen','setError'];
 const ctx={
  embedded,embeddedProjectId:current,project:currentProject,
  onBeforePrimaryProjectLoad:shellCallback?(id=>{operations.approved.push(id);return approved}):undefined,
  onPrimaryUploadedProjectCommitted:()=>operations.uploadCommits.push(pid),
  onPrimaryProjectLoaded:id=>operations.uploadCommits.push('loaded:'+id),
  onPrimaryProjectLoadFailed:id=>operations.notice.push('failed:'+id),
  setNotice:value=>operations.notice.push(value),
  latestProjectRequest:{current:0},
  projectOperations:{current:{begin:id=>{operations.generation.push(id);return 1},
   accepts:(id,generation)=>id===pid&&generation===1}},
  get:async url=>{
   operations.reads.push(url);
   if(fail)throw Error('backend unavailable');
   if(url.endsWith('/live-profile')){
    if(selectedAfterFetch!==null)sharedSelection=selectedAfterFetch;
    return {version:0};
   }
   return {id:pid,filename:'existing.csv'};
  },
  localStorage:{
   getItem:name=>{assert.equal(name,'pilotodin-current');return sharedSelection},
   setItem:(name,value)=>{sharedSelection=value;operations.storage.push([name,value])},
  },
  mayCommitProjectSelection,
  embeddedStage:embedded?'prepare':undefined,
  requestedStudioStage:()=> 'quality',
  scrollRef:{current:{}}
 };
 for(const name of setters)ctx[name]=value=>{operations.mutations.push(name)};
 const names=Object.keys(ctx);
 const exports={};
 const fn=new Function(...names,'exports',compiled.outputText+'\nreturn exports.loadProject;')(
  ...Object.values(ctx),exports);
 return {load:()=>fn(pid,preapproved),operations,ctx,getShared:()=>sharedSelection};
}

test('denied direct Studio project switch does not clear state or start any request',async()=>{
 const h=harness();
 assert.equal(await h.load(),false);
 assert.deepEqual(h.operations.approved,['B']);
 assert.deepEqual(h.operations.generation,[]);
 assert.deepEqual(h.operations.mutations,[]);
 assert.deepEqual(h.operations.reads,[]);
 assert.deepEqual(h.operations.storage,[]);
 assert.equal(h.ctx.latestProjectRequest.current,0);
});
test('approved direct Studio switch proceeds through existing project loading',async()=>{
 const h=harness({approved:true});
 assert.equal(await h.load(),true);
 assert.deepEqual(h.operations.approved,['B']);
 assert.deepEqual(h.operations.generation,['B']);
 assert.equal(h.operations.reads.length,2);
 assert.deepEqual(h.operations.storage,[['pilotodin-current','B']]);
 assert.ok(h.operations.mutations.includes('setProject'));
});
test('opening the current project does not request a destructive project transition',async()=>{
 const h=harness({current:'A',pid:'A'});
 assert.equal(await h.load(),true);
 assert.deepEqual(h.operations.approved,[]);
});
test('embedded Studio refuses another project before it changes local data',async()=>{
 const h=harness({embedded:true,pid:'B',current:'A'});
 assert.equal(await h.load(),false);
 assert.deepEqual(h.operations.approved,[]);
 assert.deepEqual(h.operations.mutations,[]);
 assert.deepEqual(h.operations.notice,['Change projects using the global project selector.']);
});
test('embedded same-project loading never calls primary project approval',async()=>{
 const h=harness({embedded:true,pid:'A'});
 assert.equal(await h.load(),true);
 assert.deepEqual(h.operations.approved,[]);
 assert.deepEqual(h.operations.storage,[]);
});
test('standalone primary Studio without a shell callback retains previous load path',async()=>{
 const h=harness({shellCallback:false});
 assert.equal(await h.load(),true);
 assert.deepEqual(h.operations.approved,[]);
 assert.equal(h.operations.reads.length,2);
});
test('an authorised API failure does not claim that another project opened',async()=>{
 const h=harness({approved:true,fail:true});
 assert.equal(await h.load(),false);
 assert.deepEqual(h.operations.storage,[]);
 assert.ok(h.operations.mutations.includes('setError'));
 assert.ok(!h.operations.mutations.includes('setProject'),'failed loads must retain the old project');
});
test('preflight is positioned before project generation, reset, and API work',()=>{
 const preflight=body.indexOf('if(!embedded&&pid!==project?.id&&!approvedBeforeUpload&&onBeforePrimaryProjectLoad&&!onBeforePrimaryProjectLoad(pid))return false;');
 assert.ok(preflight>0);
 for(const token of ['++latestProjectRequest.current','projectOperations.current.begin(pid)','setProject(null)','Promise.all([get<Project>']){
  assert.ok(body.indexOf(token)>preflight,token+' happened before approval');
 }
});
test('shell guards a different requested project with the existing edit warning',()=>{
 const start=shell.indexOf('const approvePrimaryProjectLoad=');
 const end=shell.indexOf('const chooseProject=',start);
 assert.ok(start>=0&&end>start);
 const section=shell.slice(start,end);
 assert.match(section,/if\(!id\|\|!workspaceReady\)return false/);
 assert.match(section,/if\(id===projectId\)return true/);
 const veto=section.indexOf('if(!confirmProjectDraftDiscard())return false;');
 assert.ok(veto>0);
 assert.ok(section.indexOf('editedDock.current=null')>veto);
});
test('only the primary Studio receives the project preflight callback',()=>{
 assert.match(app,/onBeforePrimaryProjectLoad\?:\(projectId:string\)=>boolean/);
 assert.match(shell,/onBeforePrimaryProjectLoad=\{approvePrimaryProjectLoad\}/);
 assert.doesNotMatch(shell,/<App embeddedStage=\{dock\.secondary!\}[^\n]*onBeforePrimaryProjectLoad/);
});
test('Studio selector and Home project cards use guarded loadProject function',()=>{
 assert.match(app,/onChange=\{e=>void loadProject\(e\.target\.value\)\}/);
 assert.match(app,/onOpenProject=\{id=>void loadProject\(id\)\}/);
});
test('project-change notifications and generation guard remain after successful load',()=>{
 assert.match(app,/window\.addEventListener\('pilotodin:project-changed',handler\)/);
 assert.match(body,/projectOperations\.current\.begin\(pid\)/);
 assert.ok(body.indexOf('projectOperations.current.begin(pid)')>body.indexOf('await Promise.all([get<Project>'),'the generation must switch only after the destination project reads succeed');
 assert.match(body,/if\(!embedded\)localStorage\.setItem\('pilotodin-current',pid\)/);
});
test('import never reports project opened when the subsequent guarded load is cancelled',()=>{
 const start=app.indexOf('  async function startUpload(){');
 const end=app.indexOf('  async function startTrain(){',start);
 assert.ok(start>0&&end>start);
 const source=app.slice(start,end);
 assert.match(source,/const opened=await loadProject\(data\.id,liveProjectId\.current===initialProjectId\)/);
 assert.match(source,/if\(!opened\)\{/);
 assert.match(source,/Dataset was imported but was not opened/);
 const cancelled=source.slice(source.indexOf('if(!opened)'),source.indexOf('Dataset imported and profiled successfully'));
 assert.match(cancelled,/setUploadOpen\(false\);setFile\(null\);onNewProjectClose\?\.\(\)/);
 assert.ok(source.indexOf('if(!opened)')<source.indexOf('Dataset imported and profiled successfully'));
});
test('project preflight introduces no form-value persistence or ML actions',()=>{
 const start=shell.indexOf('const approvePrimaryProjectLoad=');
 const end=shell.indexOf('const chooseProject=',start);
 const section=shell.slice(start,end);
 assert.doesNotMatch(section,/localStorage|sessionStorage|fetch\(|post\(|upload\(|predictVals|train\(|setProjectId/);
});

test('pre-approved upload opens its project without a second project-switch warning',async()=>{
 const h=harness({preapproved:true});
 assert.equal(await h.load(),true);
 assert.deepEqual(h.operations.approved,[]);
 assert.deepEqual(h.operations.uploadCommits,['loaded:B','B']);
 assert.deepEqual(h.operations.storage,[['pilotodin-current','B']]);
});
test('failed project load after upload does not consume approval or discard old project',async()=>{
 const h=harness({preapproved:true,fail:true});
 assert.equal(await h.load(),false);
 assert.deepEqual(h.operations.uploadCommits,[]);
 assert.ok(!h.operations.mutations.includes('setProject'));
 assert.deepEqual(h.operations.storage,[]);
});
test('project reads must succeed before old primary state is reset',()=>{
 const fetch=body.indexOf('await Promise.all([get<Project>');
 const reset=body.indexOf('setProject(null)');
 assert.ok(fetch>=0&&reset>fetch,'old project must survive a failed API request');
});

test('stale startup read may not overwrite another tab latest selection',async()=>{
 const h=harness({current:'A',pid:'A',selectedAfterFetch:'B'});
 assert.equal(await h.load(),false);
 assert.equal(h.getShared(),'B');
 assert.deepEqual(h.operations.storage,[]);
 assert.deepEqual(h.operations.uploadCommits,[]);
 assert.ok(!h.operations.mutations.includes('setProject'));
 assert.equal(h.operations.notice.length,2);
});
test('stale approved local read may not replace a third-project selection',async()=>{
 const h=harness({approved:true,pid:'B',selectedAfterFetch:'C'});
 assert.equal(await h.load(),false);
 assert.equal(h.getShared(),'C');
 assert.deepEqual(h.operations.storage,[]);
 assert.deepEqual(h.operations.uploadCommits,[]);
 assert.ok(!h.operations.mutations.includes('setProject'));
});
test('approved local switch remains allowed if shared selection is unchanged or already desired',async()=>{
 const first=harness({approved:true,pid:'B'});
 assert.equal(await first.load(),true);
 assert.equal(first.getShared(),'B');
 const chosen=harness({approved:true,pid:'B',selectedAfterFetch:'B'});
 assert.equal(await chosen.load(),true);
 assert.deepEqual(chosen.operations.storage,[['pilotodin-current','B']]);
});
test('failed authorized project GET reports failure without clearing any old form',async()=>{
 const h=harness({approved:true,fail:true});
 assert.equal(await h.load(),false);
 assert.deepEqual(h.operations.uploadCommits,[]);
 assert.ok(h.operations.notice.includes('failed:B'));
 assert.deepEqual(h.operations.storage,[]);
 assert.ok(!h.operations.mutations.includes('setProject'));
});
test('stale selection guard never reads drafts or performs any backend operation',()=>{
 const src=fs.readFileSync(guardPath,'utf8');
 assert.doesNotMatch(src,/localStorage|sessionStorage|fetch\(|post\(|upload\(|train\(/);
 assert.equal(mayCommitProjectSelection('A','B','A'),false);
 assert.equal(mayCommitProjectSelection('A','A','B'),true);
 assert.equal(mayCommitProjectSelection('A','B','B'),true);
 assert.equal(mayCommitProjectSelection('A','C','B'),false);
 assert.equal(mayCommitProjectSelection('A','A',''),false);
});

test('only a successful approved external load stages a one-use verified project/profile for keyed Studio',()=>{
 assert.match(app,/export type PrimaryProjectLoadSnapshot=\{id:string;project:Project;version:number\}/);
 assert.match(app,/const initialVerifiedProject=!embedded&&primaryProjectHandoff\?\.id===\(localStorage\.getItem\('pilotodin-current'\)\|\|''\)/);
 assert.match(app,/useState<Project\|null>\(\(\)=>initialVerifiedProject\?\.project\?\?null\)/);
 assert.match(app,/useState\(initialVerifiedProject\?\.version\?\?0\)/);
 assert.match(app,/if\(pid&&pid!==initialVerifiedProject\?\.id\)void loadProject\(pid\)/);
 assert.match(app,/const verifiedProject:Project=q\.profile\?\{\.\.\.p,profile:q\.profile\}:p/);
 assert.match(app,/onPrimaryProjectLoaded\?\.\(pid,\{id:pid,project:verifiedProject,version:q\.version\}\)/);
 assert.match(shell,/primaryProjectHandoff\.current=snapshot/);
 assert.match(shell,/primaryProjectHandoff=\{primaryProjectHandoff\.current\?\.id===projectId\?primaryProjectHandoff\.current:undefined\}/);
 assert.match(shell,/onPrimaryProjectHandoffConsumed=\{consumePrimaryProjectHandoff\}/);
 const refIndex=shell.indexOf('primaryProjectHandoff.current=snapshot');
 const successIndex=shell.indexOf('setProjectId(id)',refIndex);
 assert.ok(refIndex>=0&&successIndex>refIndex,'snapshot must be staged before keyed shell remount');
 const catchBody=app.slice(app.indexOf('}catch(e){',app.indexOf('async function loadProject(')),app.indexOf('useEffect(()=>{if(!project||!target)'));
 assert.doesNotMatch(catchBody,/onPrimaryProjectLoaded|primaryProjectHandoff/,'failed project GET must not create a verified handoff');
});
