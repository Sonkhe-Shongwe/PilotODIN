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
  // Only explicit, synthetic read-only approval scenarios may accept dialogs.
  // Reject silent approval added to any Cancel, import or unrelated browser test.
  const approvedTitles=new Set([
    'approved cross-tab project read failure preserves primary Prepare without stealing storage',
    'approved cross-tab successful project load avoids duplicate failing profile request',
    'approved same-tab global project read failure preserves edited primary Prepare',
    'approved same-tab global project load commits B only after verified GETs',
    'genuine primary Prepare reload Stay preserves draft and Leave discards only in-memory edit',
    'genuine cross-tab reload Stay keeps A draft and Leave adopts shared B selection',
    'isolated import Quality and failed project switch preserve the synthetic unsaved draft',
  ]);
  const approvedScenarios=spec.split(/^test\('/m).slice(1)
    .filter(section=>section.includes('await dialog.accept()'));
  assert.equal(approvedScenarios.length,approvedTitles.size,
    'every approved dialog scenario must have an explicit, reviewed title');
  for(const section of approvedScenarios){
    const title=section.slice(0,section.indexOf("',async"));
    assert.ok(approvedTitles.has(title),
      'unapproved browser scenario must never silently accept a discard prompt: '+title);
  }
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

test('approved A-to-B Prepare fixture serves the complete bounded read-only request set',async()=>{
  const {call,audit}=await setup(true);
  const base='http://127.0.0.1:8000/api';
  const requests=[
    {path:'/projects',check:value=>value.length===2},
    {path:'/ai/settings',check:value=>value.cloud_enabled===false},
    {path:'/projects/playwright-synthetic-project',check:value=>value.id==='playwright-synthetic-project'},
    {path:'/projects/playwright-synthetic-project/live-profile',check:value=>value.version===0},
    {path:'/projects/playwright-synthetic-project/target-opportunities?expected_version=0',
      check:value=>value.version===0&&value.abstained===true},
    {path:'/projects/playwright-synthetic-project/preparation?target=fraud_reported&expected_version=0',
      check:value=>value.target==='fraud_reported'&&value.quality_version===0},
    {path:'/projects/playwright-synthetic-project/features?target=fraud_reported&expected_version=0',
      check:value=>value.version===0&&Array.isArray(value.features)},
    {path:'/projects/playwright-synthetic-second-project',
      check:value=>value.id==='playwright-synthetic-second-project'},
    {path:'/projects/playwright-synthetic-second-project/live-profile',
      check:value=>value.version===0&&value.profile.filename==='synthetic_second_fixture.csv'},
    {path:'/projects/playwright-synthetic-second-project/target-opportunities?expected_version=0',
      check:value=>value.version===0&&value.abstained===true
        &&value.business_context_state==='unverified'
        &&value.note==='Synthetic second-project fixture only'},
  ];
  for(const {path,check} of requests){
    const response=await call(base+path);
    assert.equal(response.kind,'fulfill',path);
    assert.equal(response.response.status,200,path);
    assert.equal(check(response.response.json),true,path);
  }
  assert.deepEqual(audit.unexpectedReads,[]);
  assert.deepEqual(audit.writes,[]);
  assert.deepEqual(audit.blockedOrigins,[]);
});

test('second-project target opportunities require explicit opt-in and version; all other B API reads remain blocked',async()=>{
  const base='http://127.0.0.1:8000/api/projects/playwright-synthetic-second-project';
  const allowed=base+'/target-opportunities?expected_version=0';
  const aOnly=await setup();
  const deniedWithoutOptIn=await aOnly.call(allowed);
  assert.equal(deniedWithoutOptIn.response.status,404);
  assert.deepEqual(aOnly.audit.unexpectedReads,
    ['/projects/playwright-synthetic-second-project/target-opportunities?expected_version=0']);
  const {call,audit}=await setup(true);
  for(const path of [
    '/target-opportunities',
    '/target-opportunities?expected_version=1',
    '/target-opportunities?expected_version=0&extra=unapproved',
    '/preparation?target=fraud_reported&expected_version=0',
    '/features?target=fraud_reported&expected_version=0',
    '/quality',
    '/explore/overview',
  ]){
    const response=await call(base+path);
    assert.equal(response.kind,'fulfill',path);
    assert.equal(response.response.status,404,path);
  }
  assert.deepEqual(audit.unexpectedReads,[
    '/projects/playwright-synthetic-second-project/target-opportunities',
    '/projects/playwright-synthetic-second-project/target-opportunities?expected_version=1',
    '/projects/playwright-synthetic-second-project/target-opportunities?expected_version=0&extra=unapproved',
    '/projects/playwright-synthetic-second-project/preparation?target=fraud_reported&expected_version=0',
    '/projects/playwright-synthetic-second-project/features?target=fraud_reported&expected_version=0',
    '/projects/playwright-synthetic-second-project/quality',
    '/projects/playwright-synthetic-second-project/explore/overview',
  ]);
  for(const method of ['POST','DELETE','PATCH']){
    const denied=await call(allowed,method);
    assert.equal(denied.response.status,403,method);
  }
  assert.equal(audit.writes.length,3);
  assert.deepEqual(audit.blockedOrigins,[]);
});


test('unversioned and stale Quality-version synthetic Prepare reads are blocked',async()=>{
 const {call,audit}=await setup(true);
 const base='http://127.0.0.1:8000/api/projects/playwright-synthetic-project';
 const paths=[
  '/preparation?target=fraud_reported',
  '/features?target=fraud_reported',
  '/preparation?target=fraud_reported&expected_version=1',
  '/features?target=fraud_reported&expected_version=1',
 ];
 for(const suffix of paths){
  const response=await call(base+suffix);
  assert.equal(response.response.status,404,suffix);
 }
 assert.deepEqual(audit.unexpectedReads,paths.map(p=>'/projects/playwright-synthetic-project'+p));
 assert.deepEqual(audit.writes,[]);
});

test('successful B Prepare mounts target screening at verified version without launching B preparation or feature reads',()=>{
  const src=fs.readFileSync(path.resolve(__dirname,'../src/TargetOpportunities.tsx'),'utf8');
  assert.match(app,/\{page==='prepare'&&profile&&/);
  assert.match(app,/<TargetOpportunities key=\{project\.id\+'-'\+qualityVersion\} projectId=\{project\.id\} version=\{qualityVersion\}/);
  assert.match(src,/\/projects\/\$\{projectId\}\/target-opportunities\?expected_version=\$\{version\}/);
  assert.match(app,/if\(!project\|\|!target\)\{setPrep\(null\);return;\}/);
  assert.match(app,/if\(!project\|\|!target\)\{setFeatureHintSnapshot\(null\);return;\}/);
  assert.match(app,/const featureHints=visibleFeatureHints\(featureHintSnapshot,project\?\.id,target,qualityVersion\)/);
  assert.match(spec,/expect\(\(await bOpportunities\)\.status\(\)\)\.toBe\(200\)/);
  assert.match(spec,/expect\(profileReads\)\.toBe\(1\)/);
  assert.match(spec,/expect\(audit\.unexpectedReads\)\.toEqual\(\[\]\)/);
});

test('same-tab global chooser synthetic failed-B regression asserts draft and selection preservation',()=>{
  const start=spec.indexOf("test('approved same-tab global project read failure preserves edited primary Prepare'");
  const end=spec.indexOf('\n});',start);
  assert.ok(start>=0&&end>start,'must retain the explicit same-tab failed-read browser scenario');
  const scenario=spec.slice(start,end);
  assert.match(scenario,/await dialog\.accept\(\)/);
  assert.match(scenario,/status:503/);
  assert.match(scenario,/await switcher\.selectOption\(TEST_PROJECT_B\)/);
  assert.match(scenario,/await expect\(switcher\)\.toHaveValue\(TEST_PROJECT\)/);
  assert.match(scenario,/await expect\(target\)\.toHaveValue\('fraud_reported'\)/);
  assert.match(scenario,/expect\(failedBProfileReads\)\.toBe\(1\)/);
  assert.match(scenario,/expect\(audit\.writes\)\.toEqual\(\[\]\)/);
  assert.match(scenario,/expect\(audit\.unexpectedReads\)\.toEqual\(\[\]\)/);
  assert.match(scenario,/expect\(audit\.blockedOrigins\)\.toEqual\(\[\]\)/);
});


test('real reload Chromium regressions request genuine navigation and keep data isolated',()=>{
  const first=spec.indexOf("test('genuine primary Prepare reload Stay");
  const second=spec.indexOf("test('genuine paused dock Prepare reload Stay");
  assert.ok(first>0&&second>first,'both real-navigation scenarios must exist');
  const primary=spec.slice(first,second),dock=spec.slice(second);
  for(const caseSource of [primary,dock]){
    assert.match(caseSource,/page\.waitForEvent\('dialog'\)/);
    assert.match(caseSource,/window\.location\.reload\(\)/);
    assert.match(caseSource,/expect\(dialog\.type\(\)\)\.toBe\('beforeunload'\)/);
    assert.match(caseSource,/await dialog\.dismiss\(\)/);
    assert.match(caseSource,/await target\.click\(\)/);
    assert.match(caseSource,/expect\(audit\.writes\)\.toEqual\(\[\]\)/);
    assert.match(caseSource,/expect\(audit\.unexpectedReads\)\.toEqual\(\[\]\)/);
    assert.match(caseSource,/expect\(audit\.blockedOrigins\)\.toEqual\(\[\]\)/);
    assert.doesNotMatch(caseSource,/new Event\('beforeunload'/);
  }
  assert.match(primary,/await dialog\.accept\(\)/);
  assert.match(primary,/page\.waitForEvent\('framenavigated'/);
  assert.match(primary,/await expect\(target\)\.toHaveValue\(''\)/);
  assert.match(dock,/await expect\(dock\)\.toBeHidden\(\)/);
  assert.match(dock,/await page\.setViewportSize\(\{width:1440,height:900\}\)/);
});


test('cross-tab real reload regression protects A until Leave without restoring stale shared storage',()=>{
  const start=spec.indexOf("test('genuine cross-tab reload Stay keeps A draft and Leave adopts shared B selection'");
  assert.ok(start>=0,'genuine cross-tab reload must have its own isolated browser scenario');
  const scenario=spec.slice(start);
  assert.match(scenario,/sessionStorage\.getItem\('pilotodin-p1-e2e-seeded'\)/);
  assert.match(scenario,/sessionStorage\.setItem\('pilotodin-p1-e2e-seeded','yes'\)/);
  assert.match(scenario,/await other\.evaluate\(id=>localStorage\.setItem\('pilotodin-current',id\),TEST_PROJECT_B\)/);
  assert.match(scenario,/expect\(externalPrompts\[0\]\)\.toMatch\(\/primary workspace/);
  assert.match(scenario,/await expect\(switcher\)\.toHaveValue\(TEST_PROJECT\)/);
  assert.match(scenario,/await expect\(target\)\.toHaveValue\('fraud_reported'\)/);
  assert.match(scenario,/window\.location\.reload\(\)/);
  assert.match(scenario,/expect\(dialog\.type\(\)\)\.toBe\('beforeunload'\)/);
  assert.match(scenario,/await dialog\.dismiss\(\)/);
  assert.match(scenario,/await dialog\.accept\(\)/);
  assert.match(scenario,/page\.waitForEvent\('framenavigated'/);
  assert.match(scenario,/await expect\(switcher\)\.toHaveValue\(TEST_PROJECT_B\)/);
  assert.match(scenario,/expect\(await page\.evaluate\(\(\)=>localStorage\.getItem\('pilotodin-current'\)\)\)\.toBe\(TEST_PROJECT_B\)/);
  assert.match(scenario,/expect\(audit\.writes\)\.toEqual\(\[\]\)/);
  assert.match(scenario,/expect\(audit\.unexpectedReads\)\.toEqual\(\[\]\)/);
  assert.match(scenario,/expect\(audit\.blockedOrigins\)\.toEqual\(\[\]\)/);
  assert.doesNotMatch(scenario,/new Event\('beforeunload'/);
});


test('keyboard, focus and emulated-DPI browser QA is isolated and clearly non-native',()=>{
  const titles=[
    'keyboard Tab Shift-Tab sidebar toggle and arrow navigation retain synthetic project',
    'keyboard dock resize preserves edited target and excludes paused controls from tab order',
    'simulated 150 percent device scale and reduced motion keep dock controls accessible'
  ];
  const scenarios=titles.map(title=>{
    const from=spec.indexOf("test('"+title+"'");
    assert.ok(from>=0,'missing named keyboard QA browser test: '+title);
    const to=spec.indexOf('\n});',from);
    assert.ok(to>from,'missing scenario boundary: '+title);
    return spec.slice(from,to);
  });
  for(const src of scenarios){
    assert.match(src,/installIsolatedAPI\(context,true\)/);
    assert.match(src,/expect\(audit\.writes\)\.toEqual\(\[\]\)/);
    assert.match(src,/expect\(audit\.unexpectedReads\)\.toEqual\(\[\]\)/);
    assert.match(src,/expect\(audit\.blockedOrigins\)\.toEqual\(\[\]\)/);
    assert.doesNotMatch(src,/window\.confirm\(|dialog\.accept\(\)|new Event\('beforeunload'/);
  }
  assert.match(scenarios[0],/page\.keyboard\.press\('Tab'\)/);
  assert.match(scenarios[0],/page\.keyboard\.press\('Shift\+Tab'\)/);
  assert.match(scenarios[0],/page\.keyboard\.press\('ArrowDown'\)/);
  assert.match(scenarios[1],/page\.keyboard\.press\('Home'\)/);
  assert.match(scenarios[1],/page\.keyboard\.press\('End'\)/);
  assert.match(scenarios[1],/await expect\(dock\)\.toBeHidden\(\)/);
  assert.match(scenarios[2],/deviceScaleFactor:1\.5,reducedMotion:'reduce'/);
  assert.match(scenarios[2],/Browser DPR emulation does not certify Windows scaling/);
});

test('import-to-Quality failure recovery scenario requires an opt-in bounded in-memory fixture',()=>{
  const anchor=spec.indexOf("test('isolated import Quality and failed project switch preserve the synthetic unsaved draft'");
  const nextScenario=spec.indexOf("\ntest(",anchor+1);
  assert.ok(anchor>0&&nextScenario>anchor);
  const scenario=spec.slice(anchor,nextScenario);
  assert.match(spec,/withSecondProject=false,withImport=false/);
  assert.match(spec,/req\.postData\(\)===expected/);
  assert.match(spec,/audit\.syntheticImports\.push\('POST \/projects \[exact synthetic multipart only\]'\)/);
  assert.match(scenario,/installIsolatedAPI\(context,true,false,true\)/);
  assert.match(scenario,/await uploadedFile\.setInputFiles\(/);
  assert.match(scenario,/failedReads\+\+/);
  assert.match(scenario,/status:503/);
  assert.match(scenario,/await expect\(target\)\.toHaveValue\('fraud_reported'\)/);
  assert.match(scenario,/expect\(audit\.syntheticImports\)\.toHaveLength\(1\)/);
  assert.match(scenario,/expect\(audit\.writes\)\.toEqual\(\[\]\)/);
  assert.match(scenario,/expect\(audit\.unexpectedReads\)\.toEqual\(\[\]\)/);
  assert.match(scenario,/expect\(audit\.blockedOrigins\)\.toEqual\(\[\]\)/);
  assert.doesNotMatch(scenario,/https:\/\/|window\.confirm|localStorage\.clear\(/);
});
