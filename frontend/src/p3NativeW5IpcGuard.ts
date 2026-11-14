/** Allow exactly the synthetic W5 native finish command through Tauri's
 * fetch-first IPC bridge. The QA page intercepts window.fetch to prohibit
 * unrelated remote/API writes. On Windows WebView2 the Tauri custom scheme
 * becomes http://ipc.localhost; on other runtimes it can be ipc://localhost.
 * Returning a synthetic HTTP 403 Response here is NOT a rejected fetch and
 * can prevent Tauri's postMessage fallback, yielding a non-Error rejection.
 *
 * The custom Rust command independently enforces debug+W5 page+main window.
 * This helper is transport allowlisting, not permission to approve data.
 */
export function isNativeW5FinishIpcRequest(
  url:URL, method:string, init?:RequestInit,
):boolean {
  if(method!=='POST'||url.pathname!=='/finish_p3_w5_synthetic_qa'||
     url.search!==''||url.hash!==''||url.port!==''||
     url.username!==''||url.password!=='')return false;
  const localIpc=(url.protocol==='ipc:'&&url.hostname==='localhost')||
    (url.protocol==='http:'&&url.hostname==='ipc.localhost');
  if(!localIpc)return false;
  const headers=new Headers(init?.headers);
  return headers.has('Tauri-Invoke-Key')&&headers.has('Tauri-Callback')&&
    headers.has('Tauri-Error');
}
