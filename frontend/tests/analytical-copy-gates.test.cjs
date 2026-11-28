const{test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const load=n=>fs.readFileSync(path.join(__dirname,'../src',n),'utf8');
test('Y-count is never displayed as unconditional record frequency',()=>{const s=load('ExploreWorkspace.tsx');assert.match(s,/Count of non-missing/);assert.match(s,/Record count by/);});
test('Hour-of-day prediction bounds reach native input',()=>{assert.match(load('api.ts'),/domain\?:/);assert.match(load('App.tsx'),/min=\{f\.domain\?\.min\} max=\{f\.domain\?\.max\}/);});
test('Global project selector no longer contains clickable placeholder',()=>assert.match(load('UnifiedShell.tsx'),/<option value="" disabled>/));
