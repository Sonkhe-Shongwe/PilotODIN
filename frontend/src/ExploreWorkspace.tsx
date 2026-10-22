import {useEffect,useState} from 'react';
import {Activity, BarChart3, ChevronDown, LoaderCircle, RefreshCw, Sparkles} from 'lucide-react';
import {get} from './api';
type Column={name:string;kind:'numeric'|'categorical';unique:number;missing:number;missing_pct:number;min?:number;max?:number;mean?:number;median?:number};
type Overview={version:number;rows:number;missing_cells:number;exact_duplicates:number;columns:Column[]};
type Plot={version:number;type:string;x:string;y:string|null;data:{label?:string;value?:number;x?:number;y?:number;min?:number;q1?:number;median?:number;q3?:number;max?:number}[];sampled:boolean;truncated?:boolean;note:string};
type Finding={category:string;column:string|null;title:string;detail:string};
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
function Viz({plot}:{plot:Plot}){
  const data=plot.data;
  if(!data.length)return <p className="body-muted">No chartable observations for this selection.</p>;
  if(plot.type==='scatter'){
    const w=740,h=320,pad=42;
    const xs=data.map(d=>d.x??0),ys=data.map(d=>d.y??0);
    const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
    const toX=(v:number)=>pad+(v-x0)/(x1-x0||1)*(w-pad*2);
    const toY=(v:number)=>h-pad-(v-y0)/(y1-y0||1)*(h-pad*2);
    return <div className="chart-scroll"><svg viewBox={`0 0 ${w} ${h}`} className="pilot-chart" aria-label={`${plot.x} versus ${plot.y} scatter plot`} role="img"><line x1={pad} y1={h-pad} x2={w-pad} y2={h-pad} stroke="#aac6bb"/><line x1={pad} y1={pad} x2={pad} y2={h-pad} stroke="#aac6bb"/>{data.map((d,i)=><circle key={i} cx={toX(d.x??0)} cy={toY(d.y??0)} r="3.5" fill="#168769" opacity="0.6"><title>{`${plot.x}: ${d.x}; ${plot.y}: ${d.y}`}</title></circle>)}<text x={w/2} y={h-6} textAnchor="middle" fontSize="12" fill="#617f7a">{plot.x}</text><text transform={`translate(15 ${h/2}) rotate(-90)`} textAnchor="middle" fontSize="12" fill="#617f7a">{plot.y}</text><text x={pad} y={h-pad+15} fontSize="10" fill="#70868c">{format(x0)}</text><text x={w-pad} y={h-pad+15} textAnchor="end" fontSize="10" fill="#70868c">{format(x1)}</text><text x={pad-6} y={pad} textAnchor="end" fontSize="10" fill="#70868c">{format(y1)}</text></svg></div>;
  }
  if(plot.type==='box'){
    const d=data[0],scale=(v:number)=>Math.max(3,Math.min(97,((v-(d.min??0))/((d.max??0)-(d.min??0)||1))*94+3));
    return <div className="boxplot"><div className="boxplot-track"><div className="boxplot-whisker" style={{left:`${scale(d.min??0)}%`,width:`${scale(d.max??0)-scale(d.min??0)}%`}}/><div className="boxplot-iqr" style={{left:`${scale(d.q1??0)}%`,width:`${scale(d.q3??0)-scale(d.q1??0)}%`}}/><div className="boxplot-median" style={{left:`${scale(d.median??0)}%`}}/></div><div className="boxplot-stats">{(['min','q1','median','q3','max'] as const).map(k=><span key={k}><small>{k.toUpperCase()}</small><b>{format(d[k]??0)}</b></span>)}</div></div>;
  }
  const numeric=data.map(d=>d.value??0);const max=Math.max(1,...numeric.map(Math.abs));
  if(plot.type==='line'){
    const w=740,h=300,pad=35;
    const min=Math.min(0,...numeric);
    const scaleY=(v:number)=>pad+(1-(v-min)/(max-min||1))*(h-pad*2);
    const pts=data.map((d,i)=>`${pad+(i/(data.length-1||1))*(w-pad*2)},${scaleY(d.value??0)}`).join(' ');
    return <div className="chart-scroll"><svg viewBox={`0 0 ${w} ${h}`} className="pilot-chart" role="img" aria-label="Aggregated line chart"><line x1={pad} y1={h-pad} x2={w-pad} y2={h-pad} stroke="#aac6bb"/><polyline points={pts} stroke="#168769" strokeWidth="3" fill="none" strokeLinejoin="round"/>{data.map((d,i)=><circle key={i} r="4" fill="#168769" cx={pad+i/(data.length-1||1)*(w-pad*2)} cy={scaleY(d.value??0)}><title>{`${d.label}: ${format(d.value??0)}`}</title></circle>)}</svg><div className="axis-hint">{data[0].label} → {data[data.length-1].label}</div></div>;
  }
  return <div className="chart-bars">{data.map((d,i)=><div className="chart-bar-item" key={`${d.label}-${i}`}><span title={d.label} className="bar-label">{d.label}</span><div className="chart-track"><div style={{width:`${Math.max(0,Math.abs(d.value??0)/max*100)}%`}} className="chart-fill"/></div><strong>{format(d.value??0)}</strong></div>)}</div>;
}

