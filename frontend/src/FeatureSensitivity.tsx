import {AlertCircle,ChartNoAxesColumnIncreasing,Info} from 'lucide-react';

export type FeatureSensitivityEvidence={
  status:'computed'|'unavailable';
  reason?:string;
  method?:string;
  metric?:string;
  reference_metric?:number;
  sample_rows?:number;
  total_test_rows?:number;
  features_evaluated?:number;
  total_predictors?:number;
  repeats?:number;
  seed?:number;
  data_source?:string;
  sampled?:boolean;
  scores?:{feature:string;mean_importance:number;repeat_std:number}[];
  limitations?:string[];
};

const decimal=(n:number)=>n.toLocaleString(undefined,{maximumFractionDigits:5});
export function FeatureSensitivity({data}:{data?:FeatureSensitivityEvidence}){
  if(!data)return <section className="po-ml-sensitivity"><p className="muted-caption">This legacy evaluation has no post-selection sensitivity analysis. Retraining is required to produce one.</p></section>;
  if(data.status!=='computed')return <section className="po-ml-sensitivity"><h3>Model feature sensitivity</h3><p className="muted-caption">{data.reason||'Sensitivity was unavailable for this model.'} Existing held-out metrics remain unchanged.</p></section>;
  const scores=data.scores??[];
  const incomplete=(data.features_evaluated??0)<(data.total_predictors??0);
  return <section className="po-ml-sensitivity" role="region" aria-label="Bounded model feature sensitivity">
    <div className="po-ml-sensitivity-head"><ChartNoAxesColumnIncreasing size={19}/><h3>Which inputs influence this model's score?</h3><span className="pill">Post-selection · descriptive</span></div>
    <p className="body-muted">After model selection, PilotODIN shuffled one feature at a time on a small fixed sample of held-out records. Positive changes mean the model's score became worse when that field was shuffled; negative changes mean it improved or varied. <strong>These are NOT causal effects, coefficients, or explanations of any single prediction.</strong></p>
    <div className="po-ml-sensitivity-stats">
      <span><strong>{data.features_evaluated??0}/{data.total_predictors??0}</strong> predictors examined</span>
      <span><strong>{data.sample_rows??0}/{data.total_test_rows??0}</strong> test rows sampled</span>
      <span><strong>{data.repeats??0}</strong> shuffles per predictor</span>
      <span><strong>{decimal(data.reference_metric??0)}</strong> unchanged sample score</span>
    </div>
    {(data.sampled||incomplete)&&<div className="po-ml-sensitivity-caution"><AlertCircle size={16}/> Partial diagnostic: untested predictors are not ranked, and no causal conclusions can be drawn from this limited sample.</div>}
    <div className="table-scroll po-ml-sensitivity-table"><table><thead><tr><th>INPUT FIELD</th><th>MEAN SCORE DETERIORATION</th><th>REPEAT VARIATION</th></tr></thead><tbody>
      {scores.map(row=><tr key={row.feature}><td><strong>{row.feature}</strong></td><td>{decimal(row.mean_importance)} <small>{data.metric}</small></td><td>{decimal(row.repeat_std)}</td></tr>)}
    </tbody></table></div>
    <p className="muted-caption"><Info size={13}/> Scored from {data.data_source?.toLowerCase()??'the frozen test set after selection'}. Seed {data.seed}. The same test result must never be used to choose, retrain or tune the model.</p>
    {data.limitations&&<details className="po-ml-sensitivity-notes"><summary>Interpretation limits</summary><ul>{data.limitations.map((note,i)=><li key={i}>{note}</li>)}</ul></details>}
  </section>;
}
