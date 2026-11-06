import type {WorkspaceView} from './workspaceLayout';

/** Plan focus after removing a tab, without changing saved layouts or project state.
 * Closing the selected tab retains the existing last-open-tab fallback.
 * Closing an inactive tab restores focus to the still-selected tab.
 */
export type WorkspaceTabClosePlan={
  remaining:WorkspaceView[];
  nextActive:WorkspaceView;
  focus:WorkspaceView;
};
export function planWorkspaceTabClose(
  tabs:readonly WorkspaceView[],
  active:WorkspaceView,
  closing:WorkspaceView
):WorkspaceTabClosePlan|null {
  if(tabs.length<=1||!tabs.includes(closing)||!tabs.includes(active))return null;
  const remaining=tabs.filter(view=>view!==closing);
  const nextActive=closing===active?remaining[remaining.length-1]:active;
  return {remaining,nextActive,focus:nextActive};
}
