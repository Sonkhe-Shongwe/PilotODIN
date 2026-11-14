import {useEffect,useState} from 'react';
import {post} from './api';

export type UserSemanticContext={
 domain_description:string;record_grain_description:string;
 field_definitions:{column:string;meaning:string}[];
 updated_at:string;verification_state:'user_described_not_independently_verified'
};
type Definition={column:string;meaning:string};

export function SemanticContextEditor({
 projectId,version,columns,existing,onSaved,onUnsavedChange,
}:{
 projectId:string;version:number;columns:string[];
 existing:UserSemanticContext|null;onSaved:(value:UserSemanticContext)=>void;
 onUnsavedChange?:(dirty:boolean)=>void
}){
 const [domain,setDomain]=useState(existing?.domain_description??'');
 const [grain,setGrain]=useState(existing?.record_grain_description??'');
 const [definitions,setDefinitions]=useState<Definition[]>(existing?.field_definitions??[]);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [success,setSuccess]=useState(false);
 const available=columns.slice(0,80);
 // Compare only version-pinned saved text. A stale/unverified description is
 // never converted into a hypothesis or persisted merely by editing a field.
 const fieldsForSave=definitions.map(d=>({column:d.column,meaning:d.meaning.trim()}));
 const dirty=domain.trim()!==(existing?.domain_description??'')||
  grain.trim()!==(existing?.record_grain_description??'')||
  JSON.stringify(fieldsForSave)!==JSON.stringify(existing?.field_definitions??[]);
 useEffect(()=>{
  onUnsavedChange?.(dirty);
  // A permitted workspace/project exit can now clear only its own edit marker.
  return()=>{if(dirty)onUnsavedChange?.(false)};
 },[dirty,onUnsavedChange]);
 const validText=(text:string)=>!text.trim()||text.trim().length>=10;
 const validFields=definitions.every(d=>available.includes(d.column)&&d.meaning.trim().length>=10)&&
                  new Set(definitions.map(d=>d.column)).size===definitions.length;
 const ready=validText(domain)&&validText(grain)&&validFields&&
             (domain.trim().length>=10||grain.trim().length>=10||definitions.length>0);
 function changeField(index:number,next:Definition){
  setDefinitions(prev=>prev.map((d,i)=>i===index?next:d));setSuccess(false);
 }
 function addField(){
  const first=available.find(name=>!definitions.some(d=>d.column===name));
  if(first&&definitions.length<8){setDefinitions(prev=>[...prev,{column:first,meaning:''}]);setSuccess(false)}
 }
 async function save(){
  if(!ready||busy)return;
  setBusy(true);setError('');setSuccess(false);
  try{
   const result=await post<UserSemanticContext>(`/projects/${projectId}/semantic-business-context`,{
    expected_version:version,
    domain_description:domain.trim(),record_grain_description:grain.trim(),
    field_definitions:definitions.map(d=>({column:d.column,meaning:d.meaning.trim()})),
   });
   onSaved(result);setSuccess(true);
  }catch(e){setError((e as Error).message)}
  finally{setBusy(false)}
 }
 return <details className="po-context-editor">
  <summary>{existing?'Review or revise your business descriptions':'Optional: describe what this dataset means'}</summary>
  <div className="po-context-fields" style={{display:'grid',gap:10,padding:'12px 0'}}>
   <p className="muted-caption">Your descriptions are stored locally for working version {version}.
    They do not verify the system's guesses, change source data, select targets or permit training.</p>
   <label className="field-label">What business area does this dataset describe?
    <textarea className="input full" rows={2} maxLength={300} value={domain}
     onChange={e=>{setDomain(e.target.value);setSuccess(false)}}/>
   </label>
   <label className="field-label">What does one row represent?
    <textarea className="input full" rows={2} maxLength={300} value={grain}
     onChange={e=>{setGrain(e.target.value);setSuccess(false)}}/>
   </label>
   <div><strong>Optional field definitions</strong>
    <p className="muted-caption">Up to eight descriptions from the first 80 fields. For prediction-target meaning and timing, continue using the separate Prepare review.</p>
   </div>
   {definitions.map((item,index)=><div key={index} className="po-context-fields" style={{display:'grid',gap:6}}>
    <label className="field-label">Field {index+1}
     <select className="input full" value={item.column}
      onChange={e=>changeField(index,{...item,column:e.target.value})}>
      {available.map(name=><option key={name} value={name} disabled={definitions.some((d,i)=>i!==index&&d.column===name)}>{name}</option>)}
     </select>
    </label>
    <label className="field-label">Owner-described meaning
     <textarea className="input full" rows={2} maxLength={300} value={item.meaning}
      onChange={e=>changeField(index,{...item,meaning:e.target.value})}/>
    </label>
    <button type="button" className="btn small" disabled={busy}
     onClick={()=>{setDefinitions(prev=>prev.filter((_,i)=>i!==index));setSuccess(false)}}>Remove field description</button>
   </div>)}
   <div><button type="button" className="btn small"
    disabled={busy||definitions.length>=8||!available.some(name=>!definitions.some(d=>d.column===name))}
    onClick={addField}>Add field definition</button></div>
   {dirty&&<p className="muted-caption" role="status">Unsaved business descriptions. Save them before changing projects or leaving Your data.</p>}
   {!ready&&<p className="muted-caption">Enter at least one description of 10 or more characters. Each selected field also needs a unique, meaningful definition.</p>}
   {error&&<p role="alert" className="alert-error">{error}</p>}
   {success&&<p role="status" className="muted-caption">Saved for this dataset version as user-provided, not independently verified.</p>}
   <div><button type="button" className="btn small" disabled={!ready||busy} onClick={()=>void save()}>
    {busy?'Saving descriptions…':'Save business descriptions'}</button></div>
  </div>
 </details>;
}
