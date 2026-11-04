const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const src=fs.readFileSync(path.resolve(__dirname,'../src/QualityWorkspace.tsx'),'utf8');
const guardPath=path.resolve(__dirname,'../src/qualityReadGuard.ts');
const guardSource=fs.readFileSync(guardPath,'utf8');
const guardJs=ts.transpileModule(guardSource,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}}).outputText;
const guardModule={exports:{}};
new Function('module','exports',guardJs)(guardModule,guardModule.exports);
const {createQualityReadGuard}=guardModule.exports;
const begin=src.indexOf('  const load=useCallback(async()=>{');
const end=src.indexOf('\n  useEffect(()=>{let live=true;load()',begin);
assert.ok(begin>0&&end>begin,'Actual production Quality read loader must exist');
const block=src.slice(begin,end);
const compiled=ts.transpileModule(block+'\nexports.load=load;',{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true,
});
assert.equal((compiled.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);
function harness(){
 let available=false,quality=null,history=null,preview=null,exportVersion=-1;
 const readGuard={current:createQualityReadGuard()};
 const reads=[],q={project_id:'isolated',version:0},h={current_version:0,versions:[{version:0}],actions:[]};
 const scope={
  useCallback:callback=>callback,
  projectId:'isolated',readGuard,
  get:async url=>{
   reads.push(url);
   if(!available)throw new Error('Could not connect to PilotODIN');
   return url.endsWith('/history')?h:q;
  },
  setQuality:v=>{quality=v},setHistory:v=>{history=v},
  setPreview:fn=>{preview=typeof fn==='function'?fn(preview):fn},
  setExportVersion:fn=>{exportVersion=fn(exportVersion)}
 };
 const keys=Object.keys(scope),exports={};
 const load=new Function(...keys,'exports',compiled.outputText+'\nreturn exports.load;')(...Object.values(scope),exports);
 return {load,restore:()=>{available=true},state:()=>({quality,history,preview,exportVersion,reads}),q,h};
}
test('actual Quality read loader retains prior state when both GETs fail offline',async()=>{
 const x=harness();
 await assert.rejects(x.load(),/Could not connect to PilotODIN/);
 assert.equal(x.state().quality,null);
 assert.equal(x.state().history,null);
});
test('same Quality loader accepts fresh snapshots after local reconnection without a write',async()=>{
 const x=harness();
 await assert.rejects(x.load(),/Could not connect to PilotODIN/);
 x.restore();
 assert.equal(await x.load(),x.q);
 assert.equal(x.state().quality,x.q);
 assert.equal(x.state().history,x.h);
 assert.equal(x.state().exportVersion,0);
 assert.deepEqual(x.state().reads,[
  '/projects/isolated/quality','/projects/isolated/quality/history',
  '/projects/isolated/quality','/projects/isolated/quality/history'
 ]);
});
test('retry button refreshes the mounted Quality snapshot and its preview without side effects',()=>{
 assert.ok(src.includes('const [retryReads,setRetryReads]=useState(0)'));
 assert.ok(src.includes('[load,retryReads]'));
 assert.ok(src.includes('[projectId,selected,offset,quality?.version,retryReads]'));
 assert.ok(src.includes('readGuard.current.beginSnapshot()'));
 assert.ok(src.includes('readGuard.current.beginPreview()'));
 const button=src.match(/<button type="button" className="btn small" onClick=\{\(\)=>\{setError\(''\);setRetryReads\(count=>count\+1\)\}\}>Retry loading Quality<\/button>/)?.[0]||'';
 assert.ok(button,'Quality errors must display an accessible manual GET retry');
 assert.doesNotMatch(button,/post\(|mutate\(|upload\(|commitProposal\(/);
});

test('a late snapshot and history response cannot roll back a newer accepted retry',async()=>{
 const pending=[],readGuard={current:createQualityReadGuard()};
 let quality=null,history=null,exportVersion=-1,preview=null;
 const get=url=>new Promise((resolve,reject)=>pending.push({url,resolve,reject}));
 const scope={
  useCallback:fn=>fn,readGuard,projectId:'isolated',get,
  setQuality:v=>{quality=v},setHistory:v=>{history=v},
  setPreview:fn=>{preview=typeof fn==='function'?fn(preview):fn},
  setExportVersion:fn=>{exportVersion=fn(exportVersion)}
 };
 const names=Object.keys(scope),exports={};
 const load=new Function(...names,'exports',compiled.outputText+'\nreturn exports.load;')(...Object.values(scope),exports);
 const old=load(),fresh=load();
 assert.equal(pending.length,4);
 const newer={project_id:'isolated',version:2,issues:[]};
 pending[2].resolve(newer);pending[3].resolve({current_version:2,versions:[{version:0},{version:1},{version:2}]});
 await fresh;
 pending[0].resolve({project_id:'isolated',version:1,issues:[{id:'old'}]});
 pending[1].resolve({current_version:1,versions:[{version:1}]});
 await old;
 assert.equal(quality,newer);
 assert.equal(history.current_version,2);
 assert.equal(exportVersion,2);
 assert.equal(preview,null);
});
test('inconsistent Quality snapshot/history pair is rejected without replacing verified state',async()=>{
 const pending=[],readGuard={current:createQualityReadGuard()},calls=[];
 const scope={
  useCallback:fn=>fn,readGuard,projectId:'isolated',
  get:url=>new Promise(resolve=>pending.push(resolve)),
  setQuality:v=>calls.push('quality'),setHistory:v=>calls.push('history'),
  setPreview:v=>calls.push('preview'),setExportVersion:v=>calls.push('export')
 };
 const exports={},keys=Object.keys(scope);
 const load=new Function(...keys,'exports',compiled.outputText+'\nreturn exports.load;')(...Object.values(scope),exports);
 const p=load();pending[0]({project_id:'isolated',version:1});pending[1]({current_version:0,versions:[{version:0}]});
 await assert.rejects(p,/snapshot changed while loading/);
 assert.deepEqual(calls,[]);
});
test('an older request cannot overwrite a higher previously accepted Quality version',()=>{
 const fence=createQualityReadGuard();
 const v2=fence.beginSnapshot();
 assert.equal(fence.acceptSnapshot(v2,2),true);
 const v1=fence.beginSnapshot();
 assert.equal(fence.acceptSnapshot(v1,1),false);
 const v3=fence.beginSnapshot();
 assert.equal(fence.acceptSnapshot(v3,3),true);
 fence.invalidateAll();
 assert.equal(fence.isLatestSnapshot(v3),false);
});

const previewBegin=src.indexOf('  useEffect(()=>{let live=true;\n    const ticket=readGuard.current.beginPreview();');
const previewEnd=src.indexOf('\n  },[projectId,selected,offset,quality?.version,retryReads]);',previewBegin);
assert.ok(previewBegin>=0&&previewEnd>previewBegin,'Actual Quality preview effect must be extractable');
const previewBlock=src.slice(previewBegin,previewEnd+
 '\n  },[projectId,selected,offset,quality?.version,retryReads]);'.length);
const previewJs=ts.transpileModule(previewBlock,{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true,
});
assert.equal((previewJs.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
function previewHarness(){
 const requests=[],readGuard={current:createQualityReadGuard()};
 let preview=null,error='';
 const run=(expectedVersion,retryReads)=>{
  let cleanup;
  const env={
   useEffect:fn=>{cleanup=fn()},readGuard,projectId:'isolated',selected:'',offset:0,
   quality:{version:expectedVersion},retryReads,
   get:url=>new Promise((resolve,reject)=>requests.push({url,resolve,reject})),
   setPreview:value=>{preview=value},setError:value=>{error=value}
  };
  const keys=Object.keys(env);
  new Function(...keys,previewJs.outputText)(...Object.values(env));
  return cleanup;
 };
 return {run,requests,state:()=>({preview,error}),readGuard};
}
test('actual Quality preview effect rejects an older response after retry, even when both use version zero',async()=>{
 const x=previewHarness(),oldCleanup=x.run(0,0);
 oldCleanup();
 const cleanup=x.run(0,1);
 assert.equal(x.requests.length,2);
 x.requests[1].resolve({version:0,rows:[{row_number:2}],total_matching_rows:1});
 await Promise.resolve();await Promise.resolve();
 assert.equal(x.state().preview.rows[0].row_number,2);
 x.requests[0].resolve({version:0,rows:[{row_number:1}],total_matching_rows:1});
 await Promise.resolve();await Promise.resolve();
 assert.equal(x.state().preview.rows[0].row_number,2);
 assert.equal(x.state().error,'');
 cleanup();
});
test('stale preview failure cannot replace a newer successful retry with an error',async()=>{
 const x=previewHarness(),cleanupOld=x.run(0,0);
 cleanupOld();x.run(0,1);
 x.requests[1].resolve({version:0,rows:[],total_matching_rows:0});
 await Promise.resolve();await Promise.resolve();
 x.requests[0].reject(new Error('old disconnected preview'));
 await Promise.resolve();await Promise.resolve();
 assert.equal(x.state().error,'');
 assert.equal(x.state().preview.version,0);
});
test('current preview with a mismatched Quality version is refused and offers retry',async()=>{
 const x=previewHarness();x.run(2,0);
 x.requests[0].resolve({version:1,rows:[{row_number:1}],total_matching_rows:1});
 await Promise.resolve();await Promise.resolve();
 assert.equal(x.state().preview,null);
 assert.match(x.state().error,/Quality preview version changed/);
});
test('inspector Refresh issues both Quality snapshot and preview GETs, never a write',()=>{
 const start=src.indexOf('<button className="btn small" onClick={()=>{setError');
 const end=src.indexOf('<RefreshCw size={14}/> Refresh',start);
 assert.ok(start>=0&&end>start);
 const handler=src.slice(start,end);
 assert.match(handler,/setRetryReads\(count=>count\+1\)/);
 assert.doesNotMatch(handler,/post\(|commitProposal\(|mutate\(/);
 assert.ok(src.includes('const verifiedPreview=quality&&preview?.version===quality.version?preview:null'));
});
