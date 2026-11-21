import {useEffect,useRef,useState} from 'react';
import type {KeyboardEvent as ReactKeyboardEvent} from 'react';
import {Archive,ArchiveRestore,FolderOpen,Pencil,X} from 'lucide-react';
import {get,put} from './api';
import './project-manager.css';

export type ManagedProject={id:string;name:string;filename:string;created_at:string;revision:number;archived_at:string|null};
type Action='rename'|'archive'|'restore';
type DeletionImpact={
 project_id:string;name:string;revision:number;archived:boolean;
 preview_only:true;deletion_available:false;linked_sqlite_rows:number;
 records:{key:string;label:string;count:number;schema_present:boolean}[];
 unclassified_tables:string[];
 artifacts:{
  original_source_present:boolean;original_source_managed:boolean;
  linked_model_directories_present:number;model_locations_requiring_review:number;
  external_exports_and_backups:string;
 };
 active_work:{model_training:number;odin_runs:number};
 blockers:string[];limitations:string;
};
type Props={currentProjectId:string;onClose:()=>void;onChanged:(project:ManagedProject)=>void};

/** Reversible metadata management, deliberately no permanent-delete route. */
export function ProjectManager({currentProjectId,onClose,onChanged}:Props){
 const [projects,setProjects]=useState<ManagedProject[]>([]);
 const [loading,setLoading]=useState(true);
 const [busy,setBusy]=useState(false);
 const [editing,setEditing]=useState<string|null>(null);
 const [draft,setDraft]=useState('');
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [reviewId,setReviewId]=useState<string|null>(null);
 const [impact,setImpact]=useState<DeletionImpact|null>(null);
 const [impactBusy,setImpactBusy]=useState(false);
 const reviewEpoch=useRef(0);
 const root=useRef<HTMLDivElement|null>(null);
 const closeButton=useRef<HTMLButtonElement|null>(null);
 useEffect(()=>{
  let mounted=true;
  const opener=document.activeElement instanceof HTMLElement?document.activeElement:null;
  closeButton.current?.focus();
  void get<ManagedProject[]>('/projects/manage').then(rows=>{
   if(mounted)setProjects(rows);
  }).catch(e=>{
   if(mounted)setError('Project library unavailable: '+String((e as Error).message));
  }).finally(()=>{if(mounted)setLoading(false)});
  return()=>{mounted=false;reviewEpoch.current++;if(opener?.isConnected)opener.focus()};
 },[]);
 const onKey=(e:ReactKeyboardEvent<HTMLDivElement>)=>{
  if(e.key==='Escape'){
   if(!busy){e.preventDefault();onClose()}
   return;
  }
  if(e.key!=='Tab'||!root.current)return;
  const controls=Array.from(root.current.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled])')).filter(el=>el.getClientRects().length>0);
  if(!controls.length)return;
  if(e.shiftKey&&document.activeElement===controls[0]){e.preventDefault();controls[controls.length-1].focus()}
  if(!e.shiftKey&&document.activeElement===controls[controls.length-1]){e.preventDefault();controls[0].focus()}
 };
 const closeReview=()=>{
  reviewEpoch.current++;
  setReviewId(null);setImpact(null);setImpactBusy(false);
 };
 const review=async(project:ManagedProject)=>{
  if(busy)return;
  const epoch=++reviewEpoch.current;
  setReviewId(project.id);setImpact(null);setImpactBusy(true);setError('');
  try{
   const result=await get<DeletionImpact>(
    '/projects/'+encodeURIComponent(project.id)+'/deletion-impact?expected_revision='+project.revision
   );
   if(epoch!==reviewEpoch.current)return;
   if(result.project_id!==project.id||result.revision!==project.revision||
      result.preview_only!==true||result.deletion_available!==false){
    setError('The impact review did not match this project. No action was taken.');
    return;
   }
   setImpact(result);
  }catch(e){
   if(epoch===reviewEpoch.current)setError('Could not review project impact: '+String((e as Error).message));
  }finally{if(epoch===reviewEpoch.current)setImpactBusy(false)}
 };
 const change=async(project:ManagedProject,action:Action)=>{
  if(busy)return;
  if(action==='archive'&&project.id===currentProjectId){
   setError('Switch to a different project before archiving the current one.');
   return;
  }
  if(action==='archive'&&!window.confirm('Archive "'+project.name+'"? This hides it from your active projects, but preserves its original data, history, models, investigations and reports. You can restore it later.'))return;
  const name=action==='rename'?draft.trim():undefined;
  if(action==='rename'&&(!name||name.length>80)){
   setError('Use a project name between 1 and 80 characters.');
   return;
  }
  closeReview();setBusy(true);setError('');setNotice('');
  try{
   const next=await put<ManagedProject>('/projects/'+encodeURIComponent(project.id)+'/lifecycle',{
    action,expected_revision:project.revision,...(name===undefined?{}:{name})
   });
   setProjects(rows=>rows.map(row=>row.id===next.id?next:row));
   setEditing(null);onChanged(next);
   setNotice(action==='rename'?'Project renamed.':action==='archive'?'Archived. You can restore it below.':'Project restored.');
  }catch(e){setError(String((e as Error).message)+' Review current project state before retrying.')}
  finally{setBusy(false)}
 };
 const item=(p:ManagedProject)=>{
  const current=p.id===currentProjectId&&p.archived_at===null;
  return <li key={p.id} className="po-pm-item">
   <FolderOpen size={19} aria-hidden="true"/>
   <div className="po-pm-details">
    {editing===p.id?<form onSubmit={e=>{e.preventDefault();void change(p,'rename')}} className="po-pm-edit">
      <label htmlFor={'po-pm-name-'+p.id}>Project name</label>
      <input id={'po-pm-name-'+p.id} value={draft} maxLength={80} disabled={busy} onChange={e=>setDraft(e.target.value)} required/>
      <button type="submit" disabled={busy||!draft.trim()}>Save</button>
      <button type="button" disabled={busy} onClick={()=>setEditing(null)}>Cancel</button>
     </form>:<strong>{p.name}{current?' (current)':''}</strong>}
    <small>{p.filename} · {p.id.slice(0,8)}…</small>
   </div>
   {editing!==p.id&&<div className="po-pm-controls">
    <button type="button" disabled={busy} onClick={()=>void review(p)} aria-label={'Review deletion impact for '+p.name}>Review impact</button>
    <button type="button" disabled={busy} onClick={()=>{setEditing(p.id);setDraft(p.name);setError('')}} aria-label={'Rename '+p.name}><Pencil size={14}/> Rename</button>
    {p.archived_at===null?
     <button type="button" disabled={busy||current} title={current?'Switch to another project first':'Archive, preserving project data'} onClick={()=>void change(p,'archive')} aria-label={'Archive '+p.name}><Archive size={14}/> Archive</button>:
     <button type="button" disabled={busy} onClick={()=>void change(p,'restore')} aria-label={'Restore '+p.name}><ArchiveRestore size={14}/> Restore</button>}
   </div>}
  </li>;
 };
 const active=projects.filter(p=>p.archived_at===null);
 const archived=projects.filter(p=>p.archived_at!==null);
 return <div className="po-pm-backdrop">
  <div className="po-pm-dialog" role="dialog" aria-modal="true" aria-labelledby="po-pm-heading" aria-describedby="po-pm-description" ref={root} onKeyDown={onKey}>
   <header><div><h2 id="po-pm-heading">Manage projects</h2>
    <p id="po-pm-description">Rename, archive or restore projects without losing their data or evidence. Permanent deletion is not available yet.</p></div>
    <button ref={closeButton} type="button" aria-label="Close project management" disabled={busy} onClick={onClose}><X size={20}/></button></header>
   {error&&<p role="alert" className="po-pm-error">{error}</p>}
   {notice&&<p role="status" className="po-pm-notice">{notice}</p>}
   {reviewId!==null&&<section className="po-pm-impact" role="region" aria-label="Deletion impact review">
    <div className="po-pm-impact-heading">
     <strong>Read-only deletion impact</strong>
     <button type="button" onClick={closeReview} aria-label="Close impact review">Close review</button>
    </div>
    {impactBusy&&<p role="status">Counting project records without changing them…</p>}
    {impact&&!impactBusy&&<>
     <p><strong>{impact.name}</strong> · revision {impact.revision} · {impact.archived?'Archived':'Active'}</p>
     <p>This review found <strong>{impact.linked_sqlite_rows}</strong> linked SQLite records. It is not permission to delete.</p>
     <ul aria-label="Project-owned record counts">
      {impact.records.filter(entry=>entry.count>0).map(entry=><li key={entry.key}>
       <span>{entry.label}</span><strong>{entry.count}</strong></li>)}
     </ul>
     <p>Original dataset: {impact.artifacts.original_source_present?'Present':'Not found'}. Location: {impact.artifacts.original_source_managed?'Managed dataset folder':'Requires location review'}.</p>
     <p>Linked model directories found: {impact.artifacts.linked_model_directories_present}. Other model locations needing review: {impact.artifacts.model_locations_requiring_review}.</p>
     {impact.unclassified_tables.length>0&&<p role="alert">Unclassified SQLite tables: {impact.unclassified_tables.join(', ')}.</p>}
     <p>Queued/running training: {impact.active_work.model_training}. Active ODIN runs: {impact.active_work.odin_runs}.</p>
     <p>Exports and backups outside PilotODIN's managed project folder are excluded. They will not be affected by this review.</p>
     <p className="po-pm-limitations">{impact.limitations}</p>
     <p className="po-pm-impact-blocked"><strong>Permanent deletion is unavailable.</strong> {impact.blockers.join(' ')}</p>
    </>}
   </section>}
   {loading?<p role="status" className="po-pm-loading">Loading projects…</p>:
    <div className="po-pm-scroll"><section aria-label="Active projects"><h3>Active projects ({active.length})</h3><ul>{active.map(item)}</ul>{!active.length&&<p>No active projects.</p>}</section>
    <section aria-label="Archived projects"><h3>Archived projects ({archived.length})</h3><ul>{archived.map(item)}</ul>{!archived.length&&<p>No archived projects.</p>}</section></div>}
   <footer><span>Archive is reversible. No project files are deleted.</span><button type="button" disabled={busy} onClick={onClose}>Done</button></footer>
  </div>
 </div>;
}