export function ExploreWorkspace({projectId,versionToken}:{projectId:string;versionToken:number}){
  const [overview,setOverview]=useState<Overview|null>(null);
  const [findings,setFindings]=useState<Finding[]>([]);
  const [suggestions,setSuggestions]=useState<ChartSuggestion[]>([]);
  const [x,setX]=useState(()=>readPreferences(projectId).x);
  const [y,setY]=useState(()=>readPreferences(projectId).y);
  const [kind,setKind]=useState(()=>readPreferences(projectId).kind);
  const [aggregation,setAggregation]=useState(()=>readPreferences(projectId).aggregation);
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
  useEffect(()=>{if(!x)return;let live=true;setLoading(true);setError('');if(kind==='scatter'&&(overview?.columns.find(c=>c.name===x)?.kind!=='numeric'||overview?.columns.find(c=>c.name===y)?.kind!=='numeric'||x===y))return;
    const params=new URLSearchParams({x,kind,aggregation});if(y)params.set('y',y);
    get<Plot>(`/projects/${projectId}/explore/chart?${params}`).then(p=>{if(live)setPlot(p)}).catch(e=>{if(live){setError(e.message);setPlot(null)}}).finally(()=>{if(live)setLoading(false)});
    return()=>{live=false};
  },[projectId,x,y,kind,aggregation,versionToken,overview]);
  const cols=overview?.columns??[];const numerical=cols.filter(c=>c.kind==='numeric');
  const selectedX=cols.find(c=>c.name===x);
  const selectedY=cols.find(c=>c.name===y);
  const scatterReady=numerical.length>=2;
  const canScatter=selectedX?.kind==='numeric'&&selectedY?.kind==='numeric'&&x!==y;
  const chartWarning=kind==='scatter'&&!canScatter?'Scatter charts require two different numeric columns. Choose numeric X and Y fields.':'';
  function changeKind(next:string){
    if(next==='scatter'){
      if(!scatterReady)return;
      const first=selectedX?.kind==='numeric'?x:numerical[0].name;
      const second=selectedY?.kind==='numeric'&&y!==first?y:numerical.find(c=>c.name!==first)!.name;
      setX(first);setY(second);
    }
    if((next==='histogram'||next==='box')&&selectedX?.kind!=='numeric'&&numerical.length){setX(numerical[0].name);setY('')}
    setKind(next);
  }
  function changeX(next:string){setX(next);if(kind==='scatter'&&cols.find(c=>c.name===next)?.kind!=='numeric')setKind('bar');
    if((kind==='histogram'||kind==='box')&&cols.find(c=>c.name===next)?.kind!=='numeric')setKind('auto')}

  return <div className="explore-page">
    <section className="quality-banner"><div><div className="eyebrow">EXPLORATION STUDIO</div><h2>Find the story in your data</h2><p>Explore distributions and relationships directly from the current, approved working dataset. No model training needed.</p></div><span className="pill">VERSION {overview?.version??'—'}</span></section>
    <div className="quality-stats"><div><small>RECORDS</small><strong>{overview?format(overview.rows):'—'}</strong></div><div><small>FIELDS</small><strong>{cols.length||'—'}</strong></div><div><small>MISSING CELLS</small><strong>{overview?format(overview.missing_cells):'—'}</strong></div><div><small>EXACT DUPLICATES</small><strong>{overview?format(overview.exact_duplicates):'—'}</strong></div></div>
    {suggestions.length>0&&<section className="panel"><div className="panel-title"><Sparkles size={18}/><h2>Recommended investigations</h2><span className="pill muted">LOCAL EVIDENCE</span></div><div className="recommend-grid">{suggestions.slice(0,6).map((r,i)=><button key={i} className="recommend-card" onClick={()=>{setX(r.x);setY(r.y??'');setKind(r.kind);setAggregation(r.aggregation)}}><strong>{r.title}</strong><small>{r.reason}</small><span>Open chart →</span></button>)}</div></section>}
    <section className="panel"><div className="panel-title"><BarChart3 size={19}/><h2>Interactive chart builder</h2><span className="pill muted">COMPUTED LOCALLY</span></div>
      <div className="chart-controls"><label>Chart type<select className="input" value={kind} onChange={(e:any)=>changeKind(e.target.value)}><option value="auto">Automatic</option><option value="bar">Bar / categories</option><option value="histogram">Histogram</option><option value="scatter" disabled={!scatterReady}>Scatter · two numeric columns</option><option value="line">Line / trend</option><option value="box">Box summary</option></select></label><label>X variable<select className="input" value={x} onChange={(e:any)=>changeX(e.target.value)}>{cols.map(c=><option key={c.name}>{c.name}</option>)}</select></label><label>Y variable<select className="input" value={y} onChange={(e:any)=>setY(e.target.value)}><option value="">None · record frequency</option>{numerical.filter(c=>c.name!==x).map(c=><option key={c.name}>{c.name}</option>)}</select></label><label>Aggregation<select className="input" value={aggregation} onChange={(e:any)=>setAggregation(e.target.value)}>{['mean','sum','median','count'].map(a=><option key={a} value={a}>{a}</option>)}</select></label></div>
      {chartWarning&&<div className="mini-info warn-icon" role="status">{chartWarning}</div>}
      {error&&<div className="alert-error"><Activity size={16}/>{error}</div>}
      {loading?<div className="chart-loading"><LoaderCircle size={20} className="spin"/> Calculating chart…</div>:plot&&<><h3 className="chart-title">{plot.x}{plot.y?` vs ${plot.y}`:''} · {plot.type}</h3><Viz plot={plot}/><p className="muted-caption">{plot.note}{plot.sampled?' Points or groups have been sampled for responsiveness.':''}{plot.truncated?' Showing the 30 most frequent groups.':''}</p></>}
    </section>
    <div className="explore-columns"><section className="panel"><div className="panel-title"><Sparkles size={18}/><h2>Proactive insights</h2></div>{findings.length?findings.map((f,i)=><button className="insight-item" key={i} onClick={()=>{if(f.column){setX(f.column);setY('');setKind('auto')}}}><span className="insight-bullet"/><span><b>{f.title}</b><small>{f.detail}</small></span><ChevronDown size={15}/></button>):<p className="body-muted">No structural or distribution warnings detected. Explore combinations to investigate further.</p>}</section>
      <section className="panel"><div className="panel-title"><Activity size={18}/><h2>Column statistics</h2></div><div className="table-scroll"><table><thead><tr><th>FIELD</th><th>TYPE</th><th>UNIQUE</th><th>MISSING</th></tr></thead><tbody>{cols.map(c=><tr key={c.name} onClick={()=>{setX(c.name);setY('');setKind('auto')}} className="clickable-row"><td className="cell-strong">{c.name}</td><td>{c.kind}</td><td>{format(c.unique)}</td><td>{c.missing_pct}%</td></tr>)}</tbody></table></div><p className="muted-caption">Click a column to explore it. Descriptive statistics do not establish causation.</p></section></div>
  </div>;
}
