/** Keyboard boundary for the version-bound Quality correction consent dialog.
 * The dialog is UI only; server-side approval and version checks remain authoritative.
 */
const FOCUSABLE='button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function handleQualityApprovalKeyDown(
  event: Pick<KeyboardEvent,'key'|'shiftKey'|'preventDefault'|'stopPropagation'>,
  dialog: HTMLElement,
  active: Element|null,
  busy: boolean,
  cancel: ()=>void
):void {
  if(event.key==='Escape'){
    event.preventDefault();event.stopPropagation();
    // Never dismiss consent while a commit request is in flight.
    if(!busy)cancel();
    return;
  }
  if(event.key!=='Tab')return;
  const eligible=Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE))
    .filter(el=>el.tabIndex>=0&&!el.closest('[hidden],[inert],[aria-hidden="true"]'));
  if(!eligible.length){event.preventDefault();dialog.focus();return;}
  const current=eligible.indexOf(active as HTMLElement);
  if(event.shiftKey&&(current===0||active===dialog||!dialog.contains(active))){
    event.preventDefault();eligible[eligible.length-1].focus();
  }else if(!event.shiftKey&&(current===eligible.length-1||active===dialog||!dialog.contains(active))){
    event.preventDefault();eligible[0].focus();
  }
}
