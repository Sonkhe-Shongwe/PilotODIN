import {useEffect,useState} from 'react';
import {Activity, BarChart3, ChevronDown, LoaderCircle, RefreshCw, Sparkles, Plus, X} from 'lucide-react';
import {get,post} from './api';
import './explore-enhancements.css';
type Column={name:string;kind:'numeric'|'categorical';unique:number;missing:number;missing_pct:number;min?:number;max?:number;mean?:number;median?:number};
type Overview={version:number;rows:number;missing_cells:number;exact_duplicates:number;columns:Column[]};
type Plot={version:number;type:string;x:string;y:string|null;aggregation?:string;data:{label?:string;value?:number;x?:number;y?:number;min?:number;q1?:number;median?:number;q3?:number;max?:number;start?:number;end?:number;whisker_low?:number;whisker_high?:number;outliers?:number[];outliers_total?:number;row_ref?:number}[];sampled:boolean;truncated?:boolean;valid_observations?:number;excluded_observations?:number;note:string};
type CorrelationCell={x:string;y:string;r:number|null;n:number};
type Correlation={version:number;method:string;columns:string[];cells:CorrelationCell[];note:string};
type Finding={category:string;column:string|null;title:string;detail:string};
type ChartSelection={kind:'category';label:string}|{kind:'bin';bin_index:number}|{kind:'point';row_ref:number};
type InspectedRow={filtered_row_number:number;cells:(string|number|boolean|null)[]};
type InspectorResponse={version:number;selection_kind:string;description:string;matched_rows:number;measure_rows:number;offset:number;limit:number;columns:string[];rows:InspectedRow[];truncated_columns:boolean;note:string;total_filtered_rows:number};
type FilterColumn={name:string;kind:'numeric'|'categorical';options?:string[];min?:number;max?:number;missing:number};
type FilterCatalog={version:number;columns:FilterColumn[];max_filters:number;note:string};
type FilterClause={column:string;op:'eq'|'range';value?:string;min?:number;max?:number};
type Workbench={version:number;total_rows:number;filtered_rows:number;overview:Overview;chart:Plot|null;chart_message:string;correlation:Correlation;note:string};
function filterFor(column:FilterColumn):FilterClause{
 return column.kind==='numeric'
  ?{column:column.name,op:'range',min:column.min??0,max:column.max??0}
  :{column:column.name,op:'eq',value:column.options?.[0]??''};
}
type ChartSuggestion={title:string;x:string;y:string|null;kind:string;aggregation:string;reason:string};
type ExplorePreferences={x:string;y:string;kind:string;aggregation:string};
const allowedKinds=new Set(['auto','bar','histogram','scatter','line','box']);
const allowedAggregations=new Set(['mean','sum','median','count']);
function preferencesKey(projectId:string){return `pilotodin-explore-prefs-v1-${encodeURIComponent(projectId)}`;}
function readPreferences(projectId:string):ExplorePreferences{
 const defaults={x:'',y:'',kind:'auto',aggregation:'mean'};
 try{const value=JSON.parse(localStorage.getItem(preferencesKey(projectId))||'null');if(!value||typeof value!=='object'||Array.isArray(value))return defaults;
  return {x:typeof value.x==='string'&&value.x.length<=256?value.x:'',y:typeof value.y==='string'&&value.y.length<=256?value.y:'',
    kind:allowedKinds.has(value.kind)?value.kind:'auto',aggregation:allowedAggregations.has(value.aggregation)?value.aggregation:'mean'};
 }catch{return defaults}
}
function format(n:number){return n.toLocaleString(undefined,{maximumFractionDigits:2})}
function correlationTone(v:number|null){
 if(v===null)return {background:'#f0f2f6',color:'#6c7893'};
 const power=Math.abs(v);
 return v>=0
  ?{background:`rgba(14,140,144,${(.12+power*.75).toFixed(3)})`,color:power>.58?'#ffffff':'#183b43'}
  :{background:`rgba(181,85,116,${(.12+power*.71).toFixed(3)})`,color:power>.58?'#ffffff':'#522f3f'};
}
function Viz({plot,onSelect}:{plot:Plot;onSelect:(choice:ChartSelection)=>void}){
  const data=plot.data;
  if(!data.length)return <p className="body-muted">No chartable observations for this selection.</p>;
  if(plot.type==='scatter'){
    const w=740,h=320,pad=42;
    const xs=data.map(d=>d.x??0),ys=data.map(d=>d.y??0);
    const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
    const toX=(v:number)=>pad+(v-x0)/(x1-x0||1)*(w-pad*2);
    const toY=(v:number)=>h-pad-(v-y0)/(y1-y0||1)*(h-pad*2);
    return <div className="chart-scroll"><svg viewBox={`0 0 ${w} ${h}`} className="pilot-chart" aria-label={`${plot.x} versus ${plot.y} scatter plot`} role="img"><line x1={pad} y1={h-pad} x2={w-pad} y2={h-pad} stroke="#aac6bb"/><line x1={pad} y1={pad} x2={pad} y2={h-pad} stroke="#aac6bb"/>{data.map((d,i)=><circle key={i} cx={toX(d.x??0)} cy={toY(d.y??0)} r="5" fill="#168769" opacity="0.68" className="po-inspect-point" tabIndex={d.row_ref===undefined?-1:0} role={d.row_ref===undefined?undefined:'button'} aria-label={d.row_ref===undefined?undefined:`Inspect plotted record ${d.row_ref+1}: ${plot.x} ${d.x}, ${plot.y} ${d.y}`} onClick={()=>{if(d.row_ref!==undefined)onSelect({kind:'point',row_ref:d.row_ref})}} onKeyDown={e=>{if(d.row_ref!==undefined&&(e.key==='Enter'||e.key===' ')){e.preventDefault();onSelect({kind:'point',row_ref:d.row_ref})}}}><title>{`${plot.x}: ${d.x}; ${plot.y}: ${d.y}`}</title></circle>)}<text x={w/2} y={h-6} textAnchor="middle" fontSize="12" fill="#617f7a">{plot.x}</text><text transform={`translate(15 ${h/2}) rotate(-90)`} textAnchor="middle" fontSize="12" fill="#617f7a">{plot.y}</text><text x={pad} y={h-pad+15} fontSize="10" fill="#70868c">{format(x0)}</text><text x={w-pad} y={h-pad+15} textAnchor="end" fontSize="10" fill="#70868c">{format(x1)}</text><text x={pad-6} y={pad} textAnchor="end" fontSize="10" fill="#70868c">{format(y1)}</text></svg></div>;
  }
  if(plot.type==='box'){
    const d=data[0],scale=(v:number)=>Math.max(3,Math.min(97,((v-(d.min??0))/((d.max??0)-(d.min??0)||1))*94+3));
    return <div className="boxplot"><div className="boxplot-track"><div className="boxplot-whisker" style={{left:`${scale(d.whisker_low??d.min??0)}%`,width:`${scale(d.whisker_high??d.max??0)-scale(d.whisker_low??d.min??0)}%`}}/><div className="boxplot-iqr" style={{left:`${scale(d.q1??0)}%`,width:`${scale(d.q3??0)-scale(d.q1??0)}%`}}/><div className="boxplot-median" style={{left:`${scale(d.median??0)}%`}}/>{d.outliers?.map((v,i)=><span className="po-box-outlier" style={{left:`${scale(v)}%`}} key={i} title={`Outlying observation: ${format(v)}`}/>)}</div><div className="po-box-scale"><span>{format(d.min??0)}</span><span>{format(d.max??0)}</span></div><div className="po-box-facts">{[['Lower whisker',d.whisker_low??d.min],['Q1',d.q1],['Median',d.median],['Q3',d.q3],['Upper whisker',d.whisker_high??d.max]].map(([label,value])=><span key={String(label)}><small>{label}</small><strong>{format(Number(value??0))}</strong></span>)}</div><p className="muted-caption">{d.outliers_total??0} outlying observations beyond 1.5×IQR; {Math.min(40,d.outliers?.length??0)} rendered as dots.</p></div>;
  }
  if(plot.type==='histogram'){
    const top=Math.max(1,...data.map(d=>d.value??0));
    return <div className="po-histogram" role="group" aria-label={`Histogram of ${plot.x} with ${data.length} equal-width numeric intervals`}><div className="po-hist-meta"><span>Frequency ↑</span><span>{plot.valid_observations??data.reduce((n,d)=>n+(d.value??0),0)} valid · {plot.excluded_observations??0} excluded</span></div><div className="po-hist-bars" style={{gridTemplateColumns:`repeat(${data.length},minmax(0,1fr))`}}>{data.map((d,i)=><button type="button" className="po-hist-bin" key={i} title={`${d.label}: ${d.value} observations. Inspect records.`} aria-label={`${d.label}: ${d.value} observations. Inspect records.`} onClick={()=>onSelect({kind:'bin',bin_index:i})}><div className="po-hist-rectangle" style={{height:`${Math.max(1,((d.value??0)/top)*100)}%`}}/><span className="po-hist-tick">{i%Math.max(1,Math.ceil(data.length/6))===0?format(d.start??0):''}</span></button>)}</div><div className="po-hist-foot">{plot.x} → · Hover or focus a bin for its interval and count.</div></div>;
  }
  const numeric=data.map(d=>d.value??0);const max=Math.max(1,...numeric.map(Math.abs));
  if(plot.type==='line'){
    const w=740,h=300,pad=35;
    const min=Math.min(0,...numeric);
    const scaleY=(v:number)=>pad+(1-(v-min)/(max-min||1))*(h-pad*2);
    const pts=data.map((d,i)=>`${pad+(i/(data.length-1||1))*(w-pad*2)},${scaleY(d.value??0)}`).join(' ');
    return <div className="chart-scroll"><svg viewBox={`0 0 ${w} ${h}`} className="pilot-chart" role="img" aria-label="Aggregated line chart"><line x1={pad} y1={h-pad} x2={w-pad} y2={h-pad} stroke="#aac6bb"/><polyline points={pts} stroke="#168769" strokeWidth="3" fill="none" strokeLinejoin="round"/>{data.map((d,i)=><circle key={i} r="4" fill="#168769" cx={pad+i/(data.length-1||1)*(w-pad*2)} cy={scaleY(d.value??0)}><title>{`${d.label}: ${format(d.value??0)}`}</title></circle>)}</svg><div className="axis-hint">{data[0].label} → {data[data.length-1].label}</div></div>;
  }
  return <div className="chart-bars">{data.map((d,i)=><button type="button" className="chart-bar-item po-inspect-bar" key={`${d.label}-${i}`} onClick={()=>onSelect({kind:'category',label:d.label??''})} title={`Inspect records in ${d.label}`}><span title={d.label} className="bar-label">{d.label}</span><div className="chart-track"><div style={{width:`${Math.max(0,Math.abs(d.value??0)/max*100)}%`}} className="chart-fill"/></div><strong>{format(d.value??0)}</strong></button>)}</div>;
}

