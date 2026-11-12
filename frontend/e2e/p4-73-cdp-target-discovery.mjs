// P4-73 pure, no-network native CDP discovery. Browser snapshot and wait are injected.
import {isExpectedDevPage, safeTargetClass} from './p4-72-cdp-target-classifier.mjs';

export async function discoverUniqueDevPage(snapshot, wait, maxAttempts=20) {
  if(!Number.isInteger(maxAttempts)||maxAttempts<1||maxAttempts>20)
    throw Error('P4-73 blocked: invalid bounded attempt count');
  let classes=[];
  for(let attempt=1;attempt<=maxAttempts;attempt++) {
    const candidates=await snapshot();
    if(!Array.isArray(candidates))return {status:'BLOCKED_INVALID_SNAPSHOT',classes:[],count:0,attempts:attempt};
    const matching=candidates.filter(p=>p&&typeof p.url==='function'&&isExpectedDevPage(p.url()));
    if(matching.length>1)return {status:'BLOCKED_AMBIGUOUS',classes:['expected-5173-root'],count:candidates.length,attempts:attempt};
    if(matching.length===1)return {status:'FOUND',page:matching[0],attempts:attempt};
    classes=candidates.map(p=>p&&typeof p.url==='function'?safeTargetClass(p.url()):'unknown-target');
    if(attempt<maxAttempts)await wait();
  }
  return {status:'BLOCKED_NO_TARGET',classes:[...new Set(classes)].sort(),count:classes.length,attempts:maxAttempts};
}

// Read-only browser-context evidence before any synthetic fixture upload or
// native UI navigation. Not an OS process identity or original-data audit.
export async function hasTauriNativeBridge(page) {
  try {
    return await page.evaluate(() =>
      Boolean(window.__TAURI_INTERNALS__ &&
        typeof window.__TAURI_INTERNALS__.invoke==='function'))===true;
  } catch {return false;}
}
