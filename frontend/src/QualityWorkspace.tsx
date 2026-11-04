import {useCallback, useEffect, useRef, useState} from 'react';
import {AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, ClipboardCheck, History, LoaderCircle, RefreshCw, RotateCcw, ShieldCheck, Sparkles, Download, FileSpreadsheet, X} from 'lucide-react';
import {downloadCleanedData,get,post} from './api';
import {resolveQualityFocus} from './qualityHandoff';
import {qualityPreviewLabel} from './qualityPreviewLabel';
import type {QualityFocus} from './qualityHandoff';
import './quality-investigation.css';

export type QualityIssue={id:string;kind:string;column:string|null;affected_rows:number;title:string;explanation:string;severity:'automatic'|'review'|'information';automatic:boolean;proposal:null|{kind:string;column:string;from?:string;to?:string};evidence:Record<string,unknown>;decision:string};
type Quality={project_id:string;version:number;rows:number;columns:number;summary:{issues:number;automatic_available:number;review_required:number;information:number;applied_actions:number};issues:QualityIssue[]};
type Preview={version:number;total_matching_rows:number;offset:number;limit:number;rows:{row_number:number;original:Record<string,unknown>;working:Record<string,unknown>;proposed:Record<string,unknown>|null}[]};
type QualityProposal={proposal_id:string;proposal_hash:string;operation:string;expected_version:number;changed_cells:number;
 steps:{issue_id?:string;action_id?:string;target_version?:number;proposal?:{kind:string;column:string;from?:string;to?:string;value?:number};affected_rows?:number}[];
 preview:{row_number:number;column:string;before:unknown;after:unknown}[];expires_at:string;warning:string};
type QualityInvestigation={
 project_id:string;version:number;issue_id:string;kind:string;column:string;stored_dtype:string;
 dataset_rows:number;affected_rows:number;affected_row_numbers:number[];shown_row_numbers:number;
 statistical_method:string;statistics:Record<string,unknown>;warning:string;
 recommended_action:string;suggested_reviews:string[];
};
type HistoryData={current_version:number;versions:{version:number;event:string;created_at:string;details:Record<string,unknown>}[];actions:{id:string;kind:string;column:string;affected_rows:number;active:boolean;source:string}[]};

const val=(v:unknown)=>v===null||v===undefined?'—':String(v);
const badge=(s:string)=>s==='automatic'?'Safe correction':s==='information'?'Information':'Needs review';

