import {useEffect,useMemo,useState} from 'react';
import {AlertTriangle,BarChart3,Database,Hash,LoaderCircle,Search,Table2} from 'lucide-react';
import {get} from './api';
import {SemanticOverview} from './SemanticOverview';
import './column-investigation.css';

type ColumnEntry={
 name:string;dtype:string;role:string;role_explanation:string;rows:number;
 non_null:number;missing:number;missing_pct:number;unique:number;unique_pct:number;
 identifier_candidate:boolean;warnings:string[];
};
type Dictionary={version:number;rows:number;column_count:number;columns:ColumnEntry[];role_counts:Record<string,number>;note:string};
type NumericStats={count:number;min:number|null;q1:number|null;median:number|null;mean:number|null;q3:number|null;max:number|null;std:number|null;zero_count:number;negative_count:number};
type ColumnDetail=ColumnEntry&{version:number;examples:(string|number|boolean|null)[];sample_rows:{row_number:number;value:string|number|boolean|null;missing:boolean}[];
 statistics:NumericStats|null;distribution:{value:string;count:number;pct:number}[];invalid_or_nonfinite:number;sample_note:string;distribution_note:string};

function pretty(value:number|null|undefined):string{
 return typeof value==='number'&&Number.isFinite(value)?value.toLocaleString(undefined,{maximumFractionDigits:3}):'—';
}
function display(value:unknown):string{return value===null||value===undefined?'(Missing)':String(value);}
type SortBy='source'|'name'|'missing'|'unique';

