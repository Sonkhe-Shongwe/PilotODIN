/** Global display preference, never scoped to a user project or dataset. */
export type SidebarMode='expanded'|'compact';
export const SIDEBAR_KEY='pilotodin-sidebar-mode-v1';
export function resolveSidebarMode(stored:unknown,viewportWidth:number):SidebarMode {
 if(stored==='expanded'||stored==='compact')return stored;
 return Number.isFinite(viewportWidth)&&viewportWidth<=900?'compact':'expanded';
}