export function ExploreWorkspace({projectId,versionToken}:{projectId:string;versionToken:number}){
  const [overview,setOverview]=useState<Overview|null>(null);
  const [findings,setFindings]=useState<Finding[]>([]);
  const [suggestions,setSuggestions]=useState<ChartSuggestion[]>([]);
  const [x,setX]=useState(()=>readPreferences(projectId).x);
  const [y,setY]=useState(()=>readPreferences(projectId).y);
  const [kind,setKind]=useState(()=>readPreferences(projectId).kind);
  const [aggregation,setAggregation]=useState(()=>readPreferences(projectId).aggregation);
  const [bins,setBins]=useState(16);
  const [corrMethod,setCorrMethod]=useState<'pearson'|'spearman'>('pearson');
  const [correlation,setCorrelation]=useState<Correlation|null>(null);
  const [filterCatalog,setFilterCatalog]=useState<FilterCatalog|null>(null);
  const [filters,setFilters]=useState<FilterClause[]>([]);
  const [filterError,setFilterError]=useState('');
  const [filteredOverview,setFilteredOverview]=useState<Overview|null>(null);
  const [chartMessage,setChartMessage]=useState('');
  const [filteredRows,setFilteredRows]=useState<number|null>(null);
  const [selection,setSelection]=useState<ChartSelection|null>(null);
  const [inspection,setInspection]=useState<InspectorResponse|null>(null);
  const [inspectOffset,setInspectOffset]=useState(0);
  const [inspectError,setInspectError]=useState('');
  const [inspectLoading,setInspectLoading]=useState(false);
  const [corrError,setCorrError]=useState('');
  useEffect(()=>{if(!overview)return;try{localStorage.setItem(preferencesKey(projectId),JSON.stringify({x,y,kind,aggregation}))}catch{/* Project evidence is stored in the backend, not here. */}},[projectId,x,y,kind,aggregation,overview]);
  const [plot,setPlot]=useState<Plot|null>(null);const [error,setError]=useState('');const [loading,setLoading]=useState(false);
  useEffect(()=>{let active=true;Promise.all([get<Overview>(`/projects/${projectId}/explore/overview`),get<{findings:Finding[]}>(`/projects/${projectId}/explore/insights`),get<{recommendations:ChartSuggestion[]}>(`/projects/${projectId}/explore/recommended`)]).then(([d,f,recommended])=>{if(!active)return;setOverview(d);setFindings(f.findings);setSuggestions(recommended.recommendations);const goodCategory=d.columns.find(c=>c.kind==='categorical'&&!/(?:id|key|code|number)$/i.test(c.name)&&c.unique<=Math.min(100,Math.max(2,d.rows*.5)));
        const chosen=recommended.recommendations[0]?.x??goodCategory?.name??d.columns.find(c=>c.kind==='numeric'&&!/(?:id|key|code|number)$/i.test(c.name))?.name??d.columns[0]?.name??'';
        if(y&&!d.columns.some(c=>c.name===y))setY('');
        if(!x||!d.columns.some(c=>c.name===x)){
          setX(chosen);
          if(recommended.recommendations[0]){const first=recommended.recommendations[0];setY(first.y??'');setKind(first.kind);setAggregation(first.aggregation);}
          const measure=d.columns.find(c=>c.kind==='numeric'&&c.name!==chosen&&/(sales|amount|revenue|profit|price|cost|quantity)/i.test(c.name));
          if(goodCategory&&measure)setY(measure.name);
          if(measure&&measure.mean!==undefined&&measure.median!==undefined&&Math.abs(measure.mean-measure.median)>Math.max(Math.abs(measure.median)*.4,1))setAggregation('median');
        }}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[projectId,versionToken]);
  useEffect(()=>{
    let active=true;setFilterCatalog(null);setFilters([]);setFilterError('');
    get<FilterCatalog>(`/projects/${projectId}/explore/filter-options`)
      .then(value=>{if(active)setFilterCatalog(value)})
      .catch(e=>{if(active)setFilterError((e as Error).message)});
    return()=>{active=false};
  },[projectId,versionToken]);
  useEffect(()=>{
    if(!x||!overview||!filterCatalog)return;
    if(overview.version!==filterCatalog.version){
      setError('Dataset version changed while loading filters. Refresh Explore.');
      return;
    }
    if(kind==='scatter'&&(overview.columns.find(c=>c.name===x)?.kind!=='numeric'||overview.columns.find(c=>c.name===y)?.kind!=='numeric'||x===y)){
      setPlot(null);setCorrelation(null);setLoading(false);return;
    }
    let live=true;setLoading(true);setError('');setCorrError('');setChartMessage('');
    setPlot(null);setCorrelation(null);setFilteredOverview(null);setFilteredRows(null);
    post<Workbench>(`/projects/${projectId}/explore/workbench`,{
      expected_version:overview.version,filters,x,y:y&&kind!=='histogram'&&kind!=='box'?y:null,
      kind,aggregation,bins,correlation_method:corrMethod
    }).then(value=>{
      if(!live)return;
      if(value.version!==overview.version){setError('Dataset changed. Refresh Explore.');return;}
      setPlot(value.chart);setChartMessage(value.chart_message);
      setCorrelation(value.correlation);setFilteredOverview(value.overview);
      setFilteredRows(value.filtered_rows);
    }).catch(e=>{if(live){setError((e as Error).message);setCorrError('Filtered correlation unavailable');setPlot(null)}})
      .finally(()=>{if(live)setLoading(false)});
    return()=>{live=false};
  },[projectId,x,y,kind,aggregation,bins,versionToken,overview,filterCatalog,filters,corrMethod]);
  // Chart selections and their row references never survive filters, version
  // changes or a new chart configuration. No selection is persisted as an ID.
  useEffect(()=>{
    setSelection(null);setInspection(null);setInspectOffset(0);setInspectError('');
  },[projectId,versionToken,x,y,kind,aggregation,bins,filters]);
  useEffect(()=>{
    if(!selection||!overview||!filterCatalog||overview.version!==filterCatalog.version)return;
    let live=true;setInspectLoading(true);setInspectError('');setInspection(null);
    post<InspectorResponse>(`/projects/${projectId}/explore/inspect`,{
      expected_version:overview.version,filters,x,y:y&&kind!=='histogram'&&kind!=='box'?y:null,
      kind,aggregation,bins,selection,offset:inspectOffset,limit:12
    }).then(value=>{
      if(!live)return;
      if(value.version!==overview.version){setInspectError('Working data changed. Refresh Explore.');return;}
      setInspection(value);
    }).catch(e=>{if(live)setInspectError((e as Error).message)})
      .finally(()=>{if(live)setInspectLoading(false)});
    return()=>{live=false};
  },[selection,inspectOffset,overview,filterCatalog,projectId,filters,x,y,kind,aggregation,bins,versionToken]);
  const cols=overview?.columns??[];const numerical=cols.filter(c=>c.kind==='numeric');
  const selectedX=cols.find(c=>c.name===x);
  const selectedY=cols.find(c=>c.name===y);
  const scatterReady=numerical.length>=2;
  const canScatter=selectedX?.kind==='numeric'&&selectedY?.kind==='numeric'&&x!==y;
  const chartWarning=kind==='scatter'&&!canScatter?'Scatter charts require two different numeric columns. Choose numeric X and Y fields.':'';
  const statOverview=filteredOverview??(filters.length?null:overview);
  const filterColumns=filterCatalog?.columns??[];
  function addFilter(){
    const available=filterColumns.find(c=>!filters.some(f=>f.column===c.name));
    if(available)setFilters(current=>[...current,filterFor(available)]);
  }
  function changeFilter(index:number,next:FilterClause){
    setFilters(current=>current.map((item,i)=>i===index?next:item));
  }
  function changeKind(next:string){
    if(next==='scatter'){
      if(!scatterReady)return;
      const first=selectedX?.kind==='numeric'?x:numerical[0].name;
      const second=selectedY?.kind==='numeric'&&y!==first?y:numerical.find(c=>c.name!==first)!.name;
      setX(first);setY(second);
    }
    if(next==='histogram'||next==='box'){setY('');if(selectedX?.kind!=='numeric'&&numerical.length)setX(numerical[0].name)}
    setKind(next);
  }
  function changeX(next:string){setX(next);if(kind==='scatter'&&cols.find(c=>c.name===next)?.kind!=='numeric')setKind('bar');
    if((kind==='histogram'||kind==='box')&&cols.find(c=>c.name===next)?.kind!=='numeric')setKind('auto')}

  return <div className="explore-page">
    <section className="quality-banner"><div><div className="eyebrow">EXPLORATION STUDIO</div><h2>Find the story in your data</h2><p>Explore distributions and relationships directly from the current, approved working dataset. No model training needed.</p></div><span className="pill">VERSION {overview?.version??'—'}</span></section>
    <div className="quality-stats"><div><small>{filters.length?'FILTERED RECORDS':'RECORDS'}</small><strong>{statOverview?format(statOverview.rows):'—'}</strong></div><div><small>FIELDS</small><strong>{statOverview?format(statOverview.columns.length):'—'}</strong></div><div><small>MISSING CELLS</small><strong>{statOverview?format(statOverview.missing_cells):'—'}</strong></div><div><small>EXACT DUPLICATES</small><strong>{statOverview?format(statOverview.exact_duplicates):'—'}</strong></div></div>
    <section className="panel po-filter-panel" aria-label="Linked Explore filters">
      <div className="panel-title"><BarChart3 size={18}/><h2>Linked analytical filters</h2><span className="pill muted">DATASET v{filterCatalog?.version??'—'}</span></div>
      <p className="body-muted">Combine up to four filters. Chart, statistics and correlation recalculate together from one approved data snapshot. No corrections are applied.</p>
      <div className="po-filter-toolbar"><button type="button" className="btn" onClick={addFilter} disabled={!filterColumns.some(c=>!filters.some(f=>f.column===c.name))||filters.length>=4}><Plus size={15}/> Add filter</button><button type="button" className="btn" disabled={!filters.length} onClick={()=>setFilters([])}>Clear filters</button><span role="status">{filteredRows===null&&loading?'Calculating linked results…':filteredRows===null?'':`${format(filteredRows)} of ${format(overview?.rows??0)} records`}</span></div>
      {filterError&&<p className="alert-error" role="alert">{filterError}</p>}
      <div className="po-filter-rows">{filters.map((clause,i)=>{const column=filterColumns.find(c=>c.name===clause.column);return <div className="po-filter-row" key={clause.column}>
        <label>Filter field<select className="input" value={clause.column} onChange={e=>{const next=filterColumns.find(c=>c.name===e.target.value);if(next)changeFilter(i,filterFor(next))}}>{filterColumns.filter(c=>c.name===clause.column||!filters.some(f=>f.column===c.name)).map(c=><option key={c.name} value={c.name}>{c.name}</option>)}</select></label>
        {column?.kind==='categorical'?<label>Equals<select className="input" value={clause.value??''} onChange={e=>changeFilter(i,{...clause,value:e.target.value})}>{column.options?.map(value=><option key={value} value={value}>{value}</option>)}</select></label>
        :<><label>Minimum<input className="input" type="number" aria-label={`Minimum ${clause.column}`} value={clause.min??''} onChange={e=>changeFilter(i,{...clause,min:e.target.value===''?undefined:Number(e.target.value)})}/></label><label>Maximum<input className="input" type="number" aria-label={`Maximum ${clause.column}`} value={clause.max??''} onChange={e=>changeFilter(i,{...clause,max:e.target.value===''?undefined:Number(e.target.value)})}/></label></>}
        <button type="button" className="po-filter-remove" aria-label={`Remove filter for ${clause.column}`} title="Remove filter" onClick={()=>setFilters(current=>current.filter((_,j)=>j!==i))}><X size={16}/></button>
      </div>})}</div>
      {filters.length===0&&<p className="muted-caption">All records are currently included. Add a filter to focus this analysis.</p>}
      <p className="muted-caption">Recommendations and proactive insights below describe the full working dataset; filtered calculations are identified above.</p>
    </section>
    {suggestions.length>0&&<section className="panel"><div className="panel-title"><Sparkles size={18}/><h2>Recommended investigations</h2><span className="pill muted">LOCAL EVIDENCE</span></div><div className="recommend-grid">{suggestions.slice(0,6).map((r,i)=><button key={i} className="recommend-card" onClick={()=>{setX(r.x);setY(r.y??'');setKind(r.kind);setAggregation(r.aggregation)}}><strong>{r.title}</strong><small>{r.reason}</small><span>Open chart →</span></button>)}</div></section>}
    <section className="panel"><div className="panel-title"><BarChart3 size={19}/><h2>Interactive chart builder</h2><span className="pill muted">COMPUTED LOCALLY</span></div>
      <div className="chart-controls"><label>Chart type<select className="input" value={kind} onChange={(e:any)=>changeKind(e.target.value)}><option value="auto">Automatic</option><option value="bar">Bar / categories</option><option value="histogram">Histogram</option><option value="scatter" disabled={!scatterReady}>Scatter · two numeric columns</option><option value="line">Line / trend</option><option value="box">Box summary</option></select></label><label>X variable<select className="input" value={x} onChange={(e:any)=>changeX(e.target.value)}>{cols.map(c=><option key={c.name}>{c.name}</option>)}</select></label>{kind!=='histogram'&&kind!=='box'&&<label>Y variable<select className="input" value={y} onChange={(e:any)=>setY(e.target.value)}><option value="">None · record frequency</option>{numerical.filter(c=>c.name!==x).map(c=><option key={c.name}>{c.name}</option>)}</select></label>}{!['histogram','box','scatter'].includes(kind)&&<label>Aggregation<select className="input" value={aggregation} onChange={(e:any)=>setAggregation(e.target.value)}>{['mean','sum','median','count'].map(a=><option key={a} value={a}>{a}</option>)}</select></label>}{kind==='histogram'&&<label>Histogram bins<select className="input" value={bins} onChange={e=>setBins(Number(e.target.value))}>{[8,12,16,24,32].map(n=><option key={n} value={n}>{n} bins</option>)}</select></label>}</div>
      {chartWarning&&<div className="mini-info warn-icon" role="status">{chartWarning}</div>}
      {error&&<div className="alert-error"><Activity size={16}/>{error}</div>}
      {loading?<div className="chart-loading"><LoaderCircle size={20} className="spin"/> Calculating linked results…</div>:chartMessage?<p className="body-muted" role="status">{chartMessage}</p>:plot&&<><h3 className="chart-title">{plot.type==='bar'&&plot.aggregation==='count'?(plot.y?`Count of non-missing ${plot.y} by ${plot.x}`:`Record count by ${plot.x}`):`${plot.x}${plot.y?` vs ${plot.y}`:''} · ${plot.type}`}</h3><Viz plot={plot} onSelect={choice=>{setSelection(choice);setInspectOffset(0)}}/><p className="muted-caption">{plot.note}{plot.sampled?' Points or groups have been sampled for responsiveness.':''}{plot.truncated?' Showing the 30 most frequent groups.':''}</p></>}
    </section>
    {selection&&<section className="panel po-record-inspector" aria-label="Selected chart records">
      <div className="panel-title"><BarChart3 size={18}/><h2>Underlying records</h2><span className="pill muted">READ-ONLY LOCAL PREVIEW</span><button type="button" className="po-inspect-dismiss" onClick={()=>{setSelection(null);setInspection(null)}} aria-label="Close chart record inspector"><X size={17}/></button></div>
      <p className="body-muted">Only rows matching your clicked chart element and current filters are displayed. No changes are made to the source.</p>
      {inspectLoading&&<p role="status">Retrieving selected records…</p>}
      {inspectError&&<p className="alert-error" role="alert">{inspectError}</p>}
      {inspection&&<><div className="po-inspect-summary"><strong>{inspection.description}</strong><span>{format(inspection.matched_rows)} matching records · Version {inspection.version}</span></div>
        {inspection.measure_rows!==inspection.matched_rows&&<p className="muted-caption">{format(inspection.measure_rows)} of the matching rows have a numeric value for the selected Y measure. This may differ from record frequency.</p>}
        {inspection.rows.length?<div className="table-scroll po-inspect-scroll"><table><thead><tr><th>FILTERED ROW</th>{inspection.columns.map((column,i)=><th key={i}>{column}</th>)}</tr></thead><tbody>{inspection.rows.map(row=><tr key={row.filtered_row_number}><td>{row.filtered_row_number}</td>{row.cells.map((cell,i)=><td key={i} title={cell===null?'Missing':String(cell)}>{cell===null?'—':String(cell)}</td>)}</tr>)}</tbody></table></div>:<p>No records on this page.</p>}
        <div className="po-inspect-pagination"><span>{inspection.matched_rows?inspectOffset+1:0}–{Math.min(inspectOffset+inspection.limit,inspection.matched_rows)} of {format(inspection.matched_rows)}</span><button type="button" className="btn" disabled={inspectLoading||inspectOffset===0} onClick={()=>setInspectOffset(v=>Math.max(0,v-12))}>Previous</button><button type="button" className="btn" disabled={inspectLoading||inspectOffset+12>=inspection.matched_rows} onClick={()=>setInspectOffset(v=>v+12)}>Next</button></div>
        <p className="muted-caption">{inspection.note}{inspection.truncated_columns?' Only the first 16 fields, prioritising chart variables, are shown.':''}</p>
      </>}
    </section>}
    <section className="panel po-correlation-panel"><div className="panel-title"><BarChart3 size={19}/><h2>Correlation heatmap</h2><span className="pill muted">VERIFIED LOCAL CALCULATION</span></div>
      <p className="body-muted">Compare numeric relationships. Click any off-diagonal cell to open its scatter plot. IDs and obvious identifiers are excluded.</p>
      <label className="po-correlation-method">Correlation method <select className="input" value={corrMethod} onChange={e=>setCorrMethod(e.target.value as 'pearson'|'spearman')}><option value="pearson">Pearson · linear association</option><option value="spearman">Spearman · rank association</option></select></label>
      {corrError&&<p role="alert" className="alert-error">{corrError}</p>}
      {correlation&&correlation.columns.length<2&&<p className="body-muted">At least two eligible numeric columns are required to compute a correlation matrix.</p>}
      {correlation&&correlation.columns.length>=2&&<div className="po-correlation-scroll"><div className="po-correlation-grid" style={{gridTemplateColumns:`minmax(115px,1.3fr) repeat(${correlation.columns.length},minmax(76px,1fr))`}}>
        <div className="po-correlation-axis">Variable ↓ / →</div>{correlation.columns.map(name=><div className="po-correlation-axis" key={`head-${name}`} title={name}>{name}</div>)}
        {correlation.columns.map(row=><div className="po-correlation-row" key={row} style={{display:'contents'}}><div className="po-correlation-axis" title={row}>{row}</div>{correlation.columns.map(column=>{const c=correlation.cells.find(item=>item.x===column&&item.y===row);const r=c?.r??null;const allowed=row!==column&&r!==null;return <button type="button" key={column} className="po-correlation-cell" disabled={!allowed} style={correlationTone(r)} title={`${row} vs ${column}: ${r===null?'Unavailable':r.toFixed(3)} (n=${c?.n??0})`} aria-label={`${row} versus ${column}: correlation ${r===null?'unavailable':r.toFixed(3)}, ${c?.n??0} valid pairs`} onClick={()=>{setX(column);setY(row);setKind('scatter')}}>{r===null?'—':r.toFixed(2)}</button>})}</div>)}
      </div></div>}
      <p className="muted-caption">{correlation?.note??(loading?'Calculating filtered correlations…':'Correlation unavailable for this selection.')} Correlations are descriptive, not causal.</p>
    </section>
    <div className="explore-columns"><section className="panel"><div className="panel-title"><Sparkles size={18}/><h2>Proactive insights</h2></div>{findings.length?findings.map((f,i)=><button className="insight-item" key={i} onClick={()=>{if(f.column){setX(f.column);setY('');setKind('auto')}}}><span className="insight-bullet"/><span><b>{f.title}</b><small>{f.detail}</small></span><ChevronDown size={15}/></button>):<p className="body-muted">No structural or distribution warnings detected. Explore combinations to investigate further.</p>}</section>
      <section className="panel"><div className="panel-title"><Activity size={18}/><h2>Column statistics</h2></div><div className="table-scroll"><table><thead><tr><th>FIELD</th><th>TYPE</th><th>UNIQUE</th><th>MISSING</th></tr></thead><tbody>{cols.map(c=><tr key={c.name} onClick={()=>{setX(c.name);setY('');setKind('auto')}} className="clickable-row"><td className="cell-strong">{c.name}</td><td>{c.kind}</td><td>{format(c.unique)}</td><td>{c.missing_pct}%</td></tr>)}</tbody></table></div><p className="muted-caption">Click a column to explore it. Descriptive statistics do not establish causation.</p></section></div>
  </div>;
}
