/** Primary Studio can unmount on cross-workspace navigation. Protect
 * a dirty Deliver narrative on ANY exit, including Explore; other legacy
 * Prepare/Model/Predict drafts keep their original Canvas-only guard.
 * Only dirty-state markers cross the shell, never private report contents.
 */
export type PrimaryStudioDraft={projectId:string;view:'understand'|'prepare'|'model'|'predict'|'deliver'};
export function needsPrimaryStudioExitApproval(
 edited:PrimaryStudioDraft|null,projectId:string,
 currentView:string,requestedView:string,workspaceReady:boolean
):boolean{
 if(!projectId||!workspaceReady||!edited||edited.projectId!==projectId||
    currentView===requestedView)return false;
 if(edited.view==='deliver'||edited.view==='understand')
  return currentView===edited.view&&requestedView!==edited.view;
 return currentView!=='investigate'&&requestedView==='investigate';
}
