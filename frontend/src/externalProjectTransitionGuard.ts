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
