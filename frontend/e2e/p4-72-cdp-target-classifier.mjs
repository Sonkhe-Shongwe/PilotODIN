// P4-72 source-only CDP target classification; no navigation, process or network.
const SOURCE_ORIGIN='http://127.0.0.1:5173';
export function isExpectedDevPage(raw){
 try {
  const url=new URL(raw);
  return url.origin===SOURCE_ORIGIN && (url.pathname==='/'||url.pathname==='/index.html');
 } catch {return false;}
}
export function safeTargetClass(raw){
 if(isExpectedDevPage(raw))return 'expected-5173-root';
 if(raw==='about:blank')return 'blank';
 try{
  const u=new URL(raw);
  if(u.protocol==='devtools:')return 'devtools';
  if(u.protocol==='tauri:')return 'tauri-scheme';
  if(u.hostname==='tauri.localhost')return 'tauri-localhost';
  if(u.hostname==='localhost'&&u.port==='5173')return 'localhost-5173-alias';
  if(u.hostname==='127.0.0.1'&&u.port==='5173')return 'nonroot-5173-target';
  if(u.protocol==='http:'||u.protocol==='https:')return 'other-web-origin';
  return 'non-web-target';
 }catch{return 'unknown-target';}
}
