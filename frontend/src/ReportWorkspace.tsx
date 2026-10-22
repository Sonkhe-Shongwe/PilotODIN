import {useEffect,useState} from 'react';
import {FileDown,FileText,History,Save,ShieldCheck,AlertCircle,Plus} from 'lucide-react';
import {get,post,downloadReportFile} from './api';
import './report-workspace.css';

type EvidenceOption={id:string;operation:string;version:number;params:Record<string,unknown>};
type ReportSummary={id:string;title:string;revision:number;updated_at:string};
type Evidence={id:string;operation:string;dataset_version:number;tool_version:string;params:Record<string,unknown>;result:Record<string,unknown>};
type SavedReport={id:string;title:string;narrative:string;revision:number;revisions:number[];dataset_versions:number[];current_dataset_version:number;has_historical_evidence:boolean;content_sha256:string;evidence:Evidence[]};

/** Persisted report composer; component-local draft, backend-owned saved revisions. */
export function ReportWorkspace({projectId,availableEvidence=[],defaultTitle='Investigation report'}:{projectId:string;availableEvidence?:EvidenceOption[];defaultTitle?:string}) {
 const [reports,setReports]=useState<ReportSummary[]>([]);
 const [projectEvidence,setProjectEvidence]=useState<EvidenceOption[]>([]);
 const [activeId,setActiveId]=useState<string|null>(null);
 const [opened,setOpened]=useState<SavedReport|null>(null);
 const [title,setTitle]=useState(defaultTitle);
 const [narrative,setNarrative]=useState('Describe what the verified results show and what remains uncertain.');
 const [selected,setSelected]=useState<string[]>([]);
 const [busy,setBusy]=useState('');
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [revision,setRevision]=useState<number|null>(null);
 useEffect(()=>{
   let mounted=true;setReports([]);setProjectEvidence([]);setActiveId(null);setOpened(null);
   setTitle(defaultTitle);setSelected([]);setError('');setNotice('');setRevision(null);
   if(!projectId)return;
   void get<ReportSummary[]>(`/projects/${encodeURIComponent(projectId)}/reports`).then(data=>{if(mounted)setReports(data)}).catch(e=>{if(mounted)setError((e as Error).message)});
   void get<EvidenceOption[]>(`/projects/${encodeURIComponent(projectId)}/report-evidence`).then(data=>{if(mounted)setProjectEvidence(data)}).catch(e=>{if(mounted)setError((e as Error).message)});
   return()=>{mounted=false};
 },[projectId]);
 async function refresh(){setReports(await get<ReportSummary[]>(`/projects/${encodeURIComponent(projectId)}/reports`));}
 async function openReport(id:string,number?:number){
   setBusy('open');setError('');
   try{
     const data=await get<SavedReport>(`/reports/${encodeURIComponent(id)}${number?`?revision=${number}`:''}`);
     if(!data){throw new Error('Report not found')}
     setActiveId(id);setOpened(data);setRevision(data.revision);setTitle(data.title);setNarrative(data.narrative);setSelected(data.evidence.map(e=>e.id));
   }catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 function newReport(){setActiveId(null);setOpened(null);setRevision(null);setSelected([]);setTitle(defaultTitle);setNarrative('Describe what the verified results show and what remains uncertain.');setNotice('');setError('');}
 async function save(){
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
 async function download(format:'html'|'pdf'){
   if(!activeId||!opened)return;
   setBusy('export');setError('');
   try{
     const rev=revision??opened.revision;
     const {blob,filename}=await downloadReportFile(`/reports/${encodeURIComponent(activeId)}/export/${format}?revision=${rev}`);
     const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;
     document.body.appendChild(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1500);
   }catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 const availableMap=new Map<string,EvidenceOption>([...projectEvidence,...availableEvidence].map(e=>[e.id,e] as const));
 const options=[...availableMap.values()].slice(0,150);
 return <div className="pd-report-workspace">
   <div className="pd-report-header"><div><span className="pd-report-eyebrow">DELIVER / LOCAL REPORTING</span><h2>Saved, evidence-backed reports</h2><p>Save revisions and export the exact same evidence to HTML or PDF. Source datasets remain unchanged.</p></div><button className="ud-btn ud-btn-quiet" onClick={newReport}><Plus size={15}/> New report</button></div>
   {error&&<p role="alert" className="pd-report-error"><AlertCircle size={16}/>{error}</p>}
   {notice&&<p role="status" className="pd-report-notice"><ShieldCheck size={16}/>{notice}</p>}
   <div className="pd-report-columns"><section className="pd-report-editor">
     <label className="pd-report-field">Report title<input value={title} maxLength={180} onChange={e=>setTitle(e.target.value)}/></label>
     <label className="pd-report-field">Interpretation and limitations<textarea value={narrative} rows={5} maxLength={6000} onChange={e=>setNarrative(e.target.value)}/></label>
     <h3>Select verified evidence</h3>
     {options.length?options.map(e=><label className="pd-report-evidence" key={e.id}><input type="checkbox" checked={selected.includes(e.id)} onChange={ev=>setSelected(ids=>ev.target.checked?ids.length>=15?ids:[...ids,e.id]:ids.filter(id=>id!==e.id))}/><span><strong>{e.operation.replaceAll('_',' ')} · v{e.version}</strong><small>{e.id.slice(0,12)}</small></span></label>):<p className="pd-report-muted">Open an investigation and compute evidence to create a new report.</p>}
     {selected.filter(id=>!availableMap.has(id)).length>0&&<p className="pd-report-muted">{selected.filter(id=>!availableMap.has(id)).length} additional saved evidence references retained from the loaded report.</p>}
     <button className="ud-btn ud-btn-primary" disabled={!!busy||title.trim().length<5||!selected.length} onClick={()=>void save()}><Save size={16}/>{busy==='save'?'Saving…':activeId?'Save new revision':'Save report'}</button>
     {opened&&<div className="pd-report-export"><div><strong>Saved revision {opened.revision}</strong><small>SHA-256 {opened.content_sha256.slice(0,18)}…</small></div><button disabled={!!busy} onClick={()=>void download('html')}><FileDown size={15}/> HTML</button><button disabled={!!busy} onClick={()=>void download('pdf')}><FileDown size={15}/> PDF</button></div>}
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
