const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const app=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
const spec=fs.readFileSync(path.resolve(__dirname,'../e2e/isolated-workspace.spec.ts'),'utf8');
const config=fs.readFileSync(path.resolve(__dirname,'../playwright.config.ts'),'utf8');
const start=spec.indexOf('const UI_ORIGIN='),end=spec.indexOf("\ntest('empty project catalogue",start);
assert.ok(start>=0&&end>start);
const compiled=ts.transpileModule(spec.slice(start,end)+'\nexport {installIsolatedAPI};',{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(x=>x.category===ts.DiagnosticCategory.Error).length,0);
const exported={};
const install=new Function('exports',compiled.outputText+'\nreturn exports.installIsolatedAPI;')(exported);
async function setup(){
  let intercept;
  const audit=await install({route:async(pattern,fn)=>{assert.equal(pattern,'**/*');intercept=fn;}},true);
  async function call(url,method='GET'){
    const calls=[];
    await intercept({request:()=>({url:()=>url,method:()=>method}),
      continue:async()=>calls.push({kind:'continue'}),
      abort:async reason=>calls.push({kind:'abort',reason}),
      fulfill:async response=>calls.push({kind:'fulfill',response})});
    assert.equal(calls.length,1);return calls[0];
  }
  return {audit,call};
}
test('target label associated and pilot uses accessible combobox',()=>{
  assert.match(app,/const targetFieldId=useId\(\)/);
  assert.match(app,/<label className="field-label" htmlFor=\{targetFieldId\}>TARGET VARIABLE<\/label><select id=\{targetFieldId\}/);
  assert.match(spec,/getByRole\('combobox',\{name:\/target variable\/i\}\)/);
});
test('synthetic GET and test Vite assets do not reach backend',async()=>{
  const {call,audit}=await setup();
  const r=await call('http://127.0.0.1:8000/api/projects');
  assert.equal(r.kind,'fulfill');assert.equal(r.response.status,200);
  assert.equal(r.response.json[0].id,'playwright-synthetic-project');
  assert.equal((await call('http://127.0.0.1:5187/src/main.tsx')).kind,'continue');
  assert.deepEqual(audit.writes,[]);
});
test('API writes and unexpected Vite writes are rejected and audited',async()=>{
  const {call,audit}=await setup();
  for(const url of ['http://127.0.0.1:8000/api/projects','http://127.0.0.1:5187/projects']){
    const r=await call(url,'POST');assert.equal(r.kind,'fulfill');assert.equal(r.response.status,403);
  }
  assert.deepEqual(audit.writes,['POST /projects','POST /projects [frontend-origin]']);
});
test('unexpected API GETs and cloud requests are recorded, never passed through',async()=>{
  const {call,audit}=await setup();
  assert.equal((await call('http://127.0.0.1:8000/api/unknown')).response.status,404);
  assert.equal((await call('https://example.com/ai?prompt=never')).kind,'abort');
  assert.deepEqual(audit.unexpectedReads,['/unknown']);
  assert.deepEqual(audit.blockedOrigins,['GET https://example.com/ai']);
  assert.equal(spec.split('expect(audit.blockedOrigins).toEqual([]);').length,3);
});
test('isolated browser does not reuse server or approve import',()=>{
  assert.match(config,/reuseExistingServer:false/);
  assert.match(config,/serviceWorkers:'block'/);
  assert.match(config,/127\.0\.0\.1:5187/);
  assert.match(spec,/await dialog\.dismiss\(\)/);
  assert.doesNotMatch(spec,/dialog\.accept\(/);
});
