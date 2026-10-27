const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');

const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
const begin=app.indexOf('  async function startUpload(){');
const end=app.indexOf('  async function startTrain(){',begin);
assert.ok(begin>=0&&end>begin,'actual startUpload must be present');
const uploadBody=app.slice(begin,end);
const output=ts.transpileModule(uploadBody+'\nexport {startUpload};',{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((output.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);

function harness({consent=true,file={name:'new.csv'},embedded=false,uploadFails=false,
 loadSucceeds=true,projectId='A',switchDuringUpload=false,withoutCallback=false}={}){
 const operations={events:[],alerts:[],loads:[],uploadCalls:0,closeCalls:0,refresh:0};
 const liveProjectId={current:projectId};
 const ctx={
  embedded,file,project:{id:projectId},liveProjectId,
  onBeforePrimaryProjectUpload:withoutCallback?undefined:()=>{
   operations.events.push('preflight');return consent;
  },
  onNewProjectClose:()=>{operations.closeCalls++},
  upload:async selected=>{
   operations.events.push('upload');operations.uploadCalls++;
   assert.equal(selected,file);
   if(uploadFails)throw Error('import service unavailable');
   if(switchDuringUpload)liveProjectId.current='another-project';
   return {id:'uploaded-B'};
  },
  refreshProjects:async()=>{operations.events.push('refresh');operations.refresh++},
  loadProject:async(id,preapproved)=>{
   operations.events.push('open');operations.loads.push({id,preapproved});
   return loadSucceeds;
  },
  setLoading:x=>operations.events.push('loading:'+x),
  setUploadOpen:x=>operations.events.push('uploadOpen:'+x),
  setError:x=>operations.alerts.push({type:'error',text:x}),
  setNotice:x=>operations.alerts.push({type:'notice',text:x}),
  setFile:x=>operations.events.push('file:'+x),
 };
 const exports={};
 const run=new Function(...Object.keys(ctx),'exports',output.outputText+'\nreturn exports.startUpload;')(
 ...Object.values(ctx),exports);
 return {run,operations,liveProjectId};
}
test('Cancel before upload makes no API request and never alters current import state',async()=>{
 const h=harness({consent:false});
 await h.run();
 assert.deepEqual(h.operations.events,['preflight']);
 assert.equal(h.operations.uploadCalls,0);
 assert.deepEqual(h.operations.alerts,[]);
 assert.equal(h.operations.closeCalls,0);
});
test('explicit consent occurs once before upload, project refresh and opening',async()=>{
 const h=harness();
 await h.run();
 assert.deepEqual(h.operations.events.slice(0,5),['preflight','loading:true','upload','refresh','open']);
 assert.equal(h.operations.events.at(-1),'loading:false');
 assert.equal(h.operations.uploadCalls,1);
 assert.deepEqual(h.operations.loads,[{id:'uploaded-B',preapproved:true}]);
 assert.equal(h.operations.closeCalls,1);
 assert.match(h.operations.alerts.at(-1).text,/Dataset imported and profiled successfully/);
});
test('upload failure cannot consume old project draft or claim imported',async()=>{
 const h=harness({uploadFails:true});
 await h.run();
 assert.equal(h.operations.uploadCalls,1);
 assert.deepEqual(h.operations.loads,[]);
 assert.equal(h.operations.events.includes('uploadOpen:false'),false);
 assert.equal(h.operations.events.includes('file:null'),false);
 assert.equal(h.operations.events.at(-1),'loading:false');
 assert.match(h.operations.alerts.at(-1).text,/import service unavailable/);
});
test('upload success with refused project opening reports imported but not opened',async()=>{
 const h=harness({loadSucceeds:false});
 await h.run();
 assert.equal(h.operations.uploadCalls,1);
 assert.equal(h.operations.closeCalls,1);
 assert.ok(h.operations.events.includes('uploadOpen:false'));
 assert.ok(h.operations.events.includes('file:null'));
 assert.match(h.operations.alerts.at(-1).text,/imported but was not opened/);
 assert.equal(h.operations.events.at(-1),'loading:false');
});
test('stale pre-upload consent is not reused if the current project changes mid-upload',async()=>{
 const h=harness({switchDuringUpload:true,loadSucceeds:false});
 await h.run();
 assert.deepEqual(h.operations.loads,[{id:'uploaded-B',preapproved:false}]);
 assert.match(h.operations.alerts.at(-1).text,/imported but was not opened/);
});
test('without a current uploaded file neither prompt nor backend call occurs',async()=>{
 const h=harness({file:null});
 await h.run();
 assert.deepEqual(h.operations.events,[]);
});
test('embedded workspace cannot upload a new project',async()=>{
 const h=harness({embedded:true});
 await h.run();
 assert.equal(h.operations.uploadCalls,0);
 assert.deepEqual(h.operations.events,[]);
 assert.match(h.operations.alerts[0].text,/primary workspace/);
});
test('standalone mode retains existing upload flow without shell callback',async()=>{
 const h=harness({withoutCallback:true});
 await h.run();
 assert.equal(h.operations.uploadCalls,1);
 assert.deepEqual(h.operations.loads,[{id:'uploaded-B',preapproved:true}]);
});
test('preflight is before loading indicators and the real upload request',()=>{
 const preflight=uploadBody.indexOf("if(onBeforePrimaryProjectUpload&&!onBeforePrimaryProjectUpload())return;");
 assert.ok(preflight>0);
 for(const name of ['setLoading(true)','setError(\'\')','upload(file)','refreshProjects()','loadProject(data.id']){
  assert.ok(uploadBody.indexOf(name)>preflight,name+' ran before approval');
 }
});
test('the shell does not clear the edit marker on mere upload consent',()=>{
 const start=shell.indexOf('const approvePrimaryProjectUpload=');
 const end=shell.indexOf('const approvePrimaryProjectLoad=',start);
 assert.ok(start>0&&end>start);
 const section=shell.slice(start,end);
 assert.match(section,/return confirmEditedDockDiscard\('switch-project'\)/);
 const authorisation=section.slice(0,section.indexOf('const commitPrimaryUploadedProject='));
 assert.doesNotMatch(authorisation,/editedDock\.current=null/);
 assert.match(section,/const commitPrimaryUploadedProject=\(\)=>\{editedDock\.current=null;\}/);
});
test('the primary Studio alone receives upload preflight and commit callbacks',()=>{
 assert.match(app,/onBeforePrimaryProjectUpload\?:\(\)=>boolean/);
 assert.match(app,/onPrimaryUploadedProjectCommitted\?:\(\)=>void/);
 assert.match(shell,/onBeforePrimaryProjectUpload=\{approvePrimaryProjectUpload\}/);
 assert.match(shell,/onPrimaryUploadedProjectCommitted=\{commitPrimaryUploadedProject\}/);
 assert.doesNotMatch(shell,/<App embeddedStage=\{dock\.secondary!\}[^\n]*onBeforePrimaryProjectUpload/);
});
test('post-upload opening cannot consume old approval after a different project becomes active',()=>{
 assert.match(uploadBody,/liveProjectId\.current===initialProjectId/);
 assert.match(app,/if\(!embedded&&pid!==project\?\.id&&!approvedBeforeUpload&&onBeforePrimaryProjectLoad/);
});
test('upload consent does not save arbitrary field contents or run ML or Quality actions',()=>{
 const start=shell.indexOf('const approvePrimaryProjectUpload=');
 const end=shell.indexOf('const approvePrimaryProjectLoad=',start);
 const section=shell.slice(start,end);
 assert.doesNotMatch(section,/localStorage|sessionStorage|predictVals|train\(|upload\(|post\(|setQualityVersion|setProjectId/);
});
