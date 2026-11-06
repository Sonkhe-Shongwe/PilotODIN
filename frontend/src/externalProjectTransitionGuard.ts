import type {EditedDock} from './dockInputDiscardGuard';
import type {SecondaryView} from './workspaceLayout';

export type ExternalProjectTransition='unchanged'|'accept'|'confirm';

/** Decide whether a project selector/storage event would discard an edited
 * primary form or a secondary dock. Only project identity markers are inspected.
 * No field values are read or persisted. Backend-confirmed removal is handled
 * by the existing non-cancellable recovery path.
 */
export function planExternalProjectTransition(
 currentProjectId:string,
 requestedProjectId:string,
 currentDock:SecondaryView|null,
 edited:EditedDock|null,
 workspaceReady:boolean,
 unavailableProject=false,
 editedPrimaryProjectId:string|null=null
):ExternalProjectTransition {
 if(requestedProjectId===currentProjectId)return 'unchanged';
 if(unavailableProject)return 'accept';
 if(!workspaceReady||!currentProjectId)return 'accept';
 if(editedPrimaryProjectId===currentProjectId)return 'confirm';
 if(!currentDock||!edited)return 'accept';
 return edited.projectId===currentProjectId&&edited.view===currentDock?'confirm':'accept';
}
/** An unsolicited storage event is not permission to discard an edited Deliver
 * report in another native window. Leave shared storage untouched; the user
 * can select a project in this window through its existing native consent path.
 */
export function shouldHoldNativeDeliverExternalProjectChange(
 eventType:string,
 decision:ExternalProjectTransition,
 native:boolean,
 currentProjectId:string,
 editedPrimary:{projectId:string;view:string}|null
):boolean {
 return eventType==='storage'&&decision==='confirm'&&native&&
  editedPrimary?.projectId===currentProjectId&&editedPrimary.view==='deliver';
}
