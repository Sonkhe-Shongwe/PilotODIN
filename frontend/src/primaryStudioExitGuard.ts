/** Primary Studio state spans its subviews; switching to Investigation
 * unmounts the entire Studio and can discard unsaved Prepare/Model/Predict.
 * Pure state-marker check. Never store or inspect form values.
 */
export type PrimaryStudioDraft={projectId:string;view:'prepare'|'model'|'predict'};
export function needsPrimaryStudioExitApproval(
 edited:PrimaryStudioDraft|null,projectId:string,
 currentView:string,requestedView:string,workspaceReady:boolean
):boolean{
 return !!projectId&&workspaceReady&&currentView!=='investigate'
  &&requestedView==='investigate'&&edited?.projectId===projectId;
}
