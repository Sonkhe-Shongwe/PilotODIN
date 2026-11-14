/** Pure selector presentation: stable project IDs are never changed. */
export type SelectorProject={id:string;name:string;filename:string};
function format(filename:string):string{
 return filename.match(/\.([a-z0-9]{1,8})$/i)?.[1]?.toUpperCase()??'FILE';
}
export function projectOptionLabels(projects:readonly SelectorProject[]):Map<string,string>{
 const groups=new Map<string,SelectorProject[]>();
 for(const project of projects){
  const key=project.name.trim().toLowerCase();
  const group=groups.get(key)??[];
  group.push(project);
  groups.set(key,group);
 }
 const labels=new Map<string,string>();
 for(const project of projects){
  const siblings=groups.get(project.name.trim().toLowerCase())??[];
  if(siblings.length===1){labels.set(project.id,project.name);continue;}
  const kind=format(project.filename);
  const sameKind=siblings.filter(other=>format(other.filename)===kind);
  // Put CSV/XLSX first so the format is visible in narrow native menus.
  const suffix=sameKind.length>1?' · '+project.id.slice(0,8):'';
  labels.set(project.id,'['+kind+'] '+project.name+suffix);
 }
 return labels;
}
