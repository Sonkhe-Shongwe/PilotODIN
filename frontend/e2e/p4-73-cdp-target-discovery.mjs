// P4-73 native CDP discovery and redacted loopback diagnostics.
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

async function fetchLoopback(fetcher, url) {
  try {
    const response = await fetcher(url, {
      redirect: 'error',
      signal: AbortSignal.timeout(2000),
    });
    return {response, httpStatus: response.status};
  } catch (error) {
    return {status: error?.name === 'TimeoutError' ? 'timeout' : 'unavailable'};
  }
}

export async function diagnoseDevPage(fetcher = fetch) {
  const [vite, debuggerList] = await Promise.all([
    fetchLoopback(fetcher, 'http://127.0.0.1:5173/'),
    fetchLoopback(fetcher, 'http://127.0.0.1:9331/json/list'),
  ]);
  const devServer = vite.response ? {httpStatus: vite.httpStatus} : vite;
  if (vite.response?.body) await vite.response.body.cancel().catch(() => {});
  if (!debuggerList.response) return {devServer, debuggerList};
  const {response, httpStatus} = debuggerList;
  if (!response.ok) {
    if (response.body) await response.body.cancel().catch(() => {});
    return {devServer, debuggerList: {httpStatus}};
  }
  let targets;
  try {
    targets = await response.json();
  } catch {
    return {devServer, debuggerList: {httpStatus, status: 'unreadable'}};
  }
  if (!Array.isArray(targets)) {
    return {devServer, debuggerList: {httpStatus, status: 'invalid'}};
  }
  const pages = targets.filter(target => target?.type === 'page');
  return {
    devServer,
    debuggerList: {
      httpStatus,
      pageCount: pages.length,
      otherTargetCount: targets.length - pages.length,
      pageClasses: [...new Set(pages.map(page => safeTargetClass(page.url)))].sort(),
    },
  };
}
