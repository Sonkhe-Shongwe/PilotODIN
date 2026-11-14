const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');

const source=fs.readFileSync(path.join(__dirname,'../src/revealRecordInspector.ts'),'utf8');
const result=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});
assert.equal((result.diagnostics??[]).filter(item=>item.category===ts.DiagnosticCategory.Error).length,0);
const mod={exports:{}};
new Function('module','exports',result.outputText)(mod,mod.exports);
const {revealRecordInspector,INSPECTOR_SCROLL_MS}=mod.exports;

function simulate(reduced=false){
 const events={};
 let animation=0,nextId=0;
 const callbacks=new Map();
 const container={
   parentElement:null,scrollTop:100,scrollHeight:2800,clientHeight:500,
   getBoundingClientRect:()=>({top:0}),
   addEventListener(name,fn){events[name]=fn},
   removeEventListener(name,fn){if(events[name]===fn)delete events[name]}
 };
 const panel={
   parentElement:container,focused:null,seen:null,
   focus(opts){this.focused=opts},
   scrollIntoView(opts){this.seen=opts},
   getBoundingClientRect:()=>({top:1200})
 };
 const old=global.window;
 global.window={
   matchMedia:()=>({matches:reduced}),
   getComputedStyle:()=>({overflowY:'auto'}),
   requestAnimationFrame(fn){const id=++nextId;callbacks.set(id,fn);return id},
   cancelAnimationFrame(id){callbacks.delete(id)},
   addEventListener(name,fn){events[name]=fn},
   removeEventListener(name,fn){if(events[name]===fn)delete events[name]}
 };
 return {
  container,panel,events,run(ms){
    const scheduled=[...callbacks.entries()];callbacks.clear();
    for(const [,cb] of scheduled)cb(ms);
  },scheduled(){return callbacks.size},restore(){global.window=old}
 };
}

test('scroll lasts 820ms, moves gradually, and lands below a visible margin',()=>{
 const env=simulate();
 try{
  assert.equal(INSPECTOR_SCROLL_MS,820);
  const cancel=revealRecordInspector(env.panel);
  assert.deepEqual(env.panel.focused,{preventScroll:true});
  assert.equal(env.container.scrollTop,100);
  env.run(0);
  env.run(200);
  assert.ok(env.container.scrollTop>100&&env.container.scrollTop<300);
  env.run(410);
  assert.ok(env.container.scrollTop>550&&env.container.scrollTop<800);
  env.run(820);
  assert.equal(Math.round(env.container.scrollTop),1272);
  assert.equal(env.scheduled(),0);
  assert.equal(env.events.wheel,undefined);
  cancel();
 }finally{env.restore()}
});

test('mouse wheel cancels any pending automatic movement',()=>{
 const env=simulate();
 try{
  revealRecordInspector(env.panel);
  env.run(0);env.run(200);
  const last=env.container.scrollTop;
  assert.equal(typeof env.events.wheel,'function');
  env.events.wheel();
  env.run(500);
  assert.equal(env.container.scrollTop,last);
  assert.equal(env.scheduled(),0);
 }finally{env.restore()}
});

test('reduced motion never schedules frames and reveals the panel immediately',()=>{
 const env=simulate(true);
 try{
  revealRecordInspector(env.panel);
  assert.deepEqual(env.panel.seen,{behavior:'auto',block:'start',inline:'nearest'});
  assert.equal(env.scheduled(),0);
 }finally{env.restore()}
});
