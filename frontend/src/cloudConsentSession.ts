// Nonpersistent renderer settings-operation fence and same-origin invalidation.
// Signals carry only an operation ID and phase, never consent or credentials.
// Server witnesses remain authoritative across missed signals and restarts.
type Snapshot=Readonly<{generation:number;pending:boolean}>;
type Ticket=Readonly<{generation:number;id:string}>;
let snapshot:Snapshot=Object.freeze({generation:0,pending:false});
let owner:Ticket|null=null;
const listeners=new Set<()=>void>();
const remoteOperations=new Set<string>();
let channel:BroadcastChannel|null=null;
let serial=0;
let rendererId='';
try{
  if(typeof window!=='undefined'&&typeof window.BroadcastChannel==='function'){
    rendererId=Array.from(window.crypto.getRandomValues(new Uint32Array(4)),n=>n.toString(16).padStart(8,'0')).join('');
    channel=new window.BroadcastChannel('pilotodin-cloud-consent-invalidation-v1');
    channel.onmessage=({data})=>{
      if(!data||typeof data.id!=='string'||!/^([0-9a-f]{32}):[0-9]+$/.test(data.id)||
        (data.phase!=='begin'&&data.phase!=='finish'))return;
      if(data.phase==='begin')remoteOperations.add(data.id);
      else remoteOperations.delete(data.id);
      advance(owner!==null||remoteOperations.size>0);
    };
    channel.onmessageerror=()=>{channel?.close();channel=null;advance(owner!==null||remoteOperations.size>0)};
  }
}catch{channel?.close();channel=null}
function signal(ticket:Ticket,phase:'begin'|'finish'){
  try{channel?.postMessage({id:ticket.id,phase})}
  catch{channel?.close();channel=null}
}
export function cloudConsentCrossWindowAvailable(){return channel!==null}
export function cloudSettingsOperationIsCurrent(ticket:Ticket){
  return owner===ticket&&snapshot.generation===ticket.generation&&remoteOperations.size===0;
}

export function cloudConsentSnapshot():Snapshot{return snapshot}
export function subscribeCloudConsent(listener:()=>void){
  listeners.add(listener);
  return ()=>{listeners.delete(listener)}
}
function advance(pending:boolean){
  snapshot=Object.freeze({generation:snapshot.generation+1,pending});
  for(const listener of [...listeners])listener();
}
export function beginCloudSettingsOperation(expectedGeneration:number):Ticket|null{
  if(owner||snapshot.pending||snapshot.generation!==expectedGeneration)return null;
  const ticket=Object.freeze({generation:snapshot.generation+1,id:rendererId+':'+(++serial)});
  owner=ticket;
  advance(true);
  signal(ticket,'begin');
  return ticket;
}
export function finishCloudSettingsOperation(ticket:Ticket):Snapshot|null{
  if(owner!==ticket)return null;
  const current=cloudSettingsOperationIsCurrent(ticket);
  owner=null;
  advance(remoteOperations.size>0);
  signal(ticket,'finish');
  return current&&!snapshot.pending?snapshot:null;
}
export function cloudConsentIsCurrent(generation:number):boolean{
  return !snapshot.pending&&snapshot.generation===generation;
}

export type SavedCloudPermission={
  cloud_enabled?:unknown;share_aggregates?:unknown;intelligence_mode?:unknown;
  credential_warning?:unknown;settings_warning?:unknown;cloud_consent_witness?:unknown;
  providers?:readonly {id?:unknown;connected?:unknown;verified?:unknown}[];
};
function permissionEnabled(saved:SavedCloudPermission|null|undefined){
  return saved?.cloud_enabled===true&&saved.share_aggregates===true&&
    (saved.intelligence_mode==='hybrid'||saved.intelligence_mode==='cloud')&&
    !saved.credential_warning&&!saved.settings_warning;
}
export function canTestCloud(saved:SavedCloudPermission|null|undefined,provider:string):boolean{
  return Boolean(permissionEnabled(saved)&&['gemini','groq','openrouter'].includes(provider)&&
    Array.isArray(saved?.providers)&&saved.providers.some(p=>p.id===provider&&p.connected===true));
}
export function savedCloudWitness(saved:SavedCloudPermission|null|undefined):string|null{
  const value=saved?.cloud_consent_witness;
  return typeof value==='string'&&/^[0-9a-f]{32}:[0-9]+$/.test(value)&&value.length<=80?value:null;
}
export function explicitHandshakeRequest(confirmed:SavedCloudPermission|null,saved:SavedCloudPermission,provider:string){
  const witness=savedCloudWitness(saved);
  return canTestCloud(confirmed,provider)&&canTestCloud(saved,provider)&&witness!==null&&
    witness===savedCloudWitness(confirmed)?{cloud_intent:true as const,cloud_consent_witness:witness}:null;
}
export function savedCloudStatus(saved:SavedCloudPermission):'local'|'unverified'|'connected'{
  if(!permissionEnabled(saved))return 'local';
  return Array.isArray(saved.providers)&&saved.providers.some(p=>
    typeof p.id==='string'&&canTestCloud(saved,p.id)&&p.verified===true)?'connected':'unverified';
}


