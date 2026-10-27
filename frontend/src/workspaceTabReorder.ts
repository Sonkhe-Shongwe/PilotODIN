import type {WorkspaceView} from './workspaceLayout';

export type TabDropSide='before'|'after';

/** Move one already-open tab around another, with no navigation or data changes. */
export function reorderWorkspaceTabs(
 tabs:readonly WorkspaceView[],source:WorkspaceView,target:WorkspaceView,side:TabDropSide
):WorkspaceView[]{
 const original=[...tabs];
 if(side!=='before'&&side!=='after')return original;
 if(source===target)return original;
 if(!original.includes(source)||!original.includes(target))return original;
 if(new Set(original).size!==original.length)return original;
 const reordered=original.filter(view=>view!==source);
 const index=reordered.indexOf(target);
 reordered.splice(index+(side==='after'?1:0),0,source);
 return reordered.every((view,i)=>view===original[i])?original:reordered;
}

/** Keyboard alternative: Alt+Shift+Left/Right moves one tab one position. */
export function shiftWorkspaceTab(
 tabs:readonly WorkspaceView[],source:WorkspaceView,direction:-1|1
):WorkspaceView[]{
 const index=tabs.indexOf(source);
 if(index<0||(direction!==-1&&direction!==1))return [...tabs];
 const target=tabs[index+direction];
 if(!target)return [...tabs];
 return reorderWorkspaceTabs(tabs,source,target,direction===-1?'before':'after');
}

/** Reject stale/cross-project HTML drag attempts, not just foreign view names. */
export function canReorderWorkspaceTab(
 projectId:string,workspaceReady:boolean,
 dragged:{projectId:string;view:WorkspaceView}|null,
 target:WorkspaceView,tabs:readonly WorkspaceView[]
):boolean{
 return !!projectId&&workspaceReady&&!!dragged&&dragged.projectId===projectId&&
  dragged.view!==target&&tabs.includes(dragged.view)&&tabs.includes(target);
}
