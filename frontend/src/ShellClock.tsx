import {useEffect,useState} from 'react';
import {formatShellClock,msUntilNextClockMinute} from './shellClockFormat';

/**
 * Satin Chronograph: one decorative, accessible local clock for the global
 * shell only. It never reads project data or calls backend / network APIs.
 */
export function ShellClock(){
 const [now,setNow]=useState(()=>new Date());
 useEffect(()=>{
  let pending:ReturnType<typeof setTimeout>|undefined;
  const refresh=()=>{
   setNow(new Date());
   if(pending!==undefined)window.clearTimeout(pending);
   pending=window.setTimeout(refresh,msUntilNextClockMinute(Date.now()));
  };
  const onVisibility=()=>{if(document.visibilityState==='visible')refresh()};
  refresh();
  document.addEventListener('visibilitychange',onVisibility);
  window.addEventListener('focus',refresh);
  return ()=>{
   if(pending!==undefined)window.clearTimeout(pending);
   document.removeEventListener('visibilitychange',onVisibility);
   window.removeEventListener('focus',refresh);
  };
 },[]);
 const display=formatShellClock(now);
 return <time className="po-shell-clock" dateTime={now.toISOString()}
  title={display.fullDescription} aria-label={display.fullDescription}>
  <span className="po-shell-clock-accent" aria-hidden="true"/>
  <span className="po-shell-clock-face" aria-hidden="true">
   <span className="po-shell-clock-time">{display.time}</span>
   <span className="po-shell-clock-date">{display.date}</span>
  </span>
 </time>;
}