export function QualityWorkspace({projectId,onChanged,initialFocus}:{projectId:string;onChanged:()=>void;initialFocus?:QualityFocus|null}){
  const [quality,setQuality]=useState<Quality|null>(null);
  const findingsRef=useRef<HTMLDivElement|null>(null);
  const consumedFocus=useRef<QualityFocus|null>(null);
  const [handoffNote,setHandoffNote]=useState('');
  const inspectorRef=useRef<HTMLDivElement|null>(null);
  const [investigation,setInvestigation]=useState<QualityInvestigation|null>(null);
  const [investigating,setInvestigating]=useState(false);
  const [history,setHistory]=useState<HistoryData|null>(null);
  const [preview,setPreview]=useState<Preview|null>(null);
  const [selected,setSelected]=useState<string>('');
  const [offset,setOffset]=useState(0);
  const [filter,setFilter]=useState<'all'|'pending'|'history'>('all');
  const [view,setView]=useState<'working'|'original'|'proposed'>('working');
  const [pendingApproval,setPendingApproval]=useState<{proposal:QualityProposal;message:string}|null>(null);
  const [exportVersion,setExportVersion]=useState(0);
  const [exportFormat,setExportFormat]=useState<'csv'|'xlsx'>('csv');
  const [exportColumns,setExportColumns]=useState<string[]>([]);
  const [exportFilterColumn,setExportFilterColumn]=useState('');
  const [exportFilterValue,setExportFilterValue]=useState('');
  const [exporting,setExporting]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  // Re-run only GET reads when the local Quality backend has restarted.
  const [retryReads,setRetryReads]=useState(0);
  const [notice,setNotice]=useState('');
  const [diagnostics,setDiagnostics]=useState<{column:string;missing_rows:number;missing_pct:number;row_numbers:number[];
     numeric_comparisons:{column:string;missing_group_median:number;other_group_median:number}[];
     categorical_comparisons:{column:string;groups:{label:string;missing_count:number;total_count:number}[]}[];
     suggested_treatments:{id:string;label:string;value?:number;tradeoff:string}[];caution:string}|null>(null);
  const [diagnosing,setDiagnosing]=useState(false);
  const load=useCallback(async()=>{
    const [q,h]=await Promise.all([get<Quality>(`/projects/${projectId}/quality`),get<HistoryData>(`/projects/${projectId}/quality/history`)]);
    setQuality(q);setHistory(h);setExportVersion(v=>h.versions.some(x=>x.version===v)?v:q.version);return q;
  },[projectId]);
  useEffect(()=>{let live=true;load().catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[load,retryReads]);
  useEffect(()=>{let live=true;const query=`/projects/${projectId}/quality/preview?offset=${offset}&limit=12${quality?`&expected_version=${quality.version}`:''}${selected?`&issue_id=${encodeURIComponent(selected)}`:''}`;
    get<Preview>(query).then(p=>{if(live)setPreview(p)}).catch(e=>{if(live){setPreview(null);setError(e.message)}});
    return()=>{live=false};
  },[projectId,selected,offset,quality?.version,retryReads]);
  useEffect(()=>{
    if(!quality||!initialFocus||consumedFocus.current===initialFocus)return;
    consumedFocus.current=initialFocus;
    const result=resolveQualityFocus(initialFocus,projectId,quality.version,quality.issues);
    if(result.status==='matched'){
      setSelected(result.issueId);setFilter('all');setOffset(0);setView('working');
      setDiagnostics(null);
      setHandoffNote('Opened the matching current-version Quality finding for review. No correction has been applied.');
    }else{
      setSelected('');setHandoffNote(result.message);
    }
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    findingsRef.current?.scrollIntoView({behavior:reduced?'auto':'smooth',block:'start',inline:'nearest'});
  },[initialFocus,projectId,quality]);
  useEffect(()=>{setInvestigation(null)},[projectId,selected,quality?.version]);
  const issue=quality?.issues.find(x=>x.id===selected);
  async function investigateFinding(selectedIssue:QualityIssue){
    if(!quality||!selectedIssue.column)return;
    setInvestigating(true);setInvestigation(null);setError('');
    try{
      const result=await get<QualityInvestigation>(`/projects/${projectId}/quality/investigate?issue_id=${encodeURIComponent(selectedIssue.id)}&expected_version=${quality.version}`);
      if(result.issue_id===selectedIssue.id&&result.version===quality.version)setInvestigation(result);
    }catch(e){setError((e as Error).message)}finally{setInvestigating(false)}
  }
  function showAffectedRecords(){
    setOffset(0);setView('working');
    const target=inspectorRef.current;
    if(!target)return;
    const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    target.scrollIntoView({behavior:reduce?'auto':'smooth',block:'start',inline:'nearest'});
  }
  async function finishVersionChange(version:number,message:string){
    const current=await load();
    if(selected&&!current.issues.some(x=>x.id===selected))setSelected('');
    setOffset(0);setExportVersion(version);setNotice(`${message} • Working version ${version}`);onChanged();
  }
  async function mutate(path:string,body:Record<string,unknown>,message:string){
    setBusy(true);setError('');setNotice('');
    try{
      if(path==='decisions'&&body.decision==='reject'){
        const result=await post<{version:number}>(`/projects/${projectId}/quality/decisions`,body);
        await finishVersionChange(result.version,message);
      }else{
        const operation=path==='autopilot'?'autopilot':path==='impute'?'impute':path==='undo'?'undo':path==='restore'?'restore':'approve';
        const proposal=await post<QualityProposal>(`/projects/${projectId}/quality/proposals`,{
          operation, expected_version:body.expected_version, issue_id:body.issue_id, column:body.column,
          action_id:body.action_id, target_version:body.target_version, strategy:body.strategy
        });
        setPendingApproval({proposal,message});
      }
    }catch(e){setError((e as Error).message);await load().catch(()=>{})}finally{setBusy(false)}
  }
  async function commitProposal(){
    if(!pendingApproval)return;
    setBusy(true);setError('');
    try{
      const {proposal,message}=pendingApproval;
      const result=await post<{version:number}>(`/projects/${projectId}/quality/commit`,{
        proposal_id:proposal.proposal_id,proposal_hash:proposal.proposal_hash
      });
      setPendingApproval(null);
      await finishVersionChange(result.version,message);
    }catch(e){setError((e as Error).message);setPendingApproval(null);await load().catch(()=>{})}
    finally{setBusy(false)}
  }
  async function exportCleanedData(){
    setExporting(true);setError('');setNotice('');
    try{
      const filters=exportFilterColumn&&exportFilterValue?[
        {column:exportFilterColumn,operator:'contains',value:exportFilterValue}
      ]:[];
      const {blob,filename}=await downloadCleanedData(`/projects/${projectId}/quality/export`,{
        version:exportVersion,format:exportFormat,columns:exportColumns.length?exportColumns:null,filters
      });
      const url=URL.createObjectURL(blob);
      try{const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;
        document.body.appendChild(anchor);anchor.click();anchor.remove();}
      finally{setTimeout(()=>URL.revokeObjectURL(url),60000)}
      setNotice(`Prepared ${filename}. Your original dataset remains unchanged.`);
    }catch(e){setError((e as Error).message)}finally{setExporting(false)}
  }
  async function diagnoseMissing(column:string){
    setDiagnosing(true);setDiagnostics(null);setError('');
    try{setDiagnostics(await get(`/projects/${projectId}/quality/missingness?column=${encodeURIComponent(column)}`));}
    catch(e){setError((e as Error).message)}finally{setDiagnosing(false)}
  }
  async function approveMedian(){if(!quality||!issue||!diagnostics)return;
    await mutate('impute',{expected_version:quality.version,issue_id:issue.id,column:issue.column,strategy:'median'},'Approved median imputation');
    setDiagnostics(null);
  }
  async function applyDecision(decision:'approve'|'reject'){
    if(!quality||!issue)return;
    await mutate('decisions',{expected_version:quality.version,issue_id:issue.id,decision},decision==='approve'?'Correction approved':'Recommendation rejected');
  }
  const display=quality?.issues.filter(x=>filter==='all'||(filter==='pending'&&x.decision==='pending'))??[];
  return <div className="quality-page">
    <section className="quality-banner"><div><div className="eyebrow">EVIDENCE-BASED SMART AUTOPILOT</div><h2>Make your dataset trustworthy</h2><p>Inspect findings, preview proposed changes and approve only what makes sense. Your original upload stays untouched.</p></div><div className="quality-banner-cta"><span className="pill">WORKING VERSION {quality?.version??'—'}</span><button className="btn primary" disabled={busy||!quality||quality.summary.automatic_available===0} onClick={()=>quality&&void mutate('autopilot',{expected_version:quality.version},'Safe corrections completed')}><Sparkles size={16}/> Review {quality?.summary.automatic_available??0} safe fixes</button></div></section>
    {error&&<div className="alert-error" role="alert"><AlertCircle size={16}/><span>{error}</span><button type="button" className="btn small" onClick={()=>{setError('');setRetryReads(count=>count+1)}}>Retry loading Quality</button></div>}
    {notice&&<div className="quality-notice"><CheckCircle2 size={16}/>{notice}</div>}
    {handoffNote&&<div className="quality-notice" role="status"><ClipboardCheck size={16}/>{handoffNote}</div>}
    <div className="quality-stats">
      <div><small>ISSUES FOUND</small><strong>{quality?.summary.issues??'—'}</strong></div>
      <div><small>NEED REVIEW</small><strong>{quality?.summary.review_required??'—'}</strong></div>
      <div><small>SAFE FIXES AVAILABLE</small><strong>{quality?.summary.automatic_available??'—'}</strong></div>
      <div><small>ACTIVE CORRECTIONS</small><strong>{quality?.summary.applied_actions??'—'}</strong></div>
    </div>
    <section className="panel" style={{padding:16,marginBottom:14}} aria-label="Export cleaned data">
      <div className="panel-title"><Download size={18}/><h2>Export cleaned dataset</h2><span className="pill muted">Original preserved</span></div>
      <p className="muted-caption">Download an approved current or historical version. Optional text filtering affects the export only; it never changes your project.</p>
      <div className="quality-toolbar" style={{display:'flex',flexWrap:'wrap',gap:10,alignItems:'center'}}>
        <label>Version <select value={exportVersion} onChange={e=>setExportVersion(Number(e.target.value))}>
          {history?.versions.map(v=><option key={v.version} value={v.version}>v{v.version} · {v.event}</option>)}
        </select></label>
        <label>Format <select value={exportFormat} onChange={e=>setExportFormat(e.target.value as 'csv'|'xlsx')}>
          <option value="csv">CSV</option><option value="xlsx">Excel XLSX</option>
        </select></label>
        <label>Optional text filter <select value={exportFilterColumn} onChange={e=>setExportFilterColumn(e.target.value)}>
          <option value="">All rows</option>{Object.keys(preview?.rows[0]?.working??{}).map(c=><option key={c} value={c}>{c}</option>)}
        </select></label>
        {exportFilterColumn&&<input aria-label="Filter contains" placeholder="Contains…" value={exportFilterValue} onChange={e=>setExportFilterValue(e.target.value)} />}
        <button className="btn primary" disabled={!quality||exporting||busy} onClick={()=>void exportCleanedData()}><FileSpreadsheet size={15}/>{exporting?'Exporting…':'Export dataset'}</button>
      </div>
      <details style={{marginTop:8}}><summary>Choose specific columns (optional)</summary>
        <p className="muted-caption">If none are selected, every column will be exported.</p>
        <div style={{display:'flex',flexWrap:'wrap',gap:12,marginTop:8}}>
          {Object.keys(preview?.rows[0]?.working??{}).map(column=><label key={column} style={{display:'flex',gap:5,alignItems:'center'}}>
            <input type="checkbox" checked={exportColumns.includes(column)} onChange={e=>setExportColumns(cols=>e.target.checked?[...cols,column]:cols.filter(c=>c!==column))}/>{column}
          </label>)}
        </div>
      </details>
    </section>
    {pendingApproval&&<div className="quality-approval-backdrop" role="presentation">
      <section className="panel quality-approval-dialog" role="dialog" aria-modal="true" aria-label="Review exact dataset change">
        <div className="panel-title"><ShieldCheck size={18}/><h2>Review before applying</h2>
          <button className="btn small" disabled={busy} onClick={()=>setPendingApproval(null)} aria-label="Cancel approval"><X size={16}/></button></div>
        <p>{pendingApproval.proposal.warning}</p>
        <p><b>Working version:</b> v{pendingApproval.proposal.expected_version} · <b>Changed cells:</b> {pendingApproval.proposal.changed_cells}</p>
        <div className="quality-approval-steps">{pendingApproval.proposal.steps.map((step,i)=><p key={i}>
          <strong>{step.proposal?.kind??pendingApproval.proposal.operation}</strong> · {step.proposal?.column??'Dataset'}
          {step.affected_rows!==undefined?` · ${step.affected_rows} rows`:''}
          {step.proposal?.from!==undefined?` · ${step.proposal.from} → ${step.proposal.to}`:''}
          {step.proposal?.value!==undefined?` · value ${step.proposal.value}`:''}
        </p>)}</div>
        <p className="muted-caption">Example changes (up to 12). Values are shown exactly for review: [SPACE], [TAB] and other markers reveal otherwise invisible whitespace. You can inspect the full affected data in the dataset inspector.</p>
        <div className="table-scroll" style={{maxHeight:230,overflowY:'auto'}}><table><thead><tr><th>Row</th><th>Column</th><th>Before</th><th>After</th></tr></thead><tbody>
          {pendingApproval.proposal.preview.map((r,i)=><tr key={i}><td>{r.row_number}</td><td>{r.column}</td><td>{qualityPreviewLabel(r.before)}</td><td>{qualityPreviewLabel(r.after)}</td></tr>)}
        </tbody></table></div>
        <div className="quality-action-row" style={{justifyContent:'flex-end',marginTop:16}}>
          <button className="btn" disabled={busy} onClick={()=>setPendingApproval(null)}>Cancel</button>
          <button className="btn primary" disabled={busy} onClick={()=>void commitProposal()}><CheckCircle2 size={15}/>{busy?'Applying…':'Approve these changes'}</button>
        </div>
      </section>
    </div>}
    <div className="quality-split">
      <div className="panel quality-table-panel" ref={inspectorRef}>
        <div className="panel-title"><ClipboardCheck size={18}/><h2>Dataset inspector</h2><span className="pill muted">{preview?.total_matching_rows??0} rows</span></div>
        <div className="quality-toolbar"><div className="workspace-tabs" style={{margin:0}}>{(['original','working','proposed'] as const).map(t=><button className={'workspace-tab '+(view===t?'selected':'')} onClick={()=>setView(t)} key={t}>{t==='original'?'Original':t==='working'?'Current':'Proposed'}</button>)}</div><button className="btn small" onClick={()=>{setOffset(0);void load()}}><RefreshCw size={14}/> Refresh</button></div>
        <p className="muted-caption">{issue?`Showing records related to: ${issue.title}`:'Showing a paginated sample of the working dataset.'} Changed cells are highlighted.</p>
        <div className="table-scroll quality-table"><table><thead><tr><th>ROW</th>{Object.keys(preview?.rows[0]?.working??{}).map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{preview?.rows.map(r=>{const data=view==='original'?r.original:view==='proposed'?(r.proposed??r.working):r.working;return <tr key={r.row_number}><td className="cell-strong">{r.row_number}</td>{Object.keys(r.working).map(c=><td key={c} className={val(data[c])!==val(r.original[c])?'changed-cell':''} title={val(data[c])}>{val(data[c]).slice(0,45)}</td>)}</tr>})}</tbody></table></div>
        {!preview?.rows.length&&<p className="body-muted">No matching records on this page.</p>}
        <div className="quality-pagination"><button className="btn small" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-12))}><ArrowLeft size={14}/> Previous</button><span>{preview?.total_matching_rows?`${offset+1}–${Math.min(offset+12,preview.total_matching_rows)} of ${preview.total_matching_rows}`:'No rows'}</span><button className="btn small" disabled={!preview||offset+12>=preview.total_matching_rows} onClick={()=>setOffset(offset+12)}>Next <ArrowRight size={14}/></button></div>
      </div>
      <div ref={findingsRef} className="panel quality-findings-panel">
        <div className="panel-title"><Sparkles size={18}/><h2>Intelligent findings</h2><span className="pill muted">LOCAL RULES</span></div>
        <div className="quality-filters">{(['all','pending','history'] as const).map(t=><button className={filter===t?'selected':''} key={t} onClick={()=>setFilter(t)}>{t==='all'?'All findings':t==='pending'?'Pending':'History'}</button>)}</div>
        {filter==='history'?<div className="history-list">
          <p className="muted-caption">Every version is retained, including reversed actions.</p>
          {history?.versions.slice().reverse().map(v=><div className="history-entry" key={v.version}><div><strong>Version {v.version} · {v.event}</strong><small>{new Date(v.created_at).toLocaleString()}</small></div>{quality&&v.version!==quality.version&&<button className="btn small" disabled={busy} onClick={()=>void mutate('restore',{expected_version:quality.version,target_version:v.version},'Version restored')}><RotateCcw size={14}/> Restore</button>}</div>)}
          <h3>Transformation log</h3>{history?.actions.map(a=><div className="history-entry" key={a.id}><div><strong>{a.kind} · {a.column}</strong><small>{a.affected_rows} rows · {a.source} · {a.active?'Active':'Inactive'}</small></div>{a.active&&quality&&<button className="btn small" disabled={busy} onClick={()=>void mutate('undo',{expected_version:quality.version,action_id:a.id},'Action undone')}><RotateCcw size={14}/> Undo</button>}</div>)}</div>:
          <><div className="quality-issue-list">{display.map(it=><button className={'quality-issue '+(selected===it.id?'active':'')} key={it.id} onClick={()=>{setSelected(it.id);setOffset(0);setView('proposed');setDiagnostics(null)}}><span className={`quality-priority ${it.severity}`}/><span><b>{it.title}</b><small>{it.column??'Entire dataset'} · {it.affected_rows.toLocaleString()} affected · {it.decision==='pending'?badge(it.severity):it.decision}</small></span><ArrowRight size={14}/></button>)}</div>
          {issue&&<div className="quality-detail"><div className="quality-detail-top"><h3>{issue.title}</h3><button className="btn small" onClick={()=>{setSelected('');setOffset(0);setView('working')}}>Clear</button></div><p>{issue.explanation}</p>{issue.proposal&&<div className="quality-proposal"><b>Proposed action</b><span>{issue.proposal.from!==undefined?`${issue.proposal.from} → ${issue.proposal.to}`:'Remove unnecessary surrounding whitespace from eligible category labels'}</span></div>}
          {Object.keys(issue.evidence).length>0&&<div className="quality-evidence">{Object.entries(issue.evidence).map(([k,v])=><span key={k}>{k.replaceAll('_',' ')}: <b>{typeof v==='object'?JSON.stringify(v):String(v)}</b></span>)}</div>}
          {(issue.decision==='pending'||issue.decision==='undone'||issue.decision==='rejected')&&issue.proposal&&<div className="quality-action-row"><button className="btn primary" disabled={busy} onClick={()=>void applyDecision('approve')}><CheckCircle2 size={15}/> {issue.automatic?'Review this correction':'Approve'}</button>{issue.decision==='pending'&&<button className="btn" disabled={busy} onClick={()=>void applyDecision('reject')}>Reject</button>}</div>}
          {issue.kind==='missing'&&issue.column&&<div className="missingness-action"><button className="btn" disabled={busy||diagnosing} onClick={()=>void diagnoseMissing(issue.column!)}>{diagnosing?<LoaderCircle className="spin" size={15}/>:<Sparkles size={15}/>} Investigate missingness</button>
             {diagnostics&&diagnostics.column===issue.column&&<div className="missingness-report" role="region" aria-label="Verified missing data investigation"><b>Local investigation · {diagnostics.missing_rows} missing ({diagnostics.missing_pct}%)</b><p>Rows: {diagnostics.row_numbers.slice(0,30).join(', ')}.</p>
             {diagnostics.numeric_comparisons.map(c=><p key={c.column}><strong>{c.column}</strong> · median of affected rows {c.missing_group_median.toLocaleString()}, other rows {c.other_group_median.toLocaleString()}.</p>)}
             {diagnostics.categorical_comparisons.map(c=><div key={c.column}><strong>{c.column}</strong><ul>{c.groups.map(g=><li key={g.label}>{g.label}: {g.missing_count}/{g.total_count} missing</li>)}</ul></div>)}
             {diagnostics.suggested_treatments.map(t=><div key={t.id} className="treatment-option"><strong>{t.label}</strong><p>{t.tradeoff}</p>{t.id==='median'&&<button className="btn primary small" disabled={busy} onClick={()=>void approveMedian()}>Review and approve median fill</button>}</div>)}
             <small>{diagnostics.caution}</small></div>}
          </div>}
          {(issue.kind==='outliers'||issue.kind==='identifier')&&issue.column&&<div className="po-quality-investigation">
             <div className="quality-action-row">
               <button className="btn" type="button" disabled={investigating||busy} onClick={()=>void investigateFinding(issue)}>{investigating?<LoaderCircle size={15} className="spin"/>:<Sparkles size={15}/>} Investigate {issue.kind==='outliers'?'unusual values':'identifier characteristics'}</button>
               <button className="btn" type="button" onClick={showAffectedRecords}><FileSpreadsheet size={15}/> Show matching source rows</button>
             </div>
             {investigation?.issue_id===issue.id&&investigation.version===quality?.version&&<div className="po-quality-investigation-result" role="region" aria-label="Read-only finding investigation">
               <div className="po-quality-investigation-heading"><strong>{investigation.statistical_method}</strong><span className="pill muted">VERIFIED · v{investigation.version}</span></div>
               <p><b>{investigation.affected_rows.toLocaleString()}</b> affected of {investigation.dataset_rows.toLocaleString()} records · field <b>{investigation.column}</b> · stored dtype <code>{investigation.stored_dtype}</code>.</p>
               <div className="po-quality-investigation-stats">{Object.entries(investigation.statistics).filter(([,value])=>typeof value==='number'||typeof value==='string').map(([name,value])=><div key={name}><small>{name.replaceAll('_',' ')}</small><strong>{typeof value==='number'?value.toLocaleString(undefined,{maximumFractionDigits:4}):String(value)}</strong></div>)}</div>
               <p className="po-quality-warning">{investigation.warning}</p>
               <h4>Review before taking action</h4>
               <ul>{investigation.suggested_reviews.map((review,i)=><li key={i}>{review}</li>)}</ul>
               <p className="muted-caption">Matching source row numbers (up to 40): {investigation.affected_row_numbers.join(', ')||'None'}. {investigation.recommended_action}</p>
               <button type="button" className="btn" onClick={showAffectedRecords}><ArrowLeft size={14}/> Inspect these records in Dataset inspector</button>
             </div>}
           </div>}
           {issue.severity==='information'&&<p className="muted-caption">Informational finding. No data transformation is proposed.</p>}{issue.decision==='undone'&&<p className="muted-caption">You undid this correction. Smart Autopilot will not silently reapply it.</p>}</div>}</>}
        {busy&&<div className="quality-loading"><LoaderCircle size={15} className="spin"/> Processing validated change…</div>}
      </div>
    </div>
    <p className="muted-caption"><ShieldCheck size={13} style={{verticalAlign:'middle'}}/> Cleaning only changes a versioned working copy. Training on a new version requires a new experiment.</p>
  </div>;
}
