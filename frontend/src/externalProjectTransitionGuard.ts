import type {EditedDock} from './dockInputDiscardGuard';
import type {SecondaryView} from './workspaceLayout';

export type ExternalProjectTransition='unchanged'|'accept'|'confirm';

/** Decide whether a project selector/storage notification would remove an edited dock.
 * No field values are read or persisted. Backend-confirmed unavailable projects cannot
 * be retained merely because an obsolete dock contains edits.
 */
export function planExternalProjectTransition(
 currentProjectId:string,
 requestedProjectId:string,
 currentDock:SecondaryView|null,
 edited:EditedDock|null,
 workspaceReady:boolean,
 unavailableProject=false
):ExternalProjectTransition {
 if(requestedProjectId===currentProjectId)return 'unchanged';
 if(unavailableProject)return 'accept';
 if(!workspaceReady||!currentProjectId||!currentDock||!edited)return 'accept';
 return edited.projectId===currentProjectId&&edited.view===currentDock?'confirm':'accept';
}
