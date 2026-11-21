/** Transient, project- and approved-version-scoped Quality navigation target. */
export type QualityFocus={projectId:string;version:number;column:string|null;kind:string};
export type QualityFinding={id:string;kind:string;column:string|null};
export type QualityFocusResult={status:'matched';issueId:string}|{status:'stale'|'unavailable';message:string};

export function resolveQualityFocus(
  focus:QualityFocus,projectId:string,version:number,issues:QualityFinding[]
):QualityFocusResult{
  if(focus.projectId!==projectId||focus.version!==version){
    return {status:'stale',message:'The source analysis belongs to another project or working version. Review the current Quality findings instead.'};
  }
  const issue=issues.find(item=>
    (focus.column===null?item.column===null:item.column===focus.column)&&
    (focus.kind==='any'||item.kind===focus.kind)
  );
  if(!issue)return {status:'unavailable',message:'No corresponding Quality finding exists in this approved version. The analytical observation is not automatically classified as a cleaning error.'};
  return {status:'matched',issueId:issue.id};
}

/** A specific handoff is offered only when a deterministic rule maps to Quality. */
export function insightQualityKind(finding:{category:string;title:string}):string|null{
  if(finding.category==='missing')return 'missing';
  if(finding.category==='distribution')return 'outliers';
  if(finding.category==='duplicates')return 'exact_duplicates';
  if(finding.category==='features'&&/identifier/i.test(finding.title))return 'identifier';
  return null;
}
