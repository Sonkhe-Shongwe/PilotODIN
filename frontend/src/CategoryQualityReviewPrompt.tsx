import {useEffect,useState} from 'react';
import {ArrowRight,ShieldCheck} from 'lucide-react';
import {get} from './api';
import type {QualityFocus} from './qualityHandoff';
import {reviewableWhitespaceFinding} from './categoryQualityAdvice';
import type {CategoryQualitySnapshot,WhitespaceFinding} from './categoryQualityAdvice';

type Props={
  projectId:string;
  version:number;
  columns:readonly string[];
  location:'prepare'|'predict';
  onReview:(focus:QualityFocus)=>void;
};

/** Read-only handoff to the existing versioned Quality approval process. */
export function CategoryQualityAdvice({projectId,version,columns,location,onReview}:Props){
  const fieldsKey=columns.join('\u0000');
  const scopeKey=projectId+':'+version+':'+fieldsKey;
  const [matched,setMatched]=useState<{scopeKey:string;finding:WhitespaceFinding}|null>(null);
  useEffect(()=>{
    let active=true;
    const controller=new AbortController();
    setMatched(null);
    if(columns.length){
      get<CategoryQualitySnapshot>('/projects/'+encodeURIComponent(projectId)+'/quality',{signal:controller.signal})
        .then(snapshot=>{
          if(!active)return;
          const finding=reviewableWhitespaceFinding(snapshot,projectId,version,columns);
          if(finding)setMatched({scopeKey,finding});
        })
        .catch(()=>{/* An unavailable Quality read does not grant approval or modify data. */});
    }
    return()=>{active=false;controller.abort()};
  },[projectId,version,fieldsKey,scopeKey]);
  if(!matched||matched.scopeKey!==scopeKey||matched.finding.column===null)return null;
  const column=matched.finding.column;
  return <section className="panel po-ml-category-advice" aria-label="Review category whitespace in Data Quality">
    <div className="panel-title"><ShieldCheck size={19}/><h2>Category labels could be made consistent</h2><span className="pill muted">Quality finding · working v{version}</span></div>
    <p className="body-muted">The current Quality scan found {matched.finding.affected_rows.toLocaleString()} value(s) with surrounding whitespace in <strong>{column}</strong>. An eligible trim can be previewed before you decide whether to create a new working-data version.</p>
    <p className="muted-caption">{location==='predict'?'This fitted model keeps its original exact category values. To use consolidated categories, approve a reviewed Quality change and train/select a new model on that version.':'Review the proposed correction before training. The original uploaded dataset remains unchanged.'} No change happens from this link.</p>
    <button type="button" className="btn" onClick={()=>onReview({projectId,version,column,kind:'whitespace'})}>Review {column} in Data Quality <ArrowRight size={16}/></button>
  </section>;
}
