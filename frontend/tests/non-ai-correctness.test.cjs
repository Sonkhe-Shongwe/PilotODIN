const{test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const read=(n)=>fs.readFileSync(path.join(__dirname,'../src',n),'utf8');
test('Model selection requires held-out evaluation first',()=>{const a=read('App.tsx');const s=a.slice(a.indexOf('async function chooseModel'),a.indexOf('async function runPrediction'));assert.match(s,/go\('evaluate'\)/);assert.doesNotMatch(s,/go\('predict'\)/)});
test('Manually excluded fields remain excluded when high-risk suggestions are applied',()=>{
 const app=read('App.tsx');
 // Preserve existing user exclusions, merge backend flags, then append only
 // frontend high-risk hints that are actual features. Never replace the list.
 assert.match(app,/setExcluded\(current=>\[\.\.\.new Set\(\[\.\.\.current,\.\.\.prep\.high_risk_features,/);
 assert.match(app,/\.\.\.featureHints\.filter\(f=>f\.risk==='high'\)\.map\(f=>f\.column\)\.filter\(column=>prep\.available_features\.includes\(column\)\)/);
});
test('Verified ties and numeric chart axis',()=>{const s=read('InvestigationCanvas.tsx');assert.match(s,/tiedLeaders\.length>1/);assert.match(s,/Equal medians do not establish equal distributions/);assert.match(s,/on a numeric axis/);assert.doesNotMatch(s,/<span>100%<\/span><span>75%<\/span>/)});
