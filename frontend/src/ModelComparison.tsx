import type {Results} from './api';
export function ModelComparison({results}:{results:Results}){
  const scores=results.models.filter(m=>m.status==='ready'&&typeof m.cv_metric==='number');
  const classification=results.task==='classification';
  const largest=Math.max(1,...scores.map(m=>Math.abs(m.cv_metric??0)),Math.abs(results.baseline_cv));
  const entries=[{key:'baseline',name:'Simple baseline',cv_metric:results.baseline_cv},...scores];
  const regressionBaseline=Math.abs(results.baseline_cv)||1;
  const bar=(score:number)=>classification?Math.min(100,Math.max(0,score/largest*100)):
    Math.min(100,Math.max(0,(results.baseline_cv-score)/regressionBaseline*100));
  return <div className="model-compare"><h3>How the models compare</h3><p className="body-muted">{classification?'Macro F1: higher is better. Percentage is not overall accuracy.':'Mean Absolute Error: lower is better. Bars show percentage reduction in error relative to the simple baseline; labels show actual MAE.'} Selection uses development folds, not the final test set.</p>
    {entries.map(m=><div key={m.key} className={'model-comparison-row '+(m.key==='baseline'?'baseline':'')}><div className="comparison-label" title={m.name}>{m.name}</div><div className="comparison-track"><span style={{width:`${bar(m.cv_metric??0)}%`}}/></div><strong>{classification?`${((m.cv_metric??0)*100).toFixed(1)}%`:(m.cv_metric??0).toLocaleString(undefined,{maximumFractionDigits:2})}</strong></div>)}
  </div>;
}
