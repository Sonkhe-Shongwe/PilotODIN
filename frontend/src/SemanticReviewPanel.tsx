import {useEffect,useState} from 'react';
import {get,post} from './api';

type Decision='acceptable'|'needs_correction'|'cannot_assess';
type SavedReview={
 decision:Decision;explanation:string;revision:number;updated_at:string;
 review_state:'owner_attestation_not_independently_verified'
};
type Candidate={
 column:string;role:string;basis:string;reason:string;hypothesis_hash:string;
 revision:number;reassessment_required:boolean;review:SavedReview|null
};
type ReviewResponse={version:number;candidates:Candidate[];note:string};
type ReviewSave=SavedReview&{column:string;role:string;hypothesis_hash:string};

const reviewKey=(item:Candidate)=>item.column+'\u0000'+item.role;
const decisionText:Record<Decision,string>={
 acceptable:'Reviewed: interpretation acceptable to me',
 needs_correction:'Needs correction',
 cannot_assess:'Cannot assess',
};

export function SemanticReviewPanel({projectId,version,onUnsavedChange}:{
 projectId:string;version:number;onUnsavedChange?:(dirty:boolean)=>void
}){
 const [candidates,setCandidates]=useState<Candidate[]>([]);
 const [selected,setSelected]=useState('');
 const [decision,setDecision]=useState<Decision|''>('');
 const [explanation,setExplanation]=useState('');
 const [busy,setBusy]=useState(false);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState('');
 const [saved,setSaved]=useState(false);
 const chosen=candidates.find(item=>reviewKey(item)===selected);
 const dirty=!!chosen&&(
  decision!==(chosen.review?.decision??'')||
  explanation.trim()!==(chosen.review?.explanation??'')
 );
 const valid=!!chosen&&dirty&&!!decision&&!busy&&
  (decision!=='needs_correction'||explanation.trim().length>=10);

 useEffect(()=>{
  let live=true;
  setLoading(true);setError('');setSelected('');setCandidates([]);setSaved(false);
  get<ReviewResponse>(`/projects/${projectId}/semantic-reviews?expected_version=${version}`)
   .then(value=>{
    if(!live)return;
    if(value.version!==version)throw new Error('Dataset version changed; refresh Your data.');
    setCandidates(value.candidates);
    if(value.candidates.length)setSelected(reviewKey(value.candidates[0]));
   })
   .catch(e=>{if(live)setError((e as Error).message)})
   .finally(()=>{if(live)setLoading(false)});
  return ()=>{live=false};
 },[projectId,version]);

 useEffect(()=>{
  setDecision(chosen?.review?.decision??'');
  setExplanation(chosen?.review?.explanation??'');
  setSaved(false);
 },[selected,chosen?.hypothesis_hash,chosen?.review?.revision]);

 useEffect(()=>{onUnsavedChange?.(dirty)},[dirty,onUnsavedChange]);
 useEffect(()=>()=>{onUnsavedChange?.(false)},[onUnsavedChange]);

 function discard(){
  setDecision(chosen?.review?.decision??'');
  setExplanation(chosen?.review?.explanation??'');
  setError('');setSaved(false);
 }
 async function save(){
  if(!valid||!chosen||!decision)return;
  setBusy(true);setError('');setSaved(false);
  try{
   const result=await post<ReviewSave>(`/projects/${projectId}/semantic-reviews`,{
    expected_version:version,column:chosen.column,role:chosen.role,
    hypothesis_hash:chosen.hypothesis_hash,decision,
    explanation:explanation.trim(),expected_revision:chosen.revision,
   });
   if(result.review_state!=='owner_attestation_not_independently_verified'||
      result.hypothesis_hash!==chosen.hypothesis_hash)
    throw new Error('Unexpected review receipt; refresh Your data.');
   setCandidates(prev=>prev.map(item=>reviewKey(item)===reviewKey(chosen)?
    {...item,revision:result.revision,reassessment_required:false,review:result}:item));
   setSaved(true);
  }catch(e){setError((e as Error).message)}
  finally{setBusy(false)}
 }
 return <details className="po-context-editor" aria-label="Owner interpretation review">
  <summary>Review tentative field interpretations ({candidates.length})</summary>
  <div className="po-context-fields" style={{display:'grid',gap:10,padding:'12px 0'}}>
   <p className="muted-caption">Human review only. Your choice is an owner assessment,
    not independently verified truth. It never changes the data, selects targets or authorises training.</p>
   {loading&&<p role="status">Loading reviewable field hypotheses…</p>}
   {error&&<p role="alert" className="alert-error">{error}</p>}
   {!loading&&candidates.length===0&&<p className="muted-caption">No tentative field-role hypotheses to review for this version.</p>}
   {chosen&&<>
    <label className="field-label">Field hypothesis to review
     <select className="input full" value={selected} disabled={busy||dirty}
      onChange={e=>{setSelected(e.target.value);setError('');setSaved(false)}}>
      {candidates.map(item=><option key={reviewKey(item)} value={reviewKey(item)}>
       {item.column} · {item.role.replaceAll('_',' ')}
      </option>)}
     </select>
    </label>
    <div role="group" aria-label="Current unverified interpretation">
     <p><strong>Field:</strong> {chosen.column}</p>
     <p><strong>Tentative role:</strong> {chosen.role.replaceAll('_',' ')}</p>
     <p className="muted-caption">{chosen.reason} Basis: {chosen.basis.replaceAll('_',' ')}.</p>
    </div>
    {chosen.reassessment_required&&<p className="muted-caption" role="status">
     An earlier review belongs to a changed hypothesis. Reassess explicitly; the old decision is not inherited.
    </p>}
    {chosen.review&&<p className="muted-caption">Previously saved owner review: {decisionText[chosen.review.decision]}.
     Revision {chosen.review.revision}. This remains unverified.</p>}
    <label className="field-label">Your assessment
     <select className="input full" value={decision} disabled={busy}
      onChange={e=>{setDecision(e.target.value as Decision|'');setSaved(false)}}>
      <option value="">Not assessed</option>
      {Object.entries(decisionText).map(([value,label])=>
       <option key={value} value={value}>{label}</option>)}
     </select>
    </label>
    <label className="field-label">Your explanation (required when correction is needed)
     <textarea className="input full" rows={2} maxLength={300} disabled={busy}
      value={explanation} onChange={e=>{setExplanation(e.target.value);setSaved(false)}}/>
    </label>
    {dirty&&<p role="status" className="muted-caption">
     Unsaved interpretation review. Save or discard before switching fields or leaving Your data.
    </p>}
    {saved&&<p role="status" className="muted-caption">Saved owner assessment for working version {version}.
     The field hypothesis is still not independently verified.</p>}
    <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
     <button type="button" className="btn small" disabled={!valid} onClick={()=>void save()}>
      {busy?'Saving review…':'Save owner review'}</button>
     <button type="button" className="btn small" disabled={!dirty||busy} onClick={discard}>Discard review edits</button>
    </div>
   </>}
  </div>
 </details>;
}
