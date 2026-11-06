/** Read-only comparison of two already-frozen, verified Deliver revisions.
 * This function does not fetch, recompute evidence, write, or trust draft state.
 */
export type FrozenExhibit = {id:string;operation:string;dataset_version:number};
export type FrozenReport = {
 id:string;revision:number;title:string;narrative:string;
 content_sha256:string;dataset_versions:number[];evidence:FrozenExhibit[];
};
export type ExhibitChange = {id:string;operation:string;fromVersion?:number;toVersion?:number};
export type RevisionComparison = {
 from:number;to:number;fromSha256:string;toSha256:string;
 titleChanged:boolean;narrativeChanged:boolean;
 oldTitle:string;newTitle:string;oldNarrative:string;newNarrative:string;
 added:ExhibitChange[];removed:ExhibitChange[];changed:ExhibitChange[];
 orderChanged:boolean;oldOrder:string[];newOrder:string[];
 versionsAdded:number[];versionsRemoved:number[];
 otherSnapshotChanged:boolean;identical:boolean;
};

export function compareFrozenReports(before:FrozenReport,after:FrozenReport):RevisionComparison {
 if(!before||!after||before.id!==after.id||!before.id||
     !Number.isSafeInteger(before.revision)||!Number.isSafeInteger(after.revision)||
     before.revision<1||after.revision<=before.revision||
     !Array.isArray(before.evidence)||!Array.isArray(after.evidence)||
     !Array.isArray(before.dataset_versions)||!Array.isArray(after.dataset_versions)){
  throw new Error('Cannot compare unrelated or incorrectly ordered saved revisions.');
 }
 const oldById=new Map(before.evidence.map(item=>[item.id,item]));
 const newById=new Map(after.evidence.map(item=>[item.id,item]));
 if(oldById.size!==before.evidence.length||newById.size!==after.evidence.length){
  throw new Error('Saved revision contains duplicate evidence identifiers.');
 }
 const detail=(item:FrozenExhibit,previous?:FrozenExhibit):ExhibitChange=>({
  id:item.id,operation:item.operation,
  ...(previous?{fromVersion:previous.dataset_version}:{}),
  toVersion:item.dataset_version,
 });
 const added=after.evidence.filter(item=>!oldById.has(item.id)).map(item=>detail(item));
 const removed=before.evidence.filter(item=>!newById.has(item.id)).map(item=>({
  id:item.id,operation:item.operation,fromVersion:item.dataset_version,
 }));
 const changed=after.evidence.filter(item=>{
  const earlier=oldById.get(item.id);
  return earlier!==undefined&&JSON.stringify(earlier)!==JSON.stringify(item);
 }).map(item=>detail(item,oldById.get(item.id)));
 // Order compares surviving common exhibits only: additions/removals have
 // already been disclosed above and are not mistaken for reordered evidence.
 const oldOrder=before.evidence.map(item=>item.id);
 const newOrder=after.evidence.map(item=>item.id);
 const commonOld=oldOrder.filter(id=>newById.has(id));
 const commonNew=newOrder.filter(id=>oldById.has(id));
 const orderChanged=commonOld.some((id,index)=>id!==commonNew[index]);
 const oldVersions=new Set(before.dataset_versions);
 const newVersions=new Set(after.dataset_versions);
 const versionsAdded=after.dataset_versions.filter(v=>!oldVersions.has(v));
 const versionsRemoved=before.dataset_versions.filter(v=>!newVersions.has(v));
 const titleChanged=before.title!==after.title;
 const narrativeChanged=before.narrative!==after.narrative;
 const visibleChanged=titleChanged||narrativeChanged||added.length>0||
   removed.length>0||changed.length>0||orderChanged||
   versionsAdded.length>0||versionsRemoved.length>0;
 const otherSnapshotChanged=before.content_sha256!==after.content_sha256&&!visibleChanged;
 return {
  from:before.revision,to:after.revision,
  fromSha256:before.content_sha256,toSha256:after.content_sha256,
  titleChanged,narrativeChanged,
  oldTitle:before.title,newTitle:after.title,
  oldNarrative:before.narrative,newNarrative:after.narrative,
  added,removed,changed,orderChanged,oldOrder,newOrder,
  versionsAdded,versionsRemoved,
  otherSnapshotChanged,
  identical:!visibleChanged&&before.content_sha256===after.content_sha256,
 };
}
