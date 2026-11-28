const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../src/ColumnInvestigation.tsx'),'utf8');
const app=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
const css=fs.readFileSync(path.join(__dirname,'../src/column-investigation.css'),'utf8');

test('Your data includes the dedicated full column investigator in place of shallow table',()=>{
 assert.match(app,/import \{ColumnInvestigation\} from '\.\/ColumnInvestigation'/);
 assert.match(app,/<ColumnInvestigation key=\{project\.id\} projectId=\{project\.id\} versionToken=\{qualityVersion\}\/>/);
 assert.doesNotMatch(app,/<h2>Column intelligence<\/h2>/);
});

test('dictionary exposes physical dtype and explicitly provisional analytical role',()=>{
 assert.match(src,/STORED DTYPE/);
 assert.match(src,/ANALYTICAL ROLE/);
 assert.match(src,/Stored dtype/);
 assert.match(src,/role_explanation/);
 assert.match(src,/Date-like and numeric-like strings remain text/);
 assert.match(src,/Sort columns/);
 assert.match(src,/Search columns by name or type/);
});

test('column drill-down is version-aware, bounded and does not mutate source data',()=>{
 assert.match(src,/get<Dictionary>\(\`\/projects\/\$\{projectId\}\/columns\/overview\`\)/);
 assert.match(src,/expected_version=\$\{dictionary\.version\}/);
 assert.match(src,/setDictionary\(null\);setDetail\(null\);setSelected\(''\)/);
 assert.match(src,/if\(data\.version!==dictionary\.version\)/);
 assert.match(src,/sample_rows/);
 assert.match(src,/invalid_or_nonfinite/);
 assert.doesNotMatch(src,/post<|put<|deleteRequest/);
});

test('responsive inspector supports row examples and consistent focus states',()=>{
 assert.match(src,/Most frequent values/);
 assert.match(src,/Numerical profile/);
 assert.match(src,/Source-order sample/);
 assert.match(src,/aria-pressed=\{selected===col\.name\}/);
 assert.match(css,/@media\(max-width:1050px\)/);
 assert.match(css,/\.po-col-field:focus-visible/);
});
