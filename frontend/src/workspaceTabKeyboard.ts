import type {WorkspaceView} from './workspaceLayout';

/**
 * APG-style navigation for the workspace tablist.
 * Only handles unmodified Left/Right, Home and End; other browser keys pass through.
 * This function only selects a view, never mutates project or saved workspace data.
 */
export function nextWorkspaceTabByKey(
  tabs:readonly WorkspaceView[],
  current:WorkspaceView,
  key:string
):WorkspaceView|null {
  if(!tabs.length)return null;
  const index=tabs.indexOf(current);
  if(index<0)return null;
  if(key==='Home')return tabs[0];
  if(key==='End')return tabs[tabs.length-1];
  if(key==='ArrowRight')return tabs[(index+1)%tabs.length];
  if(key==='ArrowLeft')return tabs[(index+tabs.length-1)%tabs.length];
  return null;
}
