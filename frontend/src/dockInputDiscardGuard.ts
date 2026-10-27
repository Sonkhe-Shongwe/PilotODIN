import type {SecondaryView} from './workspaceLayout';

/** Tracks only a conservative edit indicator, never field values or dataset content.
 * An explicit action is guarded only while it would remove the edited dock.
 */
export type EditedDock={projectId:string;view:SecondaryView};
export function isEditableDockInput(tagName:string):boolean {
  return tagName==='INPUT'||tagName==='TEXTAREA'||tagName==='SELECT';
}
export function needsDockInputDiscardApproval(
  edited:EditedDock|null,
  projectId:string,
  current:SecondaryView|null,
  action:'close'|'replace'|'switch-project'|'reset'|'close-tab'|'activate',
  proposed:SecondaryView|null=null
):boolean {
  if(!edited||!projectId||edited.projectId!==projectId||!current||edited.view!==current)return false;
  if(action==='replace')return proposed!==null&&proposed!==current;
  if(action==='activate')return proposed===current;
  return true;
}
