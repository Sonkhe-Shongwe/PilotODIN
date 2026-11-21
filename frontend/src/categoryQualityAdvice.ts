/** Read-only, project/version-pinned guidance for existing Quality review. */
export type WhitespaceFinding = {
  id:string;
  kind:string;
  column:string|null;
  affected_rows:number;
  decision:string;
  proposal:null|{kind:string;column:string};
};
export type CategoryQualitySnapshot = {
  project_id:string;
  version:number;
  issues:WhitespaceFinding[];
};

export function reviewableWhitespaceFinding(
  snapshot:CategoryQualitySnapshot,
  projectId:string,
  workingVersion:number,
  columns:readonly string[]
):WhitespaceFinding|null{
  if(snapshot.project_id!==projectId||snapshot.version!==workingVersion||!columns.length)return null;
  const allowed=new Set(columns);
  return snapshot.issues.find(issue=>
    issue.kind==='whitespace'&&issue.column!==null&&allowed.has(issue.column)&&
    issue.decision==='pending'&&issue.affected_rows>0&&
    issue.proposal?.kind==='trim_whitespace'&&issue.proposal.column===issue.column
  )??null;
}

/** A fitted categorical encoder can contain distinct strings that look the same after trimming. */
export function hasWhitespaceCategoryCollision(options:readonly string[]):boolean{
  const seen=new Map<string,string>();
  for(const value of options){
    const readable=value.trim();
    if(!readable)continue;
    const first=seen.get(readable);
    if(first!==undefined&&first!==value)return true;
    seen.set(readable,value);
  }
  return false;
}
