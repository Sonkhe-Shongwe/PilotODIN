import {invoke} from '@tauri-apps/api/core';

// Development remains on :8000; production uses an authenticated, per-launch
// local port provided privately by the Rust desktop process supervisor.
let desktopEndpoint: {port:number;token:string}|null = null;
export function configureDesktopAPI(connection:{port:number;token:string}) {
  if (!Number.isInteger(connection.port) || connection.port < 1024 || connection.port > 65535 || !connection.token) {
    throw new Error('Invalid desktop API connection details');
  }
  desktopEndpoint = connection;
}
export function apiBase():string {return `http://127.0.0.1:${desktopEndpoint?.port ?? 8000}/api`;}
function authHeaders(): Record<string,string> {
  return desktopEndpoint ? {'X-PilotODIN-Session': desktopEndpoint.token} : {};
}
export type Col = {name:string;kind:'numeric'|'categorical';missing:number;missing_pct:number;unique:number;identifier_risk:boolean;leakage_risk:boolean;sample_values:(string|number|null)[]};
export type Profile = {filename:string;rows:number;columns_count:number;missing_cells:number;duplicate_rows:number;columns:Col[];preview:Record<string,unknown>[];target_candidates:string[];warnings:string[];summary:string;summary_source:string;guidance:string[]};
export type Prep = {task:'classification'|'regression';target:string;available_features:string[];recommend_exclude:{column:string;reason:string;requires_review:boolean}[];missing_targets:number;transformations:string[];warnings:string[]};
export type ModelReport = {key:string;name:string;cv_metric?:number;cv_std?:number;status:'ready'|'failed';error?:string};
export type Field = {name:string;kind:'number'|'select'|'text';min?:number;max?:number;options?:string[];required:boolean;domain?:{min?:number;max?:number;integer?:boolean}|null};
export type Results = {task:string;target:string;features:string[];excluded_features:string[];labelled_rows:number;train_rows:number;test_rows:number;folds:number;primary_metric:string;baseline_cv:number;models:ModelReport[];input_schema:Field[];warning:string;beats_baseline?:boolean;split_strategy?:string;split_column?:string|null};
export type Experiment = {id:string;project_id:string;status:string;config:{target:string;task:string;excluded:string[];models:string[];quality_version?:number;split_strategy?:string;split_column?:string|null};results:Results|null;error:string|null;selected_model:string|null;final_results:Record<string,unknown>|null;is_stale?:boolean;dataset_version?:number;current_version?:number};
export type Project = {id:string;name:string;filename:string;profile:Profile;experiments:{id:string;status:string;selected_model:string|null;created_at:string}[]};

