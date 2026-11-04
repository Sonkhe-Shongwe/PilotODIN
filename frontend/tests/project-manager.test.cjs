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

test('read-only impact review is pinned to project revision with no destructive call',()=>{
 assert.match(manager,/deletion-impact\?expected_revision=/);
 assert.match(manager,/get<DeletionImpact>/);
 assert.match(manager,/result\.preview_only!==true\|\|result\.deletion_available!==false/);
 assert.match(manager,/role="region" aria-label="Deletion impact review"/);
 assert.match(manager,/Permanent deletion is unavailable/);
 assert.match(manager,/onClick=\{\(\)=>void review\(p\)\}/);
 assert.doesNotMatch(manager,/DELETE|method:'DELETE'|deleteProject|purgeProject/);
});

test('remote lifecycle signal has no personal data; backend verification precedes UI updates',()=>{
 const code=file('projectLifecycleSignal.ts');
 assert.match(code,/Object\.keys\(v\)\.sort\(\)/);
 assert.match(code,/Number\.isSafeInteger/);
 assert.match(code,/PROJECT_LIFECYCLE_SIGNAL_KEY/);
 assert.match(code,/preserveMountedUnavailableProject/);
 assert.match(shell,/get<ManagedProject\[]>\('\/projects\/manage'\)/);
 assert.match(shell,/row\.revision<signal\.revision/);
 assert.match(shell,/heldArchivedRef\.current=isArchived\?row\.id:''/);
 assert.match(shell,/publishProjectLifecycleSignal/);
 assert.match(shell,/preserveMountedUnavailableProject/);
 assert.match(shell,/Archived in another window \(restore to continue\)/);
 assert.match(shell,/Your unsaved fields remain visible here/);
 assert.doesNotMatch(code,/dataset_path|profile|original_source|setItem\([^)]*filename/);
});
