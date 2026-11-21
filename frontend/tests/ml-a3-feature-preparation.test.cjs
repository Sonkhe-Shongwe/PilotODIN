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
 assert.match(app,/r\.version===requested\.version\?\{\.\.\.requested,features:r\.features\}:null/);
 assert.match(app,/if\(live\)setFeatureHintSnapshot\(null\)/);
 assert.doesNotMatch(app,/setFeatureHints\(/);
});

test('Prepare and advice are version-pinned and refuse wrong response revisions',()=>{
 assert.match(api,/export type Prep = \{quality_version:number;task:/);
 assert.match(app,/preparation\?target=\$\{encodeURIComponent\(target\)\}&expected_version=\$\{qualityVersion\}/);
 assert.match(app,/if\(!active\|\|p\.quality_version!==qualityVersion\|\|p\.target!==target\)return/);
 assert.match(app,/features\?target=\$\{encodeURIComponent\(requested\.target\)\}&expected_version=\$\{requested\.version\}/);
 assert.match(app,/r\.version===requested\.version\?\{\.\.\.requested,features:r\.features\}:null/);
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

test('selected predictor budget updates with current exclusions and retains backend authority',()=>{
 const helper=read('selectedFeatureBudget.ts');
 assert.match(app,/selectedFeatureBudget\(prep\.feature_audit,prep\.resource_plan,excluded,splitStrategy,splitColumn,categoricalImputation\)/);
 assert.match(app,/const modelBudgetExceeded=rowBudgetExceeded\|\|!!selectedBudget\?\.denseLimitExceeded/);
 assert.match(app,/selectedBudget\.estimatedEncodedColumns\.toLocaleString\(\)/);
 assert.match(app,/selectedBudget\?\.encodedColumnsByField\.get\(f\.column\)/);
 assert.match(helper,/Math\.min\(25, field\.distinct \+ Number\(missingMarker\)\)/);
 assert.match(helper,/denseLimitExceeded: !safe \|\| width===0 \|\| bytes >/);
});


test('numeric imputation choice is version-reset, user-selectable and persists into experiment request',()=>{
 const engine=fs.readFileSync(path.join(__dirname,'../../backend/engine.py'),'utf8');
 const backend=fs.readFileSync(path.join(__dirname,'../../backend/main.py'),'utf8');
 assert.match(app,/const \[numericImputation,setNumericImputation\]=useState<'median'\|'mean'>\('median'\)/);
 assert.match(app,/setNumericImputation\('median'\);setCategoricalImputation\('most_frequent'\);if\(!project\|\|!target\)/);
 assert.match(app,/aria-label="Numeric imputation method"/);
 assert.match(app,/numeric_imputation:numericImputation/);
 assert.match(app,/f\.kind==='numeric'\?`Numeric: \${numericImputation} imputation/);
 assert.match(backend,/numeric_imputation: Literal\['median','mean'\] = 'median'/);
 assert.match(backend,/"numeric_imputation":body\.numeric_imputation/);
 assert.match(backend,/numeric_imputation=config\.get\("numeric_imputation", "median"\)/);
 assert.match(engine,/SimpleImputer\(strategy=numeric_imputation, keep_empty_features=True\)/);
 assert.match(engine,/make_pipeline\(X_train,task,models\[0\],numeric_imputation,categorical_imputation\)/);
 assert.match(engine,/make_pipeline\(X_train,task,key,numeric_imputation,categorical_imputation\)/);
});

test('categorical marker option is scoped, allowlisted and wired into both fold pipelines',()=>{
  const engine=fs.readFileSync(path.join(__dirname,'../../backend/engine.py'),'utf8');
  const backend=fs.readFileSync(path.join(__dirname,'../../backend/main.py'),'utf8');
  assert.match(app,/setCategoricalImputation\('most_frequent'\);if\(!project\|\|!target\)/);
  assert.match(app,/aria-label="Categorical imputation method"/);
  assert.match(app,/categorical_imputation:categoricalImputation/);
  assert.match(backend,/categorical_imputation: Literal\['most_frequent','constant'\] = 'most_frequent'/);
  assert.match(backend,/"categorical_imputation":body\.categorical_imputation/);
  assert.match(backend,/categorical_imputation=config\.get\("categorical_imputation", "most_frequent"\)/);
  assert.match(engine,/check_categorical_missing_marker\(X, categorical_imputation\)/);
  assert.match(engine,/fill_value=CATEGORICAL_MISSING_MARKER if categorical_imputation == "constant" else None/);
  assert.match(engine,/make_pipeline\(X_train,task,models\[0\],numeric_imputation,categorical_imputation\)/);
  assert.match(engine,/make_pipeline\(X_train,task,key,numeric_imputation,categorical_imputation\)/);
});

test('Evaluate and Predict display saved preprocessing provenance rather than current Prepare draft',()=>{
  const section=app.slice(app.indexOf('function RecordedExperimentPreprocessing('),app.indexOf('/** A one-use, memory-only snapshot'));
  assert.match(section,/experiment\.config\.numeric_imputation/);
  assert.match(section,/experiment\.config\.categorical_imputation/);
  assert.match(section,/experiment\.config\.quality_version/);
  assert.match(section,/numeric===undefined\?'Median \(legacy default; not recorded\)'/);
  assert.match(section,/categorical===undefined\?'Mode \(legacy default; not recorded\)'/);
  assert.match(section,/not the current Prepare draft or independent proof of a fitted model/);
  assert.match(section,/aria-label="Recorded experiment preprocessing"/);
  const matches=app.match(/<RecordedExperimentPreprocessing experiment=\{experiment\}\/>/g)||[];
  assert.equal(matches.length,2);
  assert.match(app,/page==='evaluate'[\s\S]*?<RecordedExperimentPreprocessing experiment=\{experiment\}\/>/);
  assert.match(app,/page==='predict'&&experiment\?\.selected_model&&experiment\.results&&!stale&&<RecordedExperimentPreprocessing/);
});
