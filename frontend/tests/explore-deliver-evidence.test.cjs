const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'../src',name),'utf8');
const saved=read('SavedExploreAnalyses.tsx');
const explore=read('ExploreWorkspace.tsx');
const app=read('App.tsx');
const deliver=read('ReportWorkspace.tsx');

test('Explore sends only a real saved snapshot ID to Deliver',()=>{
 assert.match(saved,/onSendToDeliver\?\:\(id:string\)=>void/);
 assert.match(saved,/Use verified evidence in Deliver/);
 assert.match(saved,/onSendToDeliver\(selected\.id\)/);
 assert.match(explore,/onSendToDeliver=\{onSendToDeliver\}/);
 assert.match(app,/onSendToDeliver=\{snapshotId=>\{if\(\/\^\[a-f0-9\]\{32\}\$\/\.test\(snapshotId\)\)/);
 assert.match(app,/setDeliverEvidenceId\(snapshotId\);go\('deliver'\)/);
 assert.match(app,/setDeliverEvidenceId\(null\)/);
});

test('Deliver scopes the selected saved snapshot to server-listed verified project evidence',()=>{
 assert.match(app,/preselectEvidenceId=\{deliverEvidenceId\}/);
 assert.match(deliver,/preselectEvidenceId=null/);
 assert.match(deliver,/projectEvidence\.find\(item=>item\.id===preselectEvidenceId\)/);
 assert.match(deliver,/This saved analysis is not available as verified evidence in the active project/);
 assert.match(deliver,/userStartedDraft\.current=true/);
 assert.match(deliver,/setActiveId\(null\);setOpened\(null\);setRevision\(null\)/);
 assert.match(deliver,/setSelected\(\[preselectEvidenceId\]\)/);
});

test('old versions remain visibly labelled and selected report revisions never change silently',()=>{
 assert.match(deliver,/e\.stale\?' · HISTORICAL'/);
 assert.match(deliver,/Saved Explore investigation/);
 assert.match(deliver,/saved revision/i);
 assert.match(saved,/HISTORICAL SNAPSHOT/);
});
