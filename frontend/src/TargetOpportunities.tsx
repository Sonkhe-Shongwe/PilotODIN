import {useEffect,useState} from 'react';
import {AlertCircle,CheckCircle2,LoaderCircle,SearchCheck} from 'lucide-react';
import {get} from './api';

type Opportunity={
 column:string;quality_version:number;task_hypothesis:'classification'|'regression'|null;
 technical_status:'reviewable'|'blocked';business_relevance:'unverified';
 possible_decision_question:string;labelled_rows:number;missing_labels:number;
 distinct_labels:number;smallest_class:number|null;observed_evidence:string[];
 blockers:string[];review_warnings:string[];safe_to_train_automatically:false
};
type OpportunityResponse={
 version:number;ranking_basis:string;suggestions:Opportunity[];
 blocked_examples:Opportunity[];eligible_count:number;blocked_count:number;
 abstained:boolean;abstention_reason:string|null;business_context_state:'unverified';
 note:string;privacy:string
};

export function TargetOpportunities({
 projectId,version,selectedTarget,onChooseTarget,
}:{
 projectId:string;version:number;selectedTarget:string;
 onChooseTarget:(column:string)=>void
}){
 const [data,setData]=useState<OpportunityResponse|null>(null);
 const [error,setError]=useState('');
 const [loading,setLoading]=useState(false);
 useEffect(()=>{
  let active=true;
  setData(null);setError('');setLoading(true);
  get<OpportunityResponse>(`/projects/${projectId}/target-opportunities?expected_version=${version}`)
    .then(result=>{
      if(!active)return;
      if(result.version!==version){setError('Dataset version changed; refresh before considering a target.');return}
      setData(result);
    }).catch((e:Error)=>{if(active)setError(e.message)})
      .finally(()=>{if(active)setLoading(false)});
  return ()=>{active=false};
 },[projectId,version]);
 return <section className="panel" aria-label="Potential prediction opportunities">
  <div className="panel-title"><SearchCheck size={19}/><h2>Potential prediction opportunities</h2><span className="pill muted">UNVERIFIED</span></div>
  <p className="body-muted">These are header-based possibilities screened for observed label support, not confirmed business objectives, model performance or permission to train. You decide the target.</p>
  {loading&&<p role="status" className="muted-caption"><LoaderCircle size={15} className="spin"/> Checking local label statistics…</p>}
  {error&&<p role="alert" className="alert-error">{error}</p>}
  {data&&<>
   {data.abstained?<div className="mini-info warn-icon"><AlertCircle size={18}/>{data.abstention_reason}</div>:
     <div className="model-grid">
      {data.suggestions.map(item=><article className="model-choice" key={item.column} style={{cursor:'default'}} aria-label={`Potential outcome ${item.column}`}>
       <div className="model-choice-copy" style={{minWidth:0,width:'100%'}}>
        <strong>{item.column}</strong><small>Possible {item.task_hypothesis} · {item.labelled_rows.toLocaleString()} observed labels · {item.missing_labels.toLocaleString()} missing</small>
        <p className="muted-caption">{item.possible_decision_question}</p>
        <p className="muted-caption">Technical status: reviewable, not approved. Business relevance: unknown until you confirm its definition and intended action.</p>
        {item.review_warnings.slice(0,3).map((warning,i)=><p className="muted-caption" key={i}><AlertCircle size={13}/> {warning}</p>)}
        <button type="button" className="btn small" aria-pressed={selectedTarget===item.column} onClick={()=>onChooseTarget(item.column)}>
         {selectedTarget===item.column?<><CheckCircle2 size={14}/> Chosen for preparation review</>:'Review this target'}
        </button>
       </div>
      </article>)}
     </div>}
   {data.blocked_examples.length>0&&<details>
    <summary>Why some named columns were not suggested ({data.blocked_count})</summary>
    {data.blocked_examples.map(item=><div className="warning-line" key={item.column}><AlertCircle size={14}/><span><b>{item.column}</b>: {item.blockers.join(' ')}</span></div>)}
   </details>}
   <p className="muted-caption">{data.ranking_basis} {data.note}</p>
   <p className="muted-caption">Current approved dataset version: {data.version}. No label values, predictions or training outcomes are returned by this screening.</p>
  </>}
 </section>
}
