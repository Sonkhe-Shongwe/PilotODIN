const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const file=p=>fs.readFileSync(path.join(__dirname,'../src',p),'utf8');
const shell=file('UnifiedShell.tsx'),manager=file('ProjectManager.tsx'),studio=file('App.tsx');
test('new independent Manage projects control opens the accessible dialog',()=>{
 assert.match(shell,/aria-label="Manage projects"/);
 assert.match(shell,/projectManagerOpen&&<ProjectManager/);
 assert.match(manager,/role="dialog" aria-modal="true"/);
});
test('only revision-bound reversible metadata changes, no permanent delete',()=>{
 assert.match(manager,/get<ManagedProject\[]>\('\/projects\/manage'\)/);
 assert.match(manager,/put<ManagedProject>/);
 assert.match(manager,/expected_revision:project.revision/);
 assert.doesNotMatch(manager,/\bdelete\s*\(/i);
});
test('active project archive blocked while archived project can be restored',()=>{
 assert.match(manager,/project.id===currentProjectId/);
 assert.match(manager,/busy\|\|current/);
 assert.match(manager,/change\(p,'restore'\)/);
});
test('escape keyboard focus containment and return, no active Studio reload',()=>{
 assert.match(manager,/e.key==='Escape'/);
 assert.match(manager,/e.key!=='Tab'/);
 assert.match(manager,/opener\?\.isConnected\)opener.focus\(\)/);
 assert.match(studio,/pilotodin:project-metadata-changed/);
 assert.match(studio,/setProject\(old=>old\?\.id===id/);
});
