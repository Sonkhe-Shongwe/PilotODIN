import {useEffect,useState} from 'react';
import {AlertCircle,CheckCircle2,LoaderCircle,SearchCheck} from 'lucide-react';
import {get} from './api';
import {TargetContextEditor} from './TargetContextEditor';
import type {UserTargetContext} from './TargetContextEditor';

type Opportunity={
 column:string;quality_version:number;task_hypothesis:'classification'|'regression'|null;
 technical_status:'reviewable'|'blocked';business_relevance:'unverified'|'user_described_unverified';
 user_context?:UserTargetContext|null;
 possible_decision_question:string;labelled_rows:number;missing_labels:number;
 distinct_labels:number;smallest_class:number|null;observed_evidence:string[];
 blockers:string[];review_warnings:string[];safe_to_train_automatically:false;
 assessment_axes?:{
  technical:{state:'structurally_reviewable'|'structurally_blocked';
   basis:'observed_aggregates_and_structural_screening';
   labelled_rows:number;distinct_labels:number;smallest_class:number|null;limitations:string};
  decision:{state:'user_described_unverified'|'undocumented';
   basis:'user_description_only'|'no_user_description';limitations:string};
  review_required:true;safe_to_train_automatically:false
 };
 risk_review?:{
  status:'needs_human_review'|'context_missing';
  verification:'unverified_user_text_and_header_clues';
  timing_cue:'not_determined'|'possible_after_event_wording';
  label_cue:'not_determined'|'possibly_unconfirmed_or_proxy'|'source_unclear';
  header_flags:{column:string;reason:string;basis:'header_name_only'}[];
  header_review_incomplete:boolean;questions:string[];note:string;
  safe_to_train_automatically:false
 }
};
type OpportunityResponse={
 version:number;ranking_basis:string;suggestions:Opportunity[];
 blocked_examples:Opportunity[];eligible_count:number;blocked_count:number;
 abstained:boolean;abstention_reason:string|null;business_context_state:'unverified'|'user_described_unverified';
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
 const [refresh,setRefresh]=useState(0);
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
 },[projectId,version,refresh]);
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
        <p className="muted-caption">Technical status: reviewable, not approved. Business relevance: {item.user_context?'user-described, not independently verified':'unknown until you describe the intended decision'}.</p>
        {item.user_context&&<p className="muted-caption"><strong>Recorded user context:</strong> {item.user_context.outcome_definition.slice(0,160)}. Decision: {item.user_context.decision_action.slice(0,160)}.</p>}
        {item.assessment_axes&&<div className="mini-info" aria-label="Two-axis prediction opportunity assessment">
         <p className="muted-caption"><strong>Technical readiness:</strong> {item.assessment_axes.technical.state==='structurally_reviewable'?'Structurally reviewable, not validated':'Structurally blocked'}; {item.assessment_axes.technical.labelled_rows.toLocaleString()} observed labels across {item.assessment_axes.technical.distinct_labels.toLocaleString()} distinct values.</p>
         <p className="muted-caption"><strong>Decision relevance:</strong> {item.assessment_axes.decision.state==='user_described_unverified'?'User-described, not independently verified':'Undocumented; business decision still unknown'}.</p>
         <p className="muted-caption">Two separate evidence states, not model accuracy or a business-value score. Human review is always required.</p>
        </div>}
        <TargetContextEditor projectId={projectId} version={version} column={item.column} existing={item.user_context??null} onSaved={()=>setRefresh(n=>n+1)}/>
        {item.risk_review&&<details className="po-risk-review">
         <summary>Prediction timing and label provenance: review required</summary>
         <p className="muted-caption">Status: {item.risk_review.status==='context_missing'?'Add user context before evaluating the proposed decision':'User description present, but not independently verified'}.</p>
         {item.risk_review.timing_cue==='possible_after_event_wording'&&<p className="muted-caption">Timing wording may refer to a post-event moment. Confirm when the target is already known.</p>}
         {item.risk_review.label_cue==='possibly_unconfirmed_or_proxy'&&<p className="muted-caption">Label-source wording mentions a report, suspicion or proxy. Confirm actual label provenance.</p>}
         {item.risk_review.label_cue==='source_unclear'&&<p className="muted-caption">Label source is described as uncertain. Obtain a documented source before relying on it.</p>}
         {item.risk_review.header_flags.length>0&&<>
          <p className="muted-caption">Header-only timing/derived-field questions, not confirmed leakage:</p>
          <ul>{item.risk_review.header_flags.map(flag=><li key={flag.column} className="muted-caption"><strong>{flag.column}</strong>: {flag.reason}</li>)}</ul>
         </>}
         {item.risk_review.header_review_incomplete&&<p className="muted-caption">Header review is bounded and may omit other risks.</p>}
         <ul>{item.risk_review.questions.map(question=><li className="muted-caption" key={question}>{question}</li>)}</ul>
         <p className="muted-caption">{item.risk_review.note}</p>
        </details>}
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
