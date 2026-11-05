import {useEffect,useRef,useState} from 'react';
import {FileDown,FileText,History,Save,ShieldCheck,AlertCircle,Plus,ArrowUp,ArrowDown,Eye,X} from 'lucide-react';
import {get,post,downloadReportFile,saveReportNative} from './api';
import {isDesktop} from './desktopBootstrap';
import './report-workspace.css';
import {ReportComposerGate,ReportReadGate} from './reportComposerGate';
import {savedReportPreviewDocument} from './reportSavedPreview';
import {compareFrozenReports,type RevisionComparison} from './reportRevisionComparison';

type EvidenceOption={id:string;operation:string;version:number;params:Record<string,unknown>;stale?:boolean;objective?:string;source?:string};
type ReportSummary={id:string;title:string;revision:number;updated_at:string};
type Evidence={id:string;operation:string;dataset_version:number;tool_version:string;params:Record<string,unknown>;result:Record<string,unknown>};
type SavedReport={id:string;title:string;narrative:string;revision:number;revisions:number[];dataset_versions:number[];current_dataset_version:number;has_historical_evidence:boolean;content_sha256:string;evidence:Evidence[];unchanged?:boolean};
type EvidenceInspection={projectId:string;id:string;operation:string;dataset_version:number;current_dataset_version:number;historical:boolean;objective:string;summary:{label:string;value:string}[];additional_summary_facts:number;note:string;disclosure:string};

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
 const [savedPreview,setSavedPreview]=useState<{projectId:string;id:string;revision:number;html:string}|null>(null);
 const [previewBusy,setPreviewBusy]=useState(false);
 const [previewError,setPreviewError]=useState('');
 const [revisionComparison,setRevisionComparison]=useState<{projectId:string;reportId:string;comparison:RevisionComparison}|null>(null);
 const [comparisonBusy,setComparisonBusy]=useState(false);
 const [comparisonError,setComparisonError]=useState('');
 const [evidenceInspection,setEvidenceInspection]=useState<EvidenceInspection|null>(null);
 const [inspectionBusy,setInspectionBusy]=useState<string|null>(null);
 const [inspectionError,setInspectionError]=useState('');
 const activeProjectRef=useRef(projectId);
 activeProjectRef.current=projectId; // Check project changes before effect cleanup runs.
 const userStartedDraft=useRef(false);
 // Invalidate pending report-open results when the user changes selection.
 const latestOpenRequest=useRef(0);
 const composerGuard=useRef(new ReportComposerGate());
 const readGuard=useRef(new ReportReadGate());
 const latestReportList=useRef(0);
 const appliedHandoff=useRef<string|null>(null);
 const [evidenceLoaded,setEvidenceLoaded]=useState(false);
 useEffect(()=>{
   let mounted=true;composerGuard.current.resetProject();readGuard.current.invalidateAll();latestReportList.current++;latestOpenRequest.current++;userStartedDraft.current=false;appliedHandoff.current=null;setBusy('');setReports([]);setProjectEvidence([]);setEvidenceLoaded(false);setActiveId(null);setOpened(null);setNarrative('');
   setTitle(defaultTitle);setSelected([]);setError('');setNotice('');setRevision(null);setSavedPreview(null);setPreviewBusy(false);setPreviewError('');setRevisionComparison(null);setComparisonBusy(false);setComparisonError('');setEvidenceInspection(null);setInspectionBusy(null);setInspectionError('');
   if(!projectId)return;
   const listTicket=++latestReportList.current;
   void get<ReportSummary[]>(`/projects/${encodeURIComponent(projectId)}/reports`).then(async data=>{
     if(!mounted||listTicket!==latestReportList.current)return;
     setReports(data);
     if(data[0]&&!userStartedDraft.current){
       try{
         const recent=await get<SavedReport>(`/reports/${encodeURIComponent(data[0].id)}`);
         if(mounted&&listTicket===latestReportList.current&&!userStartedDraft.current){
           setActiveId(recent.id);setOpened(recent);setRevision(recent.revision);
           setTitle(recent.title);setNarrative(recent.narrative);setSelected(recent.evidence.map(e=>e.id));
         }
       }catch(err){if(mounted&&listTicket===latestReportList.current&&!userStartedDraft.current)setError(`Saved reports were found, but the latest revision could not be restored: ${(err as Error).message}`)}
     }
   }).catch(e=>{if(mounted&&listTicket===latestReportList.current)setError((e as Error).message)});
   const initialEvidenceTicket=readGuard.current.beginEvidence();
   void get<EvidenceOption[]>(`/projects/${encodeURIComponent(projectId)}/report-evidence`).then(data=>{
     if(mounted&&readGuard.current.isCurrentEvidence(initialEvidenceTicket)){
       setProjectEvidence(data);setEvidenceLoaded(true);
     }
   }).catch(e=>{
     if(mounted&&readGuard.current.isCurrentEvidence(initialEvidenceTicket)){
       setEvidenceLoaded(true);setError((e as Error).message);
     }
   });
   return()=>{mounted=false;composerGuard.current.resetProject();readGuard.current.invalidateAll();latestReportList.current++;latestOpenRequest.current++};
 },[projectId]);
 useEffect(()=>{
   if(!preselectEvidenceId||!evidenceLoaded||appliedHandoff.current===preselectEvidenceId)return;
   appliedHandoff.current=preselectEvidenceId;
   readGuard.current.invalidatePreview();setSavedPreview(null);setPreviewBusy(false);setPreviewError('');
   latestOpenRequest.current++;composerGuard.current.navigate();setBusy('');
   clearComparison();closeEvidenceInspection();
   const option=projectEvidence.find(item=>item.id===preselectEvidenceId);
   if(!option){setError('This saved analysis is not available as verified evidence in the active project.');return;}
   userStartedDraft.current=true;
   setActiveId(null);setOpened(null);setRevision(null);
   setTitle(option.objective?`${option.objective} report`:'Explore investigation report');
   setNarrative('');setSelected([preselectEvidenceId]);setError('');
   setNotice(`Verified ${option.stale?'historical ':' '}Explore evidence selected. Review its dataset version and add your interpretation before saving.`);
 },[projectEvidence,preselectEvidenceId,evidenceLoaded]);
 function closeEvidenceInspection(){
   readGuard.current.invalidateEvidenceInspection();
   setEvidenceInspection(null);setInspectionBusy(null);setInspectionError('');
 }
 async function inspectVerifiedEvidence(id:string){
   const view=composerGuard.current.currentView();
   const ticket=readGuard.current.beginEvidenceInspection();
   const isCurrent=()=>activeProjectRef.current===projectId&&
     composerGuard.current.isCurrentView(view)&&readGuard.current.isCurrentEvidenceInspection(ticket);
   setInspectionBusy(id);setInspectionError('');setEvidenceInspection(null);
   try{
     const data=await get<Omit<EvidenceInspection,'projectId'>>(
       `/projects/${encodeURIComponent(projectId)}/report-evidence/${encodeURIComponent(id)}/preview`);
     if(!isCurrent())return;
     if(data.id!==id)throw new Error('Evidence identity changed during inspection.');
     setEvidenceInspection({projectId,...data});
   }catch(e){if(isCurrent())setInspectionError((e as Error).message)}
   finally{if(isCurrent())setInspectionBusy(null)}
 }
 function clearComparison(){
   readGuard.current.invalidateComparison();
   setRevisionComparison(null);setComparisonBusy(false);setComparisonError('');
 }
 async function comparePreviousSavedRevision(){
   if(!activeId||!opened)return;
   const previousRevisions=opened.revisions.filter(v=>v<opened.revision);
   const priorRevision=previousRevisions[previousRevisions.length-1];
   if(priorRevision===undefined)return;
   const view=composerGuard.current.currentView();
   const ticket=readGuard.current.beginComparison();
   const reportId=activeId,latest=opened;
   const isCurrent=()=>activeProjectRef.current===projectId&&
     composerGuard.current.isCurrentView(view)&&readGuard.current.isCurrentComparison(ticket);
   setComparisonBusy(true);setComparisonError('');setRevisionComparison(null);
   try{
     // Both snapshots originate from the immutable authenticated report API.
     const before=await get<SavedReport>(`/reports/${encodeURIComponent(reportId)}?revision=${priorRevision}`);
     if(!isCurrent())return;
     setRevisionComparison({projectId,reportId,comparison:compareFrozenReports(before,latest)});
   }catch(e){if(isCurrent())setComparisonError((e as Error).message)}
   finally{if(isCurrent())setComparisonBusy(false)}
 }
 async function openReport(id:string,number?:number){
   if(composerGuard.current.hasPending()){setError('A report write is still completing. Finish it before switching reports.');return;}
   closeEvidenceInspection();clearComparison();
   readGuard.current.invalidatePreview();setSavedPreview(null);setPreviewBusy(false);setPreviewError('');
   composerGuard.current.navigate();
   const ticket=++latestOpenRequest.current;
   userStartedDraft.current=true;setBusy('open');setError('');setNotice('');
   try{
     const data=await get<SavedReport>(`/reports/${encodeURIComponent(id)}${number?`?revision=${number}`:''}`);
     if(ticket!==latestOpenRequest.current)return;
     if(!data){throw new Error('Report not found')}
     setActiveId(id);setOpened(data);setRevision(data.revision);setTitle(data.title);setNarrative(data.narrative);setSelected(data.evidence.map(e=>e.id));
   }catch(e){if(ticket===latestOpenRequest.current)setError((e as Error).message)}
   finally{if(ticket===latestOpenRequest.current)setBusy('')}
 }
 function newReport(){
   if(composerGuard.current.hasPending()){setError('A report write is still completing. Finish it before creating another draft.');return;}
   closeEvidenceInspection();clearComparison();
   readGuard.current.invalidatePreview();setSavedPreview(null);setPreviewBusy(false);setPreviewError('');
   composerGuard.current.navigate();latestOpenRequest.current++;setBusy('');userStartedDraft.current=true;setActiveId(null);setOpened(null);setRevision(null);setSelected([]);setTitle(defaultTitle);setNarrative('');setNotice('');setError('');}
 async function save(){
   clearComparison();
   readGuard.current.invalidatePreview();setSavedPreview(null);setPreviewBusy(false);setPreviewError('');
   userStartedDraft.current=true;
   if(!selected.length){setError('Choose verified evidence before saving.');return;}
   const gate=composerGuard.current;
   const ticket=gate.begin('save');
   if(!ticket){setError('Another report write is still completing.');return;}
   latestOpenRequest.current++; // A pending read cannot replace a committed write's UI.
   setBusy('save');setError('');setNotice('');
   const payload={title:title.trim(),narrative,evidence_ids:[...selected]};
   let saved:SavedReport;
   try{
     saved=activeId?await post<SavedReport>(`/reports/${encodeURIComponent(activeId)}/revisions`,payload)
       :await post<SavedReport>(`/projects/${encodeURIComponent(projectId)}/reports`,payload);
   }catch(e){
     if(gate.sameView(ticket))setError((e as Error).message);
     if(gate.finish(ticket))setBusy('');
     return;
   }
   if(gate.sameView(ticket)){
     const untouched=gate.sameDraft(ticket);
     setActiveId(saved.id);setOpened(saved);setRevision(saved.revision);
     setNotice(saved.unchanged
       ?(untouched
         ?`No changes to save. Saved revision ${saved.revision} remains unchanged.`
         :`Submitted revision ${saved.revision} was already saved. Newer draft edits were NOT included; save them separately.`)
       :(untouched
         ?`Saved revision ${saved.revision} with ${saved.evidence.length} verified evidence artifacts.`
         :`Saved submitted revision ${saved.revision}. Newer draft edits were NOT included; save them separately.`));
     // Never replace title/narrative/selected: they may have changed since POST.
   }
   const listTicket=++latestReportList.current;
   try{
     const items=await get<ReportSummary[]>(`/projects/${encodeURIComponent(projectId)}/reports`);
     if(gate.sameView(ticket)&&listTicket===latestReportList.current)setReports(items);
   }catch(e){
     if(gate.sameView(ticket))setError(`Report revision was saved, but the report library could not refresh: ${(e as Error).message}`);
   }finally{
     if(gate.finish(ticket))setBusy('');
   }
 }
 async function captureQualityAudit(){
   userStartedDraft.current=true;
   const gate=composerGuard.current;
   const ticket=gate.begin('quality');
   if(!ticket){setError('Another report write is still completing.');return;}
   latestOpenRequest.current++;
   setBusy('quality');setError('');setNotice('');
   let captured:{id:string;dataset_version:number;findings_total:number}|null=null;
   try{
     const state=await get<{version:number}>(`/projects/${encodeURIComponent(projectId)}/quality`);
     if(!gate.sameView(ticket))return;
     captured=await post<{id:string;dataset_version:number;findings_total:number}>(`/projects/${encodeURIComponent(projectId)}/report-quality`,{expected_version:state.version});
     if(!gate.sameView(ticket))return;
     const evidenceTicket=readGuard.current.beginEvidence();
     const options=await get<EvidenceOption[]>(`/projects/${encodeURIComponent(projectId)}/report-evidence`);
     if(!gate.sameView(ticket)||!readGuard.current.isCurrentEvidence(evidenceTicket))return;
     setProjectEvidence(options);setEvidenceLoaded(true);
     if(gate.sameDraft(ticket)){
       setSelected(ids=>ids.length>=15||ids.includes(captured!.id)?ids:[...ids,captured!.id]);
       setNotice(idsafeMessage(captured,selected.length>=15));
     }else{
       setNotice(`Quality audit v${captured.dataset_version} captured, but your newer draft selection was not changed. Select its evidence explicitly if needed.`);
     }
   }catch(e){
     if(gate.sameView(ticket)){
       const detail=(e as Error).message;
       if(captured)setEvidenceLoaded(true);
       setError(captured
         ?`Quality audit v${captured.dataset_version} was captured, but its evidence list could not refresh: ${detail}`
         :detail);
     }
   }finally{if(gate.finish(ticket))setBusy('')}
 }
 function closeSavedPreview(){
   readGuard.current.invalidatePreview();
   setSavedPreview(null);setPreviewBusy(false);setPreviewError('');
 }
 async function previewSavedRevision(){
   if(!activeId||!opened)return;
   const viewTicket=composerGuard.current.currentView();
   const ticket=readGuard.current.beginPreview();
   const current=()=>activeProjectRef.current===projectId&&composerGuard.current.isCurrentView(viewTicket)&&readGuard.current.isCurrentPreview(ticket);
   const id=activeId,rev=revision??opened.revision;
   setPreviewBusy(true);setPreviewError('');setSavedPreview(null);
   try{
     // Same authenticated immutable-revision endpoint and filename/HTML
     // checks as Save As; obtaining a Blob does NOT download or write it.
     const {blob}=await downloadReportFile(`/reports/${encodeURIComponent(id)}/export/html?revision=${rev}`);
     const raw=await blob.text();
     if(!current())return;
     setSavedPreview({projectId,id,revision:rev,html:savedReportPreviewDocument(raw)});
   }catch(e){if(current())setPreviewError((e as Error).message)}
   finally{if(current())setPreviewBusy(false)}
 }
 async function download(format:'html'|'pdf'){
   if(!activeId||!opened)return;
   const viewTicket=composerGuard.current.currentView();
   const draftTicket=composerGuard.current.currentDraft();
   const exportTicket=readGuard.current.beginExport();
   const sameView=()=>activeProjectRef.current===projectId&&composerGuard.current.isCurrentView(viewTicket)&&readGuard.current.isCurrentExport(exportTicket);
   // Edited drafts must not unexpectedly open Save As for an old saved revision.
   const isCurrent=()=>sameView()&&composerGuard.current.isCurrentDraft(draftTicket);
   const reportId=activeId;
   const rev=revision??opened.revision;
   setBusy('export');setError('');
   try{
     const {blob,filename}=await downloadReportFile(`/reports/${encodeURIComponent(reportId)}/export/${format}?revision=${rev}`);
     if(!isCurrent())return; // Never launch Save As or a browser download for a superseded view.
     if(isDesktop()){
       const outcome=await saveReportNative(blob,filename,format);
       if(!isCurrent())return; // An already-open native dialog/write cannot be undone.
       if(outcome.status==='cancelled'){
         setNotice('Save As cancelled. No report file was written.');
       }else{
         setNotice(`Saved report revision ${rev} to ${outcome.filename??filename} using Windows Save As.`);
       }
     }else{
       const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;
       document.body.appendChild(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1500);
       setNotice(`Started browser download for saved revision ${rev}: ${filename}. Confirm the file in Downloads.`);
     }
   }catch(e){if(isCurrent())setError((e as Error).message)}
   // A draft edit vetoes this export but must not leave the workspace stuck busy.
   finally{if(sameView())setBusy('')}
 }
 function onDraftEdit(){
   userStartedDraft.current=true;composerGuard.current.editDraft();setNotice('');
   // An in-flight report Open must not replace a draft the user edited after clicking.
   latestOpenRequest.current++;
   if(busy==='open')setBusy('');
 }
 function shiftEvidence(id:string,by:number){
   onDraftEdit();
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
   <div className="pd-report-header"><div><span className="pd-report-eyebrow">DELIVER / LOCAL REPORTING</span><h2>Saved, evidence-backed reports</h2><p>Save revisions and export the exact same evidence to HTML or PDF. Source datasets remain unchanged.</p></div><button className="ud-btn ud-btn-quiet" disabled={busy==='save'||busy==='quality'||busy==='export'} onClick={newReport}><Plus size={15}/> New report</button></div>
   <nav aria-label="Report creation steps" className="pd-report-flow">{[['1','Compose'],['2','Save revision'],['3','Export']].map(([step,label],i)=><span key={step} className={Number(step)===reportStep?'pd-report-step-current':Number(step)<reportStep?'pd-report-step-done':''}><b>{step}</b>{label}</span>)}</nav>
   {hasDraftChanges&&<p role="status" className="pd-report-warning">Unsaved changes. Exports remain linked to the saved revision until you save again.</p>}
   {error&&<p role="alert" className="pd-report-error"><AlertCircle size={16}/>{error}</p>}
   {notice&&<p role="status" className="pd-report-notice"><ShieldCheck size={16}/>{notice}</p>}
   <div className="pd-report-columns"><section className="pd-report-editor">
     <label className="pd-report-field">Report title<input value={title} maxLength={180} onChange={e=>{onDraftEdit();setTitle(e.target.value)}}/></label>
     <label className="pd-report-field">Interpretation and limitations<textarea value={narrative} placeholder="Describe what the verified evidence establishes, what remains uncertain, and any important limitations. This text is authored by you." rows={5} maxLength={6000} onChange={e=>{onDraftEdit();setNarrative(e.target.value)}}/></label>
     <h3>Select verified evidence</h3>
     <div className="pd-report-quality-capture"><div><strong>Capture Quality findings</strong><small>Create a read-only, version-bound audit with issue counts and reviewed correction history. No source records or automatic corrections.</small></div><button type="button" className="ud-btn ud-btn-quiet" disabled={!!busy} onClick={()=>void captureQualityAudit()}>{busy==='quality'?'Capturing…':'Capture current Quality audit'}</button></div>
      {options.length?options.map(e=><div className="pd-report-evidence-row" key={e.id}><label className="pd-report-evidence"><input type="checkbox" checked={selected.includes(e.id)} onChange={ev=>{onDraftEdit();setSelected(ids=>ev.target.checked?ids.length>=15?ids:[...ids,e.id]:ids.filter(id=>id!==e.id))}}/><span><strong>{e.operation==='explore_snapshot'?'Saved Explore investigation':e.operation==='model_evaluation'?'Selected model evaluation':e.operation==='quality_audit'?'Saved Quality audit':e.operation.replaceAll('_',' ')} · v{e.version}{e.stale?' · HISTORICAL':''}</strong><small>{e.operation==='explore_snapshot'?(e.objective??'Saved analysis'):`${Object.entries(e.params||{}).map(([k,v])=>`${k}: ${String(v)}`).join(' · ')||'Dataset profile'}` } · Evidence {e.id.slice(0,12)}</small></span></label><button type="button" className="pd-report-inspect" aria-label={`Inspect verified ${e.operation.replaceAll('_',' ')} evidence ${e.id.slice(0,12)}`} disabled={!!inspectionBusy} onClick={()=>void inspectVerifiedEvidence(e.id)}>{inspectionBusy===e.id?'Inspecting…':'Inspect facts'}</button></div>):<p className="pd-report-muted">Capture a Quality audit, save an Explore analysis, evaluate a model, or create investigation evidence to start a report.</p>}
      {inspectionBusy&&<p role="status" className="pd-report-muted">Reading verified evidence facts…</p>}
      {inspectionError&&<p role="alert" className="pd-report-error">{inspectionError}</p>}
      {evidenceInspection&&evidenceInspection.projectId===projectId&&<section className="pd-report-evidence-inspection" aria-label="Verified evidence facts">
       <div className="pd-report-inspection-heading"><h4>Verified evidence facts · dataset v{evidenceInspection.dataset_version}</h4><button type="button" className="ud-btn ud-btn-quiet" onClick={closeEvidenceInspection} aria-label="Close evidence facts">Close</button></div>
       <p className="pd-report-muted">{evidenceInspection.operation.replaceAll('_',' ')} · {evidenceInspection.objective||'Verified analysis'} · {evidenceInspection.id.slice(0,12)}</p>
       {evidenceInspection.historical&&<p className="pd-report-warning">Historical evidence from version {evidenceInspection.dataset_version}. Your current dataset is version {evidenceInspection.current_dataset_version}; these facts have not been recomputed.</p>}
       {evidenceInspection.summary.length>0?<dl>{evidenceInspection.summary.map((fact,index)=><div key={index}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl>:<p className="pd-report-muted">No bounded aggregate facts are available for this verified artifact. You can still review the complete saved report after choosing it.</p>}
       {evidenceInspection.additional_summary_facts>0&&<p className="pd-report-muted">{evidenceInspection.additional_summary_facts} additional aggregate facts are intentionally omitted from this compact preview.</p>}
       {evidenceInspection.note&&<p className="pd-report-muted">{evidenceInspection.note}</p>}
       <p className="pd-report-muted">{evidenceInspection.disclosure}</p>
      </section>}
     {selected.filter(id=>!availableMap.has(id)).length>0&&<p className="pd-report-muted">{selected.filter(id=>!availableMap.has(id)).length} additional saved evidence references retained from the loaded report.</p>}
     {selected.length>1&&<section className="pd-report-order" aria-label="Order of report exhibits"><h4>Report exhibit order</h4><p className="pd-report-muted">Exhibits appear in this order in both saved HTML and PDF revisions.</p><ol>{selected.map((id,index)=><li key={id}><span><b>{index+1}.</b> {availableMap.get(id)?.operation.replaceAll('_',' ')||'Saved evidence'} · {id.slice(0,8)} · v{availableMap.get(id)?.version??opened?.evidence.find(item=>item.id===id)?.dataset_version??'?'}</span><div><button type="button" className="pd-report-order-button" aria-label={`Move exhibit ${index+1} earlier`} title="Move earlier" disabled={!!busy||index===0} onClick={()=>shiftEvidence(id,-1)}><ArrowUp size={15}/></button><button type="button" className="pd-report-order-button" aria-label={`Move exhibit ${index+1} later`} title="Move later" disabled={!!busy||index===selected.length-1} onClick={()=>shiftEvidence(id,1)}><ArrowDown size={15}/></button></div></li>)}</ol></section>}
     <div className="pd-report-actions"><div><strong>{selected.length} verified evidence artifacts selected</strong><small>{!saveReady?'Enter a report title and select evidence to continue.':hasDraftChanges?'Save your changes before exporting an updated revision.':opened?'Current saved revision is ready for export.':'Save a frozen report revision to enable HTML/PDF exports.'}</small></div><button className="ud-btn ud-btn-primary" disabled={!!busy||!saveReady||!hasDraftChanges&&!!opened} onClick={()=>void save()}><Save size={16}/>{busy==='save'?'Saving…':activeId?'Save new revision':'Save report'}</button></div>
     <details className="pd-report-preview"><summary>Preview report contents</summary><h4>{title}</h4><p>{narrative||'No narrative supplied. Verified evidence will be presented below.'}</p><ul>{selected.map(id=><li key={id}>{availableMap.get(id)?.operation.replaceAll('_',' ')||'Saved evidence'} · {id.slice(0,12)}</li>)}</ul></details>
     {opened&&<div className="pd-report-export"><div><strong>Saved revision {opened.revision}</strong><small>SHA-256 {opened.content_sha256.slice(0,18)}…</small></div><button type="button" disabled={!!busy||previewBusy} title="Preview the exact saved HTML revision locally without downloading" onClick={()=>void previewSavedRevision()}><Eye size={15}/>{previewBusy?'Loading preview…':'Preview saved HTML'}</button><button disabled={!!busy||hasDraftChanges} title={hasDraftChanges?'Save draft changes before exporting':'Export the last saved revision as HTML'} onClick={()=>void download('html')}><FileDown size={15}/> Export HTML</button><button disabled={!!busy||hasDraftChanges} title={hasDraftChanges?'Save draft changes before exporting':'Export the last saved revision as PDF'} onClick={()=>void download('pdf')}><FileDown size={15}/> Export PDF</button></div>}
     {opened?.has_historical_evidence&&<p className="pd-report-warning">Historical evidence: at least one included dataset version differs from the current active version. Existing calculations are preserved, not silently recomputed.</p>}
     {opened&&opened.dataset_versions.length>1&&<p className="pd-report-warning">This saved report intentionally includes evidence from dataset versions {opened.dataset_versions.join(', ')}.</p>}
   </section><aside className="pd-report-library"><h3><History size={17}/> Saved reports</h3>
     {reports.length===0&&<p className="pd-report-muted">No reports saved in this project yet.</p>}
     {reports.map(item=><button key={item.id} disabled={busy==='save'||busy==='quality'||busy==='export'} className={activeId===item.id?'pd-report-selected':''} onClick={()=>void openReport(item.id)}><FileText size={17}/><span><strong>{item.title}</strong><small>Revision {item.revision} · {new Date(item.updated_at).toLocaleDateString()}</small></span></button>)}
     {opened&&<label className="pd-report-field">Open saved revision<select value={revision??opened.revision} disabled={busy==='save'||busy==='quality'||busy==='export'} onChange={e=>void openReport(opened.id,Number(e.target.value))}>{opened.revisions.map(n=><option key={n} value={n}>Revision {n}</option>)}</select></label>}
     {opened&&opened.revisions.some(n=>n<opened.revision)&&<button type="button" className="ud-btn ud-btn-quiet" disabled={!!busy||comparisonBusy} onClick={()=>void comparePreviousSavedRevision()}>{comparisonBusy?'Comparing saved revisions…':'Compare with previous saved revision'}</button>}
     {opened&&<p className="pd-report-muted">Exports are generated locally from a saved revision. Editing above does not change the exported report until you save a new revision.</p>}
   </aside></div>
   {comparisonError&&<p role="alert" className="pd-report-error">{comparisonError}</p>}
   {revisionComparison&&revisionComparison.projectId===projectId&&revisionComparison.reportId===activeId&&
    revisionComparison.comparison.to===(revision??opened?.revision)&&
    <section className="pd-report-preview pd-report-revision-comparison" aria-label="Saved report revision differences">
     <h3>Saved revision comparison</h3>
     <p>Revision {revisionComparison.comparison.from} compared with revision {revisionComparison.comparison.to}. Only frozen saved evidence is compared; unsaved draft edits are excluded.</p>
     <p className="pd-report-muted">Previous SHA-256: {revisionComparison.comparison.fromSha256.slice(0,16)}… · Selected SHA-256: {revisionComparison.comparison.toSha256.slice(0,16)}…</p>
     {revisionComparison.comparison.identical&&<p>No saved report content differences detected.</p>}
     {revisionComparison.comparison.titleChanged&&<div><h4>Title changed</h4><p><strong>Previous:</strong> {revisionComparison.comparison.oldTitle}</p><p><strong>Selected:</strong> {revisionComparison.comparison.newTitle}</p></div>}
     {revisionComparison.comparison.narrativeChanged&&<div><h4>Interpretation changed</h4><p className="pd-report-diff-text"><strong>Previous:</strong> {revisionComparison.comparison.oldNarrative||'(empty)'}</p><p className="pd-report-diff-text"><strong>Selected:</strong> {revisionComparison.comparison.newNarrative||'(empty)'}</p></div>}
     {revisionComparison.comparison.added.length>0&&<div><h4>New evidence</h4><ul>{revisionComparison.comparison.added.map(e=><li key={e.id}>{e.operation} · {e.id.slice(0,12)} · dataset v{e.toVersion}</li>)}</ul></div>}
     {revisionComparison.comparison.removed.length>0&&<div><h4>Removed evidence</h4><ul>{revisionComparison.comparison.removed.map(e=><li key={e.id}>{e.operation} · {e.id.slice(0,12)} · dataset v{e.fromVersion}</li>)}</ul></div>}
     {revisionComparison.comparison.changed.length>0&&<div><h4>Revised evidence snapshots</h4><ul>{revisionComparison.comparison.changed.map(e=><li key={e.id}>{e.operation} · {e.id.slice(0,12)} · dataset v{e.fromVersion} → v{e.toVersion}</li>)}</ul></div>}
     {revisionComparison.comparison.orderChanged&&<p><strong>Exhibit order changed.</strong> Both revisions retain their original saved exhibit ordering.</p>}
     {(revisionComparison.comparison.versionsAdded.length>0||revisionComparison.comparison.versionsRemoved.length>0)&&<p><strong>Dataset version coverage changed.</strong> Added: {revisionComparison.comparison.versionsAdded.join(', ')||'none'}; removed: {revisionComparison.comparison.versionsRemoved.join(', ')||'none'}.</p>}
     {revisionComparison.comparison.otherSnapshotChanged&&<p>Other verified snapshot fields changed. Review the complete saved exports for full details; source evidence has not been recomputed.</p>}
     {hasDraftChanges&&<p className="pd-report-warning">Your unsaved draft changes are not included in this comparison.</p>}
    </section>}
   {previewError&&<p role="alert" className="pd-report-error">{previewError}</p>}
   {savedPreview&&savedPreview.projectId===projectId&&savedPreview.id===activeId&&savedPreview.revision===(revision??opened?.revision)&&<section className="pd-report-saved-preview" aria-label="Saved HTML report preview">
     <div className="pd-report-preview-heading">
       <div><strong>Preview: saved revision {savedPreview.revision}</strong>
         <p>This is the stored HTML report, not your unsaved edits or the PDF layout. No download was created.</p>
       </div>
       <button type="button" className="ud-btn ud-btn-quiet" onClick={closeSavedPreview} aria-label="Close saved report preview"><X size={16}/> Close preview</button>
     </div>
     {hasDraftChanges&&<p role="status" className="pd-report-warning">Unsaved draft changes are not included in this saved revision preview.</p>}
     <iframe title={`Saved HTML report revision ${savedPreview.revision}, read-only`}
       sandbox="" referrerPolicy="no-referrer" loading="lazy"
       srcDoc={savedPreview.html} className="pd-report-saved-preview-frame"/>
   </section>}
 </div>;
}
