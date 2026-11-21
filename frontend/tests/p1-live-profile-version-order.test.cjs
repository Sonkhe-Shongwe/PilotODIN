const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const guardSource=fs.readFileSync(path.resolve(__dirname,'../src/liveProfileVersionGuard.ts'),'utf8');
function js(s){const c=ts.transpileModule(s,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});assert.equal((c.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);return c.outputText}
const m={exports:{}};new Function('module','exports',js(guardSource))(m,m.exports);
const {createLiveProfileVersionGuard}=m.exports;

test('old or invalid Quality profile replies cannot overwrite a higher accepted version',()=>{
 const g=createLiveProfileVersionGuard('A',0);
 assert.equal(g.accept('A',1),true);
 assert.equal(g.accept('A',2),true);
 assert.equal(g.accept('A',1),false);
 assert.equal(g.accept('B',3),false);
 assert.equal(g.accept('A',-1),false);
 assert.equal(g.accept('A',Number.NaN),false);
 assert.equal(g.accept('A',2),true);
 assert.deepEqual(g.snapshot(),{projectId:'A',version:2});
});
test('switching verified project resets version fence without permitting old project replies',()=>{
 const g=createLiveProfileVersionGuard('A',8);
 g.reset('B',0);
 assert.equal(g.accept('A',9),false);
 assert.equal(g.accept('B',1),true);
 assert.equal(g.isCurrent('B',0),false);
 assert.equal(g.isCurrent('B',1),true);
 assert.deepEqual(g.snapshot(),{projectId:'B',version:1});
});
const start=app.indexOf('  async function qualityChanged(){');
const end=app.indexOf('\n  return <div className=',start);
assert.ok(start>=0&&end>start,'Actual Studio Quality callback must be extractable');
const handlerSource=js(app.slice(start,end)+'\nexports.handler=qualityChanged;');
function harness(){
 const pending=[],fence=createLiveProfileVersionGuard('A',0);
 let profile={label:'start'},version=0,experiment={id:'exp',project_id:'A'},prediction={label:'existing'};
 const props={
  project:{id:'A'},experiment,projectOperations:{current:{snapshot:()=>1,accepts:(id,g)=>id==='A'&&g===1}},
  liveProfileVersionGuard:{current:fence},
  get:url=>new Promise((resolve,reject)=>pending.push({url,resolve,reject})),
  setQualityVersion:v=>{version=v},
  setProject:fn=>{profile=fn({id:'A',profile}).profile},
  setExperiment:fn=>{experiment=fn(experiment)},
  setPrediction:v=>{prediction=v},setNotice:()=>{},setError:()=>{}
 };
 const names=Object.keys(props),exports={};
 const qualityChanged=new Function(...names,'exports',handlerSource+'\nreturn exports.handler')(...Object.values(props),exports);
 return {qualityChanged,pending,fence,state:()=>({profile,version,experiment,prediction})};
}
test('real Studio Quality callback rejects out-of-order older live-profile response',async()=>{
 const h=harness(),old=h.qualityChanged(),fresh=h.qualityChanged();
 assert.equal(h.pending.length,2);
 h.pending[1].resolve({version:2,profile:{label:'fresh'}});
 await Promise.resolve();
 assert.equal(h.pending[2]?.url,'/experiments/exp');
 h.pending[2].resolve({id:'exp',project_id:'A',label:'fresh-experiment'});
 await fresh;
 h.pending[0].resolve({version:1,profile:{label:'old'}});
 await old;
 assert.equal(h.state().version,2);
 assert.equal(h.state().profile.label,'fresh');
 assert.equal(h.state().experiment.label,'fresh-experiment');
});
test('old experiment metadata response cannot replace current Quality-version experiment',async()=>{
 const h=harness(),old=h.qualityChanged();
 h.pending[0].resolve({version:1,profile:{label:'version1'}});
 await Promise.resolve();
 assert.equal(h.pending[1]?.url,'/experiments/exp');
 const fresh=h.qualityChanged();
 h.pending[2].resolve({version:2,profile:{label:'version2'}});
 await Promise.resolve();
 assert.equal(h.pending[3]?.url,'/experiments/exp');
 h.pending[3].resolve({id:'exp',project_id:'A',label:'new'});
 await fresh;
 h.pending[1].resolve({id:'exp',project_id:'A',label:'old'});
 await old;
 assert.equal(h.state().version,2);
 assert.equal(h.state().experiment.label,'new');
});
test('both real Studio profile refresh entry points share the version fence',()=>{
 assert.ok(app.includes("import {createLiveProfileVersionGuard} from './liveProfileVersionGuard'"));
 assert.ok(app.includes('liveProfileVersionGuard.current.reset(pid,q.version)'));
 assert.ok(app.includes('liveProfileVersionGuard.current.accept(currentProjectId,next.version)'));
 assert.ok(app.includes('liveProfileVersionGuard.current.accept(projectId,v.version)'));
});
