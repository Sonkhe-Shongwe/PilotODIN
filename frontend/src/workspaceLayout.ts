/** Pure, validated, project-scoped desktop layout contract. No analytical data lives here. */
export const WORKSPACE_VIEWS = [
  'overview','understand','investigate','quality','explore','prepare',
  'model','evaluate','predict','deliver','assistant','ai_settings'
] as const;
export type WorkspaceView = typeof WORKSPACE_VIEWS[number];
export type SecondaryView = Exclude<WorkspaceView,'investigate'|'overview'>;
export type DockSide = 'left'|'right';
export type DockLayout = {schema:2; secondary:SecondaryView|null; side:DockSide; fraction:number};
export const DEFAULT_DOCK_LAYOUT:DockLayout = {schema:2,secondary:null,side:'right',fraction:0.39};
export const DOCK_MIN_FRACTION = 0.28;
export const DOCK_MAX_FRACTION = 0.58;
const secondarySet:ReadonlySet<string> = new Set(WORKSPACE_VIEWS.filter(v=>v!=='investigate'&&v!=='overview'));
const viewSet:ReadonlySet<string> = new Set(WORKSPACE_VIEWS);
export function isWorkspaceView(v:unknown):v is WorkspaceView {return typeof v==='string'&&viewSet.has(v)}
export function isSecondaryView(v:unknown):v is SecondaryView {return typeof v==='string'&&secondarySet.has(v)}
export function clampFraction(value:number):number {
  return Number.isFinite(value)?Math.max(DOCK_MIN_FRACTION,Math.min(DOCK_MAX_FRACTION,value)):DEFAULT_DOCK_LAYOUT.fraction;
}
export function parseDockLayout(raw:unknown):DockLayout {
  if(!raw||typeof raw!=='object'||Array.isArray(raw))return {...DEFAULT_DOCK_LAYOUT};
  const input=raw as Record<string,unknown>;
  // Reject unknown schema revisions rather than silently interpreting incompatible layout data.
  if(input.schema!==2)return {...DEFAULT_DOCK_LAYOUT};
  return {
    schema:2,
    secondary:isSecondaryView(input.secondary)?input.secondary:null,
    side:input.side==='left'?'left':'right',
    fraction:clampFraction(typeof input.fraction==='number'?input.fraction:NaN)
  };
}
export function dockStorageKey(projectId:string):string {
  // Only the project identifier scopes layout state; never store dataset rows or project content.
  return `pilotodin-dock-layout-v2-${encodeURIComponent(projectId||'none')}`;
}
export function makeDockResize(layout:DockLayout, pointerX:number,left:number,width:number):DockLayout {
  if(!Number.isFinite(width)||width<=0||!Number.isFinite(pointerX))return layout;
  const position=(pointerX-left)/width;
  const fraction=layout.side==='right'?1-position:position;
  return {...layout,fraction:clampFraction(fraction)};
}
export function nextDockLayout(layout:DockLayout, action:
  |{kind:'open';view:WorkspaceView}
  |{kind:'close'}
  |{kind:'flip'}
  |{kind:'resize';fraction:number}
  |{kind:'reset'}
):DockLayout {
  if(action.kind==='reset')return {...DEFAULT_DOCK_LAYOUT};
  if(action.kind==='close')return {...layout,secondary:null};
  if(action.kind==='flip')return {...layout,side:layout.side==='right'?'left':'right'};
  if(action.kind==='resize')return {...layout,fraction:clampFraction(action.fraction)};
  if(action.kind==='open')return isSecondaryView(action.view)?{...layout,secondary:action.view}:layout;
  return layout;
}

/**
 * A saved project may have been deleted or archived since the last session.
 * A slow project-list response must not clear a newer selection made meanwhile.
 * Never infer that an empty selection is invalid: it means no project is open.
 */
export function shouldClearUnavailableProject(
  selectedAtRequestStart:string,
  currentSelection:string,
  availableProjects:readonly {id:string}[]
):boolean {
  return !!selectedAtRequestStart &&
    selectedAtRequestStart === currentSelection &&
    !availableProjects.some(project=>project.id===currentSelection);
}
