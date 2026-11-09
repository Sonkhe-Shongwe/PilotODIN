import {useEffect,useState} from 'react';
import {AlertCircle,CheckCircle2,LoaderCircle,SearchCheck} from 'lucide-react';
import {get} from './api';
import {TargetContextEditor} from './TargetContextEditor';
import type {UserTargetContext} from './TargetContextEditor';

type DecisionUtilityReview={
 state:'independent_evidence_required';
 action_state:'owner_described_unverified'|'undocumented';
 baseline_comparison_state:'not_established';
 verified_label_origin:false;verified_prediction_time:false;
 verified_group_independence:false;measured_decision_benefit:false;
 entity_repetition:{
  rows_examined:number;total_rows:number;identifier_headers_examined:number;
  scan_truncated:boolean;basis:'bounded_observed_values_in_identifier_like_headers';
  interpretation:string;repeated:{
   column:string;nonmissing_observations:number;distinct_observed_values:number;
   additional_occurrences:number
  }[]
 };
 next_questions:string[];training_authorised:false;
};

function DecisionUtilityEvidence({review}:{review:DecisionUtilityReview}){
 return <div className="mini-info" aria-label="Decision usefulness evidence">
  <p className="muted-caption"><strong>Decision usefulness: not established.</strong>
   {' '}An owner description does not verify practical benefit, label origin, decision timing or safe validation.</p>
  <p className="muted-caption"><strong>Decision action:</strong> {review.action_state==='owner_described_unverified'
   ?'Owner described an intended action; independent operational evidence is still required.'
   :'No intended action is documented.'}</p>
  <p className="muted-caption"><strong>Comparison with the existing process:</strong>
   {' '}No measured benefit, costs or non-model baseline have been established.</p>
  <p className="muted-caption"><strong>Record-dependence check:</strong>
   {' '}{review.entity_repetition.rows_examined.toLocaleString()} of
   {' '}{review.entity_repetition.total_rows.toLocaleString()} records examined;
   {' '}{review.entity_repetition.identifier_headers_examined} identifier-like headers checked.</p>
  {review.entity_repetition.repeated.length>0?<ul>
   {review.entity_repetition.repeated.map(x=><li className="muted-caption" key={x.column}>
    <strong>{x.column}</strong>: {x.nonmissing_observations.toLocaleString()} non-missing values,
    {' '}{x.distinct_observed_values.toLocaleString()} distinct;
    {' '}{x.additional_occurrences.toLocaleString()} additional occurrences beyond the first.
   </li>)}
  </ul>:<p className="muted-caption">No repeated identifier-like values detected in the bounded scan.</p>}
  {review.entity_repetition.scan_truncated&&<p className="muted-caption">
   Scan limits reached; additional identifier repetition may be unreported.</p>}
  <p className="muted-caption">{review.entity_repetition.interpretation}</p>
  <ul>{review.next_questions.map(question=><li className="muted-caption" key={question}>{question}</li>)}</ul>
  <p className="muted-caption">No business value, lawful use, label truth, group independence,
   model performance or training permission is established by this review.</p>
 </div>
}

