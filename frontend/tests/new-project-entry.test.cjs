const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const shell=fs.readFileSync(path.join(__dirname,'../src/UnifiedShell.tsx'),'utf8');
const studio=fs.readFileSync(path.join(__dirname,'../src/App.tsx'),'utf8');
const styles=fs.readFileSync(path.join(__dirname,'../src/unified-shell.css'),'utf8');

test('header distinguishes switching existing projects from importing a new one',()=>{
 assert.match(shell,/aria-label="Switch project"/);
 assert.match(shell,/<option value="" disabled>/);
 assert.match(shell,/className="po-new-project-action"/);
 assert.match(shell,/aria-label="New project: import dataset"/);
 assert.match(shell,/setNewProjectOpen\(true\);navigate\('overview'\)/);
 assert.match(shell,/forceNewProject=\{newProjectOpen&&active==='overview'\}/);
 assert.match(shell,/onNewProjectClose=\{\(\)=>setNewProjectOpen\(false\)\}/);
});

test('new-project request reuses the existing uploader and preserves old data until upload',()=>{
 assert.match(studio,/forceNewProject=false,onNewProjectClose/);
 assert.match(studio,/const showUpload=uploadOpen\|\|\(!embedded&&forceNewProject\)/);
 assert.match(studio,/\(\(!project&&page!=='ai_settings'\)\|\|showUpload\)/);
 assert.match(studio,/project&&!showUpload&&page!=='ai_settings'/);
 assert.match(studio,/const data=await upload\(file\);await refreshProjects\(\);await loadProject\(data.id\)/);
 assert.match(studio,/onNewProjectClose\?\.\(\)/);
});

test('new-project action supports compact headers and keyboard focus',()=>{
 assert.match(styles,/\.po-new-project-action:focus-visible/);
 assert.match(styles,/@media\(max-width:980px\)/);
 assert.match(styles,/\.po-new-project-action span\{display:none\}/);
});
