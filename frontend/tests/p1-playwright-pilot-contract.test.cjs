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
async function setup(withSecondProject=false){
  let intercept;
  const audit=await install({route:async(pattern,fn)=>{assert.equal(pattern,'**/*');intercept=fn;}},true,withSecondProject);
  async function call(url,method='GET',body=null,headers={}){
    const calls=[];
    await intercept({request:()=>({url:()=>url,method:()=>method,postDataJSON:()=>body,headers:()=>headers}),
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
  assert.equal((spec.match(/^  expect\(audit\.blockedOrigins\)\.toEqual\(\[\]\);$/gm)||[]).length,
    (spec.match(/^test\('/gm)||[]).length,'each browser scenario checks blocked origins');
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
test('Explore synthetic GET endpoints match the read-only backend response shapes',async()=>{
  const {call,audit}=await setup();
  const root='http://127.0.0.1:8000/api/projects/playwright-synthetic-project/explore/';
  const expected={
    overview:response=>response.version===0&&response.rows===2&&response.columns.length===2,
    insights:response=>response.version===0&&Array.isArray(response.findings),
    recommended:response=>response.version===0&&Array.isArray(response.recommendations),
    'filter-options':response=>response.version===0&&response.max_filters===4&&Array.isArray(response.columns),
    saved:response=>Array.isArray(response)&&response.length===0,
  };
  for(const [endpoint,check] of Object.entries(expected)){
    const response=await call(root+endpoint);
    assert.equal(response.kind,'fulfill');
    assert.equal(response.response.status,200,endpoint);
    assert.equal(check(response.response.json),true,endpoint);
  }
  assert.deepEqual(audit.unexpectedReads,[]);
  assert.deepEqual(audit.readOnlyCalculations,[]);
});
test('Explore workbench POST is read-only, exact synthetic input, and never continued',async()=>{
  const {call,audit}=await setup();
  const url='http://127.0.0.1:8000/api/projects/playwright-synthetic-project/explore/workbench';
  const input={expected_version:0,filters:[],x:'fraud_reported',y:'amount',
    kind:'auto',aggregation:'mean',bins:16,correlation_method:'pearson',color_by:null};
  const response=await call(url,'POST',input);
  assert.equal(response.kind,'fulfill');
  assert.equal(response.response.status,200);
  assert.equal(response.response.json.version,0);
  assert.equal(response.response.json.filtered_rows,2);
  assert.equal(response.response.json.chart.type,'bar');
  assert.deepEqual(audit.readOnlyCalculations,['POST /projects/playwright-synthetic-project/explore/workbench']);
  assert.deepEqual(audit.writes,[]);
});
test('malformed, wrong-version or unapproved Explore POST still blocks and audits',async()=>{
  const {call,audit}=await setup();
  const url='http://127.0.0.1:8000/api/projects/playwright-synthetic-project/explore/workbench';
  const valid={expected_version:0,filters:[],x:'fraud_reported',y:'amount',
    kind:'auto',aggregation:'mean',bins:16,correlation_method:'pearson',color_by:null};
  for(const body of [{...valid,expected_version:1},{...valid,filters:[{column:'amount',op:'range'}]},
    {...valid,prompt:'secret dataset'},null]){
    const response=await call(url,'POST',body);
    assert.equal(response.kind,'fulfill');
    assert.equal(response.response.status,403);
  }
  const save=await call('http://127.0.0.1:8000/api/projects/playwright-synthetic-project/explore/saved','POST',valid);
  assert.equal(save.response.status,403);
  assert.equal(audit.writes.length,5);
  assert.deepEqual(audit.readOnlyCalculations,[]);
});
test('only the synthetic Explore calculation receives a CORS preflight',async()=>{
  const {call,audit}=await setup();
  const path='http://127.0.0.1:8000/api/projects/playwright-synthetic-project/explore/workbench';
  const validHeaders={
    origin:'http://127.0.0.1:5187',
    'access-control-request-method':'POST',
    'access-control-request-headers':'content-type',
  };
  const ok=await call(path,'OPTIONS',null,validHeaders);
  assert.equal(ok.kind,'fulfill');
  assert.equal(ok.response.status,204);
  assert.equal(ok.response.headers['access-control-allow-origin'],'http://127.0.0.1:5187');
  assert.deepEqual(audit.writes,[]);

  for(const headers of [
    {...validHeaders,'access-control-request-method':'DELETE'},
    {...validHeaders,origin:'https://example.com'},
    {...validHeaders,'access-control-request-headers':'content-type, x-private-secret'},
  ]){
    const blocked=await call(path,'OPTIONS',null,headers);
    assert.equal(blocked.kind,'fulfill');
    assert.equal(blocked.response.status,403);
  }
  assert.equal(audit.writes.length,3);
  assert.deepEqual(audit.readOnlyCalculations,[]);
});
test('second synthetic project is opt-in and never exposes an unmocked real project',async()=>{
  const mainOnly=await setup();
  const url='http://127.0.0.1:8000/api/projects';
  assert.equal((await mainOnly.call(url)).response.json.length,1);
  const second=await setup(true);
  const result=await second.call(url);
  assert.equal(result.kind,'fulfill');
  assert.deepEqual(result.response.json.map(project=>project.id),[
    'playwright-synthetic-project','playwright-synthetic-second-project']);
  const id='playwright-synthetic-second-project';
  const detail=await second.call('http://127.0.0.1:8000/api/projects/'+id);
  const prof=await second.call('http://127.0.0.1:8000/api/projects/'+id+'/live-profile');
  assert.equal(detail.response.json.id,id);
  assert.equal(prof.response.json.version,0);
  assert.equal(prof.response.json.profile.filename,'synthetic_second_fixture.csv');
  assert.deepEqual(second.audit.writes,[]);
  assert.deepEqual(second.audit.unexpectedReads,[]);
  assert.deepEqual(second.audit.blockedOrigins,[]);
});
