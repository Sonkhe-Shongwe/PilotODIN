import type {SecondaryView,WorkspaceView} from './workspaceLayout';
import type {EditedDock} from './dockInputDiscardGuard';

export type ExternalRouteActivation='unchanged'|'promote'|'confirm-promote';

/** Pure decision for URL/history changes, which bypass normal tab and Studio go() handlers.
 * Never stores, reads or copies form content. Browser history rollback belongs to the caller.
 */
export function planExternalRouteActivation(
 current:WorkspaceView,
 requested:WorkspaceView,
 dock:SecondaryView|null,
 edited:EditedDock|null,
 projectId:string,
 workspaceReady:boolean
):ExternalRouteActivation {
 if(!workspaceReady||!projectId||current===requested||dock!==requested)return 'unchanged';
 if(edited&&edited.projectId===projectId&&edited.view===dock)return 'confirm-promote';
 return 'promote';
}