// Saved cloud preferences are not user intent. Preserve only local routes.
export type LocalPanelProvider='auto'|'local'|'ollama';
export function isLocalPanelProvider(value:unknown):value is LocalPanelProvider{
  return value==='auto'||value==='local'||value==='ollama';
}
export function localPanelProvider(value:unknown):LocalPanelProvider{
  return isLocalPanelProvider(value)?value:'auto';
}
export function projectCloudProviderName(value:unknown):string|null{
  switch(value){
    case 'gemini':return 'Google Gemini';
    case 'groq':return 'GroqCloud';
    case 'openrouter':return 'OpenRouter';
    default:return null;
  }
}
// Intermediate C4 batch: the project-data path remains closed pending
// server-generation binding and cross-renderer result invalidation.
export function projectCloudHold(value:unknown):string{
  return value==='openrouter'?'OpenRouter project-data sharing is disabled because downstream destinations are not established.':
    'Project-data cloud requests are not available until consent and response safeguards are verified.';
}
export const projectCloudDisclosure='A cloud request may include bounded column names, row counts, supported aggregate statistics, quality issue categories, aggregate model metrics and your question. Summaries are not guaranteed anonymous. Do not include private information in the question. Uploaded rows, local paths, individual prediction inputs and previous answers are excluded. Only the selected provider is intended; no automatic fallback to another provider. Already sent data cannot be recalled.';
export function localPanelRequest(value:unknown):{selected_provider:LocalPanelProvider;cloud_intent:false}|null{
  return isLocalPanelProvider(value)?{selected_provider:value,cloud_intent:false}:null;
}
export function localPanelMayContinue(source:unknown):boolean{return source==='local_llm'}

export type ProjectCloudProvider='gemini'|'groq';
export type ProjectCloudRoute={selected_provider:ProjectCloudProvider;cloud_intent:true;cloud_consent_witness:string;expected_dataset_version:number};
export function projectCloudRoute(reviewed:SavedCloudPermission|null,saved:SavedCloudPermission|null,provider:string,version:number):ProjectCloudRoute|null{
  if(!Number.isSafeInteger(version)||version<0)return null;
  if((provider!=='gemini'&&provider!=='groq')||!saved)return null;
  const body=explicitHandshakeRequest(reviewed,saved,provider);
  return body?{selected_provider:provider,...body,expected_dataset_version:version}:null;
}
export function projectCloudConfirmationText(provider:string,scope:string,version:number,question:string,deep:boolean):string{
  return 'Send one '+(deep?'deeper':'routine')+' request to '+projectCloudProviderName(provider)+'?\nWorkspace: '+scope+' · Working dataset v'+version+'\nQuestion: '+question+'\n\n'+projectCloudDisclosure+'\n\nConfirm only this request.';
}
type CloudOutcome<T>={status:'cancelled'|'stale'}|{status:'result';response:T};
// The confirmation callback runs synchronously from the explicit click, before
// any await. An independent fresh read must match the reviewed witness before
// dispatch and again before publication. No automatic retry.
export async function confirmedProjectCloud<T>(reviewed:SavedCloudPermission|null,provider:string,version:number,
  confirm:()=>boolean,read:()=>Promise<SavedCloudPermission>,send:(route:ProjectCloudRoute)=>Promise<T>,
  current:()=>boolean):Promise<CloudOutcome<T>>{
  if(!current()||!cloudConsentCrossWindowAvailable()||!projectCloudRoute(reviewed,reviewed,provider,version))return {status:'stale'};
  if(!confirm())return {status:'cancelled'};
  const route=projectCloudRoute(reviewed,await read(),provider,version);
  if(!route||!current()||!cloudConsentCrossWindowAvailable())return {status:'stale'};
  const response=await send(route);
  if(!current()||!cloudConsentCrossWindowAvailable())return {status:'stale'};
  if(!projectCloudRoute(reviewed,await read(),provider,version)||!current()||!cloudConsentCrossWindowAvailable())return {status:'stale'};
  return {status:'result',response};
}
export function cloudResponseMatches(response:{source?:unknown;provider?:unknown;fallback?:unknown;dataset_version?:unknown;scope?:unknown},provider:string,scope:string,version:number):boolean{
  return response.dataset_version===version&&response.scope===scope&&
    ((response.source==='cloud_llm'&&response.provider===provider&&response.fallback===false)||
     (response.source==='local_computed_rules'&&response.provider==='local'&&response.fallback===true));
}
