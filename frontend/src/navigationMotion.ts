/**
 * Real workspace navigation transitions (browser / WebView2 when supported).
 * Preserve the previous frame as the next page renders so navigation does not
 * look like an abrupt unmount. No artificial delay, and no captured app data.
 * Falls back to normal hash navigation on older engines and reduced-motion OSes.
 */
type TransitionDocument=Document&{
 startViewTransition?:(callback:()=>Promise<void>)=>{finished:Promise<void>};
};
let navigationSerial=0;

export function navigateHashSmoothly(nextHash:string,onRouteChanged?:()=>void):void{
 if(location.hash===nextHash){onRouteChanged?.();return;}
 const doc=document as TransitionDocument;
 const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches??false;
 if(reduced||typeof doc.startViewTransition!=='function'){
  location.hash=nextHash;onRouteChanged?.();return;
 }
 const serial=++navigationSerial;
 document.documentElement.classList.add('po-navigation-in-flight');
 try{
  const transition=doc.startViewTransition(async()=>{
   location.hash=nextHash;
   onRouteChanged?.();
   // Hashchange listeners update both UnifiedShell and App asynchronously.
   // Two paint opportunities ensure the new React view is in the next snapshot.
   await new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));
  });
  void transition.finished.catch(()=>{/* navigation already occurred */}).finally(()=>{
   if(serial===navigationSerial)document.documentElement.classList.remove('po-navigation-in-flight');
  });
 }catch{
  document.documentElement.classList.remove('po-navigation-in-flight');
  if(location.hash!==nextHash)location.hash=nextHash;
  onRouteChanged?.();
 }
}
