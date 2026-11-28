const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=file=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8');
const evaluation=read('EvaluationDetails.tsx');
const app=read('App.tsx');
const css=read('studio.css');

test('held-out comparison has separate frozen simple-baseline and model results',()=>{
  assert.match(evaluation,/Selected model versus a simple held-out baseline/);
  assert.match(evaluation,/baseline_test_metric/);
  assert.match(evaluation,/beats_heldout_baseline/);
  assert.match(evaluation,/Did not outperform baseline/);
  assert.match(evaluation,/this comparison did not determine the winning model/);
  assert.match(evaluation,/Legacy experiment|Legacy|No training-derived held-out baseline/i);
  assert.match(css,/\.po-ml-heldout-baseline/);
});

test('reopened model requires inspection of evaluation before Predict',()=>{
  const from=app.indexOf('async function reopenExperiment(');
  const to=app.indexOf('useEffect(()=>{setPredictVals(',from);
  assert.ok(from>=0&&to>from);
  const block=app.slice(from,to);
  assert.match(block,/go\('evaluate'\)/);
  assert.doesNotMatch(block,/go\(exp\.selected_model\?'predict':'evaluate'\)/);
  assert.match(app,/Model selected\. Review held-out evaluation results before proceeding to Predict Studio/);
  assert.match(app,/Open Predict Studio/);
});

test('prediction UI discloses lack of class-probability calibration',()=>{
  assert.match(app,/probability_estimates_calibrated\?:boolean/);
  assert.match(app,/prediction\.probability_estimates_calibrated!==true/);
  assert.match(app,/probability estimates are not independently calibrated/i);
  assert.match(app,/prediction\.input_warnings\?\.map/);
  assert.match(css,/\.po-ml-uncalibrated/);
});
