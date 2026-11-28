import type {DockLayout,WorkspaceView} from './workspaceLayout';

/** Scope explicit dock-dismiss focus to the current restored project.
 * Never stores or reads draft form content.
 */
export type DockDismissFocus={projectId:string;view:WorkspaceView};
export function planDockDismissFocus(
  projectId:string,
  active:WorkspaceView,
  openTabs:readonly WorkspaceView[],
  dock:DockLayout,
  workspaceReady:boolean
):DockDismissFocus|null {
  if(!workspaceReady||!projectId||dock.secondary===null||!openTabs.includes(active))return null;
  return {projectId,view:active};
}

/** A queued focus request is safe only after the pane is closed and the same
 * project's active tab is still rendered.
 */
export function canRestoreDockDismissFocus(
  pending:DockDismissFocus|null,
  projectId:string,
  active:WorkspaceView,
  openTabs:readonly WorkspaceView[],
  dock:DockLayout,
  workspaceReady:boolean
):boolean {
  return pending!==null&&workspaceReady&&pending.projectId===projectId&&
    pending.view===active&&openTabs.includes(active)&&dock.secondary===null;
}
