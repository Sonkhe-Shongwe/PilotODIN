/** Other-window notification only; the backend remains authoritative.
 * No dataset, user drafts, names, file paths or credentials are stored here.
 */
export const PROJECT_LIFECYCLE_SIGNAL_KEY='pilotodin-project-lifecycle-signal-v1';
export type ProjectLifecycleSignal={id:string;revision:number;archived:boolean};
export function parseProjectLifecycleSignal(raw:string|null):ProjectLifecycleSignal|null{
 if(!raw||raw.length>160)return null;
 try{
  const item:unknown=JSON.parse(raw);
  if(!item||typeof item!=='object'||Array.isArray(item))return null;
  const v=item as Record<string,unknown>;
  if(Object.keys(v).sort().join(',')!=='archived,id,revision')return null;
  if(typeof v.id!=='string'||!/^[a-f0-9]{32}$/.test(v.id))return null;
  if(!Number.isSafeInteger(v.revision)||Number(v.revision)<0)return null;
  if(typeof v.archived!=='boolean')return null;
  return {id:v.id,revision:v.revision as number,archived:v.archived};
 }catch{return null}
}
export function publishProjectLifecycleSignal(signal:ProjectLifecycleSignal):void{
 const validated=parseProjectLifecycleSignal(JSON.stringify(signal));
 if(!validated)return;
 try{localStorage.setItem(PROJECT_LIFECYCLE_SIGNAL_KEY,JSON.stringify(validated))}
 catch{/* Lost notification never reverses a confirmed backend write. */}
}
/** Do not discard this window's mounted form because another tab's shared
 * selection points to an archived/unavailable project.
 */
export function preserveMountedUnavailableProject(
 mountedId:string,sharedSelectedId:string,unavailableId:string,heldArchived:boolean
):boolean{
 return !!mountedId&&!!unavailableId&&(
  mountedId!==sharedSelectedId||(heldArchived&&mountedId===unavailableId)
 );
}
