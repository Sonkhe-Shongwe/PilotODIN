import {useEffect,useState} from 'react';
import {BookOpen,Check,History,LoaderCircle,Save,ShieldCheck} from 'lucide-react';
import {get,post} from './api';
import './saved-explore-analyses.css';

export type ExploreState={
 x:string;y:string|null;kind:string;aggregation:string;bins:number;
 correlation_method:'pearson'|'spearman';
 filters:{column:string;op:string;value?:string;min?:number;max?:number}[];
};
type SavedSummary={id:string;title:string;dataset_version:number;created_at:string;stale:boolean;sha256:string};
type FrozenEvidence={
 version:number;total_rows:number;filtered_rows:number;
 chart:{type:string;x:string;y:string|null;sampled:boolean;truncated?:boolean;data:{label?:string;value?:number}[];note:string}|null;
 overview:{rows:number;columns:{name:string}[];missing_cells:number;exact_duplicates:number};
 correlation:{method:string;columns:string[]};source:string;limitations:string[];
};
type SavedAnalysis=SavedSummary&{project_id:string;current_dataset_version:number;configuration:ExploreState;snapshot:FrozenEvidence};
function number(n:number){return n.toLocaleString(undefined,{maximumFractionDigits:2})}

export function SavedExploreAnalyses({projectId,version,configuration,onRestore,ready}:{
 projectId:string;version:number|null;configuration:ExploreState;
 onRestore:(config:ExploreState)=>void;ready:boolean;
}){
 const [title,setTitle]=useState('');
 const [list,setList]=useState<SavedSummary[]>([]);
 const [selected,setSelected]=useState<SavedAnalysis|null>(null);
 const [busy,setBusy]=useState<'save'|'open'|''>('');
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');

 useEffect(()=>{
  let active=true;setList([]);setSelected(null);setTitle('');setError('');setNotice('');
  get<SavedSummary[]>(`/projects/${projectId}/explore/saved`).then(result=>{if(active)setList(result)})
   .catch(e=>{if(active)setError((e as Error).message)});
  return()=>{active=false};
 },[projectId,version]);

 async function saveCurrent(){
  if(!ready||version===null||!title.trim())return;
  setBusy('save');setError('');setNotice('');
  try{
   const result=await post<SavedAnalysis>(`/projects/${projectId}/explore/saved`,{
     title:title.trim(),expected_version:version,...configuration
   });
   setSelected(result);setTitle('');
   setList(await get<SavedSummary[]>(`/projects/${projectId}/explore/saved`));
   setNotice(`Saved verified analysis "${result.title}" for dataset version ${result.dataset_version}.`);
  }catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 async function openSaved(id:string){
  setBusy('open');setError('');setNotice('');
  try{
   const saved=await get<SavedAnalysis>(`/projects/${projectId}/explore/saved/${encodeURIComponent(id)}`);
   if(saved.project_id!==projectId)throw new Error('Saved analysis belongs to another project');
   setSelected(saved);
   if(!saved.stale&&saved.dataset_version===version){
     onRestore(saved.configuration);
     setNotice('Saved configuration restored to the current Explore workbench.');
   }else{
     setNotice('Historical snapshot opened read-only. Live filters and charts have not changed.');
   }
  }catch(e){setError((e as Error).message)}finally{setBusy('')}
 }

 return <section className="panel po-saved-analyses" aria-label="Saved analytical investigations">
  <div className="panel-title"><BookOpen size={19}/><h2>Saved analyses and evidence</h2><span className="pill muted">LOCAL · VERSIONED</span></div>
  <p className="body-muted">Preserve your current filters, chart setup and verified analytical results. A saved snapshot is immutable and can be reopened even after the dataset changes.</p>
  <div className="po-saved-controls">
   <label>Analysis title<input className="input" maxLength={120} minLength={4} placeholder="e.g. Claims by region above R10,000" value={title} onChange={e=>setTitle(e.target.value)}/></label>
   <button className="btn primary" type="button" disabled={!ready||version===null||title.trim().length<4||busy!==''} onClick={()=>void saveCurrent()}>{busy==='save'?<LoaderCircle size={16} className="spin"/>:<Save size={16}/>} Save current analysis</button>
  </div>
  {error&&<p className="alert-error" role="alert">{error}</p>}
  {notice&&<p className="po-saved-success" role="status"><Check size={15}/>{notice}</p>}
  <div className="po-saved-library">
   <div><h3><History size={17}/> Saved investigation library</h3><p className="muted-caption">{list.length} recent saved analyses for this project.</p></div>
   {list.length?<div className="po-saved-items">{list.map(item=><div className="po-saved-item" key={item.id}>
      <div><strong>{item.title}</strong><small>Dataset v{item.dataset_version} · {new Date(item.created_at).toLocaleString()}</small><span className={item.stale?'po-saved-stale':'po-saved-current'}>{item.stale?'Historical version':'Current version'}</span></div>
      <button type="button" className="btn" disabled={busy!==''} onClick={()=>void openSaved(item.id)}>{busy==='open'?<LoaderCircle size={14} className="spin"/>:'Open'}</button>
   </div>)}</div>:<p className="body-muted">No saved analyses yet. Name your current investigation and save it to this project.</p>}
  </div>
  {selected&&<div className="po-saved-frozen" aria-label="Saved analytical evidence">
    <div className="po-saved-frozen-title"><ShieldCheck size={18}/><strong>{selected.title}</strong><span className={selected.stale?'po-saved-stale':'po-saved-current'}>{selected.stale?'HISTORICAL SNAPSHOT':'VERIFIED SNAPSHOT'}</span></div>
    <p className="body-muted">{selected.stale?'This evidence belongs to an older approved dataset version. Its results are frozen and were not recalculated on the current data.':'The saved configuration is available in Explore. Its evidence below is the original verified, frozen result.'}</p>
    <div className="po-saved-kpis"><span><small>Version</small><strong>{selected.dataset_version}</strong></span><span><small>Rows in original dataset</small><strong>{number(selected.snapshot.total_rows)}</strong></span><span><small>Filtered rows</small><strong>{number(selected.snapshot.filtered_rows)}</strong></span><span><small>Chart</small><strong>{selected.snapshot.chart?.type??'No chartable rows'}</strong></span></div>
    <p className="muted-caption">Chart: {selected.configuration.x}{selected.configuration.y?` vs ${selected.configuration.y}`:''} · {selected.configuration.filters.length} filters · {selected.configuration.aggregation} aggregation</p>
    {selected.snapshot.chart&&selected.snapshot.chart.type==='bar'&&<div className="po-saved-summary-table"><table><thead><tr><th>Saved group</th><th>Saved value</th></tr></thead><tbody>{selected.snapshot.chart.data.slice(0,12).map((row,i)=><tr key={i}><td>{row.label??'—'}</td><td>{row.value===undefined?'—':number(row.value)}</td></tr>)}</tbody></table></div>}
    <p className="muted-caption">SHA-256: <code>{selected.sha256}</code></p>
    <p className="muted-caption">These results are locally computed descriptive evidence, not causal conclusions. Export and attachment to Deliver will be handled in the reporting macro.</p>
  </div>}
 </section>;
}
