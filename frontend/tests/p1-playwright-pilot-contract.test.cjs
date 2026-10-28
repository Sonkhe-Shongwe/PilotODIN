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
test('only the exact declared Google Fonts stylesheet is replaced with local CSS',async()=>{
  const {call,audit}=await setup();
  const url='https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;550;600;650;700;750;800&family=Manrope:wght@500;600;650;700;750;800&display=swap';
  const response=await call(url);
  assert.equal(response.kind,'fulfill');
  assert.equal(response.response.status,200);
  assert.match(response.response.contentType,/^text\/css/);
  assert.doesNotMatch(response.response.body,/@import|@font-face|https?:\/\//);
  assert.deepEqual(audit.stubbedFontStylesheets,['GET https://fonts.googleapis.com/css2']);
  assert.deepEqual(audit.blockedOrigins,[]);
  assert.deepEqual(audit.writes,[]);
});
test('font exception rejects changed families, wrong paths, methods and font binaries',async()=>{
  const {call,audit}=await setup();
  const expected='https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;550;600;650;700;750;800&family=Manrope:wght@500;600;650;700;750;800&display=swap';
  const denied=[
    {url:expected,method:'POST'},
    {url:'https://fonts.googleapis.com/css2?family=Roboto:wght@400&display=swap',method:'GET'},
    {url:'https://fonts.googleapis.com/other',method:'GET'},
    {url:'https://fonts.gstatic.com/s/test.woff2',method:'GET'},
  ];
  for(const item of denied)assert.equal((await call(item.url,item.method)).kind,'abort');
  assert.deepEqual(audit.blockedOrigins,[
    'POST https://fonts.googleapis.com/css2',
    'GET https://fonts.googleapis.com/css2',
    'GET https://fonts.googleapis.com/other',
    'GET https://fonts.gstatic.com/s/test.woff2'
  ]);
  assert.deepEqual(audit.stubbedFontStylesheets,[]);
});
