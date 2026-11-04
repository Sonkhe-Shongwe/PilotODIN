const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript');
const src=fs.readFileSync(path.resolve(__dirname,'../src/QualityWorkspace.tsx'),'utf8');
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
 let available=false,quality=null,history=null,exportVersion=-1;
 const reads=[],q={project_id:'isolated',version:0},h={current_version:0,versions:[{version:0}],actions:[]};
 const scope={
  useCallback:callback=>callback,
  projectId:'isolated',
  get:async url=>{
   reads.push(url);
   if(!available)throw new Error('Could not connect to PilotODIN');
   return url.endsWith('/history')?h:q;
  },
  setQuality:v=>{quality=v},setHistory:v=>{history=v},
  setExportVersion:fn=>{exportVersion=fn(exportVersion)}
 };
 const keys=Object.keys(scope),exports={};
 const load=new Function(...keys,'exports',compiled.outputText+'\nreturn exports.load;')(...Object.values(scope),exports);
 return {load,restore:()=>{available=true},state:()=>({quality,history,exportVersion,reads}),q,h};
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
 const button=src.match(/<button type="button" className="btn small" onClick=\{\(\)=>\{setError\(''\);setRetryReads\(count=>count\+1\)\}\}>Retry loading Quality<\/button>/)?.[0]||'';
 assert.ok(button,'Quality errors must display an accessible manual GET retry');
 assert.doesNotMatch(button,/post\(|mutate\(|upload\(|commitProposal\(/);
});
