const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../src/ReportWorkspace.tsx'),'utf8');

test('Report open responses are tagged with a monotonically newer request ticket',()=>{
 assert.match(src,/const latestOpenRequest=useRef\(0\)/);
 assert.match(src,/async function openReport\(id:string,number\?:number\)\{[\s\S]*?composerGuard\.current\.navigate\(\);\s*const ticket=\+\+latestOpenRequest\.current/);
 assert.match(src,/if\(ticket!==latestOpenRequest\.current\)return;/);
});

test('Superseded Open failures and finalizers do not overwrite current UI state',()=>{
 assert.match(src,/catch\(e\)\{if\(ticket===latestOpenRequest\.current\)setError/);
 assert.match(src,/finally\{if\(ticket===latestOpenRequest\.current\)setBusy\(''\)\}/);
 assert.match(src,/setActiveId\(id\);setOpened\(data\);setRevision\(data\.revision\)/);
});

test('New report, project switch, and explicit Explore evidence handoff invalidate pending opens',()=>{
 assert.match(src,/function newReport\(\)\{[\s\S]*?composerGuard\.current\.navigate\(\);latestOpenRequest\.current\+\+;setBusy\(''\)/);
 assert.match(src,/let mounted=true;composerGuard\.current\.resetProject\(\);readGuard\.current\.invalidateAll\(\);latestReportList\.current\+\+;latestOpenRequest\.current\+\+;/);
 assert.match(src,/return\(\)=>\{mounted=false;composerGuard\.current\.resetProject\(\);readGuard\.current\.invalidateAll\(\);latestReportList\.current\+\+;latestOpenRequest\.current\+\+\}/);
 // The existing saved-preview invalidation is part of this navigation sequence.
 assert.match(src,/appliedHandoff\.current=preselectEvidenceId;\s*readGuard\.current\.invalidatePreview\(\);setSavedPreview\(null\);setPreviewBusy\(false\);setPreviewError\(''\);\s*latestOpenRequest\.current\+\+;composerGuard\.current\.navigate\(\);setBusy\(''\)/);
});

test('Revision ordering, immutable saved exports and explicit target project evidence remain unchanged',()=>{
 assert.match(src,/\?revision=\$\{number\}/);
 assert.match(src,/userStartedDraft\.current=true/);
 assert.match(src,/hasDraftChanges/);
 assert.match(src,/projectEvidence\.find\(item=>item\.id===preselectEvidenceId\)/);
 assert.match(src,/saveReportNative\(blob,filename,format\)/);
});
