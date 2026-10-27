const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const f=path.resolve(__dirname,'../src/categoryQualityAdvice.ts');
const compiled=ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText;
const m=new Module(f,module);m.filename=f;m.paths=module.paths;m._compile(compiled,f);
const {reviewableWhitespaceFinding,hasWhitespaceCategoryCollision}=m.exports;
const eligible={id:'w1',kind:'whitespace',column:'Region',affected_rows:5,decision:'pending',proposal:{kind:'trim_whitespace',column:'Region'}};
const snap={project_id:'p0',version:0,issues:[eligible]};
test('eligible version-pinned current-project finding is reviewable, not applied',()=>{
  assert.equal(reviewableWhitespaceFinding(snap,'p0',0,['Region']),eligible);
  assert.equal(snap.version,0);
});
test('never hand off stale version or another project',()=>{
  assert.equal(reviewableWhitespaceFinding(snap,'p0',1,['Region']),null);
  assert.equal(reviewableWhitespaceFinding(snap,'other',0,['Region']),null);
});
test('only the included category column may be offered',()=>{
  assert.equal(reviewableWhitespaceFinding(snap,'p0',0,['Other']),null);
  assert.equal(reviewableWhitespaceFinding(snap,'p0',0,[]),null);
});
test('missing approval, unsafe proposal, wrong column, or no changed rows is denied',()=>{
 for(const issue of [
  {...eligible,decision:'applied'},
  {...eligible,proposal:null},
  {...eligible,proposal:{kind:'replace_exact',column:'Region'}},
  {...eligible,proposal:{kind:'trim_whitespace',column:'Other'}},
  {...eligible,affected_rows:0},
  {...eligible,kind:'identifier'}
 ])assert.equal(reviewableWhitespaceFinding({...snap,issues:[issue]},'p0',0,['Region']),null);
});
test('matching fitted values with different invisible boundary spaces are identified',()=>{
 assert.equal(hasWhitespaceCategoryCollision(['Gauteng',' Gauteng ','Mpumalanga']),true);
 assert.equal(hasWhitespaceCategoryCollision(['Gauteng','Mpumalanga']),false);
 assert.equal(hasWhitespaceCategoryCollision(['  ','','Mpumalanga']),false);
 assert.equal(hasWhitespaceCategoryCollision(['Gauteng','Gauteng']),false);
});
test('source data, exact raw labels, and issue objects are not mutated',()=>{
 const options=Object.freeze([' Gauteng ','Gauteng']);
 const finding=Object.freeze({...eligible});
 const source=Object.freeze({project_id:'p0',version:0,issues:Object.freeze([finding])});
 assert.equal(hasWhitespaceCategoryCollision(options),true);
 assert.equal(reviewableWhitespaceFinding(source,'p0',0,['Region']),finding);
 assert.deepEqual(options,[' Gauteng ','Gauteng']);
});
test('read-only component fetches current version and links to existing Quality approval without writes',()=>{
 const s=fs.readFileSync(path.resolve(__dirname,'../src/CategoryQualityReviewPrompt.tsx'),'utf8');
 assert.match(s,/get<CategoryQualitySnapshot>\(/);
 assert.match(s,/reviewableWhitespaceFinding\(snapshot,projectId,version,columns\)/);
 assert.match(s,/AbortController/);
 assert.match(s,/matched\.scopeKey!==scopeKey/);
 assert.match(s,/onReview\(\{projectId,version,column,kind:'whitespace'\}\)/);
 assert.doesNotMatch(s,/\bpost\s*\(|\/quality\/commit|\/quality\/proposals/);
});
test('Prepare and Predict offer only version-scoped read-only Quality navigation',()=>{
 const s=fs.readFileSync(path.resolve(__dirname,'../src/App.tsx'),'utf8');
 assert.match(s,/import \{CategoryQualityAdvice\} from '\.\/CategoryQualityReviewPrompt'/);
 assert.match(s,/import \{hasWhitespaceCategoryCollision\} from '\.\/categoryQualityAdvice'/);
 assert.match(s,/hasWhitespaceCategoryCollision\(f\.options\?\?\[\]\)/);
 assert.match(s,/setQualityFocus\(focus\);go\('quality'\)/);
 assert.match(s,/!embedded/);
 assert.match(s,/onReview=\{\(focus:QualityFocus\)=>/);
});

test('Quality offers a focused review for an automatic pending finding before any commit',()=>{
 const s=fs.readFileSync(path.resolve(__dirname,'../src/QualityWorkspace.tsx'),'utf8');
 assert.match(s,/\(issue\.decision==='pending'\|\|issue\.decision==='undone'\|\|issue\.decision==='rejected'\)&&issue\.proposal/);
 assert.match(s,/issue\.automatic\?'Review this correction':'Approve'/);
 assert.match(s,/onClick=\{\(\)=>void applyDecision\('approve'\)\}/);
 assert.match(s,/setPendingApproval\(\{proposal,message\}\)/);
 assert.match(s,/No correction has been applied/);
});
