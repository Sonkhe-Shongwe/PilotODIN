import {useState} from 'react';
import {post} from './api';

export type UserTargetContext={
 target_column:string;outcome_definition:string;decision_action:string;
 prediction_moment:string;label_source:string;updated_at:string;
 verification_state:'user_described_not_independently_verified'
};

export function TargetContextEditor({
 projectId,version,column,existing,onSaved,
}:{
 projectId:string;version:number;column:string;
 existing:UserTargetContext|null;onSaved:()=>void
}){
 const [definition,setDefinition]=useState(existing?.outcome_definition??'');
 const [action,setAction]=useState(existing?.decision_action??'');
 const [moment,setMoment]=useState(existing?.prediction_moment??'');
 const [source,setSource]=useState(existing?.label_source??'');
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [saved,setSaved]=useState(false);
 const ready=[definition,action,moment,source].every(s=>s.trim().length>=10);
 async function submit(){
  if(!ready||busy)return;
  setError('');setBusy(true);setSaved(false);
  try{
   await post<UserTargetContext>(`/projects/${projectId}/target-business-context`,{
    expected_version:version,target_column:column,
    outcome_definition:definition.trim(),decision_action:action.trim(),
    prediction_moment:moment.trim(),label_source:source.trim(),
   });
   setSaved(true);onSaved();
  }catch(e){setError((e as Error).message)}
  finally{setBusy(false)}
 }
 return <details className="po-context-editor">
  <summary>{existing?'Review saved user description':'Describe this target before business ranking'}</summary>
  <div className="po-context-fields" style={{display:'grid',gap:9,padding:'12px 0'}}>
   <p className="muted-caption">Your descriptions remain local and bound to this dataset version. They are not verified facts or permission to train.</p>
   <label className="field-label">What exactly does this outcome mean?
    <textarea className="input full" rows={2} maxLength={600} value={definition} onChange={e=>{setDefinition(e.target.value);setSaved(false)}}/>
   </label>
   <label className="field-label">Which real decision or action would improve?
    <textarea className="input full" rows={2} maxLength={600} value={action} onChange={e=>{setAction(e.target.value);setSaved(false)}}/>
   </label>
   <label className="field-label">At what moment would a prediction be needed?
    <textarea className="input full" rows={2} maxLength={500} value={moment} onChange={e=>{setMoment(e.target.value);setSaved(false)}}/>
   </label>
   <label className="field-label">Who or what produces and verifies the historical label?
    <textarea className="input full" rows={2} maxLength={500} value={source} onChange={e=>{setSource(e.target.value);setSaved(false)}}/>
   </label>
   {error&&<p role="alert" className="alert-error">{error}</p>}
   {saved&&<p role="status" className="muted-caption">User-provided context saved for dataset version {version}. Not independently verified.</p>}
   <button type="button" className="btn small" disabled={!ready||busy} onClick={()=>void submit()}>{busy?'Saving…':'Save user description'}</button>
  </div>
 </details>
}
