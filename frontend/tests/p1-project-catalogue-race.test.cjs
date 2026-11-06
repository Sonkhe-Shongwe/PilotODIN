const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');
const filename=path.resolve(__dirname,'../src/projectCatalogRequestGuard.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{
  compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}
}).outputText;
const m=new Module(filename,module);m.filename=filename;m.paths=module.paths;m._compile(compiled,filename);
const {createProjectCatalogRequestGuard}=m.exports;
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return{promise,resolve,reject}};

test('latest request supersedes earlier request, even for the same project',()=>{
 const guard=createProjectCatalogRequestGuard();
 const first=guard.begin(),second=guard.begin();
 assert.equal(guard.accepts(first),false);
 assert.equal(guard.accepts(second),true);
 assert.equal(guard.accepts(0),false);
});

test('out-of-order successful project catalogues never replace a newer one',async()=>{
 const guard=createProjectCatalogRequestGuard(),slow=deferred(),fast=deferred();
 let displayed=['existing'];
 const run=async job=>{const id=guard.begin();const result=await job.promise;if(guard.accepts(id))displayed=result};
 const older=run(slow),newer=run(fast);
 fast.resolve(['recent','new project']);await newer;
 slow.resolve(['old snapshot']);await older;
 assert.deepEqual(displayed,['recent','new project']);
});

test('out-of-order catalogue rejection cannot overwrite current ready state',async()=>{
 const guard=createProjectCatalogRequestGuard(),slow=deferred(),fast=deferred();
 let state='loading';
 const run=async job=>{const id=guard.begin();try{await job.promise;if(guard.accepts(id))state='ready'}
   catch{if(guard.accepts(id))state='failed'}};
 const older=run(slow),newer=run(fast);
 fast.resolve([]);await newer;
 slow.reject(new Error('stale offline response'));await older;
 assert.equal(state,'ready');
});

test('failed newest request does not allow an older success to replace its result',async()=>{
 const guard=createProjectCatalogRequestGuard(),slow=deferred(),fast=deferred();
 let state='ready',rows=['known'];
 const run=async job=>{const id=guard.begin();try{const result=await job.promise;if(guard.accepts(id)){rows=result;state='ready'}}
   catch{if(guard.accepts(id))state='error'}};
 const older=run(slow),newer=run(fast);
 fast.reject(new Error('offline'));await newer;
 slow.resolve(['stale selection']);await older;
 assert.equal(state,'error');
 assert.deepEqual(rows,['known']);
});

test('invalidation before any request never accepts an unissued token',()=>{
 const guard=createProjectCatalogRequestGuard();
 guard.invalidate();
 assert.equal(guard.accepts(1),false);
 const actual=guard.begin();
 assert.equal(guard.accepts(actual),true);
});

test('unmount invalidation excludes all in-flight completions',()=>{
 const guard=createProjectCatalogRequestGuard();
 const id=guard.begin();guard.invalidate();
 assert.equal(guard.accepts(id),false);
 assert.equal(guard.accepts(guard.begin()),true);
});

test('guards are isolated to each shell, with no stored project or data identifiers',()=>{
 const a=createProjectCatalogRequestGuard(),b=createProjectCatalogRequestGuard();
 const old=a.begin(),newer=a.begin(),own=b.begin();
 assert.equal(a.accepts(old),false);
 assert.equal(a.accepts(newer),true);
 assert.equal(b.accepts(own),true);
 assert.deepEqual(Object.keys(a).sort(),['accepts','begin','invalidate']);
});

test('UnifiedShell gates both late success and late error before altering project state',()=>{
 const s=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(s,/import \{createProjectCatalogRequestGuard\} from '\.\/projectCatalogRequestGuard'/);
 assert.match(s,/const catalogRequests=useRef\(createProjectCatalogRequestGuard\(\)\)/);
 assert.match(s,/const requestId=catalogRequests\.current\.begin\(\)/);
 assert.match(s,/const rows=await get<ProjectListItem\[\]>\('\/projects'\);\s+if\(!catalogRequests\.current\.accepts\(requestId\)\)return;\s+setProjects\(rows\)/);
 assert.match(s,/catch\(e\)\{\s+if\(!catalogRequests\.current\.accepts\(requestId\)\)return;/);
 assert.match(s,/useEffect\(\(\)=>\(\)=>catalogRequests\.current\.invalidate\(\),\[\]\)/);
 assert.match(s,/shouldClearUnavailableProject\(selectedAtRequestStart,latest,rows\)/);
 assert.match(s,/setCatalogState\(previous=>previous==='ready'\?'ready':'failed'\)/);
});
