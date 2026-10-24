const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const input=fs.readFileSync(path.join(__dirname,'../src/navigationMotion.ts'),'utf8');
const compiled=ts.transpileModule(input,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}});
function harness(reduced=false){
 const calls=[],events=[],classes=new Set(),controls=[];
 const pane={animate:(frames,options)=>{
  let resolve;const finished=new Promise(r=>{resolve=r});
  const item={frames,options,cancel:()=>{},finished,finish:()=>resolve()};
  controls.push(item);return item;
 }};
 const document={documentElement:{classList:{add:x=>classes.add(x),remove:x=>classes.delete(x)}},querySelector:()=>pane};
 const window={matchMedia:()=>({matches:reduced}),dispatchEvent:e=>{events.push(e.type)}};
 const location={hash:'#/studio/prepare'};
 const Event=function(type){this.type=type};
 const getComputedStyle=()=>({getPropertyValue:()=>''});
 const module={exports:{}};
 const requireMock=id=>id==='react-dom'?{flushSync:fn=>{calls.push('flush');fn()}}:require(id);
 new Function('module','exports','require','document','window','location','Event','getComputedStyle',compiled.outputText)(
  module,module.exports,requireMock,document,window,location,Event,getComputedStyle);
 return {navigate:module.exports.navigateHashSmoothly,events,classes,controls,location,calls};
}
test('route remains on original workspace until outgoing animation completes',async()=>{
 const h=harness();h.navigate('#/studio/model');
 assert.equal(h.location.hash,'#/studio/prepare');
 assert.equal(h.controls.length,1);
 h.controls[0].finish();await Promise.resolve();await Promise.resolve();
 assert.equal(h.location.hash,'#/studio/model');
 assert.equal(h.controls.length,2);
 assert.deepEqual(h.events,['pilotodin:route-commit']);
 assert.deepEqual(h.calls,['flush']);
 h.controls[1].finish();await Promise.resolve();await Promise.resolve();
 assert.equal(h.classes.has('po-route-animating'),false);
});
test('reduced motion updates route immediately and creates no animation',()=>{
 const h=harness(true);h.navigate('#/studio/model');
 assert.equal(h.location.hash,'#/studio/model');
 assert.equal(h.controls.length,0);
});
test('newest quick navigation cancels stale route',async()=>{
 const h=harness();h.navigate('#/studio/model');const first=h.controls[0];
 h.navigate('#/studio/evaluate');
 first.finish();await Promise.resolve();await Promise.resolve();
 assert.equal(h.location.hash,'#/studio/prepare');
 h.controls[1].finish();await Promise.resolve();await Promise.resolve();
 assert.equal(h.location.hash,'#/studio/evaluate');
});
