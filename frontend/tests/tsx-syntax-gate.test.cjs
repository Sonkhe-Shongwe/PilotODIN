const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');

function walk(directory){
  return fs.readdirSync(directory,{withFileTypes:true}).flatMap(entry=>{
    const full=path.join(directory,entry.name);
    if(entry.isDirectory())return walk(full);
    if(/\.tsx?$/.test(entry.name))return [full];
    return [];
  });
}

test('all production TypeScript/TSX modules parse before source-pattern assertions',()=>{
  const root=path.join(__dirname,'../src');
  const files=walk(root);
  assert.ok(files.length>10,'Expected PilotODIN frontend source files');
  for(const file of files){
    const content=fs.readFileSync(file,'utf8');
    const language=file.endsWith('.tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS;
    const parsed=ts.createSourceFile(file,content,ts.ScriptTarget.Latest,true,language);
    const errors=parsed.parseDiagnostics.filter(d=>d.category===ts.DiagnosticCategory.Error);
    assert.deepEqual(errors.map(d=>{
      const where=parsed.getLineAndCharacterOfPosition(d.start??0);
      return `${path.relative(root,file)}:${where.line+1}:${where.character+1} TS${d.code} ${ts.flattenDiagnosticMessageText(d.messageText,' ')}`;
    }),[],`Syntax errors in ${path.relative(root,file)}`);
  }
});

test('Model Lab high-risk acknowledgement closes its JSX expression before Train action panel',()=>{
  const app=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
  const marker=`aria-label="High-risk predictor review"`;
  const at=app.indexOf(marker);
  assert.ok(at>=0,'Review gate must stay visible in Model Lab');
  const until=app.indexOf('Start your experiment',at);
  assert.ok(until>at);
  const scope=app.slice(at,until);
  assert.match(scope,/<\/div>\}/);
  assert.match(scope,/acknowledgeFeatureRisks/);
});
