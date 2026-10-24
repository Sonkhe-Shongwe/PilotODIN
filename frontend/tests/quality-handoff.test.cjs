const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const load=file=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8');
const moduleSource=load('qualityHandoff.ts');
const compiled=ts.transpileModule(moduleSource,{compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},reportDiagnostics:true});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const exportsObj={};new Function('exports','module',compiled.outputText)(exportsObj,{exports:exportsObj});
const {resolveQualityFocus,insightQualityKind}=exportsObj;

test('handoff only selects a real current-version Quality issue',()=>{
 const issues=[{id:'i1',kind:'missing',column:'Amount'},{id:'i2',kind:'outliers',column:'Amount'},{id:'i3',kind:'exact_duplicates',column:null}];
 assert.deepEqual(resolveQualityFocus({projectId:'one',version:3,column:'Amount',kind:'outliers'},'one',3,issues),{status:'matched',issueId:'i2'});
 assert.deepEqual(resolveQualityFocus({projectId:'one',version:3,column:null,kind:'exact_duplicates'},'one',3,issues),{status:'matched',issueId:'i3'});
 assert.equal(resolveQualityFocus({projectId:'two',version:3,column:'Amount',kind:'any'},'one',3,issues).status,'stale');
 assert.equal(resolveQualityFocus({projectId:'one',version:2,column:'Amount',kind:'any'},'one',3,issues).status,'stale');
 assert.equal(resolveQualityFocus({projectId:'one',version:3,column:'NotInData',kind:'any'},'one',3,issues).status,'unavailable');
});

test('proactive evidence maps deterministically without labelling all insights as Quality errors',()=>{
 assert.equal(insightQualityKind({category:'missing',title:'3 missing'}),'missing');
 assert.equal(insightQualityKind({category:'distribution',title:'Unusual values'}),'outliers');
 assert.equal(insightQualityKind({category:'duplicates',title:'Duplicate rows'}),'exact_duplicates');
 assert.equal(insightQualityKind({category:'features',title:'ClaimID looks like an identifier'}),'identifier');
 assert.equal(insightQualityKind({category:'features',title:'No variation'}),null);
});

test('application routes only active-project and current-version evidence to Quality',()=>{
 const explore=load('ExploreWorkspace.tsx'),app=load('App.tsx'),quality=load('QualityWorkspace.tsx');
 assert.match(explore,/onReviewQuality\?\(focus:QualityFocus\)=>void/);
 assert.match(explore,/onReviewQuality\(\{projectId,version:overview\.version,kind,column\}\)/);
 assert.match(explore,/Inspect in Quality →/);
 assert.match(app,/focus\.projectId===project\.id&&focus\.version===qualityVersion/);
 assert.match(app,/setQualityFocus\(focus\);go\('quality'\)/);
 assert.match(app,/setProject\(null\).*setQualityFocus\(null\)/);
 assert.match(quality,/resolveQualityFocus\(initialFocus,projectId,quality\.version,quality\.issues\)/);
 assert.match(quality,/setSelected\(result\.issueId\)/);
 assert.match(quality,/role="status"/);
});