export function ColumnInvestigation({projectId,versionToken}:{projectId:string;versionToken:number}){
 const [dictionary,setDictionary]=useState<Dictionary|null>(null);
 const [selected,setSelected]=useState('');
 const [detail,setDetail]=useState<ColumnDetail|null>(null);
 const [loading,setLoading]=useState(false);
 const [detailLoading,setDetailLoading]=useState(false);
 const [error,setError]=useState('');
 const [detailError,setDetailError]=useState('');
 const [search,setSearch]=useState('');
 const [roleFilter,setRoleFilter]=useState('all');
 const [sortBy,setSortBy]=useState<SortBy>('source');

 useEffect(()=>{
  let live=true;setLoading(true);setError('');setDictionary(null);setDetail(null);setSelected('');
  get<Dictionary>(`/projects/${projectId}/columns/overview`)
   .then(data=>{
    if(!live)return;
    setDictionary(data);
    setSelected(data.columns[0]?.name??'');
   }).catch(e=>{if(live)setError((e as Error).message)})
   .finally(()=>{if(live)setLoading(false)});
  return()=>{live=false};
 },[projectId,versionToken]);

 useEffect(()=>{
  if(!dictionary||!selected||!dictionary.columns.some(c=>c.name===selected))return;
  let live=true;setDetailLoading(true);setDetailError('');setDetail(null);
  get<ColumnDetail>(`/projects/${projectId}/columns/detail?name=${encodeURIComponent(selected)}&expected_version=${dictionary.version}`)
   .then(data=>{
    if(!live)return;
    if(data.version!==dictionary.version){setDetailError('Dataset version changed. Refresh Your data.');return;}
    setDetail(data);
   }).catch(e=>{if(live)setDetailError((e as Error).message)})
   .finally(()=>{if(live)setDetailLoading(false)});
  return()=>{live=false};
 },[projectId,versionToken,dictionary,selected]);

 const columns=useMemo(()=>{
  const items=(dictionary?.columns??[]).filter(c=>(roleFilter==='all'||c.role===roleFilter)&&
    (c.name.toLowerCase().includes(search.trim().toLowerCase())||
     c.dtype.toLowerCase().includes(search.trim().toLowerCase())||
     c.role.toLowerCase().includes(search.trim().toLowerCase())));
  if(sortBy==='name')return [...items].sort((a,b)=>a.name.localeCompare(b.name));
  if(sortBy==='missing')return [...items].sort((a,b)=>b.missing-a.missing);
  if(sortBy==='unique')return [...items].sort((a,b)=>b.unique-a.unique);
  return items;
 },[dictionary,search,roleFilter,sortBy]);

 return <section className="panel po-col-investigation" aria-label="Data dictionary and field investigation">
  <div className="panel-title"><Database size={19}/><h2>Data dictionary and column investigation</h2><span className="pill muted">WORKING VERSION {dictionary?.version??'—'}</span></div>
  <p className="body-muted">Inspect each field's stored dtype, inferred analytical role, completeness, values and distribution. This is read-only and calculated locally.</p>
  {loading&&<p className="po-col-status" role="status"><LoaderCircle size={16} className="spin"/> Loading current field metadata…</p>}
  {error&&<p className="alert-error" role="alert">{error}</p>}
  {dictionary&&<>
   <div className="po-col-summary" aria-label="Field type summary">
    <span><strong>{pretty(dictionary.column_count)}</strong> fields</span>
    <span><strong>{pretty(dictionary.rows)}</strong> records</span>
    {Object.entries(dictionary.role_counts).map(([role,count])=><span key={role}><strong>{count}</strong> {role}</span>)}
   </div>
   <SemanticOverview key={projectId+'-'+dictionary.version} projectId={projectId} version={dictionary.version}
    columns={dictionary.columns.map(item=>item.name)}/>
   <div className="po-col-toolbar">
    <label className="po-col-search"><Search size={15}/><input aria-label="Search columns by name or type" placeholder="Find a field or dtype…" value={search} onChange={e=>setSearch(e.target.value)}/></label>
    <label>Analytical role<select aria-label="Filter columns by analytical role" value={roleFilter} onChange={e=>setRoleFilter(e.target.value)}><option value="all">All roles</option>{Object.keys(dictionary.role_counts).map(role=><option key={role} value={role}>{role}</option>)}</select></label>
    <label>Sort<select aria-label="Sort columns" value={sortBy} onChange={e=>setSortBy(e.target.value as SortBy)}><option value="source">Dataset order</option><option value="name">Field name</option><option value="missing">Most missing</option><option value="unique">Most distinct</option></select></label>
   </div>
   <div className="po-col-layout">
    <div className="po-col-list">
     <div className="po-col-table-scroll">
      <table><thead><tr><th>FIELD</th><th>STORED DTYPE</th><th>ANALYTICAL ROLE</th><th>MISSING</th><th>DISTINCT</th></tr></thead>
       <tbody>{columns.map(col=><tr key={col.name} className={selected===col.name?'po-col-selected':''}>
        <td><button type="button" className="po-col-field" aria-pressed={selected===col.name} onClick={()=>setSelected(col.name)}>{col.name}{col.warnings.length>0&&<AlertTriangle size={13} aria-label="Review field warnings"/>}</button></td>
        <td><code>{col.dtype}</code></td><td><span className="po-col-role">{col.role}</span></td>
        <td>{pretty(col.missing_pct)}%</td><td>{pretty(col.unique)}</td>
       </tr>)}</tbody>
      </table>
     </div>
     {columns.length===0&&<p className="body-muted">No columns match this search or role. Clear the filters to see all fields.</p>}
     <p className="muted-caption">{columns.length} of {dictionary.column_count} fields shown. Select a field to investigate its actual values.</p>
    </div>
    <div className="po-col-detail" aria-label="Selected field investigation" aria-live="polite">
     {detailLoading&&<p className="po-col-status" role="status"><LoaderCircle size={16} className="spin"/> Inspecting {selected}…</p>}
     {detailError&&<p className="alert-error" role="alert">{detailError}</p>}
     {!detailLoading&&!detailError&&detail&&<>
      <div className="po-col-detail-head"><div><div className="eyebrow">SELECTED FIELD</div><h3>{detail.name}</h3></div><span className="po-col-role">{detail.role}</span></div>
      <div className="po-col-metadata"><div><small>Stored dtype</small><strong>{detail.dtype}</strong></div><div><small>Analytical role</small><strong>{detail.role}</strong></div><div><small>Non-missing</small><strong>{pretty(detail.non_null)}</strong></div><div><small>Missing</small><strong>{pretty(detail.missing)} ({pretty(detail.missing_pct)}%)</strong></div><div><small>Distinct</small><strong>{pretty(detail.unique)}</strong></div><div><small>Distinct among present</small><strong>{pretty(detail.unique_pct)}%</strong></div></div>
      <p className="po-col-description">{detail.role_explanation}</p>
      {detail.warnings.length>0&&<div className="po-col-warnings">{detail.warnings.map((warning,i)=><p key={i}><AlertTriangle size={14}/>{warning}</p>)}</div>}
      {detail.statistics&&<><h4><BarChart3 size={16}/> Numerical profile</h4><div className="po-col-metadata po-col-numeric">{([
       ['Minimum',detail.statistics.min],['Q1 (25%)',detail.statistics.q1],['Median',detail.statistics.median],
       ['Mean',detail.statistics.mean],['Q3 (75%)',detail.statistics.q3],['Maximum',detail.statistics.max],
       ['Std. deviation',detail.statistics.std],['Zeros',detail.statistics.zero_count],
       ['Negatives',detail.statistics.negative_count],['Finite observations',detail.statistics.count]
      ] as [string,number|null][]).map(([label,value])=><div key={label}><small>{label}</small><strong>{pretty(value)}</strong></div>)}</div>
      {detail.invalid_or_nonfinite>0&&<p className="po-col-warning-inline">{pretty(detail.invalid_or_nonfinite)} present values are non-finite or unusable for numerical summaries.</p>}</>}
      {detail.distribution.length>0&&<><h4><BarChart3 size={16}/> Most frequent values</h4><div className="po-col-frequencies">{detail.distribution.map((v,i)=><div key={i} className="po-col-frequency"><span title={v.value}>{v.value}</span><div className="po-col-frequency-track"><div style={{width:`${v.pct}%`}}/></div><strong>{pretty(v.count)} · {pretty(v.pct)}%</strong></div>)}</div><p className="muted-caption">{detail.distribution_note}</p></>}
      <h4><Hash size={16}/> Observed examples</h4><div className="po-col-examples">{detail.examples.length?detail.examples.map((value,i)=><span key={i} title={display(value)}>{display(value)}</span>):<p className="body-muted">No non-missing examples.</p>}</div>
      <h4><Table2 size={16}/> Source-order sample</h4><div className="po-col-sample"><table><thead><tr><th>ROW</th><th>VALUE</th><th>STATUS</th></tr></thead><tbody>{detail.sample_rows.map(row=><tr key={row.row_number}><td>{row.row_number}</td><td title={display(row.value)}>{display(row.value)}</td><td>{row.missing?'Missing':'Present'}</td></tr>)}</tbody></table></div>
      <p className="muted-caption">{detail.sample_note} Row numbers refer to this working version and may change after cleaning.</p>
     </>}
     {!selected&&!detailLoading&&<p className="body-muted">Select a field from the dictionary to inspect its values.</p>}
    </div>
   </div>
   <p className="muted-caption">{dictionary.note} Date-like and numeric-like strings remain text until explicitly corrected or converted in a reviewed workflow.</p>
  </>}
 </section>;
}
