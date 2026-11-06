/** Detects Deliver work that would be replaced by New report or Open report.
 * The initial auto-filled report title is not an edit; any actual narrative,
 * selected evidence or changed title in a new draft is unsaved work.
 * For saved revisions compare to the immutable loaded snapshot, not the
 * previous render or a pre-POST copy.
 */
export type ReportDraftState={
 title:string;
 narrative:string;
 selected:string[];
 defaultTitle:string;
 saved?:{title:string;narrative:string;evidence:{id:string}[]}|null;
};

export function hasUnsavedReportDraft(state:ReportDraftState):boolean{
 const {title,narrative,selected,defaultTitle,saved}=state;
 if(!saved){
  return title!==defaultTitle||narrative.length>0||selected.length>0;
 }
 const oldIds=saved.evidence.map(item=>item.id);
 return title!==saved.title||narrative!==saved.narrative||
  selected.length!==oldIds.length||selected.some((id,index)=>id!==oldIds[index]);
}
