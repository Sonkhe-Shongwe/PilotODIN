const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const vm=require('node:vm');

const root=path.join(__dirname,'../src');
const code=fs.readFileSync(path.join(root,'reportDraftOutline.ts'),'utf8');
const translated=ts.transpileModule(code,{compilerOptions:{
 target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS
},reportDiagnostics:true});
assert.equal(translated.diagnostics?.length,0);
const exported={};
vm.runInNewContext(translated.outputText,{exports:exported},{filename:'reportDraftOutline.js'});
const {REPORT_OUTLINES,createReportOutline,canStartReportOutline,reportOutlineProgress}=exported;
const ui=fs.readFileSync(path.join(root,'ReportWorkspace.tsx'),'utf8');

function fullyWritten(id){
 const skeleton=createReportOutline(id);
 const template=REPORT_OUTLINES.find(item=>item.id===id);
 return template.headings.reduce((text,heading,index)=>
  text.replace(heading+'\n\n',heading+'\nUser-authored interpretation '+(index+1)+'.\n\n'),
  skeleton+'\n');
}

test('BEHAVIOR: all three templates contain structure only, never claimed facts or fabricated numeric evidence',()=>{
 assert.deepEqual(Array.from(REPORT_OUTLINES,x=>x.id),['analysis','quality','model']);
 for(const item of REPORT_OUTLINES){
  assert.equal(item.headings.length,4);
  const skeleton=createReportOutline(item.id);
  assert.equal(skeleton,Array.from(item.headings).join('\n\n')+'\n');
  assert.equal(/\d/.test(skeleton),false);
  assert.equal(/\b(accuracy|p-value|revenue|rows)\s*[:=]\s*\d/i.test(skeleton),false);
  assert.equal(reportOutlineProgress(item.id,skeleton).complete,false);
 }
});

test('BEHAVIOR: empty narrative only can receive headings; existing user work is never eligible for overwrite',()=>{
 assert.equal(canStartReportOutline(''),true);
 assert.equal(canStartReportOutline(' \n \t'),true);
 assert.equal(canStartReportOutline('An analyst already wrote this.'),false);
 assert.equal(canStartReportOutline('Purpose and decision\n'),false);
});

test('BEHAVIOR: all sections need original user-authored content before complete',()=>{
 for(const item of REPORT_OUTLINES){
  const written=fullyWritten(item.id);
  const status=reportOutlineProgress(item.id,written);
  assert.equal(status.complete,true);
  assert.equal(status.completeCount,4);
  assert.equal(status.total,4);
  assert.ok(Array.from(status.entries).every(x=>x.complete===true));
 }
});

test('BEHAVIOR: missing content in one section cannot silently pass',()=>{
 const id='analysis';
 const drafted=fullyWritten(id);
 const incomplete=drafted.replace('User-authored interpretation 3.','  ');
 const progress=reportOutlineProgress(id,incomplete);
 assert.equal(progress.complete,false);
 assert.equal(progress.completeCount,3);
 assert.equal(progress.entries[2].complete,false);
});

test('BEHAVIOR: deleted or duplicated exact headings prevent completion',()=>{
 const id='quality',original=fullyWritten(id);
 const heading=REPORT_OUTLINES[1].headings[1];
 assert.equal(reportOutlineProgress(id,original.replace(heading,heading+' missing')).complete,false);
 assert.equal(reportOutlineProgress(id,original+'\n'+heading+'\nExtra text').complete,false);
});

test('BEHAVIOR: arbitrary analyst text and script-like strings remain plain text',()=>{
 const id='model',text=fullyWritten(id).replace(
  'User-authored interpretation 2.',
  'A reviewer wrote: <script>alert("synthetic")</script>, not a fact.'
 );
 assert.equal(reportOutlineProgress(id,text).complete,true);
 assert.ok(text.includes('<script>'));
});

test('INTEGRATION: editable Deliver enforces blank-only outline insertion and never bypasses save guard',()=>{
 assert.match(ui,/import \{REPORT_OUTLINES,canStartReportOutline,createReportOutline,reportOutlineProgress/);
 assert.match(ui,/function startReportOutline\(id:ReportOutlineId\)/);
 assert.match(ui,/!canStartReportOutline\(narrative\)/);
 assert.match(ui,/Existing writing was not replaced/);
 assert.match(ui,/onDraftEdit\(\);\s*setNarrative\(createReportOutline\(id\)\);setActiveOutlineId\(id\)/);
 assert.match(ui,/function useFreeformWriting\(\)/);
 assert.match(ui,/setActiveOutlineId\(null\);setError\(''\)/);
 assert.match(ui,/if\(activeOutlineId&&!reportOutlineProgress\(activeOutlineId,narrative\)\.complete\)/);
 assert.match(ui,/saveReady=title\.trim\(\)\.length>=5&&selected\.length>0&&\(!outlineProgress\|\|outlineProgress\.complete\)/);
 assert.match(ui,/No generated statistics, claims or AI conclusions/i);
 assert.match(ui,/Use \{item\.label\} outline/);
 assert.match(ui,/Use freeform writing \(keep my text\)/);
});

test('INTEGRATION: opening or creating another report resets checklist rather than applying it to historic revisions',()=>{
 assert.match(ui,/setNarrative\(data\.narrative\);setActiveOutlineId\(null\)/);
 assert.match(ui,/setTitle\(defaultTitle\);setNarrative\(''\);setActiveOutlineId\(null\)/);
 assert.match(ui,/setNarrative\(''\);setActiveOutlineId\(null\);setSelected\(\[id\]\)/);
});
