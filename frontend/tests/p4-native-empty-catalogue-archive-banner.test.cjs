const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const Module=require('node:module');

const filename=path.resolve(__dirname,'../src/projectLifecycleSignal.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{
 compilerOptions:{target:ts.ScriptTarget.ES2021,module:ts.ModuleKind.CommonJS}
}).outputText;
const m=new Module(filename,module);m.filename=filename;m.paths=module.paths;
m._compile(compiled,filename);
const {isCurrentProjectHeldArchived,preserveMountedUnavailableProject}=m.exports;

test('empty no-project startup cannot report phantom external archive',()=>{
 assert.equal(isCurrentProjectHeldArchived('',''),false);
 assert.equal(isCurrentProjectHeldArchived('','a'.repeat(32)),false);
 assert.equal(isCurrentProjectHeldArchived('a'.repeat(32),''),false);
});

test('only the same non-empty mounted project can retain genuine archive warning',()=>{
 const a='a'.repeat(32),b='b'.repeat(32);
 assert.equal(isCurrentProjectHeldArchived(a,a),true);
 assert.equal(isCurrentProjectHeldArchived(a,b),false);
 assert.equal(preserveMountedUnavailableProject(a,a,a,true),true);
 assert.equal(preserveMountedUnavailableProject(a,a,a,false),false);
});

test('refreshProjects uses non-empty guard for both normal and unavailable catalogue paths',()=>{
 const source=fs.readFileSync(path.resolve(__dirname,'../src/UnifiedShell.tsx'),'utf8');
 assert.match(source,/const mountedIsHeldArchived=isCurrentProjectHeldArchived\(mountedId,heldArchivedRef\.current\)/);
 assert.match(source,/preserveMountedUnavailableProject\(mountedId,latest,selectedAtRequestStart,\s*mountedIsHeldArchived\)/);
 assert.equal((source.match(/setWarning\(mountedIsHeldArchived/g)||[]).length,2);
 assert.doesNotMatch(source,/heldArchivedRef\.current===mountedId/);
});
