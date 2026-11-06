const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript'),Module=require('node:module');
const p=path.resolve(__dirname,'../src/primaryStudioExitGuard.ts');
const compiled=ts.transpileModule(fs.readFileSync(p,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS},
 reportDiagnostics:true
});
assert.equal((compiled.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const m=new Module(p,module);m.filename=p;m.paths=module.paths;m._compile(compiled.outputText,p);
const {needsPrimaryStudioExitApproval:needs}=m.exports;
const edit=view=>({projectId:'A',view});
test('Prepare Model Predict edited primary forms require consent before entering canvas',()=>{
 for(const view of ['prepare','model','predict']){
  assert.equal(needs(edit(view),'A',view,'investigate',true),true);
  assert.equal(needs(edit(view),'A','quality','investigate',true),true);
 }
});
test('Studio stays mounted during internal navigation, no needless confirmation',()=>{
 for(const view of ['prepare','model','predict']){
  assert.equal(needs(edit(view),'A',view,'quality',true),false);
  assert.equal(needs(edit(view),'A','quality','model',true),false);
 }
});
test('missing, stale, unready and canvas states never demand consent',()=>{
 assert.equal(needs(edit('model'),'B','model','investigate',true),false);
 assert.equal(needs(edit('model'),'A','model','investigate',false),false);
 assert.equal(needs(null,'A','model','investigate',true),false);
 assert.equal(needs(edit('model'),'A','investigate','quality',true),false);
});
test('exit guard only checks identity marker and shell connects every entry path',()=>{
 const src=fs.readFileSync(p,'utf8');
 const shell=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.doesNotMatch(src,/localStorage|sessionStorage|fetch\(|post\(|window\.|predictVals|train\(/);
 assert.match(shell,/const navigateWithDockGuard=\(view:View,afterNavigate\?:\(\)=>void,nativeApproved=false\):boolean=>\{\s*const primaryExit=needsPrimaryStudioExitApproval\(/);
 assert.match(shell,/if\(primaryExit\)editedPrimary\.current=null/);
 assert.match(shell,/const beforeRoutePush=\(event:Event\)=>\{/);
 assert.match(shell,/preapprovedRoutePush\.current=view==='investigate'\?'#\/canvas'/);
});
