const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const filename=path.resolve(__dirname,'../src/qualityPreviewLabel.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}
}).outputText;
const mod=new Module(filename,module);
mod.filename=filename;
mod.paths=module.paths;
mod._compile(compiled,filename);
const {qualityPreviewLabel}=mod.exports;

test('whitespace-trim correction has visibly different Before and After values',()=>{
  assert.equal(qualityPreviewLabel(' Gauteng '),'"[SPACE]Gauteng[SPACE]"');
  assert.equal(qualityPreviewLabel('Gauteng'),'"Gauteng"');
  assert.notEqual(qualityPreviewLabel(' Gauteng '),qualityPreviewLabel('Gauteng'));
});

test('reverse/undo preview exposes the same difference with inverted values',()=>{
  const before='Gauteng',after=' Gauteng ';
  assert.notEqual(qualityPreviewLabel(before),qualityPreviewLabel(after));
  assert.equal(qualityPreviewLabel(after),'"[SPACE]Gauteng[SPACE]"');
});

test('different whitespace code points are visibly identifiable',()=>{
  assert.equal(qualityPreviewLabel('\tGauteng'),'"[TAB]Gauteng"');
  assert.equal(qualityPreviewLabel('Gauteng\n'),'"Gauteng[LINE FEED]"');
  assert.equal(qualityPreviewLabel('\u00a0Gauteng'),'"[NO-BREAK SPACE]Gauteng"');
  assert.equal(qualityPreviewLabel('Gauteng\u2003'),'"Gauteng[U+2003]"');
});

test('null, empty, numeric and normal text keep meaningful read-only labels',()=>{
  assert.equal(qualityPreviewLabel(null),'—');
  assert.equal(qualityPreviewLabel(undefined),'—');
  assert.equal(qualityPreviewLabel(''),'(empty string)');
  assert.equal(qualityPreviewLabel(0),'0');
  assert.equal(qualityPreviewLabel(false),'false');
  assert.equal(qualityPreviewLabel('Mpumalanga'),'"Mpumalanga"');
});

test('formatter never mutates original strings or dataset objects',()=>{
  const original=Object.freeze({before:' Gauteng ',after:'Gauteng'});
  qualityPreviewLabel(original.before);
  qualityPreviewLabel(original.after);
  assert.deepEqual(original,{before:' Gauteng ',after:'Gauteng'});
});

test('Quality preview displays labels only, preserving exact proposal/commit guards',()=>{
  const source=fs.readFileSync(path.resolve(__dirname,'../src/QualityWorkspace.tsx'),'utf8');
  assert.match(source,/import \{qualityPreviewLabel\} from '\.\/qualityPreviewLabel'/);
  assert.match(source,/<td>\{qualityPreviewLabel\(r\.before\)\}<\/td><td>\{qualityPreviewLabel\(r\.after\)\}<\/td>/);
  assert.match(source,/\[SPACE\], \[TAB\]/);
  assert.match(source,/setPendingApproval\(\{proposal,message\}\)/);
  assert.match(source,/proposal_id:proposal\.proposal_id,proposal_hash:proposal\.proposal_hash/);
  assert.match(source,/<button className="btn" disabled=\{busy\} onClick=\{\(\)=>setPendingApproval\(null\)\}>Cancel<\/button>/);
});
