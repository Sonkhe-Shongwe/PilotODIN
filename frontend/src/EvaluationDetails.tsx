import {Activity,AlertTriangle,BarChart3,CheckCircle2,ShieldAlert} from 'lucide-react';
import type {Experiment} from './api';
type ClassRow={label:string|number;precision:number;recall:number;f1:number;support:number};
type Sample={actual:string|number;predicted:string|number};
type Eval={accuracy?:number;f1_macro?:number;precision_macro?:number;recall_macro?:number;roc_auc?:number;mae?:number;rmse?:number;r2?:number;class_labels?:(string|number)[];class_report?:ClassRow[];confusion_matrix?:number[][];evaluation_rows?:Sample[];reliability?:{level:string;issues:string[];message:string};sample_count?:number;baseline_test_metric?:number;baseline_test_label?:string;baseline_test_reference?:string;beats_heldout_baseline?:boolean;baseline_test_note?:string;baseline_cv?:number;cv_score?:number};
const pct=(n:number|undefined)=>n===undefined?'—':(n*100).toFixed(1)+'%';
const num=(n:number|undefined)=>n===undefined?'—':n.toLocaleString(undefined,{maximumFractionDigits:3});
function Card({name,value,description}:{name:string;value:string;description:string}){return <div className="eval-card"><small>{name}</small><strong>{value}</strong><span>{description}</span></div>}
export function EvaluationDetails({experiment}:{experiment:Experiment}){
  if(!experiment.final_results||!experiment.results)return null;
  const r=experiment.final_results as unknown as Eval;const classification=experiment.results.task==='classification';
  const rows=r.evaluation_rows??[];const numeric=rows.map(v=>({actual:Number(v.actual),predicted:Number(v.predicted)})).filter(v=>Number.isFinite(v.actual)&&Number.isFinite(v.predicted));
  const min=Math.min(...numeric.flatMap(v=>[v.actual,v.predicted]),0);const max=Math.max(...numeric.flatMap(v=>[v.actual,v.predicted]),1);
  const position=(v:number)=>35+(v-min)/(max-min||1)*310;
  return <section className="panel evaluate-panel">
    <div className="panel-title"><BarChart3 size={19}/><h2>Held-out test report</h2><span className="pill">{r.sample_count??experiment.results.test_rows} observations</span></div>
    {r.reliability?.issues?.length?<div className="reliability-warning" role="alert"><ShieldAlert size={23}/><div><strong>Model reliability warning</strong><p>Do not interpret the selected model as reliable simply because it ranked first.</p><ul>{r.reliability.issues.map((w,i)=><li key={i}>{w}</li>)}</ul></div></div>:<div className="mini-info"><CheckCircle2 size={16}/> Preliminary result. Validate with independent data before deploying.</div>}
    <div className="po-ml-heldout-baseline" role="region" aria-label="Holdout comparison to simple baseline">
      <h3>Selected model versus a simple held-out baseline</h3>
      {r.baseline_test_metric!==undefined?<><div className="po-ml-baseline-row">
        <div><small>Selected model · {classification?'Macro F1 (higher is better)':'MAE (lower is better)'}</small><strong>{classification?pct(r.f1_macro):num(r.mae)}</strong></div>
        <div><small>Simple baseline · {r.baseline_test_label??'same metric'}</small><strong>{classification?pct(r.baseline_test_metric):num(r.baseline_test_metric)}</strong></div>
        <div><small>Comparison on untouched holdout</small><strong>{r.beats_heldout_baseline?'Outperformed baseline':'Did not outperform baseline'}</strong></div>
      </div><p className="muted-caption">Baseline prediction: {r.baseline_test_reference}. Its constant prediction came from development-training targets only. Both results were scored on the same held-out rows after model selection; this comparison did not determine the winning model.</p></>:
      <p className="muted-caption">{r.baseline_test_note??'No training-derived held-out baseline is available for this experiment.'}</p>}
      <p className="muted-caption">Development cross-validation and held-out evaluation answer different questions. A single test result does not establish production performance or fairness.</p>
    </div>
    {classification?<>
      <div className="eval-metrics"><Card name="Accuracy" value={pct(r.accuracy)} description="Share of test predictions correct"/><Card name="Macro F1" value={pct(r.f1_macro)} description="Balances precision and recall across classes"/><Card name="Precision" value={pct(r.precision_macro)} description="How often predicted classes are correct"/><Card name="Recall" value={pct(r.recall_macro)} description="How often actual classes were found"/></div>
      {r.confusion_matrix&&<><h3>Confusion matrix</h3><p className="body-muted">Rows are actual outcomes; columns are predicted outcomes. The diagonal contains correct predictions.</p><div className="table-scroll"><table className="confusion-table"><thead><tr><th>Actual ↓ / Predicted →</th>{r.class_labels?.map((c,i)=><th key={i}>{String(c)}</th>)}</tr></thead><tbody>{r.confusion_matrix.map((row,i)=><tr key={i}><th>{String(r.class_labels?.[i]??i)}</th>{row.map((n,j)=><td className={i===j?'confusion-correct':''} key={j}>{n}</td>)}</tr>)}</tbody></table></div></>}
      {r.class_report&&<><h3>Performance by class</h3><div className="table-scroll"><table><thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th><th>Cases</th></tr></thead><tbody>{r.class_report.map((c,i)=><tr key={i}><td>{String(c.label)}</td><td>{pct(c.precision)}</td><td>{pct(c.recall)}</td><td>{pct(c.f1)}</td><td>{c.support}</td></tr>)}</tbody></table></div></>}
    </>:<>
      <div className="eval-metrics"><Card name="Mean absolute error" value={num(r.mae)} description="Typical absolute error in the target's units"/><Card name="Root mean squared error" value={num(r.rmse)} description="Penalises large errors more"/><Card name="R² score" value={num(r.r2)} description="Explained variance measure; NOT accuracy"/></div>
      {numeric.length>0&&<div className="actual-predicted"><h3>Actual vs predicted values</h3><p className="body-muted">Points closer to the diagonal indicate more accurate numeric predictions. Display limited to 120 test cases.</p><svg viewBox="0 0 400 400" aria-label="Actual versus predicted scatterplot" role="img"><line x1="35" y1="345" x2="345" y2="35" stroke="#b1c2c9" strokeDasharray="7 6"/><line x1="35" y1="345" x2="345" y2="345" stroke="#9fb2bb"/><line x1="35" y1="35" x2="35" y2="345" stroke="#9fb2bb"/>{numeric.map((v,i)=><circle key={i} cx={position(v.actual)} cy={380-position(v.predicted)} r="4" fill="#268975" opacity=".55"><title>{`Actual ${v.actual}, predicted ${v.predicted}`}</title></circle>)}<text x="200" y="383" textAnchor="middle" fontSize="12">Actual {experiment.results.target}</text><text x="14" y="200" textAnchor="middle" transform="rotate(-90 14 200)" fontSize="12">Predicted</text></svg></div>}
    </>}
    <div className="mini-info"><AlertTriangle size={16}/> Only {r.sample_count??experiment.results.test_rows} test observations; this evaluation is not a guarantee of future accuracy. Training, validation and test data were separated.</div>
  </section>;
}
