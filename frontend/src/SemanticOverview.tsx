import {useEffect,useState} from 'react';
import {AlertTriangle,BookOpen,LoaderCircle} from 'lucide-react';
import {get} from './api';
import {SemanticContextEditor} from './SemanticContextEditor';
import type {UserSemanticContext} from './SemanticContextEditor';

type SemanticHypothesis={
 role:string;state:'hypothesis';basis:string;reason:string
};
type Semantics={
 version:number;rows:number;columns_examined:number;columns_total:number;
 domain:{state:'hypothesis'|'unknown';label:string|null;evidence_columns:string[];reason:string};
 grain:{state:'hypothesis'|'unknown';identifier_column:string|null;reason:string};
 fields:{column:string;observed:{dtype:string;missing:number;unique:number;rows:number};hypotheses:SemanticHypothesis[]}[];
 observed:string;inferred:string;unknown:string;note:string;
 user_context:UserSemanticContext|null
};
const humanRole=(text:string)=>text.replaceAll('_',' ');

export function SemanticOverview({projectId,version,columns}:{projectId:string;version:number;columns:string[]}){
 const [data,setData]=useState<Semantics|null>(null);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 useEffect(()=>{
  let live=true;
  setBusy(true);setError('');setData(null);
  get<Semantics>(`/projects/${projectId}/semantics?expected_version=${version}`)
   .then(result=>{
    if(!live)return;
    if(result.version!==version){setError('Dataset version changed; refresh the data dictionary.');return}
    setData(result);
   })
   .catch(e=>{if(live)setError((e as Error).message)})
   .finally(()=>{if(live)setBusy(false)});
  return ()=>{live=false};
 },[projectId,version]);
 return <section className="po-semantic-overview" aria-label="Business context hypotheses">
  <div className="panel-title"><BookOpen size={18}/><h3>Business meaning hypotheses</h3><span className="pill muted">UNVERIFIED</span></div>
  <p className="body-muted">PilotODIN checks column names and summary statistics locally. Business meaning is <strong>not confirmed</strong> and no prediction target is selected.</p>
  {busy&&<p className="po-col-status" role="status"><LoaderCircle size={15} className="spin"/> Checking local metadata…</p>}
  {error&&<p className="alert-error" role="alert">{error}</p>}
  {data&&<>
   <div className="po-col-metadata">
    <div><small>Possible domain</small><strong>{data.domain.state==='hypothesis'?data.domain.label:'Unknown — insufficient evidence'}</strong></div>
    <div><small>Potential unique record key</small><strong>{data.grain.state==='hypothesis'?data.grain.identifier_column:'Unknown or ambiguous'}</strong></div>
   </div>
   <p className="muted-caption">{data.domain.reason} {data.domain.evidence_columns.length>0&&`Header clues: ${data.domain.evidence_columns.join(', ')}.`}</p>
   <p className="muted-caption">{data.grain.reason}</p>
   <details>
    <summary>Inspect tentative field meanings ({data.fields.length} fields with hints)</summary>
    <div className="po-col-table-scroll">
     <table><thead><tr><th>FIELD</th><th>POSSIBLE ROLE</th><th>EVIDENCE BASIS</th><th>REVIEW NOTE</th></tr></thead>
      <tbody>{data.fields.slice(0,20).flatMap(item=>item.hypotheses.map(h=><tr key={item.column+'-'+h.role}><td>{item.column}</td><td>{humanRole(h.role)} (unverified)</td><td>{humanRole(h.basis)}</td><td>{h.reason}</td></tr>))}</tbody>
     </table>
    </div>
    {data.fields.length>20&&<p className="muted-caption">Showing the first 20 fields with hypotheses; no field was automatically modified.</p>}
   </details>
   {data.user_context&&<div className="po-col-metadata" aria-label="Owner-described business context">
    <div><small>User description, not independently verified</small>
     {data.user_context.domain_description&&<p><strong>Domain:</strong> {data.user_context.domain_description}</p>}
     {data.user_context.record_grain_description&&<p><strong>Row meaning:</strong> {data.user_context.record_grain_description}</p>}
     {data.user_context.field_definitions.map(item=><p key={item.column}><strong>{item.column}:</strong> {item.meaning}</p>)}
    </div>
   </div>}
   <SemanticContextEditor projectId={projectId} version={version} columns={columns}
    existing={data.user_context} onSaved={value=>setData(prev=>prev?{...prev,user_context:value}:prev)}/>
   <p className="muted-caption"><AlertTriangle size={13}/> {data.unknown} If the record grain or outcome timing matters, confirm it before modelling.</p>
   <p className="muted-caption">{data.note} Working version: {data.version}.</p>
  </>}
 </section>;
}
