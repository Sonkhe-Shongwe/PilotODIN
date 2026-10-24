/** Gradual, interruptible scroll to a chart's newly opened record inspector.
 * The closest scrollable workspace receives the animation; never move sibling panes.
 * Respect reduced-motion preferences and let the user interrupt with input.
 */
export const INSPECTOR_SCROLL_MS = 820;

export function revealRecordInspector(panel: HTMLElement): () => void {
  panel.focus({preventScroll:true});
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    panel.scrollIntoView({behavior:'auto',block:'start',inline:'nearest'});
    return () => {};
  }
  let parent: HTMLElement|null = panel.parentElement;
  while (parent) {
    const style = window.getComputedStyle(parent);
    if (/(auto|scroll)/.test(style.overflowY) && parent.scrollHeight > parent.clientHeight + 2) break;
    parent = parent.parentElement;
  }
  if (!parent) {
    // Keep native scrolling for documents without an actual independent scroll area.
    panel.scrollIntoView({behavior:'smooth',block:'start',inline:'nearest'});
    return () => {};
  }

  const scrollContainer=parent;
  const start=scrollContainer.scrollTop;
  const margin=28;
  const panelTop=panel.getBoundingClientRect().top;
  const containerTop=scrollContainer.getBoundingClientRect().top;
  const target=Math.max(0,Math.min(scrollContainer.scrollHeight-scrollContainer.clientHeight,
    start + panelTop - containerTop - margin));
  const distance=target-start;
  if (Math.abs(distance) < 3) return () => {};

  let active=true;
  let handle=0;
  let started:number|null=null;
  function cleanup(){
    if (!active) return;
    active=false;
    window.cancelAnimationFrame(handle);
    scrollContainer.removeEventListener('wheel',cleanup);
    scrollContainer.removeEventListener('touchstart',cleanup);
    window.removeEventListener('keydown',onKeyboard);
  }
  function onKeyboard(event:KeyboardEvent) {
    if (['PageDown','PageUp','ArrowUp','ArrowDown','Home','End',' '].includes(event.key)) cleanup();
  }
  function tick(now:number){
    if (!active) return;
    if (started===null) started=now;
    const t=Math.min(1,(now-started)/INSPECTOR_SCROLL_MS);
    // Smooth start and finish rather than the abrupt native scroll initiation.
    const eased=t<.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2;
    scrollContainer.scrollTop=start+distance*eased;
    if (t>=1) cleanup();
    else handle=window.requestAnimationFrame(tick);
  }
  scrollContainer.addEventListener('wheel',cleanup,{passive:true});
  scrollContainer.addEventListener('touchstart',cleanup,{passive:true});
  window.addEventListener('keydown',onKeyboard);
  handle=window.requestAnimationFrame(tick);
  return cleanup;
}