type Opportunity={
 column:string;quality_version:number;task_hypothesis:'classification'|'regression'|null;
 technical_status:'reviewable'|'blocked';business_relevance:'unverified'|'user_described_unverified';
 user_context?:UserTargetContext|null;
 possible_decision_question:string;labelled_rows:number;missing_labels:number;
 distinct_labels:number;smallest_class:number|null;observed_evidence:string[];
 blockers:string[];review_warnings:string[];safe_to_train_automatically:false;
 decision_utility?:DecisionUtilityReview;
 assessment_axes?:{
  technical:{state:'structurally_reviewable'|'structurally_blocked';
   basis:'observed_aggregates_and_structural_screening';
   labelled_rows:number;distinct_labels:number;smallest_class:number|null;limitations:string};
  decision:{state:'user_described_unverified'|'undocumented';
   basis:'user_description_only'|'no_user_description';limitations:string};
  review_required:true;safe_to_train_automatically:false
 };
 review_priority?:{
  position:number;total_reviewable:number;
  group:'described_question_first'|'decision_not_described';
  ordering_reason:string;label_support_reason:string;
  required_checks:{topic:string;state:string;action:string}[];
  business_value:'not_established';target_safety:'not_established';
  training_authorised:false
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
type ReviewDisposition='deferred'|'declined';

type OpportunityResponse={
 version:number;ranking_basis:string;suggestions:Opportunity[];
 ranking_contract?:{
  purpose:'human_review_queue_not_business_value_ranking';ordered_by:string[];
  business_value_verified:false;model_performance_measured:false;
  automatic_target_selection:false
 };
 other_reviewable?:Opportunity[];omitted_reviewable_count?:number;
 blocked_examples:Opportunity[];eligible_count:number;blocked_count:number;
 abstained:boolean;abstention_reason:string|null;business_context_state:'unverified'|'user_described_unverified';
 note:string;privacy:string
};

export function TargetOpportunities({
 projectId,version,selectedTarget,onChooseTarget,onClearTarget,
}:{
 projectId:string;version:number;selectedTarget:string;
 onChooseTarget:(column:string)=>void;onClearTarget:()=>void
}){
 const [data,setData]=useState<OpportunityResponse|null>(null);
 const [error,setError]=useState('');
 const [loading,setLoading]=useState(false);
 const [refresh,setRefresh]=useState(0);
 // Review dispositions are temporary UI state. They never modify saved
 // target context, block manual selection or authorise a training experiment.
 const [reviewDispositions,setReviewDispositions]=useState<Record<string,ReviewDisposition>>({});
 const [abstained,setAbstained]=useState(false);
 // Blocked examples are a bounded, read-only subset. Manual selection of a
 // known blocked target must not be mislabelled as merely outside the queue.
 const selectedCandidate=data&&selectedTarget
  ?[...data.suggestions,...(data.other_reviewable??[]),...data.blocked_examples]
    .find(item=>item.column===selectedTarget)
  :undefined;
 function markDisposition(column:string,decision:ReviewDisposition){
  setReviewDispositions(previous=>({...previous,[column]:decision}));
  setAbstained(false);
  // An owner who defers/declines the currently chosen target must not retain
  // a stale preparation plan or experiment in the parent Studio.
  if(selectedTarget===column)onClearTarget();
 }
 function abstainForNow(){
  setAbstained(true);
  if(selectedTarget)onClearTarget();
 }
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
   <div className="mini-info" aria-label="Target suitability review options">
    <p className="muted-caption"><strong>Owner decision:</strong> You may review a target,
     defer it, decline it for this review, or continue without a prediction objective.
     Deferring and declining are temporary UI choices, not saved assessments, permanent
     exclusions or permissions to train. The manual target selector remains available.</p>
    <button type="button" className="btn small" onClick={abstainForNow}>
     No prediction objective right now
    </button>
    {abstained&&!selectedTarget&&<p className="muted-caption" role="status">
     No prediction target selected in this review. Preparation is cleared; you can
     explore descriptively or choose a target later. This choice is not saved.
    </p>}
   </div>
   {selectedTarget&&<div className="mini-info" role="group"
     aria-label="Selected target suitability checkpoint">
    <p className="muted-caption"><strong>Selected for preparation review:</strong> {selectedTarget}.
     This selection is not evidence of suitability or permission to train.</p>
    {selectedCandidate?<>
     {selectedCandidate.technical_status==='blocked'?<div
       className="mini-info warn-icon" role="alert"
       aria-label="Selected target structural blockers">
      <strong>Structurally blocked target: not recommended or approved for training.</strong>
      <p className="muted-caption">This was manually selected despite known P4
       screening blockers. Choosing it does not resolve those blockers or override
       downstream preparation and training safeguards.</p>
      <ul>{selectedCandidate.blockers.map(reason=>
       <li className="muted-caption" key={reason}>{reason}</li>)}</ul>
     </div>:<p className="muted-caption">
      Structurally reviewable, not independently validated or approved.</p>}
     <p className="muted-caption">Observed: {selectedCandidate.labelled_rows.toLocaleString()}
      {' '}non-missing labels, {selectedCandidate.missing_labels.toLocaleString()} missing.
      Technical screening: {selectedCandidate.technical_status}; independent decision
      value, label origin and prediction timing remain unverified.</p>
     <p className="muted-caption">Review group/time dependence before choosing a split.
      {' '}{selectedCandidate.decision_utility?.entity_repetition.repeated.length??0}
      {' '}identifier-like columns showed repeated values in the bounded scan;
      this does not independently establish entity identity or leakage.</p>
    </>:<p className="muted-caption">This manually selected column is not in the
      bounded P4 review queue or bounded blocked examples. No target suitability
      finding is implied. The list is incomplete; absence from it is not approval.
      Check its label meaning, prediction timing and validation risks independently.</p>}
    <button type="button" className="btn small" onClick={onClearTarget}>
     Clear selected target and preparation
    </button>
   </div>}
   {data.ranking_contract&&<p className="muted-caption" role="note">
    <strong>Review order, not an estimated business-value ranking.</strong> Documented questions
    appear first, followed by observed label support and a deterministic name tie-break.
    No target has been independently verified or selected for training.
   </p>}
   {data.abstained?<div className="mini-info warn-icon"><AlertCircle size={18}/>{data.abstention_reason}</div>:
     <div className="model-grid">
      {data.suggestions.map(item=><article className="model-choice" key={item.column} style={{cursor:'default'}} aria-label={`Potential outcome ${item.column}`}>
       <div className="model-choice-copy" style={{minWidth:0,width:'100%'}}>
        <strong>{item.column}</strong><small>Possible {item.task_hypothesis} · {item.labelled_rows.toLocaleString()} observed labels · {item.missing_labels.toLocaleString()} missing</small>
        <p className="muted-caption">{item.possible_decision_question}</p>
        {item.review_priority&&<>
         <p className="muted-caption"><strong>Review position {item.review_priority.position}
          of {item.review_priority.total_reviewable}:</strong> {item.review_priority.ordering_reason}
          {' '}{item.review_priority.label_support_reason}</p>
         <details aria-label={`Evidence needed for ${item.column}`}>
          <summary>Evidence needed before selecting this target</summary>
          <ul>{item.review_priority.required_checks.map(check=>
           <li key={check.topic} className="muted-caption">
            <strong>{check.topic.replaceAll('_',' ')}:</strong> {check.action}
           </li>)}</ul>
          {item.decision_utility&&<DecisionUtilityEvidence review={item.decision_utility}/>}
          <p className="muted-caption">Business value and target safety are not established
           by these observed counts or an owner description.</p>
         </details>
        </>}
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
        {selectedTarget!==item.column&&reviewDispositions[item.column]&&
         <p className="muted-caption" role="status">
          {reviewDispositions[item.column]==='deferred'?'Deferred':'Declined'} for this
          review only. Not saved or excluded from manual selection.
         </p>}
        <button type="button" className="btn small" aria-pressed={selectedTarget===item.column} onClick={()=>onChooseTarget(item.column)}>
         {selectedTarget===item.column?<><CheckCircle2 size={14}/> Chosen for preparation review</>:'Review this target'}
        </button>
        <button type="button" className="btn small"
         aria-pressed={selectedTarget!==item.column&&reviewDispositions[item.column]==='deferred'}
         onClick={()=>markDisposition(item.column,'deferred')}>Defer target in this review</button>
        <button type="button" className="btn small"
         aria-pressed={selectedTarget!==item.column&&reviewDispositions[item.column]==='declined'}
         onClick={()=>markDisposition(item.column,'declined')}>Decline target in this review</button>
       </div>
      </article>)}
     </div>}
   {(data.other_reviewable?.length??0)>0&&<details aria-label="Additional reviewable target alternatives">
    <summary>More structurally reviewable targets ({data.eligible_count-data.suggestions.length})</summary>
    <p className="muted-caption">These candidates are not lower in proven business value.
     You may review an alternative, but normal Prepare, validation and consent
     gates still apply. No target is selected automatically.</p>
    {data.other_reviewable!.map(item=><div className="warning-line" key={item.column}>
     <div style={{display:'grid',gap:6}}>
      <p className="muted-caption"><strong>{item.column}</strong> · possible
       {' '}{item.task_hypothesis} · {item.labelled_rows.toLocaleString()} observed labels.
       {' '}{item.review_priority?.ordering_reason}</p>
      <details aria-label={`Review evidence for alternative ${item.column}`}>
       <summary>Inspect evidence and unresolved risks</summary>
       <p className="muted-caption"><strong>Review priority {item.review_priority?.position} of {item.review_priority?.total_reviewable}:</strong>
        {' '}{item.review_priority?.ordering_reason} This is not a business-value or model-performance ranking.</p>
       <p className="muted-caption"><strong>Technical evidence:</strong> {item.labelled_rows.toLocaleString()} observed labels,
        {' '}{item.distinct_labels.toLocaleString()} distinct values;
        {' '}{item.assessment_axes?.technical.state==='structurally_reviewable'?'structurally reviewable, not validated':'requires structural review'}.</p>
       <p className="muted-caption"><strong>Decision evidence:</strong> {item.user_context
        ?'Owner-described, not independently verified':'Undocumented; intended decision remains unknown'}.</p>
       <ul>{(item.review_priority?.required_checks??[]).map(check=>
        <li className="muted-caption" key={check.topic}><strong>{check.topic.replaceAll('_',' ')}:</strong> {check.action}</li>)}</ul>
       {item.risk_review&&<>
        {item.risk_review.timing_cue==='possible_after_event_wording'&&
         <p className="muted-caption">Owner wording may indicate a post-event prediction moment; verify timing.</p>}
        {item.risk_review.label_cue!=='not_determined'&&
         <p className="muted-caption">Label provenance remains uncertain or potentially proxy-based; investigate the original source.</p>}
        {item.risk_review.header_flags.length>0&&<p className="muted-caption">Header-only risk clues:
         {' '}{item.risk_review.header_flags.map(flag=>flag.column).join(', ')}. These do not prove leakage.</p>}
        {item.risk_review.header_review_incomplete&&
         <p className="muted-caption">Header review is bounded and may omit other risks.</p>}
       </>}
       {item.decision_utility&&<DecisionUtilityEvidence review={item.decision_utility}/>}
       <p className="muted-caption">Business value and target safety remain unverified. Review is not permission to train.</p>
      </details>
      <TargetContextEditor projectId={projectId} version={version} column={item.column}
       existing={item.user_context??null} onSaved={()=>setRefresh(n=>n+1)}/>
      {selectedTarget!==item.column&&reviewDispositions[item.column]&&
       <p className="muted-caption" role="status">
        {reviewDispositions[item.column]==='deferred'?'Deferred':'Declined'} for this
        review only. Not saved or excluded from manual selection.
       </p>}
      <button type="button" className="btn small" aria-pressed={selectedTarget===item.column}
       onClick={()=>onChooseTarget(item.column)}>
       {selectedTarget===item.column?'Chosen for preparation review':'Review this alternative target'}
      </button>
      <button type="button" className="btn small"
       aria-pressed={selectedTarget!==item.column&&reviewDispositions[item.column]==='deferred'}
       onClick={()=>markDisposition(item.column,'deferred')}>Defer target in this review</button>
      <button type="button" className="btn small"
       aria-pressed={selectedTarget!==item.column&&reviewDispositions[item.column]==='declined'}
       onClick={()=>markDisposition(item.column,'declined')}>Decline target in this review</button>
     </div>
    </div>)}
   </details>}
   {(data.omitted_reviewable_count??0)>0&&<p className="muted-caption" role="note">
    {data.omitted_reviewable_count} additional reviewable columns are not expanded
    in this bounded list. The existing manual target chooser remains available.
   </p>}
   {data.blocked_examples.length>0&&<details>
    <summary>Why some named columns were not suggested ({data.blocked_count})</summary>
    {data.blocked_examples.map(item=><div className="warning-line" key={item.column}><AlertCircle size={14}/><span><b>{item.column}</b>: {item.blockers.join(' ')}</span></div>)}
    {data.blocked_count>data.blocked_examples.length&&<p className="muted-caption">
     {data.blocked_count-data.blocked_examples.length} additional blocked named
     columns are not expanded in this bounded list. Omitted does not mean cleared.
    </p>}
   </details>}
   <p className="muted-caption">{data.ranking_basis} {data.note}</p>
   <p className="muted-caption">Current approved dataset version: {data.version}. No label values, predictions or training outcomes are returned by this screening.</p>
  </>}
 </section>
}
