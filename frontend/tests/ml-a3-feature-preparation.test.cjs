const{test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'../src',name),'utf8');
const app=read('App.tsx'),api=read('api.ts'),css=read('studio.css');

test('Prepare binds feature-advice identity to the current selection before showing risk hints',()=>{
 const scope=read('featureHintScope.ts');
 assert.match(scope,/snapshot\.projectId===projectId&&snapshot\.target===target&&/);
 assert.match(scope,/snapshot\.version===version\?snapshot\.features:\[\]/);
 assert.match(app,/const \[featureHintSnapshot,setFeatureHintSnapshot\]=useState<ScopedFeatureHints\|null>\(null\)/);
 assert.match(app,/const featureHints=visibleFeatureHints\(featureHintSnapshot,project\?\.id,target,qualityVersion\)/);
 assert.match(app,/setFeatureHintSnapshot\(\{\.\.\.requested,features:r\.features\}\)/);
 assert.match(app,/if\(live\)setFeatureHintSnapshot\(null\)/);
 assert.doesNotMatch(app,/setFeatureHints\(/);
});

test('Prepare exposes server-derived per-feature treatments rather than guessing model importance',()=>{
 assert.match(api,/export type FeatureAudit = \{column:string/);
 assert.match(api,/high_risk_features:string\[\]/);
 assert.match(app,/Feature-by-feature preparation audit/);
 assert.match(app,/prep\.feature_audit\.map\(f=>/);
 assert.match(app,/f\.missing_pct/);
 assert.match(app,/f\.treatment/);
 assert.match(app,/f\.reasons\.join\('; '\)/);
 assert.match(app,/Excluded as split key/);
 assert.match(app,/!f\.default_included\?'Unusable \/ excluded'/);
 assert.match(app,/INCLUDED PREDICTORS/);
 assert.match(css,/\.po-ml-feature-audit\{max-height:390px/);
});

test('high-risk predictors need a user decision in both UI and backend request',()=>{
 assert.match(app,/const \[acknowledgeFeatureRisks,setAcknowledgeFeatureRisks\]=useState\(false\)/);
 assert.match(app,/const unresolvedFeatureRisks=\(prep\?\.high_risk_features\?\?\[\]\)\.filter/);
 assert.match(app,/setAcknowledgeFeatureRisks\(false\).*\[project\?\.id,target,qualityVersion,excluded,splitStrategy,splitColumn\]/);
 assert.match(app,/acknowledge_feature_risks:acknowledgeFeatureRisks/);
 assert.match(app,/Review required: \{unresolvedFeatureRisks.length\} included high-risk predictors/);
 assert.match(app,/!acknowledgeFeatureRisks\)\|\|busy==='train'/);
 assert.match(app,/I deliberately accept their inclusion in this experiment/);
});

test('Prepare previews an additive exclusion diff and requires an explicit second click',()=>{
 assert.match(app,/const \[reviewHighRiskExclusions,setReviewHighRiskExclusions\]=useState\(false\)/);
 assert.match(app,/const pendingHighRiskExclusions=highRiskExclusionCandidates\.filter/);
 assert.match(app,/Will additionally exclude \(\{pendingHighRiskExclusions\.length\}\)/);
 assert.match(app,/Already excluded, kept unchanged \(\{excluded\.length\}\)/);
 assert.match(app,/Included predictors: \{includedNow\} before, \{includedAfterReview\} after/);
 assert.match(app,/if\(!prep\|\|!reviewHighRiskExclusions\)return/);
 assert.match(app,/setReviewHighRiskExclusions\(false\).*\[project\?\.id,target,qualityVersion\]/);
});

test('suggested exclusions never remove manual exclusions and temporal guard is visible',()=>{
 assert.match(app,/setExcluded\(current=>\[\.\.\.new Set\(\[\.\.\.current,/);
 assert.match(app,/Identical timestamps at a train\/test boundary are rejected/);
 assert.match(app,/go\('evaluate'\);\s*setNotice\('Model selected\. Review held-out evaluation results/);
});