async function check(res:Response){
  if(!res.ok){let detail = `Request failed (${res.status})`;try{const o=await res.json();detail=typeof o.detail==='string'?o.detail:JSON.stringify(o.detail)}catch{}throw new Error(detail)}
  return res.json();
}
async function fetchLocal(path:string,options:RequestInit):Promise<Response>{
 try {return await fetch(`${apiBase()}${path}`,options);}
 catch(error){
  if(error instanceof Error&&error.name==='AbortError')throw error;
  const origin=new URL(apiBase()).origin;
  throw new Error(`Could not connect to PilotODIN's local analytics service at ${origin} (request: ${path}). Check that the PilotODIN Backend window is running, then try again.`);
 }
}
// Passive health checks must not allocate 1.5+ GB for a model on an 8 GB machine.
// Only actions explicitly requesting AI reasoning can start the bundled worker.
export function shouldLaunchBundledAI(path:string, method:'GET'|'POST', body?:unknown):boolean {
  // Never start inference for passive probes or explicitly cloud-routed requests.
  if(method!=='POST')return false;
  if(/^\/investigations\/[^/]+\/autonomy\/(start|resume)$/.test(path))return true;
  if(!(/^\/projects\/[^/]+\/ai\/insight$/.test(path)))return false;
  if(body&&typeof body==='object'&&!Array.isArray(body)){
    const provider=(body as {selected_provider?:unknown}).selected_provider;
    if(provider==='gemini'||provider==='groq'||provider==='openrouter'||provider==='local')return false;
  }
  return true;
}
// A desktop launch error must not disappear when the analytical fallback works.
// Only return fixed diagnostic categories, never Tauri exception text or paths.
function bundledStartIssue(error:unknown):string {
 const detail=String(error).toLowerCase();
 if(detail.includes('integrity')||detail.includes('checksum'))return 'model_integrity_failed';
 if(detail.includes('manifest')||detail.includes('model missing'))return 'model_assets_missing';
 if(detail.includes('inference executable')||detail.includes('sidecar'))return 'inference_runtime_missing';
 if(detail.includes('start analytics'))return 'analytics_not_started';
 return 'worker_launch_failed';
}
async function requestLocalAI(path:string,method:'GET'|'POST',body?:unknown):Promise<string|null>{
 if(!desktopEndpoint || !shouldLaunchBundledAI(path,method,body))return null;
 try {await invoke('launch_bundled_ai');return null;}
 catch (error) {return bundledStartIssue(error);}
}
export async function get<T>(path:string, options?:{signal?:AbortSignal}):Promise<T>{return check(await fetchLocal(path,{headers:authHeaders(),signal:options?.signal}));}
export async function post<T>(path:string, body:unknown):Promise<T>{
 const startupIssue=await requestLocalAI(path,'POST',body);
 const result=await check(await fetchLocal(path,{method:'POST',headers:{...authHeaders(),'Content-Type':'application/json'},body:JSON.stringify(body)}));
 // Preserve deterministic answers, but attach the verified desktop startup
 // failure so the UI does not describe a fallback as successful offline AI.
 if(startupIssue&&result&&typeof result==='object'&&result.fallback===true){
  return {...result,local_startup_issue:startupIssue} as T;
 }
 return result as T;
}
export async function put<T>(path:string, body:unknown):Promise<T>{return check(await fetchLocal(path,{method:'PUT',headers:{...authHeaders(),'Content-Type':'application/json'},body:JSON.stringify(body)}));}
export async function upload(file:File):Promise<{id:string;name:string;profile:Profile}>{
 const form=new FormData();form.append('file',file);
 try{return await check(await fetch(`${apiBase()}/projects`,{method:'POST',headers:authHeaders(),body:form}));}
 catch(error){
  if(error instanceof TypeError)throw new Error(`Could not connect to PilotODIN's local analytics service at ${new URL(apiBase()).origin} (request: /projects). Check that the PilotODIN Backend window is running, then try again.`);
  throw error;
 }
}

/** Read-only download: authentication never appears in the URL. */
export async function downloadCleanedData(path:string,body:unknown):Promise<{blob:Blob;filename:string}> {
 const response=await fetchLocal(path,{method:'POST',headers:{...authHeaders(),'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!response.ok){await check(response);throw new Error('Dataset export failed')}
 const disposition=response.headers.get('content-disposition')??'';
 const encoded=disposition.match(/filename\*=utf-8''([^;]+)/i)?.[1];
 const name=encoded?decodeURIComponent(encoded):disposition.match(/filename="?([^";]+)"?/i)?.[1]??'pilotodin_cleaned_data.csv';
 return {blob:await response.blob(),filename:name.replace(/[\\/]/g,'_')};
}

/** Authenticated binary download. Never put desktop session credentials in URLs. */
export async function downloadReportFile(path:string):Promise<{blob:Blob;filename:string}> {
 const response=await fetchLocal(path,{method:'GET',headers:authHeaders()});
 if(!response.ok){await check(response);throw new Error('Report export failed')}
 const contentDisposition=response.headers.get('content-disposition')??'';
 const format=path.match(/\/export\/(html|pdf)(?:\?|$)/)?.[1]??'pdf';
  const filename=contentDisposition.match(/filename="?([^";]+)"?/i)?.[1]??`pilotodin_report.${format}`;
 return {blob:await response.blob(),filename:filename.replace(/[\\/]/g,'_')};
}
