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
 // Exact column-name pairing only. User descriptions are not tested for
 // agreement with the inferred analytical role or treated as validated truth.
 const ownerFieldDescriptions=new Map(
  (data?.user_context?.field_definitions??[]).map(item=>[item.column,item.meaning] as const)
 );
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
   {data.user_context&&<p className="muted-caption">Review system hypotheses beside your descriptions below. Matching words do not prove agreement; conflicting wording is not automatically classified. No model or dataset is changed.</p>}
   <details>
    <summary>Inspect tentative field meanings ({data.fields.length} fields with hints)</summary>
    <div className="po-col-table-scroll">
     <table><thead><tr><th>FIELD</th><th>POSSIBLE ROLE</th><th>EVIDENCE BASIS</th><th>REVIEW NOTE</th><th>USER DESCRIPTION (UNVERIFIED)</th></tr></thead>
      <tbody>{data.fields.slice(0,20).flatMap(item=>item.hypotheses.map(h=><tr key={item.column+'-'+h.role}><td>{item.column}</td><td>{humanRole(h.role)} (unverified)</td><td>{humanRole(h.basis)}</td><td>{h.reason}</td><td>{ownerFieldDescriptions.has(item.column)?
        <span>{ownerFieldDescriptions.get(item.column)} (user-described, not independently verified)</span>
        :'No user description'}</td></tr>))}</tbody>
     </table>
    </div>
    {data.fields.length>20&&<p className="muted-caption">Showing the first 20 fields with hypotheses; no field was automatically modified.</p>}
   </details>
   {data.user_context&&<div className="po-col-metadata" role="region" aria-label="Owner-described business context">
    <div><small>User description, not independently verified</small>
     {data.user_context.domain_description&&<div role="group" aria-label="Compare unverified domain statements">
      <p><strong>System domain hypothesis:</strong> {data.domain.state==='hypothesis'?data.domain.label:'Unknown'}</p>
      <p><strong>User-described domain:</strong> {data.user_context.domain_description}</p>
      <p className="muted-caption">No automatic equivalence or disagreement finding; the dataset owner must review.</p>
     </div>}
     {data.user_context.record_grain_description&&<div role="group" aria-label="Compare record-key and row-meaning statements">
      <p><strong>Possible unique row key:</strong> {data.grain.state==='hypothesis'?data.grain.identifier_column:'Unknown'}</p>
      <p><strong>User-described row meaning:</strong> {data.user_context.record_grain_description}</p>
      <p className="muted-caption">A unique row key does not independently establish what one row represents.</p>
     </div>}
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
