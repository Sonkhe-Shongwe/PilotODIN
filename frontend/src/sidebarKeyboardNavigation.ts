import type {WorkspaceView} from './workspaceLayout';

/** Keyboard traversal follows the rendered navigation order, including section boundaries.
 * Pure selection only: it never changes a project, dataset, or sidebar preference.
 */
export function nextSidebarViewByKey(
  views:readonly WorkspaceView[],
  current:WorkspaceView,
  key:string
):WorkspaceView|null {
  if(views.length===0)return null;
  const index=views.indexOf(current);
  if(index<0)return null;
  if(key==='ArrowDown')return views[(index+1)%views.length];
  if(key==='ArrowUp')return views[(index+views.length-1)%views.length];
  if(key==='Home')return views[0];
  if(key==='End')return views[views.length-1];
  return null;
}
