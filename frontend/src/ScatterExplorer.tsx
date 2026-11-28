import {useId,useState} from 'react';
import {ArrowDown,ArrowLeft,ArrowRight,ArrowUp,Minus,Plus,RotateCcw} from 'lucide-react';
import './scatter-explorer.css';

type Point={x?:number;y?:number;row_ref?:number;group?:string};
export type ScatterPlotData={
 x:string;y:string|null;data:Point[];color_by?:string;
 color_groups?:{label:string;count:number}[];sampled:boolean;
 valid_observations?:number;excluded_observations?:number;
};
const colors=['#3659c4','#cb6348','#128b8a','#9a5cc2','#b18832','#5c7e36','#c34e91','#6b7489'];
function fmt(v:number){return v.toLocaleString(undefined,{maximumFractionDigits:2})}
function clamp(value:number,min:number,max:number){return Math.min(max,Math.max(min,value))}

export function ScatterExplorer({plot,onSelect}:{plot:ScatterPlotData;onSelect:(row_ref:number)=>void}){
 const [zoom,setZoom]=useState(1);
 const [panX,setPanX]=useState(.5);
 const [panY,setPanY]=useState(.5);
 const [activeGroup,setActiveGroup]=useState<string|null>(null);
 const clipId=useId().replaceAll(':','-');
 const data=plot.data;
 if(!data.length)return <p className="body-muted">No valid plotted pairs.</p>;
 const w=740,h=350,pad=46;
 const xs=data.map(p=>p.x??0),ys=data.map(p=>p.y??0);
 const rawXMin=Math.min(...xs),rawXMax=Math.max(...xs),rawYMin=Math.min(...ys),rawYMax=Math.max(...ys);
 const fullX=Math.max(1e-9,rawXMax-rawXMin),fullY=Math.max(1e-9,rawYMax-rawYMin);
 const xSpan=fullX/zoom,ySpan=fullY/zoom;
 const xMin=rawXMin+clamp(panX*fullX-xSpan/2,0,fullX-xSpan);
 const yMin=rawYMin+clamp(panY*fullY-ySpan/2,0,fullY-ySpan);
 const xMax=xMin+xSpan,yMax=yMin+ySpan;
 const toX=(v:number)=>pad+(v-xMin)/xSpan*(w-pad*2);
 const toY=(v:number)=>h-pad-(v-yMin)/ySpan*(h-pad*2);
 const current=data.filter(p=>p.x!==undefined&&p.y!==undefined&&p.x>=xMin&&p.x<=xMax&&p.y>=yMin&&p.y<=yMax);
 const visible=activeGroup===null?current:current.filter(p=>p.group===activeGroup);
 const palette=new Map((plot.color_groups??[]).map((g,i)=>[g.label,colors[i%colors.length]]));
 const move=(axis:'x'|'y',delta:number)=>{
  const shift=delta/(zoom*3);
  if(axis==='x')setPanX(v=>clamp(v+shift,1/(2*zoom),1-1/(2*zoom)));
  else setPanY(v=>clamp(v+shift,1/(2*zoom),1-1/(2*zoom)));
 };
 const changeZoom=(next:number)=>{setZoom(clamp(next,1,8));};
 const reset=()=>{setZoom(1);setPanX(.5);setPanY(.5);setActiveGroup(null)};
 return <div className="po-scatter-explorer">
  <div className="po-scatter-toolbar" aria-label="Scatter zoom and pan controls">
   <span className="po-scatter-zoom-status" role="status">{zoom}× view · {visible.length} of {data.length} plotted points visible</span>
   <button type="button" aria-label="Zoom out" title="Zoom out" disabled={zoom===1} onClick={()=>changeZoom(zoom/2)}><Minus size={15}/></button>
   <button type="button" aria-label="Zoom in" title="Zoom in" disabled={zoom===8} onClick={()=>changeZoom(zoom*2)}><Plus size={15}/></button>
   <button type="button" aria-label="Pan left" title="Pan left" disabled={zoom===1} onClick={()=>move('x',-1)}><ArrowLeft size={15}/></button>
   <button type="button" aria-label="Pan right" title="Pan right" disabled={zoom===1} onClick={()=>move('x',1)}><ArrowRight size={15}/></button>
   <button type="button" aria-label="Pan up" title="Pan up" disabled={zoom===1} onClick={()=>move('y',1)}><ArrowUp size={15}/></button>
   <button type="button" aria-label="Pan down" title="Pan down" disabled={zoom===1} onClick={()=>move('y',-1)}><ArrowDown size={15}/></button>
   <button type="button" aria-label="Reset scatter view" title="Reset zoom, pan and legend selection" onClick={reset}><RotateCcw size={15}/></button>
  </div>
  <div className="chart-scroll">
   <svg viewBox={`0 0 ${w} ${h}`} className="pilot-chart" role="group" aria-label={`${plot.x} versus ${plot.y}: interactive scatter chart`}>
    <defs><clipPath id={clipId}><rect x={pad} y={pad} width={w-pad*2} height={h-pad*2}/></clipPath></defs>
    <rect x={pad} y={pad} width={w-pad*2} height={h-pad*2} fill="#fbfcff"/>
    {[.25,.5,.75].map(t=><g key={t}><line x1={pad} y1={pad+(h-pad*2)*t} x2={w-pad} y2={pad+(h-pad*2)*t} stroke="#e9eaf4"/><line x1={pad+(w-pad*2)*t} y1={pad} x2={pad+(w-pad*2)*t} y2={h-pad} stroke="#e9eaf4"/></g>)}
    <line x1={pad} y1={h-pad} x2={w-pad} y2={h-pad} stroke="#9ba9c8"/>
    <line x1={pad} y1={pad} x2={pad} y2={h-pad} stroke="#9ba9c8"/>
    <g clipPath={`url(#${clipId})`}>{visible.map((point,i)=><circle key={point.row_ref??i} cx={toX(point.x??0)} cy={toY(point.y??0)} r="5" fill={palette.get(point.group??'')??'#3967ba'} opacity=".77" className="po-inspect-point" tabIndex={point.row_ref===undefined?-1:0} role={point.row_ref===undefined?undefined:'button'} aria-label={`Inspect plotted record ${point.row_ref===undefined?'':point.row_ref+1}, ${plot.x} ${point.x}, ${plot.y} ${point.y}${point.group?`, group ${point.group}`:''}`} onClick={()=>{if(point.row_ref!==undefined)onSelect(point.row_ref)}} onKeyDown={event=>{if(point.row_ref!==undefined&&(event.key==='Enter'||event.key===' ')){event.preventDefault();onSelect(point.row_ref)}}}><title>{`${plot.x}: ${point.x}; ${plot.y}: ${point.y}${point.group?`; ${plot.color_by}: ${point.group}`:''}`}</title></circle>)}</g>
    <text x={w/2} y={h-7} textAnchor="middle" fontSize="12" fill="#526486">{plot.x}</text>
    <text transform={`translate(14 ${h/2}) rotate(-90)`} textAnchor="middle" fontSize="12" fill="#526486">{plot.y}</text>
    <text x={pad} y={h-pad+16} fontSize="10" fill="#64748e">{fmt(xMin)}</text>
    <text x={w-pad} y={h-pad+16} textAnchor="end" fontSize="10" fill="#64748e">{fmt(xMax)}</text>
    <text x={pad-7} y={pad} textAnchor="end" fontSize="10" fill="#64748e">{fmt(yMax)}</text>
    <text x={pad-7} y={h-pad} textAnchor="end" fontSize="10" fill="#64748e">{fmt(yMin)}</text>
   </svg>
  </div>
  {(plot.color_groups?.length??0)>0&&<div className="po-scatter-legend" aria-label="Scatter category legend">
    <strong>{plot.color_by}</strong>
    <button type="button" aria-pressed={activeGroup===null} className={activeGroup===null?'chosen':''} onClick={()=>setActiveGroup(null)}>All plotted</button>
    {plot.color_groups!.map(g=><button type="button" aria-pressed={activeGroup===g.label} className={activeGroup===g.label?'chosen':''} key={g.label} onClick={()=>setActiveGroup(activeGroup===g.label?null:g.label)}><span className="po-scatter-legend-swatch" style={{background:palette.get(g.label)}}/>{g.label} ({g.count})</button>)}
   </div>}
  <p className="muted-caption">{plot.valid_observations??data.length} finite X/Y pairs, {plot.excluded_observations??0} excluded. {plot.sampled?'A reproducible sample of at most 500 pairs is plotted. ':'All valid pairs are plotted. '}Zoom and legend choices affect visibility only, not the source data or saved analytical filters. Select any visible point to inspect its record.</p>
 </div>;
}
