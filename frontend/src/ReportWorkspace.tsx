import {useEffect,useRef,useState} from 'react';
import {FileDown,FileText,History,Save,ShieldCheck,AlertCircle,Plus,ArrowUp,ArrowDown} from 'lucide-react';
import {get,post,downloadReportFile} from './api';
import './report-workspace.css';

type EvidenceOption={id:string;operation:string;version:number;params:Record<string,unknown>;stale?:boolean;objective?:string;source?:string};
type ReportSummary={id:string;title:string;revision:number;updated_at:string};
type Evidence={id:string;operation:string;dataset_version:number;tool_version:string;params:Record<string,unknown>;result:Record<string,unknown>};
type SavedReport={id:string;title:string;narrative:string;revision:number;revisions:number[];dataset_versions:number[];current_dataset_version:number;has_historical_evidence:boolean;content_sha256:string;evidence:Evidence[]};

function idsafeMessage(saved:{dataset_version:number;findings_total:number},selectionFull:boolean):string {
 return `Captured read-only Quality audit v${saved.dataset_version} with ${saved.findings_total} findings. ${selectionFull?'Evidence selection is full (15); deselect an item to include this audit.':'Audit selected for the next saved revision.'}`;
}

/** Persisted report composer; component-local draft, backend-owned saved revisions. */
export function ReportWorkspace({projectId,availableEvidence=[],defaultTitle='Investigation report',preselectEvidenceId=null}:{projectId:string;availableEvidence?:EvidenceOption[];defaultTitle?:string;preselectEvidenceId?:string|null}) {
 const [reports,setReports]=useState<ReportSummary[]>([]);
 const [projectEvidence,setProjectEvidence]=useState<EvidenceOption[]>([]);
 const [activeId,setActiveId]=useState<string|null>(null);
 const [opened,setOpened]=useState<SavedReport|null>(null);
 const [title,setTitle]=useState(defaultTitle);
 const [narrative,setNarrative]=useState('');
 const [selected,setSelected]=useState<string[]>([]);
 const [busy,setBusy]=useState('');
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [revision,setRevision]=useState<number|null>(null);
 const userStartedDraft=useRef(false);
 const appliedHandoff=useRef<string|null>(null);
 const [evidenceLoaded,setEvidenceLoaded]=useState(false);
 useEffect(()=>{
   let mounted=true;userStartedDraft.current=false;appliedHandoff.current=null;setReports([]);setProjectEvidence([]);setEvidenceLoaded(false);setActiveId(null);setOpened(null);setNarrative('');
   setTitle(defaultTitle);setSelected([]);setError('');setNotice('');setRevision(null);
   if(!projectId)return;
   void get<ReportSummary[]>(`/projects/${encodeURIComponent(projectId)}/reports`).then(async data=>{
     if(!mounted)return;
     setReports(data);
     if(data[0]&&!userStartedDraft.current){
       try{
         const recent=await get<SavedReport>(`/reports/${encodeURIComponent(data[0].id)}`);
         if(mounted&&!userStartedDraft.current){
           setActiveId(recent.id);setOpened(recent);setRevision(recent.revision);
           setTitle(recent.title);setNarrative(recent.narrative);setSelected(recent.evidence.map(e=>e.id));
         }
       }catch(err){if(mounted)setError(`Saved reports were found, but the latest revision could not be restored: ${(err as Error).message}`)}
     }
   }).catch(e=>{if(mounted)setError((e as Error).message)});
   void get<EvidenceOption[]>(`/projects/${encodeURIComponent(projectId)}/report-evidence`).then(data=>{if(mounted){setProjectEvidence(data);setEvidenceLoaded(true)}}).catch(e=>{if(mounted){setEvidenceLoaded(true);setError((e as Error).message)}});
   return()=>{mounted=false};
 },[projectId]);
 useEffect(()=>{
   if(!preselectEvidenceId||!evidenceLoaded||appliedHandoff.current===preselectEvidenceId)return;
   appliedHandoff.current=preselectEvidenceId;
   const option=projectEvidence.find(item=>item.id===preselectEvidenceId);
   if(!option){setError('This saved analysis is not available as verified evidence in the active project.');return;}
   userStartedDraft.current=true;
   setActiveId(null);setOpened(null);setRevision(null);
   setTitle(option.objective?`${option.objective} report`:'Explore investigation report');
   setNarrative('');setSelected([preselectEvidenceId]);setError('');
   setNotice(`Verified ${option.stale?'historical ':' '}Explore evidence selected. Review its dataset version and add your interpretation before saving.`);
 },[projectEvidence,preselectEvidenceId,evidenceLoaded]);
 async function refresh(){setReports(await get<ReportSummary[]>(`/projects/${encodeURIComponent(projectId)}/reports`));}
 async function openReport(id:string,number?:number){
   userStartedDraft.current=true;setBusy('open');setError('');
   try{
     const data=await get<SavedReport>(`/reports/${encodeURIComponent(id)}${number?`?revision=${number}`:''}`);
     if(!data){throw new Error('Report not found')}
     setActiveId(id);setOpened(data);setRevision(data.revision);setTitle(data.title);setNarrative(data.narrative);setSelected(data.evidence.map(e=>e.id));
   }catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 function newReport(){userStartedDraft.current=true;setActiveId(null);setOpened(null);setRevision(null);setSelected([]);setTitle(defaultTitle);setNarrative('');setNotice('');setError('');}
 async function save(){
   userStartedDraft.current=true;
   if(!selected.length){setError('Choose verified evidence before saving.');return;}
   setBusy('save');setError('');setNotice('');
   try{
     const payload={title:title.trim(),narrative,evidence_ids:selected};
     const response=activeId?await post<SavedReport>(`/reports/${encodeURIComponent(activeId)}/revisions`,payload)
       :await post<SavedReport>(`/projects/${encodeURIComponent(projectId)}/reports`,payload);
     setActiveId(response.id);setOpened(response);setRevision(response.revision);
     setNotice(`Saved revision ${response.revision} with ${response.evidence.length} verified evidence artifacts.`);
     await refresh();
   }catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 async function captureQualityAudit(){
   userStartedDraft.current=true;setBusy('quality');setError('');setNotice('');
   try{
     const state=await get<{version:number}>(`/projects/${encodeURIComponent(projectId)}/quality`);
     const saved=await post<{id:string;dataset_version:number;findings_total:number}>(`/projects/${encodeURIComponent(projectId)}/report-quality`,{expected_version:state.version});
     const options=await get<EvidenceOption[]>(`/projects/${encodeURIComponent(projectId)}/report-evidence`);
     setProjectEvidence(options);
     setSelected(ids=>ids.length>=15||ids.includes(saved.id)?ids:[...ids,saved.id]);
     setNotice(idsafeMessage(saved,selected.length>=15));
   }catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 async function download(format:'html'|'pdf'){
   if(!activeId||!opened)return;
   setBusy('export');setError('');
   try{
     const rev=revision??opened.revision;
     const {blob,filename}=await downloadReportFile(`/reports/${encodeURIComponent(activeId)}/export/${format}?revision=${rev}`);
     const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;
     document.body.appendChild(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1500);
     setNotice(`Started browser download for saved revision ${rev}: ${filename}. Confirm the file in Downloads. Native desktop Save As remains subject to Windows acceptance.`);
   }catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 function shiftEvidence(id:string,by:number){
   userStartedDraft.current=true;
   setSelected(ids=>{const from=ids.indexOf(id);const to=from+by;if(from<0||to<0||to>=ids.length)return ids;
     const ordered=[...ids];[ordered[from],ordered[to]]=[ordered[to],ordered[from]];return ordered;});
 }
 const availableMap=new Map<string,EvidenceOption>([...projectEvidence,...availableEvidence].map(e=>[e.id,e] as const));
 const options=[...availableMap.values()].slice(0,150);
 const savedIds=opened?.evidence.map(e=>e.id)??[];
 const hasDraftChanges=!!opened&&(title!==opened.title||narrative!==opened.narrative||selected.length!==savedIds.length||selected.some((id,index)=>id!==savedIds[index]));
 const saveReady=title.trim().length>=5&&selected.length>0;
 const reportStep=opened&&!hasDraftChanges?3:saveReady?2:1;
 return <div className="pd-report-workspace">
   <div className="pd-report-header"><div><span className="pd-report-eyebrow">DELIVER / LOCAL REPORTING</span><h2>Saved, evidence-backed reports</h2><p>Save revisions and export the exact same evidence to HTML or PDF. Source datasets remain unchanged.</p></div><button className="ud-btn ud-btn-quiet" onClick={newReport}><Plus size={15}/> New report</button></div>
   <nav aria-label="Report creation steps" className="pd-report-flow">{[['1','Compose'],['2','Save revision'],['3','Export']].map(([step,label],i)=><span key={step} className={Number(step)===reportStep?'pd-report-step-current':Number(step)<reportStep?'pd-report-step-done':''}><b>{step}</b>{label}</span>)}</nav>
   {hasDraftChanges&&<p role="status" className="pd-report-warning">Unsaved changes. Exports remain linked to the saved revision until you save again.</p>}
   {error&&<p role="alert" className="pd-report-error"><AlertCircle size={16}/>{error}</p>}
   {notice&&<p role="status" className="pd-report-notice"><ShieldCheck size={16}/>{notice}</p>}
   <div className="pd-report-columns"><section className="pd-report-editor">
     <label className="pd-report-field">Report title<input value={title} maxLength={180} onChange={e=>{userStartedDraft.current=true;setTitle(e.target.value)}}/></label>
     <label className="pd-report-field">Interpretation and limitations<textarea value={narrative} placeholder="Describe what the verified evidence establishes, what remains uncertain, and any important limitations. This text is authored by you." rows={5} maxLength={6000} onChange={e=>{userStartedDraft.current=true;setNarrative(e.target.value)}}/></label>
     <h3>Select verified evidence</h3>
     <div className="pd-report-quality-capture"><div><strong>Capture Quality findings</strong><small>Create a read-only, version-bound audit with issue counts and reviewed correction history. No source records or automatic corrections.</small></div><button type="button" className="ud-btn ud-btn-quiet" disabled={!!busy} onClick={()=>void captureQualityAudit()}>{busy==='quality'?'Capturing…':'Capture current Quality audit'}</button></div>
     {options.length?options.map(e=><label className="pd-report-evidence" key={e.id}><input type="checkbox" checked={selected.includes(e.id)} onChange={ev=>{userStartedDraft.current=true;setSelected(ids=>ev.target.checked?ids.length>=15?ids:[...ids,e.id]:ids.filter(id=>id!==e.id))}}/><span><strong>{e.operation==='explore_snapshot'?'Saved Explore investigation':e.operation==='model_evaluation'?'Selected model evaluation':e.operation==='quality_audit'?'Saved Quality audit':e.operation.replaceAll('_',' ')} · v{e.version}{e.stale?' · HISTORICAL':''}</strong><small>{e.operation==='explore_snapshot'?(e.objective??'Saved analysis'):`${Object.entries(e.params||{}).map(([k,v])=>`${k}: ${String(v)}`).join(' · ')||'Dataset profile'}`} · Evidence {e.id.slice(0,12)}</small></span></label>):<p className="pd-report-muted">Capture a Quality audit, save an Explore analysis, evaluate a model, or create investigation evidence to start a report.</p>}
     {selected.filter(id=>!availableMap.has(id)).length>0&&<p className="pd-report-muted">{selected.filter(id=>!availableMap.has(id)).length} additional saved evidence references retained from the loaded report.</p>}
     {selected.length>1&&<section className="pd-report-order" aria-label="Order of report exhibits"><h4>Report exhibit order</h4><p className="pd-report-muted">Exhibits appear in this order in both saved HTML and PDF revisions.</p><ol>{selected.map((id,index)=><li key={id}><span><b>{index+1}.</b> {availableMap.get(id)?.operation.replaceAll('_',' ')||'Saved evidence'} · {id.slice(0,8)} · v{availableMap.get(id)?.version??opened?.evidence.find(item=>item.id===id)?.dataset_version??'?'}</span><div><button type="button" className="pd-report-order-button" aria-label={`Move exhibit ${index+1} earlier`} title="Move earlier" disabled={!!busy||index===0} onClick={()=>shiftEvidence(id,-1)}><ArrowUp size={15}/></button><button type="button" className="pd-report-order-button" aria-label={`Move exhibit ${index+1} later`} title="Move later" disabled={!!busy||index===selected.length-1} onClick={()=>shiftEvidence(id,1)}><ArrowDown size={15}/></button></div></li>)}</ol></section>}
     <div className="pd-report-actions"><div><strong>{selected.length} verified evidence artifacts selected</strong><small>{!saveReady?'Enter a report title and select evidence to continue.':hasDraftChanges?'Save your changes before exporting an updated revision.':opened?'Current saved revision is ready for export.':'Save a frozen report revision to enable HTML/PDF exports.'}</small></div><button className="ud-btn ud-btn-primary" disabled={!!busy||!saveReady||!hasDraftChanges&&!!opened} onClick={()=>void save()}><Save size={16}/>{busy==='save'?'Saving…':activeId?'Save new revision':'Save report'}</button></div>
     <details className="pd-report-preview"><summary>Preview report contents</summary><h4>{title}</h4><p>{narrative||'No narrative supplied. Verified evidence will be presented below.'}</p><ul>{selected.map(id=><li key={id}>{availableMap.get(id)?.operation.replaceAll('_',' ')||'Saved evidence'} · {id.slice(0,12)}</li>)}</ul></details>
     {opened&&<div className="pd-report-export"><div><strong>Saved revision {opened.revision}</strong><small>SHA-256 {opened.content_sha256.slice(0,18)}…</small></div><button disabled={!!busy||hasDraftChanges} title={hasDraftChanges?'Save draft changes before exporting':'Export the last saved revision as HTML'} onClick={()=>void download('html')}><FileDown size={15}/> Export HTML</button><button disabled={!!busy||hasDraftChanges} title={hasDraftChanges?'Save draft changes before exporting':'Export the last saved revision as PDF'} onClick={()=>void download('pdf')}><FileDown size={15}/> Export PDF</button></div>}
     {opened?.has_historical_evidence&&<p className="pd-report-warning">Historical evidence: at least one included dataset version differs from the current active version. Existing calculations are preserved, not silently recomputed.</p>}
     {opened&&opened.dataset_versions.length>1&&<p className="pd-report-warning">This saved report intentionally includes evidence from dataset versions {opened.dataset_versions.join(', ')}.</p>}
   </section><aside className="pd-report-library"><h3><History size={17}/> Saved reports</h3>
     {reports.length===0&&<p className="pd-report-muted">No reports saved in this project yet.</p>}
     {reports.map(item=><button key={item.id} className={activeId===item.id?'pd-report-selected':''} onClick={()=>void openReport(item.id)}><FileText size={17}/><span><strong>{item.title}</strong><small>Revision {item.revision} · {new Date(item.updated_at).toLocaleDateString()}</small></span></button>)}
     {opened&&<label className="pd-report-field">Open saved revision<select value={revision??opened.revision} onChange={e=>void openReport(opened.id,Number(e.target.value))}>{opened.revisions.map(n=><option key={n} value={n}>Revision {n}</option>)}</select></label>}
     {opened&&<p className="pd-report-muted">Exports are generated locally from a saved revision. Editing above does not change the exported report until you save a new revision.</p>}
   </aside></div>
 </div>;
}
